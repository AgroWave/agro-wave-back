"""SQLModel implementation of SimulationRepository."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.engine import Engine
from sqlmodel import Session, col, delete, select

from agrowave.modules.simulation.domain.models import (
    ElevationProfileSeries,
    FresnelAnalysis,
    FresnelVerdict,
    LinkResult,
    PathLossPrediction,
    PathLossQuantile,
    ScenarioSnapshot,
    SensitivityOrigin,
    Simulation,
    SimulationResult,
    SimulationStatus,
    SimulationSummary,
    SimulationWarning,
    Technology,
)
from agrowave.modules.simulation.infrastructure.row_models import (
    SimulationLinkProfileRow,
    SimulationLinkResultRow,
    SimulationPathLossQuantileRow,
    SimulationSimulationRow,
    SimulationWarningRow,
)


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensures a datetime loaded from SQLite/PostgreSQL is timezone-aware UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class SqlModelSimulationRepository:
    """PostgreSQL / SQLModel repository for the Simulation aggregate root."""

    def __init__(self, engine: Engine) -> None:
        """Initializes the repository with a database engine."""
        self._engine = engine

    def add(self, simulation: Simulation) -> None:
        """Persists a new simulation row."""
        with Session(self._engine) as session:
            row = self._to_simulation_row(simulation)
            session.add(row)
            session.commit()

    def save(self, simulation: Simulation) -> None:
        """Updates an existing simulation and replaces its child result rows if completed."""
        with Session(self._engine) as session:
            existing = session.get(SimulationSimulationRow, simulation.id)
            if existing is None:
                row = self._to_simulation_row(simulation)
                session.add(row)
            else:
                existing.name = simulation.name
                existing.description = simulation.description
                existing.status = simulation.status.value
                existing.failure_reason = simulation.failure_reason
                existing.started_at = simulation.started_at
                existing.finished_at = simulation.finished_at
                if simulation.summary is not None:
                    existing.viable_links_pct = simulation.summary.viable_links_pct
                    existing.min_margin_db = simulation.summary.min_margin_db
                    existing.mean_margin_db = simulation.summary.mean_margin_db
                    existing.fresnel_clear_count = simulation.summary.fresnel_clear_count
                    existing.fresnel_marginal_count = simulation.summary.fresnel_marginal_count
                    existing.fresnel_obstructed_count = simulation.summary.fresnel_obstructed_count
                else:
                    existing.viable_links_pct = None
                    existing.min_margin_db = None
                    existing.mean_margin_db = None
                    existing.fresnel_clear_count = None
                    existing.fresnel_marginal_count = None
                    existing.fresnel_obstructed_count = None
                session.add(existing)

            prev_link_rows = session.exec(
                select(SimulationLinkResultRow).where(
                    SimulationLinkResultRow.simulation_id == simulation.id
                )
            ).all()
            for lr_row in prev_link_rows:
                session.exec(
                    delete(SimulationPathLossQuantileRow).where(
                        col(SimulationPathLossQuantileRow.link_result_id) == lr_row.id
                    )
                )
                session.exec(
                    delete(SimulationLinkProfileRow).where(
                        col(SimulationLinkProfileRow.link_result_id) == lr_row.id
                    )
                )
                session.delete(lr_row)

            session.exec(
                delete(SimulationWarningRow).where(
                    col(SimulationWarningRow.simulation_id) == simulation.id
                )
            )
            session.flush()

            if simulation.result is not None:
                link_id_to_result_id: dict[UUID, UUID] = {}
                for lr in simulation.result.link_results:
                    link_id_to_result_id[lr.link_id] = lr.id
                    lr_row = SimulationLinkResultRow(
                        id=lr.id,
                        simulation_id=simulation.id,
                        link_id=lr.link_id,
                        end_node_name=lr.end_node_name,
                        access_node_name=lr.access_node_name,
                        distance_m=lr.distance_m,
                        fresnel_min_ratio=lr.fresnel.min_clearance_ratio,
                        fresnel_min_at_m=lr.fresnel.min_clearance_at_m,
                        fresnel_max_radius_m=lr.fresnel.max_radius_m,
                        fresnel_verdict=lr.fresnel.verdict.value,
                        free_space_loss_db=lr.path_loss.free_space_loss_db,
                        received_power_dbm=lr.received_power_dbm,
                        sensitivity_used_dbm=lr.sensitivity_used_dbm,
                        sensitivity_origin=lr.sensitivity_origin.value,
                        margin_db=lr.margin_db,
                        viable=lr.viable,
                    )
                    session.add(lr_row)

                session.flush()

                for lr in simulation.result.link_results:
                    for q in lr.path_loss.loss_by_quantile:
                        session.add(
                            SimulationPathLossQuantileRow(
                                link_result_id=lr.id,
                                reliability_pct=q.reliability_pct,
                                confidence_pct=q.confidence_pct,
                                loss_db=q.loss_db,
                            )
                        )

                    session.add(
                        SimulationLinkProfileRow(
                            link_result_id=lr.id,
                            series=lr.profile_series.to_dict(),
                            series_version=lr.profile_series.series_version,
                        )
                    )

                for warn in simulation.result.warnings:
                    mapped_lr_id = (
                        link_id_to_result_id.get(warn.link_id) if warn.link_id is not None else None
                    )
                    session.add(
                        SimulationWarningRow(
                            id=warn.id,
                            simulation_id=simulation.id,
                            link_result_id=mapped_lr_id,
                            source=warn.source,
                            code=warn.code,
                            message=warn.message,
                        )
                    )

            session.commit()

    def get_by_id(self, simulation_id: UUID, owner_id: UUID) -> Simulation | None:
        """Retrieves a simulation owned by the given user, including child results."""
        with Session(self._engine) as session:
            stmt = select(SimulationSimulationRow).where(
                SimulationSimulationRow.id == simulation_id,
                SimulationSimulationRow.owner_id == owner_id,
            )
            row = session.exec(stmt).first()
            if row is None:
                return None
            return self._to_domain(session, row, load_details=True)

    def get_by_id_unscoped(self, simulation_id: UUID) -> Simulation | None:
        """Retrieves a simulation by ID without owner filtering for background execution."""
        with Session(self._engine) as session:
            row = session.get(SimulationSimulationRow, simulation_id)
            if row is None:
                return None
            return self._to_domain(session, row, load_details=True)

    def list_by_owner(
        self,
        owner_id: UUID,
        q: str | None = None,
        technology: Technology | None = None,
        status: SimulationStatus | None = None,
        comparison_group_id: UUID | None = None,
        sort: str = "newest",
    ) -> list[Simulation]:
        """Lists simulations belonging to the owner with optional filters and sort order."""
        with Session(self._engine) as session:
            stmt = select(SimulationSimulationRow).where(
                SimulationSimulationRow.owner_id == owner_id
            )
            if q:
                stmt = stmt.where(col(SimulationSimulationRow.name).ilike(f"%{q.strip()}%"))
            if technology is not None:
                stmt = stmt.where(SimulationSimulationRow.technology == technology.value)
            if status is not None:
                stmt = stmt.where(SimulationSimulationRow.status == status.value)
            if comparison_group_id is not None:
                stmt = stmt.where(
                    SimulationSimulationRow.comparison_group_id == comparison_group_id
                )

            if sort == "oldest":
                stmt = stmt.order_by(col(SimulationSimulationRow.created_at).asc())
            elif sort == "name":
                stmt = stmt.order_by(col(SimulationSimulationRow.name).asc())
            else:
                stmt = stmt.order_by(col(SimulationSimulationRow.created_at).desc())

            rows = session.exec(stmt).all()
            return [self._to_domain(session, r, load_details=False) for r in rows]

    def delete(self, simulation_id: UUID, owner_id: UUID) -> None:
        """Deletes a simulation and its child rows."""
        with Session(self._engine) as session:
            stmt = select(SimulationSimulationRow).where(
                SimulationSimulationRow.id == simulation_id,
                SimulationSimulationRow.owner_id == owner_id,
            )
            row = session.exec(stmt).first()
            if row is None:
                return

            link_rows = session.exec(
                select(SimulationLinkResultRow).where(
                    SimulationLinkResultRow.simulation_id == simulation_id
                )
            ).all()
            for lr_row in link_rows:
                session.exec(
                    delete(SimulationPathLossQuantileRow).where(
                        col(SimulationPathLossQuantileRow.link_result_id) == lr_row.id
                    )
                )
                session.exec(
                    delete(SimulationLinkProfileRow).where(
                        col(SimulationLinkProfileRow.link_result_id) == lr_row.id
                    )
                )
                session.delete(lr_row)

            session.exec(
                delete(SimulationWarningRow).where(
                    col(SimulationWarningRow.simulation_id) == simulation_id
                )
            )
            session.delete(row)
            session.commit()

    def mark_running_as_failed_on_startup(self, reason: str) -> int:
        """Marks any simulations left in RUNNING state as FAILED on process startup."""
        with Session(self._engine) as session:
            stmt = select(SimulationSimulationRow).where(
                SimulationSimulationRow.status == SimulationStatus.RUNNING.value
            )
            rows = session.exec(stmt).all()
            now = datetime.now(UTC)
            for row in rows:
                row.status = SimulationStatus.FAILED.value
                row.failure_reason = reason
                row.finished_at = now
                session.add(row)
            if rows:
                session.commit()
            return len(rows)

    def _to_simulation_row(self, simulation: Simulation) -> SimulationSimulationRow:
        """Maps a domain Simulation aggregate to SimulationSimulationRow."""
        return SimulationSimulationRow(
            id=simulation.id,
            owner_id=simulation.owner_id,
            scenario_id=simulation.scenario_id,
            comparison_group_id=simulation.comparison_group_id,
            name=simulation.name,
            description=simulation.description,
            status=simulation.status.value,
            technology=simulation.technology.value,
            propagation_model_id=simulation.propagation_model_id,
            snapshot=simulation.snapshot.to_dict(),
            snapshot_version=simulation.snapshot.snapshot_version,
            viable_links_pct=(simulation.summary.viable_links_pct if simulation.summary else None),
            min_margin_db=simulation.summary.min_margin_db if simulation.summary else None,
            mean_margin_db=simulation.summary.mean_margin_db if simulation.summary else None,
            fresnel_clear_count=(
                simulation.summary.fresnel_clear_count if simulation.summary else None
            ),
            fresnel_marginal_count=(
                simulation.summary.fresnel_marginal_count if simulation.summary else None
            ),
            fresnel_obstructed_count=(
                simulation.summary.fresnel_obstructed_count if simulation.summary else None
            ),
            failure_reason=simulation.failure_reason,
            created_at=simulation.created_at,
            started_at=simulation.started_at,
            finished_at=simulation.finished_at,
        )

    def _to_domain(
        self,
        session: Session,
        row: SimulationSimulationRow,
        load_details: bool,
    ) -> Simulation:
        """Reconstructs a Simulation domain aggregate from database rows."""
        snapshot = ScenarioSnapshot.from_dict(row.snapshot, row.snapshot_version)
        summary: SimulationSummary | None = None
        if row.viable_links_pct is not None and row.min_margin_db is not None:
            summary = SimulationSummary(
                viable_links_pct=row.viable_links_pct,
                min_margin_db=row.min_margin_db,
                mean_margin_db=row.mean_margin_db or 0.0,
                fresnel_clear_count=row.fresnel_clear_count or 0,
                fresnel_marginal_count=row.fresnel_marginal_count or 0,
                fresnel_obstructed_count=row.fresnel_obstructed_count or 0,
            )

        result: SimulationResult | None = None
        if load_details and row.status == SimulationStatus.COMPLETED.value:
            lr_rows = session.exec(
                select(SimulationLinkResultRow).where(
                    SimulationLinkResultRow.simulation_id == row.id
                )
            ).all()
            link_results: list[LinkResult] = []
            result_id_to_link_id: dict[UUID, UUID] = {}

            for lr_row in lr_rows:
                result_id_to_link_id[lr_row.id] = lr_row.link_id
                q_rows = session.exec(
                    select(SimulationPathLossQuantileRow)
                    .where(SimulationPathLossQuantileRow.link_result_id == lr_row.id)
                    .order_by(col(SimulationPathLossQuantileRow.reliability_pct).asc())
                ).all()
                quantiles = tuple(
                    PathLossQuantile(
                        reliability_pct=q.reliability_pct,
                        confidence_pct=q.confidence_pct,
                        loss_db=q.loss_db,
                    )
                    for q in q_rows
                )
                prof_row = session.get(SimulationLinkProfileRow, lr_row.id)
                if prof_row is not None:
                    series = ElevationProfileSeries.from_dict(
                        prof_row.series, prof_row.series_version
                    )
                else:
                    series = ElevationProfileSeries(
                        distances_m=(),
                        terrain_with_curvature_m=(),
                        los_m=(),
                        f1_radius_m=(),
                    )
                link_results.append(
                    LinkResult(
                        id=lr_row.id,
                        link_id=lr_row.link_id,
                        end_node_name=lr_row.end_node_name,
                        access_node_name=lr_row.access_node_name,
                        distance_m=lr_row.distance_m,
                        fresnel=FresnelAnalysis(
                            min_clearance_ratio=lr_row.fresnel_min_ratio,
                            min_clearance_at_m=lr_row.fresnel_min_at_m,
                            max_radius_m=lr_row.fresnel_max_radius_m,
                            verdict=FresnelVerdict(lr_row.fresnel_verdict),
                        ),
                        path_loss=PathLossPrediction(
                            free_space_loss_db=lr_row.free_space_loss_db,
                            loss_by_quantile=quantiles,
                        ),
                        received_power_dbm=lr_row.received_power_dbm,
                        sensitivity_used_dbm=lr_row.sensitivity_used_dbm,
                        sensitivity_origin=SensitivityOrigin(lr_row.sensitivity_origin),
                        margin_db=lr_row.margin_db,
                        viable=lr_row.viable,
                        profile_series=series,
                    )
                )

            warn_rows = session.exec(
                select(SimulationWarningRow).where(SimulationWarningRow.simulation_id == row.id)
            ).all()
            warnings = tuple(
                SimulationWarning(
                    id=w.id,
                    link_id=(
                        result_id_to_link_id.get(w.link_result_id)
                        if w.link_result_id is not None
                        else None
                    ),
                    source=w.source,
                    code=w.code,
                    message=w.message,
                )
                for w in warn_rows
            )
            result = SimulationResult(
                link_results=tuple(link_results),
                warnings=warnings,
            )

        return Simulation(
            id=row.id,
            owner_id=row.owner_id,
            scenario_id=row.scenario_id,
            comparison_group_id=row.comparison_group_id,
            name=row.name,
            description=row.description,
            status=SimulationStatus(row.status),
            technology=Technology(row.technology),
            propagation_model_id=row.propagation_model_id,
            snapshot=snapshot,
            summary=summary,
            result=result,
            failure_reason=row.failure_reason,
            created_at=_ensure_utc(row.created_at) or datetime.now(UTC),
            started_at=_ensure_utc(row.started_at),
            finished_at=_ensure_utc(row.finished_at),
        )
