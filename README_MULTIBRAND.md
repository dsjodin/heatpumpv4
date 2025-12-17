# Heat Pump Monitor - Multi-Brand Support

Avancerad övervakningslösning för värmepumpar med stöd för flera märken.

## Stödda Värmepumpar

### ✅ Thermia Diplomat
- Modeller: Diplomat Optimum G3, Atlas, Atria, Robust
- Controller: H66 Gateway
- Features:
  - ✅ Effektmätning (CFAA register)
  - ✅ Energimätning (5FAB register)
  - ✅ COP-beräkning
  - ✅ Kostnadsanalys
  - ✅ Sankey energiflödesdiagram med verklig power

### ✅ IVT Greenline
- Modeller: IVT Greenline med Rego 600/637 controller
- Controller: H66 Gateway
- Features:
  - ✅ Heat Carrier sensorer (interna VP-temperaturer)
  - ✅ Separata värmesteg (3kW + 6kW individual status)
  - ✅ Detaljerad runtime-analys (Uppvärmning vs Varmvatten)
  - ✅ COP-beräkning (temp-baserad)
  - ✅ Sankey energiflödesdiagram (runtime-estimerad)

## Snabbstart

### 1. Välj Din Värmepump

Öppna `config.yaml` och ställ in din pump-typ:

```yaml
system:
  # Välj: "thermia_diplomat" eller "ivt_greenline"
  pump_type: "thermia_diplomat"
  
  # Visa ditt modellnamn i dashboard
  pump_model: "Thermia Diplomat Optimum G3"

mqtt:
  broker: 10.1.40.140
  port: 1883
  # ... resten av MQTT-konfigurationen
```

### 2. För IVT Greenline

Om du använder IVT, ändra till:

```yaml
system:
  pump_type: "ivt_greenline"
  pump_model: "IVT Greenline HT Plus"

mqtt:
  broker: 10.1.40.140
  # ... din MQTT-konfiguration
  h66_mac: "083a8d015430"  # Ditt H66 MAC-adress
```

### 3. Starta Systemet

```bash
docker-compose up -d
```

Dashboard öppnas på: `http://localhost:8050`

## Funktioner per Märke

### Gemensamma Features (Alla Märken)

✅ Temperaturer: Ute, Inne, Varmvatten, Radiator, Köldbärare  
✅ COP-beräkning (värmefaktor)  
✅ Kompressor & pump-status  
✅ Varmvattencykler  
✅ Alarm-hantering  
✅ Händelselogg  
✅ Live systemschema  
✅ Grafer: Temperatur, Prestanda, Växelventil  

### Thermia-Specifikt

🔋 **Power Consumption Card** - Visar aktuell effektförbrukning i Watt  
💰 **Energy Cost Tracking** - Exakta kostnader baserat på verklig förbrukning  
📊 **Sankey med Verklig Power** - Exakt energiflöde från H66 power-data  
⚡ **Power Graph** - Faktisk effektförbrukning över tid  
📈 **Tillsatsvärme Procent** - Kontinuerlig procentindikering  

### IVT-Specifikt

🌡️ **Heat Carrier Temps** - Interna VP-sensorer (0003/0004)  
🔥 **Separata Värmesteg** - 3kW och 6kW visas individuellt  
⏱️ **Detaljerad Runtime**:
  - Kompressor: Uppvärmning vs Varmvatten (timmar)
  - Tillsats: Uppvärmning vs Varmvatten (timmar)  
📊 **Sankey med Estimat** - Runtime-baserad energiflöde  
💡 **Warm Water 2 Sensor** - Extern tank-sensor (000A)  

## Register-Mappning

Systemet använder pump-specifika register-profiler:

```
collector/pump_profiles/
├── thermia_diplomat.yaml    # Thermia register
└── ivt_greenline.yaml        # IVT register
```

Varje profil innehåller:
- Register-ID till logiska namn
- Enheter och typer
- Beskrivningar
- Alarm-koder

## Dashboard-Beteende

### För Thermia
- Headern visar: **"Thermia Värmepump Monitor"**
- Status badges visar: **"Tillsats 45%"** (kontinuerligt)
- KPI-kort visar: Energikostnad i kr (verklig data)
- Power card visas med live Watt-värden

### För IVT
- Headern visar: **"IVT Värmepump Monitor"**
- Status badges visar: **"3kW PÅ"** och **"6kW PÅ"** (separata)
- KPI-kort + Detaljerad runtime-breakdown
- Power card visas INTE (IVT saknar power-register)
- Heat carrier temp-kort visas under secondary temps

## Teknisk Arkitektur

### Backend (Collector)
```
collector/
├── collector.py              # MQTT → InfluxDB
├── register_manager.py       # Multi-brand register hantering
├── metrics.py                # Data konvertering
└── pump_profiles/
    ├── thermia_diplomat.yaml
    └── ivt_greenline.yaml
```

### Frontend (Dashboard)
```
dashboard/
├── app.py                    # Main app (pump-aware)
├── pump_config.py           # Config helper
├── layout.py                # Main layout
├── layout_components.py     # UI components (pump-aware)
├── callbacks_kpi.py         # KPI callbacks (IVT extensions)
├── callbacks_status.py      # Status callbacks
├── callbacks_graphs.py      # Graph callbacks
└── data_query.py            # InfluxDB queries (pump-aware)
```

## Troubleshooting

### Problem: Dashboard visar inte IVT-specifika features

**Lösning:**
1. Kontrollera `config.yaml`: `pump_type: "ivt_greenline"`
2. Restarta containers: `docker-compose restart`
3. Kontrollera logs: `docker-compose logs dashboard`

### Problem: Register saknas i InfluxDB

**Lösning:**
1. Kontrollera collector logs: `docker-compose logs collector`
2. Verifiera H66 MAC-adress i config.yaml
3. Kontrollera att H66 skickar rätt register-ID:n

### Problem: Alarm-koder visar fel beskrivning

**Lösning:**
- Systemet laddar automatiskt rätt alarm-koder från pump-profilen
- Kontrollera att `pump_type` är korrekt satt

## Lägg Till Fler Märken

Vill du lägga till t.ex. Nibe, Bosch eller NIBE?

1. Skapa ny pump-profil: `collector/pump_profiles/nibe_fighter.yaml`
2. Definiera register enligt Nibe's dokumentation
3. Lägg till pump_type i `pump_config.py`
4. (Optional) Lägg till märkesspecifika UI-komponenter

Systemet är designat för enkel skalbarhet! 🚀

## Support

För frågor eller problem:
1. Kontrollera logs: `docker-compose logs`
2. Verifiera config.yaml
3. Testa MQTT-anslutning: `mosquitto_sub -h <broker> -t "#"`

## Version

- **v2.0** - Multi-brand support (Thermia + IVT)
- v1.0 - Initial release (Thermia only)

---

**Gjort med ❤️ för svenska värmepumpsägare**
