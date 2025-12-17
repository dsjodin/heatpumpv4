# 🚀 Quick Start - Byt från Thermia till IVT

## Steg 1: Uppdatera config.yaml

Öppna `/mnt/project/config.yaml` och ändra:

```yaml
# FRÅN (Thermia):
system:
  pump_type: "thermia_diplomat"
  pump_model: "Thermia Diplomat Optimum G3"

# TILL (IVT):
system:
  pump_type: "ivt_greenline"
  pump_model: "IVT Greenline HT Plus"
```

## Steg 2: Restarta Containers

```bash
docker-compose restart
```

## Steg 3: Verifiera

Öppna `http://localhost:8050` och kontrollera:

### IVT-Specifika Features Ska Visas:

✅ **Header:** "IVT Värmepump Monitor"

✅ **Efter KPI-kort:** "IVT Detaljerad Drifttidsanalys"
- Kompressor: Uppvärmning / Varmvatten
- Tillsatsvärme: Uppvärmning / Varmvatten

✅ **Efter Secondary Temps:** "IVT Interna Sensorer"
- VP Retur
- VP Fram

✅ **Status Badges:** 
- "3kW PÅ" (istället för "Tillsats 45%")
- "6kW PÅ" (när aktiv)

✅ **Saknas (normalt för IVT):**
- Power consumption card (IVT saknar power-register)

## Steg 4: Testa MQTT

Verifiera att IVT-specifika register kommer in:

```bash
# Kolla collector logs
docker-compose logs collector | grep -E "(0003|0004|1A02|1A03|6C55)"

# Du ska se:
# - 0003: heat_carrier_return
# - 0004: heat_carrier_forward
# - 1A02: add_heat_step_1
# - 1A03: add_heat_step_2
# - 6C55: compressor_runtime_heating
# - 6C56: compressor_runtime_hotwater
```

## Troubleshooting

### Problem: Ser fortfarande "Thermia Värmepump Monitor"

**Lösning:**
```bash
# Hårdare restart
docker-compose down
docker-compose up -d

# Rensa browser cache och ladda om
```

### Problem: IVT-komponenter visas inte

**Lösning:**
```bash
# Kontrollera config
cat /mnt/project/config.yaml | grep pump_type

# Ska visa:
# pump_type: "ivt_greenline"

# Om fel, ändra och restarta
docker-compose restart
```

### Problem: "heat_carrier_return" data kommer inte in

**Lösning:**
1. Kontrollera att H66 skickar register 0003/0004
2. Vissa IVT-modeller kanske inte har dessa sensorer
3. Kolla H66 web interface för tillgängliga register

## Byt Tillbaka till Thermia

```yaml
system:
  pump_type: "thermia_diplomat"
  pump_model: "Thermia Diplomat Optimum G3"
```

```bash
docker-compose restart
```

Dashboard återgår till Thermia-läge med alla power/energy features!

## Nästa Steg

- Läs [README_MULTIBRAND.md](README_MULTIBRAND.md) för fullständig dokumentation
- Läs [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) för tekniska detaljer
- Anpassa `pump_model` för att matcha din exakta modell

---

**🎉 Lycka till med din IVT Greenline övervakning!**
