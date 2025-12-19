# Heat Pump Data Collector

## Overview

The collector polls the H66/H60 Gateway HTTP API at regular intervals
and stores all sensor data in InfluxDB with synchronized timestamps.

## Features

- **Perfect synchronization**: All sensors get identical timestamps (single API call)
- **No chart gaps**: All data points align perfectly
- **Multi-brand support**: Works with Thermia, IVT, NIBE via provider architecture
- **Simple polling**: Configurable interval (default: 30 seconds)

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `H66_IP` | (required) | IP address of H66 gateway |
| `COLLECTION_INTERVAL` | 30 | Polling interval in seconds |
| `INFLUXDB_URL` | http://influxdb:8086 | InfluxDB URL |
| `INFLUXDB_TOKEN` | (required) | InfluxDB authentication token |
| `INFLUXDB_ORG` | thermia | InfluxDB organization |
| `INFLUXDB_BUCKET` | heatpump | InfluxDB bucket |
| `HEATPUMP_BRAND` | thermia | Brand: thermia, ivt, or nibe |

### docker-compose.yml Example

```yaml
collector:
  build: ./collector
  environment:
    - H66_IP=192.168.1.100
    - COLLECTION_INTERVAL=30
    - INFLUXDB_URL=http://influxdb:8086
    - INFLUXDB_TOKEN=${INFLUXDB_TOKEN}
    - INFLUXDB_ORG=thermia
    - INFLUXDB_BUCKET=heatpump
    - HEATPUMP_BRAND=thermia
  depends_on:
    - influxdb
```

### config.yaml Alternative

Instead of `HEATPUMP_BRAND` env var, you can set brand in `/app/config.yaml`:

```yaml
brand: thermia  # or ivt, nibe
```

## H66 Gateway Setup

1. Enable API on H66:
   - Log into H66 web interface
   - Set `API_ENABLED = 1` (read-only) or `2` (read/write)
   - Restart H66 gateway

2. Verify API works:
   ```bash
   curl http://<H66-IP>/api/alldata
   ```

## Data Flow

```
H66 Gateway
     │
     │  GET /api/alldata (every 30s)
     ▼
┌─────────────┐
│  Collector  │  → Converts raw values (÷10 for temps)
└─────────────┘  → Uses brand-specific register definitions
     │
     │  Write points
     ▼
┌─────────────┐
│  InfluxDB   │  → Stores: measurement=heatpump
└─────────────┘  → Tags: register_id, name, type, unit
                 → Field: value (converted)
```

## Troubleshooting

### "Unknown register: XXXX"

The register is not defined in your brand's register file.
Check `providers/<brand>/registers.py`.

### "Failed to fetch data from API"

- Verify H66 IP is correct
- Check H66 is reachable: `ping <H66-IP>`
- Verify API is enabled on H66

### No data in InfluxDB

- Check collector logs: `docker-compose logs collector`
- Verify InfluxDB token is correct
- Verify bucket exists
