"""The MELCloud Climate integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import ClientConnectionError, ClientResponseError
from pymelcloud import get_devices
from pymelcloud.atw_device import AtwDevice, Zone

try:
    from pymelcloud.atw_device import EFFECTIVE_FLAGS
except ImportError:
    EFFECTIVE_FLAGS = "EffectiveFlags"

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed

from .coordinator import MelCloudConfigEntry, MelCloudDeviceUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.WATER_HEATER,
]

PROPERTY_ZONE_1_FLOW_TEMPERATURE = "zone_1_flow_temperature"
PROPERTY_ZONE_2_FLOW_TEMPERATURE = "zone_2_flow_temperature"

_FLOW_TEMPERATURE_FLAG = 0x1000004000020
_COOLING_OPERATION_MODES = {3, 4}


def _state_value(state: dict[str, Any], key: str, default: Any = None) -> Any:
    """Return a MELCloud state value from current or nested state data."""
    if key in state:
        return state[key]

    device = state.get("Device")
    if isinstance(device, dict):
        return device.get(key, default)

    return default


def _zone_state(zone: Zone) -> dict[str, Any] | None:
    """Return the raw state dict for a pymelcloud ATW zone."""
    device = getattr(zone, "_device", None)
    state = getattr(device, "_state", None)
    if isinstance(state, dict):
        return state

    device_state = getattr(zone, "_device_state", None)
    if callable(device_state):
        state = device_state()
        if isinstance(state, dict):
            return state

    return None


def _ha_atw_get_device_prop(self: AtwDevice, key: str) -> Any:
    """Return a raw ATW device property from pymelcloud state/config data."""
    state = getattr(self, "_state", None)
    if isinstance(state, dict) and key in state:
        return state.get(key)

    conf = getattr(self, "_device_conf", {}) or {}
    if callable(conf):
        conf = conf()

    device = conf.get("Device", conf) if isinstance(conf, dict) else {}
    if isinstance(device, dict):
        return device.get(key)

    return None


def _ha_atw_make_prop(key: str) -> property:
    """Create an ATW compatibility property."""
    return property(lambda self, _key=key: _ha_atw_get_device_prop(self, _key))


def _patch_flow_temperature_control() -> None:
    """Patch pymelcloud to support ATW/Ecodan flow temperature writes."""
    if not hasattr(Zone, "set_target_flow_temperature"):

        async def set_target_flow_temperature(
            self: Zone, target_temperature: float
        ) -> None:
            """Set target flow temperature for this zone."""
            prop = (
                PROPERTY_ZONE_1_FLOW_TEMPERATURE
                if self.zone_index == 1
                else PROPERTY_ZONE_2_FLOW_TEMPERATURE
            )
            await self._device.set({prop: target_temperature})

        Zone.set_target_flow_temperature = set_target_flow_temperature

    if not hasattr(Zone, "target_flow_temperature"):

        def target_flow_temperature(self: Zone) -> float | None:
            """Return target flow temperature for this zone."""
            state = _zone_state(self)
            if state is None:
                return None

            operation_mode = getattr(self, "operation_mode", None)
            if operation_mode == "heat":
                return state.get(f"SetHeatFlowTemperatureZone{self.zone_index}")

            return state.get(f"SetCoolFlowTemperatureZone{self.zone_index}")

        Zone.target_flow_temperature = property(target_flow_temperature)

    if getattr(AtwDevice, "_flow_temperature_patch_applied", False):
        return

    original_apply_write: Callable[..., None] = AtwDevice.apply_write

    def apply_write(self: AtwDevice, state: dict[str, Any], key: str, value: Any) -> None:
        """Apply ATW flow-temperature writes, otherwise use pymelcloud default."""
        if key not in (
            PROPERTY_ZONE_1_FLOW_TEMPERATURE,
            PROPERTY_ZONE_2_FLOW_TEMPERATURE,
        ):
            original_apply_write(self, state, key, value)
            return

        flags = int(_state_value(state, EFFECTIVE_FLAGS, 0) or 0)
        flags |= _FLOW_TEMPERATURE_FLAG

        if key == PROPERTY_ZONE_1_FLOW_TEMPERATURE:
            mode = _state_value(state, "OperationModeZone1")
            if mode in _COOLING_OPERATION_MODES:
                state["SetCoolFlowTemperatureZone1"] = self.round_temperature(value)
            else:
                state["SetHeatFlowTemperatureZone1"] = self.round_temperature(value)
        else:
            mode = _state_value(state, "OperationModeZone2")
            if mode in _COOLING_OPERATION_MODES:
                state["SetCoolFlowTemperatureZone2"] = self.round_temperature(value)
            else:
                state["SetHeatFlowTemperatureZone2"] = self.round_temperature(value)

        state[EFFECTIVE_FLAGS] = flags

    AtwDevice.apply_write = apply_write
    AtwDevice._flow_temperature_patch_applied = True
    _LOGGER.debug("Applied MELCloud ATW flow temperature control patch")


def _patch_atw_sensor_compatibility() -> None:
    """Patch pymelcloud ATW attributes expected by Home Assistant entities."""
    if getattr(AtwDevice, "_ha_sensor_compat_patch_applied", False):
        return

    AtwDevice.get_device_prop = _ha_atw_get_device_prop

    AtwDevice.flow_temperature = _ha_atw_make_prop("FlowTemperature")
    AtwDevice.return_temperature = _ha_atw_make_prop("ReturnTemperature")
    AtwDevice.flow_temperature_boiler = _ha_atw_make_prop("FlowTemperatureBoiler")
    AtwDevice.return_temperature_boiler = _ha_atw_make_prop("ReturnTemperatureBoiler")
    AtwDevice.mixing_tank_temperature = _ha_atw_make_prop("MixingTankWaterTemperature")
    AtwDevice.condensing_temperature = _ha_atw_make_prop("CondensingTemperature")
    AtwDevice.heat_pump_frequency = _ha_atw_make_prop("HeatPumpFrequency")
    AtwDevice.demand_percentage = _ha_atw_make_prop("DemandPercentage")
    AtwDevice.wifi_signal = _ha_atw_make_prop("WifiSignalStrength")

    AtwDevice.total_energy_consumed = _ha_atw_make_prop("CurrentEnergyConsumed")
    AtwDevice.daily_heating_energy_consumed = _ha_atw_make_prop(
        "DailyHeatingEnergyConsumed"
    )
    AtwDevice.daily_heating_energy_produced = _ha_atw_make_prop(
        "DailyHeatingEnergyProduced"
    )
    AtwDevice.daily_cooling_energy_consumed = _ha_atw_make_prop(
        "DailyCoolingEnergyConsumed"
    )
    AtwDevice.daily_cooling_energy_produced = _ha_atw_make_prop(
        "DailyCoolingEnergyProduced"
    )
    AtwDevice.daily_hot_water_energy_consumed = _ha_atw_make_prop(
        "DailyHotWaterEnergyConsumed"
    )
    AtwDevice.daily_hot_water_energy_produced = _ha_atw_make_prop(
        "DailyHotWaterEnergyProduced"
    )

    AtwDevice.has_energy_consumed_meter = property(
        lambda self: bool(_ha_atw_get_device_prop(self, "HasEnergyConsumedMeter"))
    )
    AtwDevice.has_outdoor_temperature = property(
        lambda self: _ha_atw_get_device_prop(self, "OutdoorTemperature") is not None
    )

    AtwDevice.boiler_status = _ha_atw_make_prop("BoilerStatus")
    AtwDevice.booster_heater1_status = _ha_atw_make_prop("BoosterHeater1Status")
    AtwDevice.booster_heater2_status = _ha_atw_make_prop("BoosterHeater2Status")
    AtwDevice.booster_heater2plus_status = _ha_atw_make_prop(
        "BoosterHeater2PlusStatus"
    )
    AtwDevice.immersion_heater_status = _ha_atw_make_prop("ImmersionHeaterStatus")
    AtwDevice.water_pump1_status = _ha_atw_make_prop("WaterPump1Status")
    AtwDevice.water_pump2_status = _ha_atw_make_prop("WaterPump2Status")
    AtwDevice.water_pump3_status = _ha_atw_make_prop("WaterPump3Status")
    AtwDevice.water_pump4_status = _ha_atw_make_prop("WaterPump4Status")
    AtwDevice.valve_3way_status = _ha_atw_make_prop("ValveStatus3Way")
    AtwDevice.valve_2way_status = _ha_atw_make_prop("ValveStatus2Way")

    AtwDevice._ha_sensor_compat_patch_applied = True
    _LOGGER.debug("Applied MELCloud ATW sensor compatibility patch")


def _apply_pymelcloud_patches() -> None:
    """Apply all pymelcloud runtime patches used by this custom integration."""
    # Flow temperature control patch for MELCloud ATW/Ecodan
    _patch_flow_temperature_control()
    _patch_atw_sensor_compatibility()


async def async_setup_entry(hass: HomeAssistant, entry: MelCloudConfigEntry) -> bool:
    """Establish connection with MELCloud."""
    _apply_pymelcloud_patches()

    try:
        async with asyncio.timeout(10):
            all_devices = await get_devices(
                token=entry.data[CONF_TOKEN],
                session=async_get_clientsession(hass),
                conf_update_interval=timedelta(minutes=30),
                device_set_debounce=timedelta(seconds=2),
            )
    except ClientResponseError as ex:
        if ex.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            raise ConfigEntryAuthFailed from ex
        if ex.status == HTTPStatus.TOO_MANY_REQUESTS:
            raise UpdateFailed(
                "MELCloud rate limit exceeded. Your account may be temporarily blocked"
            ) from ex
        raise UpdateFailed(f"Error communicating with MELCloud: {ex}") from ex
    except (TimeoutError, ClientConnectionError) as ex:
        raise UpdateFailed(f"Error communicating with MELCloud: {ex}") from ex

    # Create per-device coordinators
    coordinators: dict[str, list[MelCloudDeviceUpdateCoordinator]] = {}
    device_registry = dr.async_get(hass)
    for device_type, devices in all_devices.items():
        # Build coordinators for this device_type
        coordinators[device_type] = [
            MelCloudDeviceUpdateCoordinator(hass, device, entry) for device in devices
        ]

        # Perform initial refreshes concurrently
        await asyncio.gather(
            *(
                coordinator.async_config_entry_first_refresh()
                for coordinator in coordinators[device_type]
            )
        )

        # Register parent devices so zone entities can reference via_device
        for coordinator in coordinators[device_type]:
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                **coordinator.device_info,
            )

    entry.runtime_data = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
