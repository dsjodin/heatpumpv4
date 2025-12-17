# Multi-Brand Heat Pump Monitor

Detta projekt stöder nu flera värmepumpmärken med en provider-baserad arkitektur.

## Märken som stöds

- **Thermia Diplomat** - Bergvärmepumpar
- **IVT Greenline** (Rego 600/637) - Bergvärmepumpar
- **NIBE Fighter/Supreme** (F/S-series) - Bergvärmepumpar

## Arkitektur

### Provider-baserad design

Projektet använder en provider-baserad arkitektur för att stödja flera märken:

```
providers/
├── base.py                    # Abstract provider base class
├── __init__.py               # Provider factory
├── thermia/
│   ├── provider.py           # Thermia-specific implementation
│   ├── registers.py          # Thermia register definitions
│   ├── alarms.py             # Thermia alarm codes
│   ├── dashboard_components.py  # Thermia UI components
│   └── callbacks.py          # Thermia callback functions
├── ivt/
│   ├── provider.py           # IVT-specific implementation
│   ├── registers.py          # IVT register definitions (Rego 600/637)
│   ├── alarms.py             # IVT alarm codes
│   ├── dashboard_components.py  # IVT UI components
│   └── callbacks.py          # IVT callback functions
└── nibe/
    ├── provider.py           # NIBE-specific implementation
    ├── registers.py          # NIBE register definitions (F/S-series)
    ├── alarms.py             # NIBE alarm codes
    ├── dashboard_components.py  # NIBE UI components
    └── callbacks.py          # NIBE callback functions
```

### Hybrid Dashboard

Dashboarden använder en **hybrid approach**:

- **Gemensamma komponenter** (alla märken):
  - Temperaturkort (radiator, outdoor, brine)
  - Status (kompressor, pumpar)
  - Larmsektion (märkesspecifika koder)
  - KPI-kort (COP, drift%)
  - Grafer (temperatur, prestanda)
  - Varmvattencykler
  - Sankey energiflöde
  - Systemschema

- **Märkesspecifika komponenter** (med egna callbacks):
  - **Thermia**:
    - Pumpvarvtal (cirkulationspump, köldbärarpump)
    - Driftläge (Auto, Normal, etc.)
    - Effektmätning (aktuell + ackumulerad)
    - Tryckrörstemperatur
    - Kyla (temperatur + börvärde)
  - **IVT**:
    - Intern värmebärare (framledning, retur)
    - Varmvatten dual sensorer (Tank 1, Tank 2)
    - Hetgas temperatur
    - Tillsatssteg (Steg 1, Steg 2, Total %)
    - Runtime split (uppvärmning, varmvatten)
    - Speciallägen (semester, sommar)
  - **NIBE**:
    - Gradminuter (DM) - NIBE värmereglering (8255, 8105)
    - Varmvattenprogram (Eco/Normal/Luxury/Smart)
    - Kompressor hastighet (variabel, %)
    - Hetgas temperatur (BT14/BT18)
    - Intern värmebärare (BT2 framledning, BT3 retur)
    - Energiuppdelning (total, varmvatten, ventilation)
    - Värmekurva inställningar (2205, 2207)
    - Pumpstatus (intern cirkulationspump, köldbärarpump)
    - 3-fas strömförbrukning (L1+L2+L3)
    - Poolläge (on/off)

## Konfiguration

### Välj märke i config.yaml

```yaml
# Heat Pump Brand Configuration
# Select your heat pump brand: 'thermia', 'ivt', or 'nibe'
brand: thermia
```

### Environment Variable (alternativ)

```bash
export HEATPUMP_BRAND=ivt  # eller 'thermia', 'nibe'
```

## Gateway & MQTT

Båda märkena använder **samma H66 gateway** och MQTT-struktur:

- Gateway: **H66** (Husdata)
- MQTT-topics: `<h66_mac>/HP/<register_id>`
- Data format: Samma
- InfluxDB: Samma databas

## Register-definitioner

### Gemensamma register (båda märken)

| Register | Thermia | IVT | Beskrivning |
|----------|---------|-----|-------------|
| 0001 | ✓ | ✓ | Radiator return |
| 0002 | ✓ | ✓ | Radiator forward |
| 0005 | ✓ | ✓ | Brine in/Evaporator |
| 0006 | ✓ | ✓ | Brine out/Condenser |
| 0007 | ✓ | ✓ | Outdoor temp |
| 0008 | ✓ | ✓ | Indoor temp |
| 0009 | ✓ | ✓ | Hot water top |
| 1A01 | ✓ | ✓ | Compressor status |
| 1A04 | ✓ | ✓ | Brine pump status |
| 1A06 | ✓ | ✓ | Radiator pump status |
| 1A07 | ✓ | ✓ | Switch valve |
| 3104 | ✓ | ✓ | Additional heat % |
| 0107 | ✓ | ✓ | Heating setpoint |

### Thermia-specifika register

| Register | Beskrivning |
|----------|-------------|
| 0012 | Pressure tube temp |
| 0013 | Cooling temp |
| 2201 | Operating mode |
| 3109 | Circulation pump speed (%) |
| 3110 | Brine pump speed (%) |
| 2A91 | **Alarm code** |
| 6C60 | Compressor runtime (total) |
| 6C63 | Aux 3kW runtime |
| 6C64 | Hot water runtime |
| 6C66 | Aux 6kW runtime |
| CFAA | Power consumption (W) |
| 5FAB | Energy accumulated (kWh) |

### NIBE-specifika register (EB100 Controller)

| Register | Beskrivning |
|----------|-------------|
| 0002 | Radiator return (BT61) |
| 0003 | Heat carrier return (BT3) |
| 0004 | Heat carrier forward (BT2) |
| 000B | Hot gas temp (LW-BT14, EW-BT18) |
| 000C | Suction gas (BT17) |
| 000D | Liquid flow (l/min) |
| 000F | Air intake (EW pumps only) |
| 0010 | Air outlet (EW pumps only) |
| 0011 | Pool temp |
| 0020-0022 | Heat circuit 2 (if installed) |
| 0106 | Room temp setpoint (current) |
| 0107 | Heating setpoint |
| 2201 | Operating mode (0=Auto, 1=Manual, 2=Only add heat) |
| 2204 | Room sensor influence |
| 2205 | Heat curve circuit 1 |
| 2207 | Heat curve offset circuit 1 |
| 2213 | Warm Water program (0=Eco, 1=Normal, 2=Luxury, 4=Smart) |
| 2218 | Pool mode (0=off, 1=On) |
| 8255 | Degree minutes - compressor |
| 8105 | Degree minutes - integral |
| 9226 | Max additional heat (kW limit) |
| 1A01 | Compressor status (0=Off, 1=On) |
| 1A04 | Brine pump status (LW pumps only) |
| 1A05 | Internal circulation pump status |
| 1A07 | Switch valve 1 (0=Radiator, 1=Hot Water) |
| 1A0C | Heating cable (AW pumps only) |
| 9108 | Compressor speed (%) |
| 3104 | Additional heat (%) |
| 9124 | Additional heat (kW) |
| 4101-4103 | Load L1-L3 (A) |
| 5C51 | Total supplied energy (kWh) |
| 5C53 | Hotwater energy (kWh) |
| 5C65 | Ventilation energy (kWh) |
| **2A20** | **Alarm code** |

### IVT-specifika register

| Register | Beskrivning |
|----------|-------------|
| 0003 | Heat carrier return (intern) |
| 0004 | Heat carrier forward (intern) |
| 000A | Warm water 2 / Mid (extern tank) |
| 000B | Hot gas / Compressor temp |
| 0111 | Warm water setpoint |
| 1A02 | Add heat step 1 (3kW) |
| 1A03 | Add heat step 2 (6kW) |
| 1A05 | Pump heat circuit |
| 2205 | Heat curve level |
| 0207 | Heat curve parallel |
| 020B | Warm water difference |
| 7209 | Extra warm water timer |
| 2210 | Holiday mode |
| 020A | Summer mode temp |
| **BA91** | **Alarm code** (OBS: olika från Thermia!) |
| 6C55 | Compressor runtime - heating |
| 6C56 | Compressor runtime - hotwater |
| 6C58 | Aux runtime - heating |
| 6C59 | Aux runtime - hotwater |

### Viktiga skillnader

#### Larmkoder
- **Thermia**: Register `2A91`, koder 10-80 (HP, LP, MP, etc.)
- **IVT**: Register `BA91`, koder 1-23 (Sensor GT1-GT11, etc.)
- **NIBE**: Register `2A20`, koder 0-255 (Sensor BT1-BT50, kompressor, flöde, etc.)

#### Runtime counters
- **Thermia**: Total runtime (heating + hotwater combined)
- **IVT**: Uppdelat på heating/hotwater separat

#### Tillsatsvärme
- **Thermia**: Procent (3104, 0-100%)
- **IVT**: Procent (3104) + Steg (1A02, 1A03)

## Lägg till nytt märke

För att lägga till ett nytt märke (t.ex. NIBE):

1. **Skapa provider-struktur**:
   ```
   providers/nibe/
   ├── __init__.py
   ├── provider.py
   ├── registers.py
   ├── alarms.py
   ├── dashboard_components.py
   └── callbacks.py
   ```

2. **Implementera provider**:
   ```python
   # providers/nibe/provider.py
   from ..base import HeatPumpProvider

   class NIBEProvider(HeatPumpProvider):
       def get_brand_name(self) -> str:
           return "nibe"

       def get_display_name(self) -> str:
           return "NIBE Fighter"

       # Implementera alla abstractmethod från base
       ...
   ```

3. **Skapa dashboard components**:
   ```python
   # providers/nibe/dashboard_components.py
   def create_nibe_specific_section():
       # Skapa UI-komponenter med unika ID:n (nibe-*)
       ...
   ```

4. **Skapa callbacks**:
   ```python
   # providers/nibe/callbacks.py
   def register_nibe_callbacks(app, data_query):
       @app.callback(Output('nibe-xxx', 'children'), ...)
       def update_nibe_xxx(n):
           # Hämta och formatera data
           ...
   ```

5. **Uppdatera factory**:
   ```python
   # providers/__init__.py
   def get_provider(brand: str):
       if brand == 'nibe':
           from .nibe.provider import NIBEProvider
           return NIBEProvider()
       ...
   ```

6. **Uppdatera layout.py**:
   ```python
   # dashboard/layout.py
   elif brand_name == 'nibe':
       from providers.nibe.dashboard_components import create_nibe_specific_section
       brand_specific_section = create_nibe_specific_section()
   ```

7. **Uppdatera app.py**:
   ```python
   # dashboard/app.py
   elif brand_name == 'nibe':
       from providers.nibe.callbacks import register_nibe_callbacks
       register_nibe_callbacks(app, data_query)
   ```

8. **Lägg till i config.yaml**:
   ```yaml
   brand: nibe
   ```

## Körning

### Byt märke

1. Stoppa services:
   ```bash
   docker-compose down
   ```

2. Ändra `brand` i `config.yaml`:
   ```yaml
   brand: ivt  # eller 'thermia'
   ```

3. Starta services:
   ```bash
   docker-compose up -d
   ```

### Loggar

```bash
# Collector logs
docker-compose logs -f collector

# Dashboard logs
docker-compose logs -f dashboard
```

Du bör se:
```
collector  | Loaded provider for brand: IVT Greenline
collector  | Monitoring 45 registers
dashboard  | Data query initialized for IVT Greenline
dashboard  | 🔥 Startar IVT Greenline Dashboard...
```

## Testing

### Thermia
```bash
# Set brand in config
brand: thermia

# Restart
docker-compose restart collector dashboard

# Verify
docker-compose logs collector | grep "Loaded provider"
# Should show: "Loaded provider for brand: Thermia Diplomat"
```

### IVT
```bash
# Set brand in config
brand: ivt

# Restart
docker-compose restart collector dashboard

# Verify
docker-compose logs collector | grep "Loaded provider"
# Should show: "Loaded provider for brand: IVT Greenline"
```

### NIBE
```bash
# Set brand in config
brand: nibe

# Restart
docker-compose restart collector dashboard

# Verify
docker-compose logs collector | grep "Loaded provider"
# Should show: "Loaded provider for brand: NIBE Fighter/Supreme"
```

## Dokumentation

### Thermia
- Registers: `providers/thermia/registers.py`
- Alarms: `providers/thermia/alarms.py`
- Provider: `providers/thermia/provider.py`
- Husdata docs: https://online.husdata.se/h-docs/C60.pdf

### IVT
- Registers: `providers/ivt/registers.py`
- Alarms: `providers/ivt/alarms.py`
- Provider: `providers/ivt/provider.py`
- IVT Rego docs: `C00.pdf`

### NIBE
- Registers: `providers/nibe/registers.py`
- Alarms: `providers/nibe/alarms.py`
- Provider: `providers/nibe/provider.py`
- NIBE docs: `C40.pdf` ✅ **Verifierad!**
- Baserat på: NIBE EB100 Controller (Husdata H66, 2025-10-03)

## Felsökning

### "Unsupported brand" error
```
ValueError: Unsupported brand: 'typo'. Supported brands: 'thermia', 'ivt', 'nibe'
```
→ Kontrollera stavning i `config.yaml`

### "Failed to load provider"
```
Failed to load provider: ..., defaulting to Thermia
```
→ Provider-filen saknas eller innehåller fel, systemet fortsätter med Thermia

### Felaktiga larmkoder
→ Kontrollera att rätt `brand` är satt i config (Thermia/IVT har olika larmkoder)

### Register saknas
→ Vissa register är märkesspecifika. Kontrollera `providers/<brand>/registers.py`

## Framtida utökningar

- [x] NIBE Fighter/Supreme support (F/S-series) ✅ Verifierad med C40.pdf
- [ ] CTC EcoPart support
- [ ] Thermia Atlas support
- [ ] Write-support för alla märken (alarm reset, heater switch, mode change)
- [ ] Multi-pump support (flera pumpar samtidigt)

## Migration från gammal struktur

Om du uppgraderar från tidigare version:

1. **Registers flyttade**: Från `config.yaml` → `providers/<brand>/registers.py`
2. **Larmkoder flyttade**: Från `data_query.py` → `providers/<brand>/alarms.py`
3. **Config.yaml enklare**: Endast brand-val + MQTT/InfluxDB settings
4. **Nya filer**: `providers/` katalog skapad
5. **Bakåtkompatibel**: Thermia fortsätter fungera som tidigare

## Support

För frågor och buggrapporter, se:
- GitHub Issues: [Repo URL]
- Husdata forum: https://online.husdata.se/
