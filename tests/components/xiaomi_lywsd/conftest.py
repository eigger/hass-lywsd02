"""Fixtures for the Xiaomi LYWSD integration."""

# <!-- hass-standards:domain-fixtures:start -->
# Use pytest_homeassistant_custom_component.common.MockConfigEntry for
# mock_config_entry when the integration uses config entries.
# Define mock_client only when an external communication client is present.
# Mock external communication boundaries, never Home Assistant core modules.
# Keep integration-specific fixtures below this managed block.
# <!-- hass-standards:domain-fixtures:end -->

import pytest
from unittest.mock import AsyncMock
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.xiaomi_lywsd.const import DOMAIN


@pytest.fixture
def mock_config_entry():
    """Provide a real Home Assistant config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="LYWSD02 CCDDEEFF",
        unique_id="AA:BB:CC:DD:EE:FF",
        data={"address": "AA:BB:CC:DD:EE:FF"},
        options={"auto_sync": "0"},
        version=2,
    )


@pytest.fixture
def mock_client():
    """Provide the BLE transport boundary."""
    client = AsyncMock()
    client.is_connected = True
    return client
