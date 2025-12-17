# API Collector - Perfect Timestamp Synchronization

## Problem with MQTT Collector

The MQTT collector receives sensor updates one at a time, each with its own timestamp:

```
10:00:00.123 → outdoor_temp
10:00:00.456 → indoor_temp
10:00:00.789 → radiator_forward
10:00:01.234 → compressor_status
```

**Result:** Different timestamps → gaps in charts when pivoting data

## Solution: API Collector

The API collector fetches ALL sensors in a single request, giving them all the SAME timestamp:

```
10:00:00.000 → {outdoor_temp, indoor_temp, radiator_forward, compressor_status, ...}
```

**Result:** Perfect synchronization → no gaps in charts!

## Quick Fix Applied (MQTT)

A temporary fix has been added to the MQTT collector:
- Timestamps are rounded to 30-second intervals
- Sensors arriving within the same 30s window get the same timestamp
- This reduces gaps but doesn't eliminate them completely

**Location:** `collector/collector.py` line 273

## Switching to API Collector

### Prerequisites

1. **Enable API on H66 Gateway:**
   - Log into H66 web interface
   - Set `API_ENABLED = 1` (read-only) or `2` (read/write)
   - Restart H66 gateway
   - Verify: `curl http://<H66-IP>/api/alldata`

2. **Get H66 IP address:**
   ```bash
   # Find it in your router or H66 web interface
   ping h66.local  # or check DHCP leases
   ```

### Installation

1. **Install required package:**
   ```bash
   pip install requests
   ```

2. **Update docker-compose.yml:**

   **Option A: Replace MQTT collector**
   ```yaml
   collector:
     build: ./collector
     command: python3 /app/api_collector.py  # Changed from collector.py
     environment:
       - H66_IP=192.168.1.100              # ADD THIS
       - COLLECTION_INTERVAL=30             # Polling interval (seconds)
       - HEATPUMP_BRAND=thermia
       - INFLUXDB_URL=http://influxdb:8086
       - INFLUXDB_TOKEN=${INFLUXDB_TOKEN}
       - INFLUXDB_ORG=thermia
       - INFLUXDB_BUCKET=heatpump
     # Remove MQTT settings - not needed anymore!
   ```

   **Option B: Run both collectors** (transition period)
   ```yaml
   # Keep existing MQTT collector as collector-mqtt
   collector-mqtt:
     build: ./collector
     command: python3 /app/collector.py
     # ... existing MQTT config ...

   # Add new API collector
   collector-api:
     build: ./collector
     command: python3 /app/api_collector.py
     environment:
       - H66_IP=192.168.1.100
       - COLLECTION_INTERVAL=30
       - HEATPUMP_BRAND=thermia
       - INFLUXDB_URL=http://influxdb:8086
       - INFLUXDB_TOKEN=${INFLUXDB_TOKEN}
       - INFLUXDB_ORG=thermia
       - INFLUXDB_BUCKET=heatpump
   ```

3. **Rebuild and restart:**
   ```bash
   docker-compose down
   docker-compose build collector
   docker-compose up -d
   ```

### Configuration

**Environment Variables:**

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `H66_IP` | Yes | - | IP address of H66 gateway |
| `COLLECTION_INTERVAL` | No | 30 | Polling interval in seconds |
| `HEATPUMP_BRAND` | No | thermia | Brand: thermia, ivt, nibe |
| `INFLUXDB_URL` | No | http://influxdb:8086 | InfluxDB server URL |
| `INFLUXDB_TOKEN` | Yes | - | InfluxDB authentication token |
| `INFLUXDB_ORG` | No | thermia | InfluxDB organization |
| `INFLUXDB_BUCKET` | No | heatpump | InfluxDB bucket name |

### Testing

1. **Verify API access:**
   ```bash
   curl http://192.168.1.100/api/alldata
   # Should return: {"0001":275,"0002":285, ...}
   ```

2. **Test collector manually:**
   ```bash
   export H66_IP=192.168.1.100
   export INFLUXDB_TOKEN=your-token-here
   python3 collector/api_collector.py
   ```

3. **Check logs:**
   ```bash
   docker-compose logs -f collector
   # Should see: "Stored 50 metrics with timestamp ..."
   ```

4. **Verify in InfluxDB:**
   ```bash
   # All sensors from same poll should have identical timestamps
   influx query 'from(bucket: "heatpump") |> range(start: -1m) |> limit(n: 10)'
   ```

## Performance Comparison

### MQTT Collector
- ✓ Real-time updates (event-driven)
- ✗ Timestamps vary by milliseconds/seconds
- ✗ Chart gaps from timestamp misalignment
- ✗ More complex code (async message handling)
- ✗ Rounded timestamps (30s) as workaround

### API Collector
- ✓ **Perfect timestamp synchronization**
- ✓ **No chart gaps**
- ✓ Simpler code (synchronous polling)
- ✓ One HTTP request gets all data
- ✗ Polling-based (30s updates)
- ✗ Requires H66 API enabled

## Recommended Setup

**Production:** Use API collector for perfect data synchronization

```yaml
collector:
  command: python3 /app/api_collector.py
  environment:
    - H66_IP=192.168.1.100
    - COLLECTION_INTERVAL=30  # 30s is good for heat pumps
```

**Development/Testing:** Can run both simultaneously to compare

## Troubleshooting

### "H66_IP environment variable must be set"
- Make sure H66_IP is set in docker-compose.yml
- Verify with: `docker-compose config | grep H66_IP`

### "Failed to fetch data from API"
- Check H66 is reachable: `ping 192.168.1.100`
- Verify API enabled: `curl http://192.168.1.100/api/alldata`
- Check H66 web interface → API settings

### "No data received from API"
- API might be disabled - check H66 settings
- API returns empty {} - heat pump might be off
- Check H66 logs for errors

### "Unknown register: XXXX"
- API returns registers not in provider definition
- Usually safe to ignore
- Add to provider if you need that sensor

## Migration Path

1. **Week 1:** Deploy API collector alongside MQTT (both running)
2. **Week 2:** Verify charts have no gaps with API data
3. **Week 3:** Disable MQTT collector if API data looks good
4. **Week 4:** Remove MQTT collector from docker-compose.yml

## Reverting to MQTT

If you need to go back:

```yaml
collector:
  command: python3 /app/collector.py  # Back to MQTT
  environment:
    # Remove H66_IP
    # Add back MQTT settings
    - MQTT_BROKER=mosquitto
    - MQTT_USERNAME=thermia
    # etc...
```

## Support

- API Documentation: https://husdata.se/docs/h60-manual/api-integration/
- Issues: File in project GitHub
- Provider configs: `/providers/<brand>/`
