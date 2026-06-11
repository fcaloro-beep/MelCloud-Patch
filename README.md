# MELCloud Flow Control per Home Assistant

Custom integration Home Assistant installabile via HACS, basata sulla core integration `melcloud`, pensata per Mitsubishi Ecodan Air-To-Water gestiti tramite MELCloud.

## Importante: domain e config entry esistente

Questa custom integration mantiene volutamente:

```json
"domain": "melcloud"
```

La struttura resta `custom_components/melcloud/`, come la core integration di Home Assistant. In questo modo Home Assistant continua a usare la config entry MELCloud gia esistente in:

```text
/config/.storage/core.config_entries
```

Non deve chiedere nuovamente username, password o token. La custom integration riusa i dati gia configurati dalla precedente integrazione ufficiale. Non inserire token, password o dati personali nella repo.

## Cosa cambia

Questa versione modded della core integration `melcloud` cambia il comportamento delle climate zone ATW/Ecodan:

- la target temperature della climate zone diventa la temperatura di mandata reale;
- `climate.casa_zone_1` comanda `SetCoolFlowTemperatureZone1` oppure `SetHeatFlowTemperatureZone1`;
- `climate.agrinido_zone_1` usa la stessa logica;
- la logica vale in generale per le zone ATW MELCloud;
- la parte ATA air-to-air non viene modificata.

La patch su `pymelcloud` non modifica `site-packages`: viene applicata a runtime in modo idempotente dentro `custom_components/melcloud/__init__.py`.

## Polling

L'integrazione usa il normale `DataUpdateCoordinator` di Home Assistant con aggiornamento interno ogni 8 minuti. Non serve creare automazioni con `homeassistant.update_entity` e non serve ricaricare l'integrazione periodicamente.

## Installazione via HACS

1. Pubblica questa cartella come repository GitHub.
2. In HACS apri i custom repository.
3. Aggiungi l'URL della repo come integration.
4. Installa `MELCloud Flow Control`.
5. Riavvia Home Assistant.

Dopo il riavvio, Home Assistant deve caricare `custom_components/melcloud` al posto della core integration ufficiale.

## Esempi di servizio

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

## Test manuali consigliati

1. Dopo installazione HACS e riavvio, verifica nei log che Home Assistant carichi `custom_components/melcloud`.
2. Verifica `climate.casa_zone_1`: in estate/raffrescamento il target deve coincidere con `SetCoolFlowTemperatureZone1`.
3. Chiama:

```yaml
action: climate.set_temperature
target:
  entity_id: climate.casa_zone_1
data:
  temperature: 24
```

Poi verifica da MELCloud web/app che la mandata Casa cambi.

4. Ripeti per Agrinido:

```yaml
action: climate.set_temperature
target:
  entity_id: climate.agrinido_zone_1
data:
  temperature: 18
```

5. Verifica che i sensori MELCloud non siano piu `Non disponibile`, in particolare:

- `sensor.casa_temperatura_di_flusso`
- `sensor.casa_return_temperature`
- `sensor.casa_heat_pump_frequency`
- `sensor.casa_demand_percentage`
- `sensor.agrinido_temperatura_di_flusso`
- `sensor.agrinido_return_temperature`

## Note

Questa integrazione non e ufficiale Mitsubishi. Sovrascrive la core integration `melcloud` tramite custom component, quindi gli aggiornamenti di Home Assistant potrebbero cambiare la core integration originale. Mantieni questo fork allineato quando aggiorni Home Assistant.
