"""SQLModel implementation of ScenarioRepository."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from agrowave.modules.scenarios.domain.models import (
    AccessNode,
    Antenna,
    Bounds,
    Deployment,
    EndNode,
    HeightAgl,
    LatLng,
    Link,
    LongleyRiceParams,
    Polarization,
    PropagationSetup,
    RadioConfig,
    Scenario,
    SensitivityOrigin,
    StudyArea,
    Technology,
    TerrainRef,
    TxPower,
)
from agrowave.modules.scenarios.domain.ports import ScenarioRepository
from agrowave.modules.scenarios.infrastructure.row_models import (
    ScenariosAccessNodeRow,
    ScenariosEndNodeRow,
    ScenariosLinkRow,
    ScenariosScenarioRow,
)


class SqlModelScenarioRepository(ScenarioRepository):
    """PostgreSQL/SQLModel implementation of ScenarioRepository."""

    def __init__(self, engine: Engine) -> None:
        """Initializes the repository with a database engine.

        Args:
            engine: SQLAlchemy/SQLModel database engine.
        """
        self._engine = engine

    @staticmethod
    def _serialize_propagation(setup: PropagationSetup | None) -> dict[str, Any] | None:
        if setup is None:
            return None
        p = setup.parameters
        return {
            "ens0": p.ens0,
            "ipol": p.ipol,
            "eps": p.eps,
            "sgm": p.sgm,
            "klim": p.klim,
            "mdvar": p.mdvar,
            "qc": p.qc,
            "qr": list(p.qr),
        }

    @staticmethod
    def _deserialize_propagation(
        model_id: str | None,
        params_dict: dict[str, Any] | None,
        version: int | None,
    ) -> PropagationSetup | None:
        if model_id is None or params_dict is None:
            return None
        qr_raw = params_dict.get("qr", [10.0, 50.0, 90.0])
        return PropagationSetup(
            model_id=model_id,
            schema_version=version or 1,
            parameters=LongleyRiceParams(
                ens0=float(params_dict.get("ens0", 314.0)),
                ipol=int(params_dict.get("ipol", 1)),
                eps=float(params_dict.get("eps", 15.0)),
                sgm=float(params_dict.get("sgm", 0.005)),
                klim=int(params_dict.get("klim", 5)),
                mdvar=int(params_dict.get("mdvar", 11)),
                qc=float(params_dict.get("qc", 50.0)),
                qr=tuple(float(x) for x in qr_raw),
            ),
        )

    def _to_entity(
        self,
        row: ScenariosScenarioRow,
        access_rows: list[ScenariosAccessNodeRow],
        end_rows: list[ScenariosEndNodeRow],
        link_rows: list[ScenariosLinkRow],
    ) -> Scenario:
        bounds = Bounds(
            south=row.south,
            west=row.west,
            north=row.north,
            east=row.east,
        )
        study_area = StudyArea(bounds=bounds)
        terrain_ref = (
            TerrainRef(dem_id=row.dem_id, window=bounds) if row.dem_id is not None else None
        )
        radio_config = (
            RadioConfig(
                profile_id=row.profile_id,
                technology=Technology(row.technology),
                band_code=row.band_code or "",
                frequency_mhz=row.frequency_mhz,
            )
            if row.profile_id is not None
            and row.technology is not None
            and row.frequency_mhz is not None
            else None
        )

        access_nodes = [
            AccessNode(
                id=an.id,
                name=an.name,
                position=LatLng(lat=an.lat, lng=an.lng),
                height_agl=HeightAgl(meters=an.height_agl_m),
                antenna=Antenna(
                    reference=an.antenna_ref,
                    gain_dbi=an.antenna_gain_dbi,
                    polarization=Polarization(an.polarization) if an.polarization else None,
                ),
                sensitivity_dbm=an.sensitivity_dbm,
                sensitivity_origin=SensitivityOrigin(an.sensitivity_origin),
            )
            for an in access_rows
        ]

        end_nodes = [
            EndNode(
                id=en.id,
                name=en.name,
                position=LatLng(lat=en.lat, lng=en.lng),
                height_agl=HeightAgl(meters=en.height_agl_m),
                antenna=Antenna(
                    reference=en.antenna_ref,
                    gain_dbi=en.antenna_gain_dbi,
                    polarization=Polarization(en.polarization) if en.polarization else None,
                ),
                tx_power=TxPower(
                    nominal_dbm=en.tx_power_nominal_dbm,
                    tolerance_db=en.tx_power_tolerance_db,
                ),
                source_template_id=en.source_template_id,
            )
            for en in end_rows
        ]

        links = [
            Link(
                id=lk.id,
                end_node_id=lk.end_node_id,
                access_node_id=lk.access_node_id,
            )
            for lk in link_rows
        ]

        return Scenario(
            id=row.id,
            owner_id=row.owner_id,
            name=row.name,
            description=row.description,
            comparison_group_id=row.comparison_group_id,
            study_area=study_area,
            terrain_ref=terrain_ref,
            radio_config=radio_config,
            deployment=Deployment(
                access_nodes=access_nodes,
                end_nodes=end_nodes,
                links=links,
            ),
            propagation_setup=self._deserialize_propagation(
                row.propagation_model_id,
                row.propagation_params,
                row.propagation_params_version,
            ),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def save(self, scenario: Scenario) -> Scenario:
        """Persists a scenario aggregate and replaces its child deployment rows atomically."""
        if scenario.study_area is None:
            raise ValueError("Scenario study_area must be defined before saving.")

        with Session(self._engine) as session:
            row = session.get(ScenariosScenarioRow, scenario.id)
            now = datetime.now(UTC)
            bounds = scenario.study_area.bounds
            dem_id = scenario.terrain_ref.dem_id if scenario.terrain_ref else None
            rc = scenario.radio_config
            ps = scenario.propagation_setup

            if row is None:
                row = ScenariosScenarioRow(
                    id=scenario.id,
                    owner_id=scenario.owner_id,
                    name=scenario.name,
                    description=scenario.description,
                    comparison_group_id=scenario.comparison_group_id,
                    south=bounds.south,
                    west=bounds.west,
                    north=bounds.north,
                    east=bounds.east,
                    dem_id=dem_id,
                    profile_id=rc.profile_id if rc else None,
                    technology=rc.technology.value if rc else None,
                    band_code=rc.band_code if rc else None,
                    frequency_mhz=rc.frequency_mhz if rc else None,
                    propagation_model_id=ps.model_id if ps else None,
                    propagation_params=self._serialize_propagation(ps),
                    propagation_params_version=ps.schema_version if ps else None,
                    created_at=scenario.created_at or now,
                    updated_at=scenario.updated_at or now,
                )
                session.add(row)
                session.flush()
            else:
                row.name = scenario.name
                row.description = scenario.description
                row.comparison_group_id = scenario.comparison_group_id
                row.south = bounds.south
                row.west = bounds.west
                row.north = bounds.north
                row.east = bounds.east
                row.dem_id = dem_id
                row.profile_id = rc.profile_id if rc else None
                row.technology = rc.technology.value if rc else None
                row.band_code = rc.band_code if rc else None
                row.frequency_mhz = rc.frequency_mhz if rc else None
                row.propagation_model_id = ps.model_id if ps else None
                row.propagation_params = self._serialize_propagation(ps)
                row.propagation_params_version = ps.schema_version if ps else None
                row.updated_at = scenario.updated_at or now

                # Delete existing child rows before inserting current deployment
                session.execute(
                    sa.delete(ScenariosLinkRow).where(
                        col(ScenariosLinkRow.scenario_id) == scenario.id
                    )
                )
                session.execute(
                    sa.delete(ScenariosEndNodeRow).where(
                        col(ScenariosEndNodeRow.scenario_id) == scenario.id
                    )
                )
                session.execute(
                    sa.delete(ScenariosAccessNodeRow).where(
                        col(ScenariosAccessNodeRow.scenario_id) == scenario.id
                    )
                )
                session.flush()

            for an in scenario.deployment.access_nodes:
                session.add(
                    ScenariosAccessNodeRow(
                        id=an.id,
                        scenario_id=scenario.id,
                        name=an.name,
                        lat=an.position.lat,
                        lng=an.position.lng,
                        height_agl_m=an.height_agl.meters,
                        antenna_ref=an.antenna.reference,
                        antenna_gain_dbi=an.antenna.gain_dbi,
                        polarization=an.antenna.polarization.value
                        if an.antenna.polarization
                        else None,
                        sensitivity_dbm=an.sensitivity_dbm,
                        sensitivity_origin=an.sensitivity_origin.value,
                    )
                )

            for en in scenario.deployment.end_nodes:
                session.add(
                    ScenariosEndNodeRow(
                        id=en.id,
                        scenario_id=scenario.id,
                        name=en.name,
                        lat=en.position.lat,
                        lng=en.position.lng,
                        height_agl_m=en.height_agl.meters,
                        antenna_ref=en.antenna.reference,
                        antenna_gain_dbi=en.antenna.gain_dbi,
                        polarization=en.antenna.polarization.value
                        if en.antenna.polarization
                        else None,
                        tx_power_nominal_dbm=en.tx_power.nominal_dbm,
                        tx_power_tolerance_db=en.tx_power.tolerance_db,
                        source_template_id=en.source_template_id,
                    )
                )
            session.flush()

            for lk in scenario.deployment.links:
                session.add(
                    ScenariosLinkRow(
                        id=lk.id,
                        scenario_id=scenario.id,
                        end_node_id=lk.end_node_id,
                        access_node_id=lk.access_node_id,
                    )
                )

            session.commit()
            return scenario

    def get_by_id(self, scenario_id: UUID) -> Scenario | None:
        """Retrieves a scenario and its deployment by ID."""
        with Session(self._engine) as session:
            row = session.get(ScenariosScenarioRow, scenario_id)
            if row is None:
                return None
            access_rows = list(
                session.exec(
                    select(ScenariosAccessNodeRow).where(
                        ScenariosAccessNodeRow.scenario_id == scenario_id
                    )
                ).all()
            )
            end_rows = list(
                session.exec(
                    select(ScenariosEndNodeRow).where(
                        ScenariosEndNodeRow.scenario_id == scenario_id
                    )
                ).all()
            )
            link_rows = list(
                session.exec(
                    select(ScenariosLinkRow).where(ScenariosLinkRow.scenario_id == scenario_id)
                ).all()
            )
            return self._to_entity(row, access_rows, end_rows, link_rows)

    def list_by_owner(self, owner_id: UUID) -> list[Scenario]:
        """Lists all scenarios owned by a user ordered by updated_at descending."""
        with Session(self._engine) as session:
            stmt = (
                select(ScenariosScenarioRow)
                .where(ScenariosScenarioRow.owner_id == owner_id)
                .order_by(col(ScenariosScenarioRow.updated_at).desc())
            )
            rows = list(session.exec(stmt).all())
            result: list[Scenario] = []
            for row in rows:
                access_rows = list(
                    session.exec(
                        select(ScenariosAccessNodeRow).where(
                            ScenariosAccessNodeRow.scenario_id == row.id
                        )
                    ).all()
                )
                end_rows = list(
                    session.exec(
                        select(ScenariosEndNodeRow).where(ScenariosEndNodeRow.scenario_id == row.id)
                    ).all()
                )
                link_rows = list(
                    session.exec(
                        select(ScenariosLinkRow).where(ScenariosLinkRow.scenario_id == row.id)
                    ).all()
                )
                result.append(self._to_entity(row, access_rows, end_rows, link_rows))
            return result

    def delete(self, scenario_id: UUID) -> None:
        """Deletes a scenario and its child deployment rows."""
        with Session(self._engine) as session:
            row = session.get(ScenariosScenarioRow, scenario_id)
            if row is not None:
                session.execute(
                    sa.delete(ScenariosLinkRow).where(
                        col(ScenariosLinkRow.scenario_id) == scenario_id
                    )
                )
                session.execute(
                    sa.delete(ScenariosEndNodeRow).where(
                        col(ScenariosEndNodeRow.scenario_id) == scenario_id
                    )
                )
                session.execute(
                    sa.delete(ScenariosAccessNodeRow).where(
                        col(ScenariosAccessNodeRow.scenario_id) == scenario_id
                    )
                )
                session.delete(row)
                session.commit()

    def is_profile_in_use(self, profile_id: UUID) -> bool:
        """Checks whether any scenario references the given LPWAN profile (RN-09)."""
        with Session(self._engine) as session:
            stmt = (
                select(ScenariosScenarioRow.id)
                .where(ScenariosScenarioRow.profile_id == profile_id)
                .limit(1)
            )
            return session.exec(stmt).first() is not None

    def is_dem_in_use(self, dem_id: UUID) -> bool:
        """Checks whether any scenario references the given DEM (RN-28)."""
        with Session(self._engine) as session:
            stmt = (
                select(ScenariosScenarioRow.id)
                .where(ScenariosScenarioRow.dem_id == dem_id)
                .limit(1)
            )
            return session.exec(stmt).first() is not None
