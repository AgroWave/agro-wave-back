"""Domain services for the scenarios bounded context."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from agrowave.modules.scenarios.domain.models import (
    AccessNode,
    Antenna,
    Deployment,
    EndNode,
    Link,
    RadioConfig,
    Scenario,
    SensitivityOrigin,
    TxPower,
    bounds_dimensions_km,
    geodesic_distance_km,
)
from agrowave.modules.scenarios.domain.ports import NodeTemplateInfo, ProfileInfo

__all__ = [
    "ScenarioVariantFactory",
    "bounds_dimensions_km",
    "geodesic_distance_km",
]


class ScenarioVariantFactory:
    """Builds a technology variant of an existing Scenario (RN-29, UC-SC-04)."""

    @staticmethod
    def create_variant(
        source: Scenario,
        target_profile: ProfileInfo,
        band_code: str,
        frequency_mhz: float,
        end_node_template: NodeTemplateInfo | None = None,
        access_node_template: NodeTemplateInfo | None = None,
        name: str | None = None,
    ) -> Scenario:
        """Creates a new scenario variant sharing the source comparison group.

        Preserves the study area, terrain_ref, node positions and heights,
        uplink links, propagation setup, and comparison_group_id (RN-29).
        Applies the target profile's technology and reference sensitivity,
        and copies radio parameters from the target technology's node templates
        (preserving source access node antenna gain when the target access node
        template has antenna_gain_dbi=None, per Q3b).

        Args:
            source: Base scenario to derive the variant from.
            target_profile: Target LPWAN profile information.
            band_code: Selected band code within the target profile.
            frequency_mhz: Operating frequency in MHz within the selected band.
            end_node_template: Optional end node template for the target technology.
            access_node_template: Optional access node template for the target technology.
            name: Optional name for the variant scenario.

        Returns:
            Newly constructed Scenario variant sharing source.comparison_group_id.
        """
        band_min: float | None = None
        band_max: float | None = None
        for b in target_profile.bands:
            if b.code == band_code:
                band_min = b.min_mhz
                band_max = b.max_mhz
                break

        radio_config = RadioConfig(
            profile_id=target_profile.id,
            technology=target_profile.technology,
            band_code=band_code,
            frequency_mhz=frequency_mhz,
            band_min_mhz=band_min,
            band_max_mhz=band_max,
        )

        access_id_map: dict[UUID, UUID] = {}
        new_access_nodes: list[AccessNode] = []
        for src_an in source.deployment.access_nodes:
            new_an_id = uuid4()
            access_id_map[src_an.id] = new_an_id
            if access_node_template is not None:
                gain = (
                    access_node_template.antenna_gain_dbi
                    if access_node_template.antenna_gain_dbi is not None
                    else src_an.antenna.gain_dbi
                )
                antenna = Antenna(
                    reference=access_node_template.antenna_ref,
                    gain_dbi=gain,
                    polarization=access_node_template.polarization,
                )
            else:
                antenna = src_an.antenna

            new_access_nodes.append(
                AccessNode(
                    id=new_an_id,
                    name=src_an.name,
                    position=src_an.position,
                    height_agl=src_an.height_agl,
                    antenna=antenna,
                    sensitivity_dbm=target_profile.reference_sensitivity_dbm,
                    sensitivity_origin=SensitivityOrigin.REFERENCE_TO_VERIFY,
                )
            )

        end_id_map: dict[UUID, UUID] = {}
        new_end_nodes: list[EndNode] = []
        for src_en in source.deployment.end_nodes:
            new_en_id = uuid4()
            end_id_map[src_en.id] = new_en_id
            if end_node_template is not None:
                en_gain = (
                    end_node_template.antenna_gain_dbi
                    if end_node_template.antenna_gain_dbi is not None
                    else src_en.antenna.gain_dbi
                )
                en_antenna = Antenna(
                    reference=end_node_template.antenna_ref,
                    gain_dbi=en_gain,
                    polarization=end_node_template.polarization,
                )
                en_tx = TxPower(
                    nominal_dbm=(
                        end_node_template.tx_power_nominal_dbm
                        if end_node_template.tx_power_nominal_dbm is not None
                        else src_en.tx_power.nominal_dbm
                    ),
                    tolerance_db=(
                        end_node_template.tx_power_tolerance_db
                        if end_node_template.tx_power_tolerance_db is not None
                        else 0.0
                    ),
                )
                src_tpl_id = end_node_template.id
            else:
                en_antenna = src_en.antenna
                en_tx = src_en.tx_power
                src_tpl_id = None

            new_end_nodes.append(
                EndNode(
                    id=new_en_id,
                    name=src_en.name,
                    position=src_en.position,
                    height_agl=src_en.height_agl,
                    antenna=en_antenna,
                    tx_power=en_tx,
                    source_template_id=src_tpl_id,
                )
            )

        new_links: list[Link] = []
        for src_link in source.deployment.links:
            new_links.append(
                Link(
                    id=uuid4(),
                    end_node_id=end_id_map[src_link.end_node_id],
                    access_node_id=access_id_map[src_link.access_node_id],
                )
            )

        now = datetime.now(UTC)
        variant_name = (
            name.strip()
            if name and name.strip()
            else f"{source.name} ({target_profile.technology.value})"
        )

        variant = Scenario(
            id=uuid4(),
            owner_id=source.owner_id,
            name=variant_name,
            description=source.description,
            comparison_group_id=source.comparison_group_id,
            study_area=source.study_area,
            terrain_ref=source.terrain_ref,
            radio_config=radio_config,
            propagation_setup=source.propagation_setup,
            created_at=now,
            updated_at=now,
        )
        variant.set_deployment(
            Deployment(
                access_nodes=new_access_nodes,
                end_nodes=new_end_nodes,
                links=new_links,
            )
        )
        return variant
