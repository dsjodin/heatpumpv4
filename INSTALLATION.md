# Multi-Brand Implementation - Installation

Detta arkiv innehåller alla filer för multi-brand support (Thermia + IVT).

## 📦 Innehåll

### ✨ NYA Filer (ska kopieras till ditt projekt)

**Backend:**
```
collector/register_manager.py                    → /mnt/project/collector/
collector/pump_profiles/thermia_diplomat.yaml   → /mnt/project/collector/pump_profiles/
collector/pump_profiles/ivt_greenline.yaml      → /mnt/project/collector/pump_profiles/
```

**Frontend:**
```
pump_config.py                                  → /mnt/project/
```

### ✅ UPPDATERADE Filer (ersätt befintliga)

```
config.yaml                 → /mnt/project/config.yaml
collector.py                → /mnt/project/collector.py
data_query.py               → /mnt/project/data_query.py
app.py                      → /mnt/project/app.py
layout.py                   → /mnt/project/layout.py
layout_components.py        → /mnt/project/layout_components.py
callbacks_kpi.py            → /mnt/project/callbacks_kpi.py
```

### 📚 Dokumentation (valfritt)

```
README_MULTIBRAND.md
QUICKSTART_IVT.md
IMPLEMENTATION_SUMMARY.md
```

## 🚀 Snabb Installation

### Steg 1: Backup
```bash
# Säkerhetskopiera ditt nuvarande projekt
cd /path/to/your/project
tar -czf backup-$(date +%Y%m%d).tar.gz .
```

### Steg 2: Kopiera Nya Filer
```bash
# Skapa pump_profiles directory
mkdir -p collector/pump_profiles

# Kopiera nya backend-filer
cp collector/register_manager.py /path/to/your/project/collector/
cp collector/pump_profiles/*.yaml /path/to/your/project/collector/pump_profiles/

# Kopiera ny frontend-fil
cp pump_config.py /path/to/your/project/
```

### Steg 3: Ersätt Uppdaterade Filer
```bash
# Ersätt uppdaterade filer
cp config.yaml /path/to/your/project/
cp collector.py /path/to/your/project/
cp data_query.py /path/to/your/project/
cp app.py /path/to/your/project/
cp layout.py /path/to/your/project/
cp layout_components.py /path/to/your/project/
cp callbacks_kpi.py /path/to/your/project/
```

### Steg 4: Verifiera config.yaml
```bash
# Kontrollera att system-sektionen finns
grep -A 3 "^system:" /path/to/your/project/config.yaml

# Du ska se:
# system:
#   pump_type: "thermia_diplomat"
#   pump_model: "Thermia Diplomat Optimum G3"
```

### Steg 5: Restarta
```bash
cd /path/to/your/project
docker-compose restart
```

### Steg 6: Testa
```bash
# Öppna dashboard
http://localhost:8050

# För Thermia (standard):
# - Ska fungera exakt som innan
# - Titel: "Thermia Värmepump Monitor"

# För IVT (ändra config.yaml till pump_type: "ivt_greenline"):
# - Titel: "IVT Värmepump Monitor"
# - IVT-specifika features visas
```

## 📋 Alternativ: Docker Compose

Om du använder Docker, kopiera filerna INNAN du startar:

```bash
# 1. Stoppa containers
docker-compose down

# 2. Kopiera alla filer (se ovan)

# 3. Starta igen
docker-compose up -d --build
```

## 🔍 Verifiera Installation

```bash
# Kolla att nya filer finns
ls -lh collector/register_manager.py
ls -lh collector/pump_profiles/*.yaml
ls -lh pump_config.py

# Kolla att config.yaml har system-sektion
grep "pump_type" config.yaml

# Kolla logs
docker-compose logs collector | grep "Loaded pump profile"
docker-compose logs dashboard | grep "Starting Heat Pump"
```

## ⚙️ Konfiguration

### Standard (Thermia)
Ingen ändring behövs! Systemet är förkonfigurerat för Thermia.

### Byt till IVT
1. Öppna `config.yaml`
2. Ändra:
   ```yaml
   system:
     pump_type: "ivt_greenline"
     pump_model: "IVT Greenline HT Plus"
   ```
3. Restarta: `docker-compose restart`

## 🆘 Troubleshooting

### Problem: "ModuleNotFoundError: No module named 'register_manager'"
**Lösning:** 
```bash
# Kontrollera att filen finns
ls -lh collector/register_manager.py
# Om saknas, kopiera från arkivet
```

### Problem: "ModuleNotFoundError: No module named 'pump_config'"
**Lösning:**
```bash
# Kontrollera att filen finns i root
ls -lh pump_config.py
# Om saknas, kopiera från arkivet
```

### Problem: Dashboard visar fel pump-typ
**Lösning:**
```bash
# Kontrollera config
cat config.yaml | grep -A 2 "system:"
# Restarta containers
docker-compose restart
```

## 📖 Dokumentation

- **README_MULTIBRAND.md** - Fullständig användarguide
- **QUICKSTART_IVT.md** - Snabbstart för IVT
- **IMPLEMENTATION_SUMMARY.md** - Tekniska detaljer

## ✅ Checklista

- [ ] Backup av nuvarande projekt
- [ ] Kopierat nya filer (register_manager.py, pump_profiles/, pump_config.py)
- [ ] Ersatt uppdaterade filer (config.yaml, collector.py, etc.)
- [ ] Verifierat att system-sektion finns i config.yaml
- [ ] Restartat Docker containers
- [ ] Testat dashboard (http://localhost:8050)
- [ ] Verifierat rätt pump-typ i header

## 🎉 Klart!

När allt fungerar:
- Thermia fortsätter fungera som innan
- IVT får nya features när du byter pump_type
- Lätt att lägga till fler märken i framtiden

**Support:** Se dokumentationen för mer hjälp!
