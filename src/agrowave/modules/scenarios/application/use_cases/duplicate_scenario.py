"""Use case for duplicating a scenario (UC-SC-03)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from agrowave.modules.scenarios.domain.errors import ScenarioNotFoundError
from agrowave.modules.scenarios.domain.models import (
    AccessNode,
    Deployment,
    EndNode,
    Link,
    Scenario,
)
from agrowave.modules.scenarios.domain.ports import ScenarioRepository


@dataclass(frozen=True)
class DuplicateScenarioCommand:
    """Command to duplicate an existing scenario."""

    scenario_id: UUID
    owner_id: UUID
    name: str | None = None


class DuplicateScenario:
    """Creates an independent copy of a scenario with a new comparison_group_id (UC-SC-03)."""

    def __init__(self, scenario_repository: ScenarioRepository) -> None:
        """Initializes DuplicateScenario.

        Args:
            scenario_repository: Scenario repository port.
        """
        self._repo = scenario_repository

    def execute(self, command: DuplicateScenarioCommand) -> Scenario:
        """Duplicates the target scenario if owned by command.owner_id.

        Args:
            command: Scenario ID, owner ID, and optional new name.

        Returns:
            Newly persisted duplicate Scenario aggregate.

        Raises:
            ScenarioNotFoundError: If not found or not owned by user.
        """
        source = self._repo.get_by_id(command.scenario_id)
        if source is None or source.owner_id != command.owner_id:
            raise ScenarioNotFoundError()

        access_id_map: dict[UUID, UUID] = {}
        new_access_nodes: list[AccessNode] = []
        for an in source.deployment.access_nodes:
            new_id = uuid4()
            access_id_map[an.id] = new_id
            new_access_nodes.append(
                AccessNode(
                    id=new_id,
                    name=an.name,
                    position=an.position,
                    height_agl=an.height_agl,
                    antenna=an.antenna,
                    sensitivity_dbm=an.sensitivity_dbm,
                    sensitivity_origin=an.sensitivity_origin,
                )
            )

        end_id_map: dict[UUID, UUID] = {}
        new_end_nodes: list[EndNode] = []
        for en in source.deployment.end_nodes:
            new_id = uuid4()
            end_id_map[en.id] = new_id
            new_end_nodes.append(
                EndNode(
                    id=new_id,
                    name=en.name,
                    position=en.position,
                    height_agl=en.height_agl,
                    antenna=en.antenna,
                    tx_power=en.tx_power,
                    source_template_id=en.source_template_id,
                )
            )

        new_links = [
            Link(
                id=uuid4(),
                end_node_id=end_id_map[lk.end_node_id],
                access_node_id=access_id_map[lk.access_node_id],
            )
            for lk in source.deployment.links
        ]

        now = datetime.now(UTC)
        new_name = (
            command.name.strip()
            if command.name and command.name.strip()
            else f"{source.name} (Copia)"
        )
        duplicated = Scenario(
            id=uuid4(),
            owner_id=source.owner_id,
            name=new_name,
            description=source.description,
            comparison_group_id=uuid4(),
            study_area=source.study_area,
            terrain_ref=source.terrain_ref,
            radio_config=source.radio_config,
            deployment=Deployment(
                access_nodes=new_access_nodes,
                end_nodes=new_end_nodes,
                links=new_links,
            ),
            propagation_setup=source.propagation_setup,
            created_at=now,
            updated_at=now,
        )
        return self._repo.save(duplicated)
