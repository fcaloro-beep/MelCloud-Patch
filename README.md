# MELCloud Flow Control for Home Assistant

Custom integration for Home Assistant installable via HACS, based on the core `melcloud` integration, designed for Mitsubishi Ecodan Air-To-Water units managed through MELCloud.

## Important: domain and existing config entry

This custom integration intentionally keeps:

```json
"domain": "melcloud"
```

The directory structure stays `custom_components/melcloud/`, matching the Home Assistant core integration. This way Home Assistant continues using the existing MELCloud config entry located at:

```text
/config/.storage/core.config_entries
```

No username, password, or token is requested again. The custom integration reuses the data already configured by the previous official integration. Do not include tokens, passwords, or personal data in the repo.

## What changes

This modded version of the core `melcloud` integration changes how ATW/Ecodan climate zones behave:

- the climate zone target temperature becomes the real flow temperature;
- `climate.casa_zone_1` controls `SetCoolFlowTemperatureZone1` or `SetHeatFlowTemperatureZone1`;
- `climate.agrinido_zone_1` uses the same logic;
- ATW devices expose a real `Power` binary sensor;
- ATW devices can be turned on or off through the `melcloud.set_atw_power` service;
- the logic applies to all MELCloud ATW zones in general;
- the ATA air-to-air part is not modified.

The `pymelcloud` patch does not modify `site-packages`: it is applied at runtime idempotently inside `custom_components/melcloud/__init__.py`.

## Polling

The integration uses the standard Home Assistant `DataUpdateCoordinator` with an internal update every 8 minutes. No need to create automations with `homeassistant.update_entity` or periodically reload the integration.

## Installation via HACS

1. Publish this folder as a GitHub repository.
2. In HACS, open custom repositories.
3. Add the repo URL as an integration.
4. Install `MELCloud Flow Control`.
5. Restart Home Assistant.

After the restart, Home Assistant should load `custom_components/melcloud` instead of the official core integration.

## Service examples

Casa:

```yaml
action: climate.set_temperature
target:
  entity_id: climate.casa_zone_1
data:
  temperature: 18
```

Agrinido:

```yaml
action: climate.set_temperature
target:
  entity_id: climate.agrinido_zone_1
data:
  temperature: 18
```

Turn ATW devices on:

```yaml
action: melcloud.set_atw_power
data:
  device_name:
    - Casa
    - Agrinido
  power: true
```

Turn ATW devices off:

```yaml
action: melcloud.set_atw_power
data:
  device_name:
    - Casa
    - Agrinido
  power: false
```

## Recommended manual tests

1. After HACS installation and restart, check the logs that Home Assistant loads `custom_components/melcloud`.
2. Verify `climate.casa_zone_1`: in summer/cooling mode the target should match `SetCoolFlowTemperatureZone1`.
3. Call:

```yaml
action: climate.set_temperature
target:
  entity_id: climate.casa_zone_1
data:
  temperature: 24
```

Then verify from MELCloud web/app that the Casa flow temperature changes.

4. Repeat for Agrinido:

```yaml
action: climate.set_temperature
target:
  entity_id: climate.agrinido_zone_1
data:
  temperature: 18
```

5. Verify that MELCloud sensors are no longer `Unavailable`, in particular:

- `sensor.casa_temperatura_di_flusso`
- `sensor.casa_return_temperature`
- `sensor.casa_heat_pump_frequency`
- `sensor.casa_demand_percentage`
- `sensor.agrinido_temperatura_di_flusso`
- `sensor.agrinido_return_temperature`

## Notes

This integration is not official Mitsubishi. It overrides the core `melcloud` integration through a custom component, so Home Assistant updates may change the original core integration. Keep this fork aligned when updating Home Assistant.
