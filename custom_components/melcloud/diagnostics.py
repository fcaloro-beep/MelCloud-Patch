"""Diagnostics support for MelCloud."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .coordinator import MelCloudConfigEntry

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MelCloudConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the config entry."""
    ent_reg = er.async_get(hass)
    entities = [
        entity.entity_id
        for entity in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    ]

    entity_states = {entity: hass.states.get(entity) for entity in entities}

    entry_dict = entry.as_dict()
    if "data" in entry_dict:
        entry_dict["data"] = {}

    return {
        "entry": entry_dict,
        "entities": entity_states,
    }
