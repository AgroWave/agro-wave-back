"""Seed predefined LPWAN profiles and reference node templates.

Revision ID: 0003_profiles_seed
Revises: 0002_profiles_tables
Create Date: 2026-10-29
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "0003_profiles_seed"
down_revision: str | None = "0002_profiles_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Deterministic UUIDs for predefined profiles
PROFILE_LORAWAN_SF12_ID = UUID("00000000-0000-0000-0000-000000000001")
PROFILE_LORAWAN_SF10_ID = UUID("00000000-0000-0000-0000-000000000002")
PROFILE_LORAWAN_SF7_ID = UUID("00000000-0000-0000-0000-000000000003")
PROFILE_NBIOT_ID = UUID("00000000-0000-0000-0000-000000000004")
PROFILE_LTEM_ID = UUID("00000000-0000-0000-0000-000000000005")

# Deterministic UUIDs for templates
TEMPLATE_LORA_END_NODE = UUID("00000000-0000-0000-0001-000000000001")
TEMPLATE_LORA_ACCESS_NODE = UUID("00000000-0000-0000-0001-000000000002")
TEMPLATE_NBIOT_END_NODE = UUID("00000000-0000-0000-0002-000000000001")
TEMPLATE_NBIOT_ACCESS_NODE = UUID("00000000-0000-0000-0002-000000000002")
TEMPLATE_LTEM_END_NODE = UUID("00000000-0000-0000-0003-000000000001")
TEMPLATE_LTEM_ACCESS_NODE = UUID("00000000-0000-0000-0003-000000000002")

NBIOT_BANDS = [
    "B1",
    "B2",
    "B3",
    "B4",
    "B5",
    "B8",
    "B12",
    "B13",
    "B14",
    "B18",
    "B19",
    "B20",
    "B25",
    "B26",
    "B27",
    "B28",
    "B66",
    "B85",
]

LTEM_BANDS = [
    "B1",
    "B2",
    "B3",
    "B4",
    "B5",
    "B8",
    "B12",
    "B13",
    "B18",
    "B19",
    "B20",
    "B25",
    "B26",
    "B28",
    "B66",
    "B71",
    "B85",
]


def upgrade() -> None:
    now = datetime.now(UTC)

    # 1. Profiles
    profiles = [
        {
            "id": PROFILE_LORAWAN_SF12_ID,
            "owner_id": None,
            "is_predefined": True,
            "name": "LoRaWAN SF12",
            "technology": "LORAWAN",
            "spreading_factor": 12,
            "reference_sensitivity_dbm": -137.0,
            "created_at": now,
        },
        {
            "id": PROFILE_LORAWAN_SF10_ID,
            "owner_id": None,
            "is_predefined": True,
            "name": "LoRaWAN SF10",
            "technology": "LORAWAN",
            "spreading_factor": 10,
            "reference_sensitivity_dbm": -130.0,
            "created_at": now,
        },
        {
            "id": PROFILE_LORAWAN_SF7_ID,
            "owner_id": None,
            "is_predefined": True,
            "name": "LoRaWAN SF7",
            "technology": "LORAWAN",
            "spreading_factor": 7,
            "reference_sensitivity_dbm": -124.0,
            "created_at": now,
        },
        {
            "id": PROFILE_NBIOT_ID,
            "owner_id": None,
            "is_predefined": True,
            "name": "NB-IoT",
            "technology": "NB_IOT",
            "spreading_factor": None,
            "reference_sensitivity_dbm": -130.0,
            "created_at": now,
        },
        {
            "id": PROFILE_LTEM_ID,
            "owner_id": None,
            "is_predefined": True,
            "name": "LTE-M",
            "technology": "LTE_M",
            "spreading_factor": None,
            "reference_sensitivity_dbm": -130.0,
            "created_at": now,
        },
    ]

    profile_table = sa.table(
        "profiles_lpwan_profile",
        sa.column("id", sa.Uuid),
        sa.column("owner_id", sa.Uuid),
        sa.column("is_predefined", sa.Boolean),
        sa.column("name", sa.String),
        sa.column("technology", sa.String),
        sa.column("spreading_factor", sa.Integer),
        sa.column("reference_sensitivity_dbm", sa.Float),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(profile_table, profiles)

    # 2. Bands
    band_rows = []
    # LoRaWAN profiles band: 902-928 MHz
    for p_id in [PROFILE_LORAWAN_SF12_ID, PROFILE_LORAWAN_SF10_ID, PROFILE_LORAWAN_SF7_ID]:
        band_rows.append(
            {
                "id": UUID(int=p_id.int + 100),
                "profile_id": p_id,
                "code": "902-928",
                "min_mhz": 902.0,
                "max_mhz": 928.0,
            }
        )

    # NB-IoT bands
    for idx, code in enumerate(NBIOT_BANDS):
        band_rows.append(
            {
                "id": UUID(int=PROFILE_NBIOT_ID.int + 1000 + idx),
                "profile_id": PROFILE_NBIOT_ID,
                "code": code,
                "min_mhz": None,
                "max_mhz": None,
            }
        )

    # LTE-M bands
    for idx, code in enumerate(LTEM_BANDS):
        band_rows.append(
            {
                "id": UUID(int=PROFILE_LTEM_ID.int + 2000 + idx),
                "profile_id": PROFILE_LTEM_ID,
                "code": code,
                "min_mhz": None,
                "max_mhz": None,
            }
        )

    band_table = sa.table(
        "profiles_profile_band",
        sa.column("id", sa.Uuid),
        sa.column("profile_id", sa.Uuid),
        sa.column("code", sa.String),
        sa.column("min_mhz", sa.Float),
        sa.column("max_mhz", sa.Float),
    )
    op.bulk_insert(band_table, band_rows)

    # 3. Node templates
    templates = [
        # LoRaWAN
        {
            "id": TEMPLATE_LORA_END_NODE,
            "technology": "LORAWAN",
            "role": "END_NODE",
            "name": "Heltec WiFi LoRa V3",
            "module_ref": "Heltec WiFi LoRa V3",
            "antenna_ref": "LoRa U.FL IP-EX",
            "antenna_gain_dbi": 2.0,
            "polarization": None,
            "tx_power_nominal_dbm": 21.0,
            "tx_power_tolerance_db": 1.0,
        },
        {
            "id": TEMPLATE_LORA_ACCESS_NODE,
            "technology": "LORAWAN",
            "role": "ACCESS_NODE",
            "name": "Dragino DLOS8N",
            "module_ref": "Dragino DLOS8N",
            "antenna_ref": "Omni 3 dBi",
            "antenna_gain_dbi": 3.0,
            "polarization": None,
            "tx_power_nominal_dbm": None,
            "tx_power_tolerance_db": None,
        },
        # NB-IoT
        {
            "id": TEMPLATE_NBIOT_END_NODE,
            "technology": "NB_IOT",
            "role": "END_NODE",
            "name": "T-SIM7070G",
            "module_ref": "T-SIM7070G",
            "antenna_ref": None,
            "antenna_gain_dbi": 5.0,
            "polarization": None,
            "tx_power_nominal_dbm": 20.0,
            "tx_power_tolerance_db": 2.7,
        },
        {
            "id": TEMPLATE_NBIOT_ACCESS_NODE,
            "technology": "NB_IOT",
            "role": "ACCESS_NODE",
            "name": "Generic NB-IoT Base Station",
            "module_ref": None,
            "antenna_ref": None,
            "antenna_gain_dbi": 0.0,
            "polarization": None,
            "tx_power_nominal_dbm": None,
            "tx_power_tolerance_db": None,
        },
        # LTE-M
        {
            "id": TEMPLATE_LTEM_END_NODE,
            "technology": "LTE_M",
            "role": "END_NODE",
            "name": "T-SIM7070G",
            "module_ref": "T-SIM7070G",
            "antenna_ref": None,
            "antenna_gain_dbi": 5.0,
            "polarization": None,
            "tx_power_nominal_dbm": 20.0,
            "tx_power_tolerance_db": 2.7,
        },
        {
            "id": TEMPLATE_LTEM_ACCESS_NODE,
            "technology": "LTE_M",
            "role": "ACCESS_NODE",
            "name": "Generic LTE-M Base Station",
            "module_ref": None,
            "antenna_ref": None,
            "antenna_gain_dbi": 0.0,
            "polarization": None,
            "tx_power_nominal_dbm": None,
            "tx_power_tolerance_db": None,
        },
    ]

    template_table = sa.table(
        "profiles_node_template",
        sa.column("id", sa.Uuid),
        sa.column("technology", sa.String),
        sa.column("role", sa.String),
        sa.column("name", sa.String),
        sa.column("module_ref", sa.String),
        sa.column("antenna_ref", sa.String),
        sa.column("antenna_gain_dbi", sa.Float),
        sa.column("polarization", sa.String),
        sa.column("tx_power_nominal_dbm", sa.Float),
        sa.column("tx_power_tolerance_db", sa.Float),
    )
    op.bulk_insert(template_table, templates)


def downgrade() -> None:
    op.execute("DELETE FROM profiles_profile_band")
    op.execute("DELETE FROM profiles_lpwan_profile WHERE is_predefined = true")
    op.execute("DELETE FROM profiles_node_template")
