
# PV Heating Rod Automation Blueprint for Home Assistant

Controls up to three heating rods based on PV feed-in surplus and battery state of charge.

---

## About This Blueprint

This automation switches heating rods according to a **stage-based control logic**, where each stage activates a specific combination of heating rods to match the available PV surplus as closely as possible in 1 kW steps.

**Surplus source**: The blueprint uses a single direct feed-in sensor (e.g., EMMA "Feed in power") rather than calculating PV minus consumption. This ensures the battery always has priority — heating rods only consume power that is actually going to the grid.

---

## Stage Table

| Stage | Rod 1 (1 kW) | Rod 2 (2 kW) | Rod 3 (3 kW) | Total |
|-------|-------------|-------------|-------------|-------|
| 0     | OFF | OFF | OFF | 0 kW |
| 1     | ON  | OFF | OFF | 1 kW |
| 2     | OFF | ON  | OFF | 2 kW |
| 3     | OFF | OFF | ON  | 3 kW |
| 4     | ON  | OFF | ON  | 4 kW |
| 5     | OFF | ON  | ON  | 5 kW |
| 6     | ON  | ON  | ON  | 6 kW |

---

## Hysteresis

To prevent rapid switching when the surplus oscillates around a threshold, the blueprint applies a configurable hysteresis:

- **Switching UP**: surplus must reach or exceed the stage threshold.
- **Switching DOWN**: surplus must drop below **(threshold − hysteresis)** before the stage decreases.

**Example** with default values (Stage 1 threshold: 1000 W, hysteresis: 200 W):

| Event | Surplus | Action |
|-------|---------|--------|
| Surplus rises | 1050 W | → Stage 1 ON (≥ 1000 W) |
| Small drop | 950 W | → stays Stage 1 (≥ 800 W, within hysteresis) |
| Surplus falls | 780 W | → Stage 0 OFF (< 800 W = 1000 − 200) |

---

## Sensor Requirements

The blueprint is **system-agnostic** — it works with any PV inverter or energy management system. All hardware-specific values are configured through the inputs.

### Surplus Sensor Convention

The surplus sensor must report power in **watts as a positive number** when energy is flowing to the grid.

| Sensor value | Meaning |
|-------------|---------|
| `2500` | 2500 W going to the grid → heating rods can run |
| `0` | No surplus → Stage 0, all rods OFF |
| negative | Not supported directly (see below) |

Some inverters and smart meters report a combined grid power sensor where **positive = drawing from grid** and **negative = feeding to grid**. In this case, create a Template Sensor in Home Assistant first:

```yaml
# configuration.yaml or template: section
template:
  - sensor:
      - name: "PV Feed-in Power"
        unit_of_measurement: W
        state: "{{ [states('sensor.your_grid_power') | float(0) * -1, 0] | max }}"
```

This inverts the sign and clamps negative values to 0. Use `sensor.pv_feed_in_power` as the blueprint input.

### Battery SOC Sensor Convention

Any sensor reporting battery state of charge as a percentage (0–100) is compatible.

---

## Sensor Examples by Manufacturer

| System | Surplus Sensor | Battery SOC Sensor |
|--------|---------------|-------------------|
| Huawei EMMA | `sensor.emma_feed_in_power` | `sensor.emma_state_of_capacity` |
| SMA Home Manager | `sensor.sma_grid_power` (may need template, see above) | `sensor.sma_battery_soc` |
| SolarEdge | `sensor.solaredge_export_power` | `sensor.solaredge_battery_level` |
| Fronius | `sensor.fronius_power_flow_p_grid` (may need template) | `sensor.fronius_battery_state_of_charge` |
| Victron (Venus OS) | `sensor.grid_feed_in_power` | `sensor.battery_soc` |

Exact entity IDs depend on your integration version and device naming in Home Assistant.

---

## Setup Instructions

1. Copy the `pv_heating_rod` folder into your Home Assistant configuration:
   ```
   /config/blueprints/automation/pv_heating_rod/
   ```

2. In Home Assistant: **Settings → Automations & Scenes → Blueprints → Import Blueprint**

3. Configure the automation:
   - Select your surplus sensor (positive W = feed-in, see above)
   - Select your battery SOC sensor
   - Configure minimum battery SOC (default: 60%)
   - Set the time window for operation (start/end time)
   - Adjust stage thresholds and hysteresis to match your system
   - Assign the switches for each heating rod

---

## Upgrading from v1.3.4

The inputs `pv_generation_sensor` and `internal_consumption_sensor` have been replaced by a single `surplus_sensor`. When upgrading, create a new automation instance and configure the new input with your feed-in power sensor (e.g., EMMA "Feed in power").

---

## Supported Devices

- Any PV inverter or energy management system with a real-time feed-in power sensor
- Huawei SUN2000 / EMMA, SMA, SolarEdge, Fronius, Victron, and more
- Smart switches for heating rods: Shelly, Zigbee, Z-Wave, etc.

---

## License

MIT License

---

## Contribution

Feel free to submit improvements via pull request.
