"""Seeding of predefined LPWAN profiles and node templates (AC-02-01)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Expected values from the parameter table (lpwan-domain-sme, radio-and-propagation.md).
EXPECTED_PROFILES = {
    "LoRaWAN SF12": ("LORAWAN", 12, -137.0),
    "LoRaWAN SF10": ("LORAWAN", 10, -130.0),
    "LoRaWAN SF7": ("LORAWAN", 7, -124.0),
    "NB-IoT": ("NB_IOT", None, -130.0),
    "LTE-M": ("LTE_M", None, -130.0),
}
EXPECTED_BAND_COUNTS = {
    "LoRaWAN SF12": 1,
    "LoRaWAN SF10": 1,
    "LoRaWAN SF7": 1,
    "NB-IoT": 18,
    "LTE-M": 17,
}


@pytest.fixture
def empty_test_database(test_database_url: str) -> Iterator[str]:
    """Reset the public schema of the test database so it starts empty."""
    engine = create_engine(test_database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    yield test_database_url


def _alembic_config(database_url: str) -> Config:
    """Build an Alembic config for the project pointed at the given database."""
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _counts(database_url: str) -> tuple[int, int, int]:
    """Return the number of predefined profiles, bands and node templates."""
    engine = create_engine(database_url)
    with engine.connect() as connection:
        profiles = connection.execute(
            text("SELECT count(*) FROM profiles_lpwan_profile WHERE is_predefined")
        ).scalar_one()
        bands = connection.execute(text("SELECT count(*) FROM profiles_profile_band")).scalar_one()
        templates = connection.execute(
            text("SELECT count(*) FROM profiles_node_template")
        ).scalar_one()
    engine.dispose()
    return profiles, bands, templates


def test_ac02_01_seed_creates_predefined_profiles(empty_test_database: str) -> None:
    config = _alembic_config(empty_test_database)

    command.upgrade(config, "head")

    engine = create_engine(empty_test_database)
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT p.name, p.technology, p.spreading_factor, p.reference_sensitivity_dbm, "
                "p.owner_id, count(b.id) AS band_count "
                "FROM profiles_lpwan_profile p "
                "LEFT JOIN profiles_profile_band b ON b.profile_id = p.id "
                "WHERE p.is_predefined GROUP BY p.id"
            )
        ).all()
        template_rows = connection.execute(
            text(
                "SELECT technology, role, module_ref, antenna_ref, antenna_gain_dbi "
                "FROM profiles_node_template"
            )
        ).all()
    engine.dispose()

    seeded = {row.name: row for row in rows}
    assert set(seeded) == set(EXPECTED_PROFILES), "the 5 predefined profiles must be seeded"
    for name, (technology, spreading_factor, sensitivity_dbm) in EXPECTED_PROFILES.items():
        row = seeded[name]
        assert row.technology == technology, f"{name}: unexpected technology"
        assert row.spreading_factor == spreading_factor, f"{name}: unexpected spreading factor"
        assert row.reference_sensitivity_dbm == sensitivity_dbm, f"{name}: unexpected sensitivity"
        assert row.owner_id is None, f"{name}: predefined profiles have no owner"
        assert row.band_count == EXPECTED_BAND_COUNTS[name], f"{name}: unexpected band count"

    expected_templates = {
        (technology, role)
        for technology in ("LORAWAN", "NB_IOT", "LTE_M")
        for role in ("END_NODE", "ACCESS_NODE")
    }
    assert {(t.technology, t.role) for t in template_rows} == expected_templates, (
        "one end node and one access node template per technology must be seeded"
    )

    # Values without a source in the parameter table are seeded as NULL ("pending").
    for technology in ("NB_IOT", "LTE_M"):
        access_node = next(
            t for t in template_rows if t.technology == technology and t.role == "ACCESS_NODE"
        )
        assert access_node.antenna_gain_dbi is None, f"{technology}: access node gain is pending"
        assert access_node.module_ref is None, f"{technology}: access node module is pending"
        assert access_node.antenna_ref is None, f"{technology}: access node antenna is pending"
        end_node = next(
            t for t in template_rows if t.technology == technology and t.role == "END_NODE"
        )
        assert end_node.antenna_ref is None, f"{technology}: end node antenna is pending"

    # Fixed ids: re-applying the seed revision must not duplicate rows.
    counts_before = _counts(empty_test_database)
    command.downgrade(config, "-1")
    command.upgrade(config, "head")
    assert _counts(empty_test_database) == counts_before, "re-seeding must not duplicate rows"
