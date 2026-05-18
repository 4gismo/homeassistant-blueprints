
# PV Heating Rod Automation Blueprint for Home Assistant

Version 2.3 — Controls up to three heating rods based on PV feed-in surplus and battery state of charge.

---

## About This Blueprint

This automation switches heating rods according to a **stage-based control logic**, where each stage activates a specific combination of heating rods to match the available PV surplus as closely as possible in 1 kW steps.

**Surplus source**: The blueprint uses a direct grid feed-in sensor rather than calculating PV minus consumption. This ensures the battery always has priority — heating rods only consume power that is actually going to the grid.

---

## Features

- **Stage-based control**: 7 stages (0–6 kW) map to combinations of three rods (1/2/3 kW)
- **Asymmetric switching**: stages up immediately on surplus, down only on the 5-min periodic check — battery absorbs cloud shadows without unnecessary rod switching
- **Hysteresis**: configurable deadband prevents oscillation around thresholds
- **Failsafe shutdown**: explicit time trigger at `end_time` + battery SOC guard
- **Correct switching sequence**: always turns OFF first, then ON — prevents momentary power overshoot
- **Lock time**: ignores new triggers for a configurable duration after each stage change
- **Grid-import kill-switch**: emergency shutdown if grid import exceeds a threshold
- **Buffer tank detection**: detects when the thermostat cuts out (no power draw) and retries after 15 minutes
- **Logbook integration**: stage changes and buffer tank events written to HA History

---

## Execution Flow

Each time the automation runs, it works through four priority levels in order:

```
1. EMERGENCY SHUTDOWN (highest priority)
   Grid import > threshold OR surplus sensor unavailable
   → All rods OFF immediately, persistent notification, stop.

2. FAILSAFE SHUTDOWN
   Outside time window OR battery SOC < minimum
   → All rods OFF, persistent notification, stop.

3. BUFFER TANK (only when triggered by a power sensor)
   All active rods draw no current for 2 min → buffer tank full
   → All rods OFF, wait 15 min, retry, stop.

4. NORMAL STAGE CONTROL
   Asymmetric switching:
   → Stage UP:   immediately on any trigger
   → Stage DOWN: only on 5-min periodic check AND battery SOC < 90 %
                 (below 90 %: stage-down is immediate so battery keeps charging)
```

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

## Asymmetric Switching (Battery Buffering)

Stage changes are intentionally asymmetric:

- **Switching UP**: as soon as the surplus sensor reaches a threshold — immediate response.
- **Switching DOWN**: only on the 5-minute periodic check, not on every sensor update.

**Why**: When a cloud passes, the surplus sensor dips briefly while the battery automatically
compensates (e.g. drops from 100 % to 96 % SOC — no grid power is drawn). Switching rods
off and immediately back on wastes switching cycles and misses heating potential.

With this behaviour, rods keep running through short cloud shadows. Only a sustained
deficit (persisting until the next 5-minute check) triggers a stage-down.

| Event | Battery SOC | Action |
|-------|-------------|--------|
| Surplus rises above threshold | any | Stage UP immediately |
| Brief cloud dip (< 5 min) | ≥ 90% | Skipped — battery buffers |
| Brief cloud dip (< 5 min) | < 90% | Stage DOWN immediately — battery keeps charging |
| Sustained low surplus (> 5 min) | any | Stage DOWN on periodic check |
| Grid import detected | any | All rods OFF immediately |
| Outside time window / low SOC | any | All rods OFF immediately |

**Why 90%**: below 90% SOC the battery is still charging. Letting it buffer heating rod
load would conflict with the goal of ending the day with a full battery. Above 90% the
battery is essentially full — a brief dip costs little and recharges quickly.

The emergency shutdown (grid import) and failsafe (end_time, low battery SOC) always
react immediately — the delay applies only to normal stage-down decisions.

---

## Configuration Reference

### Sensors

| Input | Description | Required |
|-------|-------------|----------|
| **PV Surplus Sensor** | Sensor at the grid connection point. For Huawei EMMA: "Feed in power". | Yes |
| **Surplus Sensor Sign Convention** | Toggle ON if your sensor reports negative values when feeding to the grid (e.g. Huawei EMMA). Leave OFF for sensors where positive = feed-in. | No (default: OFF) |
| **Battery SOC Sensor** | Battery state of charge, 0–100 %. For Huawei EMMA: "State of capacity". | Yes |
| **Grid Power Sensor** | Grid power for emergency shutdown. For Huawei EMMA: "Active power". Convention: positive = import, negative = export. | Recommended |
| **Maximum Tolerated Grid Import** | Emergency shutdown threshold in watts. Default 150 W. | No |

### Heating Rods

| Input | Description |
|-------|-------------|
| **Switch for Rod 1 (1 kW)** | Switch entity controlling the 1 kW heating rod. |
| **Switch for Rod 2 (2 kW)** | Switch entity controlling the 2 kW heating rod. |
| **Switch for Rod 3 (3 kW)** | Switch entity controlling the 3 kW heating rod. |

### Operation Settings

| Input | Default | Description |
|-------|---------|-------------|
| **Start Time** | 08:00 | Rods only operate after this time. |
| **End Time** | 18:00 | All rods shut down at this time (hard trigger). |
| **Minimum Battery SOC** | 60 % | Rods disabled when battery drops below this. |
| **Hysteresis** | 200 W | Deadband below threshold before switching down. |
| **Lock Time After Switching** | 2 min | New triggers ignored after a stage change (max 5 min). |

### Stage Thresholds

Six configurable watt thresholds — one per stage. Defaults match a system with 1/2/3 kW rods:

| Input | Default |
|-------|---------|
| Stage 1 (Rod 1 only, 1 kW) | 1000 W |
| Stage 2 (Rod 2 only, 2 kW) | 2000 W |
| Stage 3 (Rod 3 only, 3 kW) | 3000 W |
| Stage 4 (Rod 1 + Rod 3, 4 kW) | 4000 W |
| Stage 5 (Rod 2 + Rod 3, 5 kW) | 5000 W |
| Stage 6 (all rods, 6 kW) | 6000 W |

Thresholds must be configured in ascending order. Inverted thresholds cause undefined behavior.

### Power Monitoring (Optional)

Enables buffer tank detection. Requires a smart plug with power monitoring (e.g. Nous D3T) on each rod.

| Input | Default | Description |
|-------|---------|-------------|
| **Power Sensor for Rod 1** | — | Power consumption sensor for rod 1. Leave empty if not available. |
| **Power Sensor for Rod 2** | — | Power consumption sensor for rod 2. |
| **Power Sensor for Rod 3** | — | Power consumption sensor for rod 3. |
| **Thermostat Cutoff Threshold** | 50 W | Rod is considered thermostated off when power drops below this value. |

### Logging

| Input | Default | Description |
|-------|---------|-------------|
| **Enable Logging** | ON | Writes stage changes and buffer tank events to the HA Logbook (History). Failsafe and emergency shutdowns always create a persistent notification regardless of this setting. |

---

## Sensor Sign Convention

Different inverter brands report grid power with different sign conventions:

| Sensor value | Meaning — Positive convention | Meaning — Negative convention |
|-------------|-------------------------------|-------------------------------|
| `2500` | 2500 W feeding to grid → rods can run | 2500 W imported from grid → rods must be OFF |
| `-2500` | 2500 W imported from grid | 2500 W feeding to grid → rods can run |

**Huawei EMMA** ("Feed in power") uses the **negative convention** — enable the **Surplus Sensor Sign Convention** toggle in the blueprint.

**SMA, SolarEdge, Fronius export sensors** typically use the **positive convention** — leave the toggle OFF.

If you are unsure: check the sensor value in **Developer Tools → States** while your system is clearly feeding to the grid. If the value is negative → enable the toggle.

---

## Grid Power Sensor Convention

The grid sensor (for emergency shutdown) always uses: **positive = importing from grid**.

For Huawei EMMA "Active power": positive value means drawing from grid, negative means exporting. This matches the expected convention — no inversion needed.

---

## Buffer Tank Detection

When power sensors are configured for the heating rods, the blueprint detects when the buffer tank thermostat cuts the rods out:

1. Rod switch is ON, but measured power stays below the cutoff threshold for 2 minutes → buffer tank is full
2. All rods are turned off and a Logbook entry is written
3. After 15 minutes, the blueprint re-evaluates the surplus and turns rods back on if conditions are met
4. After 2 more minutes, it checks whether the rods are actually drawing power
5. If they are → Logbook: "retry successful, buffer cooling"
6. If not → rods turned off again, cycle repeats automatically when power stays low for another 2 minutes

---

## Safety

### Failsafe Shutdown

Rods are shut down (with a persistent notification) when:
- Current time is outside the configured time window (`end_time` fires an explicit trigger)
- Battery SOC drops below the configured minimum

### Emergency Grid-Import Shutdown

When a grid sensor is configured, an emergency shutdown triggers immediately if grid import exceeds the threshold — regardless of lock delays or retry cycles. A persistent notification is always created.

**Note**: The emergency shutdown cannot interrupt an active lock delay or buffer tank retry cycle because `mode: single` prevents re-entry during delays. Keep the lock time low (default 2 min) to minimize this window. For a hard real-time grid guard, add a separate automation outside this blueprint.

### Invalid Sensor Safety

If the surplus sensor reports `unavailable` or `unknown` and any rod is ON, all rods are immediately shut down.

---

## Sensor Examples by Manufacturer

| System | Surplus Sensor | Sign Convention Toggle | Battery SOC Sensor | Grid Sensor |
|--------|---------------|----------------------|-------------------|-------------|
| Huawei EMMA | `sensor.emma_feed_in_power` | **ON** (negative = feed-in) | `sensor.emma_state_of_capacity` | `sensor.emma_active_power` |
| SMA Home Manager | `sensor.sma_grid_power` | OFF (check sign) | `sensor.sma_battery_soc` | — |
| SolarEdge | `sensor.solaredge_export_power` | OFF | `sensor.solaredge_battery_level` | — |
| Fronius | `sensor.fronius_power_flow_p_grid` | OFF (check sign) | `sensor.fronius_battery_state_of_charge` | — |
| Victron (Venus OS) | `sensor.grid_feed_in_power` | OFF | `sensor.battery_soc` | — |

Exact entity IDs depend on your integration version and device naming in Home Assistant.

---

## Setup Instructions

1. Copy the `pv_heating_rod` folder into your Home Assistant configuration:
   ```
   /config/blueprints/automation/pv_heating_rod/
   ```

2. In Home Assistant: **Settings → Automations & Scenes → Blueprints → Reload Blueprints**

3. Create a new automation from the blueprint and configure:

   **Sensors section**
   - Select your surplus sensor (e.g. EMMA "Feed in power")
   - Enable the sign convention toggle if your sensor reports negative values for feed-in (Huawei EMMA)
   - Select your battery SOC sensor
   - Select your grid power sensor (strongly recommended)

   **Heating Rods section**
   - Assign the switch for each heating rod

   **Operation Settings section**
   - Set your start/end times
   - Set the minimum battery SOC (default 60%)
   - Adjust hysteresis and lock time if needed

   **Stage Thresholds section** (collapsed by default)
   - Defaults match a 1/2/3 kW rod system — adjust only if your rods have different power ratings

   **Power Monitoring section** (collapsed by default, optional)
   - Assign power sensors if available (e.g. Nous D3T)
   - Leave empty to disable buffer tank detection

   **Logging section** (collapsed by default)
   - Enable to write stage changes to the HA Logbook

---

## Upgrading from v1.3.4

The inputs `pv_generation_sensor` and `internal_consumption_sensor` have been replaced by a single `surplus_sensor`. When upgrading, create a new automation instance and configure it from scratch.

Major changes in v2.0:
- Single surplus sensor input instead of PV minus consumption
- v2.1: Configurable sign convention — no template sensor needed for Huawei EMMA
- Hysteresis to prevent oscillation
- Correct switching sequence (OFF before ON)
- Lock time via `mode: single` (was broken in v1.3.4)
- Failsafe shutdown now actually fires at `end_time`
- Buffer tank detection with automatic retry cycle
- Grid-import emergency kill-switch
- Logbook integration

---

## Supported Devices

- Any PV inverter or energy management system with a real-time feed-in power sensor
- Huawei SUN2000 / EMMA, SMA, SolarEdge, Fronius, Victron, and more
- Smart switches for heating rods: Shelly, Zigbee, Z-Wave, etc.
- Optional power monitoring: Nous D3T, Shelly Plug S, or any smart plug with power metering

---

## Known Limitations

- Overnight time windows (e.g. 23:00 to 01:00) are not supported
- Stage thresholds must be in ascending order — not validated at runtime
- The grid-import kill-switch cannot interrupt an active lock delay (see Safety section)
- Stage-down decisions are delayed up to 5 minutes (periodic check) — intentional, see Asymmetric Switching

---

## License

MIT License

---

## Contribution

Feel free to submit improvements via pull request.
