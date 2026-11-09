"""Use case for creating a scenario variant with another LPWAN profile (UC-SC-04, RN-29)."""

from dataclasses import dataclass
from uuid import UUID

from agrowave.modules.scenarios.domain.errors import (
    FrequencyOutOfProfileError,
    ProfileNotFoundError,
    ScenarioNotFoundError,
)
from agrowave.modules.scenarios.domain.models import Scenario
from agrowave.modules.scenarios.domain.ports import (
    NodeTemplateInfo,
    ProfileLookup,
    ScenarioRepository,
)
from agrowave.modules.scenarios.domain.services import ScenarioVariantFactory


@dataclass(frozen=True)
class CreateScenarioVariantCommand:
    """Command to create a technology variant of an existing scenario."""

    scenario_id: UUID
    owner_id: UUID
    target_profile_id: UUID
    band_code: str | None = None
    frequency_mhz: float | None = None
    name: str | None = None


class CreateScenarioVariant:
    """Creates a technology variant sharing the source comparison_group_id (UC-SC-04, RN-29)."""

    def __init__(
        self,
        scenario_repository: ScenarioRepository,
        profile_lookup: ProfileLookup,
    ) -> None:
        """Initializes CreateScenarioVariant.

        Args:
            scenario_repository: Scenario repository port.
            profile_lookup: Port for looking up target LPWAN profile and templates.
        """
        self._repo = scenario_repository
        self._profiles = profile_lookup

    def execute(self, command: CreateScenarioVariantCommand) -> Scenario:
        """Creates and persists a technology variant of the source scenario.

        Args:
            command: Variant creation payload.

        Returns:
            Newly persisted Scenario variant sharing source.comparison_group_id.

        Raises:
            ScenarioNotFoundError: If the source scenario is not found or not owned by user.
            FrequencyOutOfProfileError: If the band or frequency is invalid for target profile.
        """
        source = self._repo.get_by_id(command.scenario_id)
        if source is None or source.owner_id != command.owner_id:
            raise ScenarioNotFoundError()

        target_profile = self._profiles.get_profile(command.target_profile_id, command.owner_id)
        if target_profile is None:
            raise ProfileNotFoundError("Target LPWAN profile was not found or is not accessible.")

        band_code = command.band_code or (
            target_profile.bands[0].code if target_profile.bands else ""
        )
        matched_band = next(
            (b for b in target_profile.bands if b.code == band_code),
            None,
        )
        if matched_band is None and target_profile.bands:
            raise FrequencyOutOfProfileError(
                f"Band '{band_code}' does not belong to the target LPWAN profile."
            )

        freq = command.frequency_mhz
        if freq is None:
            if (
                matched_band
                and matched_band.min_mhz is not None
                and matched_band.max_mhz is not None
            ):
                freq = round((matched_band.min_mhz + matched_band.max_mhz) / 2.0, 3)
            elif source.radio_config is not None:
                freq = source.radio_config.frequency_mhz
            else:
                freq = 915.0

        templates = self._profiles.get_templates(target_profile.technology)
        end_tpl: NodeTemplateInfo | None = next(
            (t for t in templates if t.role == "END_NODE"),
            None,
        )
        access_tpl: NodeTemplateInfo | None = next(
            (t for t in templates if t.role == "ACCESS_NODE"),
            None,
        )

        variant = ScenarioVariantFactory.create_variant(
            source=source,
            target_profile=target_profile,
            band_code=band_code,
            frequency_mhz=freq,
            end_node_template=end_tpl,
            access_node_template=access_tpl,
            name=command.name,
        )
        return self._repo.save(variant)
