
# PV Heating Rod Automation Blueprint for Home Assistant

Version 3.1 — Controls up to three heating rods based on PV feed-in surplus and battery state of charge.

---

## About This Blueprint

This automation switches heating rods according to a **stage-based control logic**. Each stage activates
a specific combination of heating rods to match the available PV surplus as closely as possible.

Stage thresholds are **calculated automatically** from the configured rod capacities — no manual threshold
tuning required. Equal-capacity rods are handled correctly: three 2 kW rods produce three clean stages
(2 / 4 / 6 kW) instead of six partially overlapping ones.

**Surplus source**: The blueprint uses a direct grid feed-in sensor rather than calculating PV minus
consumption. This ensures the battery always has priority — heating rods only consume power that is
actually going to the grid.

---

## Features

- **Dynamic stage table**: derived from rod capacities (kW each) — not manual thresholds.
  Equal-power combinations are automatically merged; fewest rods wins (see Stage Table below).
- **1–3 rods supported**: Rod 2 and Rod 3 are optional — leave their switch empty to disable.
- **Battery capacity (kWh)**: configurable for informational display in log messages alongside SOC%.
- **Asymmetric switching**: stages up immediately on surplus; stage-down suppressed when SOC ≥ 90%
  and stage > Stage 1 — battery absorbs cloud shadows without unnecessary rod switching.
- **Hysteresis**: configurable deadband prevents oscillation around thresholds.
- **Failsafe shutdown**: explicit time trigger at `end_time` + battery SOC guard.
- **Correct switching sequence**: always turns OFF first, then ON — prevents momentary power overshoot.
- **Lock time**: ignores new triggers for a configurable duration after each stage change.
- **Grid-import kill-switch**: emergency shutdown if grid import exceeds a threshold.
- **Buffer tank detection**: detects when the thermostat cuts out (no power draw) and retries after 15 min (or 60 min when a buffer temperature sensor is configured and above the threshold).
- **Buffer tank temperature sensor** (optional): prevents rapid cycling when the buffer is hot — extends the retry wait to 60 minutes when the sensor reads at or above a configurable threshold.
- **Logbook integration**: stage changes and buffer tank events written to HA History.

---

## Execution Flow

Each time the automation runs, it works through four priority levels in order:

```
1. EMERGENCY SHUTDOWN (highest priority)
   Grid import > threshold OR surplus sensor unavailable
   → All rods OFF immediately, Logbook entry, stop.

2. FAILSAFE SHUTDOWN
   Outside time window OR battery SOC < minimum
   → All rods OFF, Logbook entry (no popup), stop.

3. BUFFER TANK (only when triggered by a power sensor)
   All active rods draw no current for 2 min → buffer tank full
   → All rods OFF, wait 15 min (or 60 min when buffer temp ≥ threshold), retry, stop.

4. NORMAL STAGE CONTROL
   Asymmetric switching:
   → Stage UP:   immediately on any trigger
   → Stage DOWN: immediately when SOC < 90%
                 suppressed (battery buffers) when SOC ≥ 90% and current stage > Stage 1
                 Stage 1 always switches down immediately (drain too slow to self-correct)
```

---

## Stage Table

The stage table is computed automatically from the rod capacities you configure. The blueprint builds
all valid rod combinations, sorts them by power, and removes duplicates (equal power → fewest rods).

**Example — three rods with different capacities (1 kW / 2 kW / 3 kW)**

| Stage | Rod 1 (1 kW) | Rod 2 (2 kW) | Rod 3 (3 kW) | Total |
|-------|-------------|-------------|-------------|-------|
| 0 (off) | OFF | OFF | OFF | 0 kW |
| 1 | ON  | OFF | OFF | 1 kW |
| 2 | OFF | ON  | OFF | 2 kW |
| 3 | OFF | OFF | ON  | 3 kW |
| 4 | ON  | OFF | ON  | 4 kW |
| 5 | OFF | ON  | ON  | 5 kW |
| 6 | ON  | ON  | ON  | 6 kW |

**Example — three equal rods (2 kW / 2 kW / 2 kW)**

Duplicate power levels (all single-rod combos = 2 kW, all dual-rod combos = 4 kW) are
automatically merged. The stage_table collapses to three meaningful levels:

| Stage | Rod 1 | Rod 2 | Rod 3 | Total |
|-------|-------|-------|-------|-------|
| 0 (off) | OFF | OFF | OFF | 0 kW |
| 1 | ON  | OFF | OFF | 2 kW |
| 2 | ON  | ON  | OFF | 4 kW |
| 3 | ON  | ON  | ON  | 6 kW |

> **Wear leveling note**: for equal-capacity rods, the same combination is always selected for a
> given power level (fewest-rods-first, stable sort order). To redistribute wear across rods,
> swap their physical assignments in the blueprint configuration.

---

## Hysteresis

To prevent rapid switching when the surplus oscillates around a threshold, the blueprint applies a
configurable hysteresis:

- **Switching UP**: surplus must reach or exceed the stage threshold.
- **Switching DOWN**: surplus must drop below **(threshold − hysteresis)** before the stage decreases.

**Example** with default values (stage threshold: 2000 W, hysteresis: 700 W):

| Event | Surplus | Action |
|-------|---------|--------|
| Surplus rises | 2050 W | → Stage ON (≥ 2000 W) |
| Cloud dip | 1400 W | → stays ON (≥ 1300 W, within hysteresis) |
| Surplus falls | 1200 W | → Stage OFF (< 1300 W = 2000 − 700) |

---

## Asymmetric Switching (Battery Buffering)

Stage changes are intentionally asymmetric:

- **Switching UP**: as soon as the surplus sensor reaches a threshold — immediate response.
- **Switching DOWN**: suppressed when the battery SOC is ≥ 90% and the current stage is above Stage 1. The battery absorbs the shortfall until SOC drops to 89%.

**Why**: When a cloud passes, the surplus sensor dips while the battery automatically
compensates. Switching rods off and immediately back on wastes switching cycles and misses
heating potential. The battery buffers the difference at no grid cost.

**Why exempt Stage 1**: Stage 1 draws the minimum rod capacity (e.g. 1 kW). At that rate the
battery would drain for 1+ hours before reaching 90% SOC — too long to hold a marginal stage.
Stage 1 therefore switches down immediately when surplus is gone.

| Event | Battery SOC | Current Stage | Action |
|-------|-------------|---------------|--------|
| Surplus rises above threshold | any | any | Stage UP immediately |
| Surplus drops (cloud / evening) | ≥ 90% | Stage 2+ | Held — battery buffers until SOC < 90% |
| Surplus drops (cloud / evening) | ≥ 90% | Stage 1 | Stage DOWN immediately |
| Surplus drops | < 90% | any | Stage DOWN immediately — battery keeps charging |
| Grid import detected | any | any | All rods OFF immediately |
| Outside time window / low SOC | any | any | All rods OFF (logbook entry) |

**Why 90%**: below 90% SOC the battery is still charging. Letting it buffer heating rod
load would conflict with the goal of ending the day with a full battery. Above 90% the
battery is essentially full — discharging a few percent costs little and recharges quickly.

---

## Configuration Reference

### Sensors

| Input | Description | Required |
|-------|-------------|----------|
| **PV Surplus Sensor** | Sensor at the grid connection point. For Huawei EMMA: "Feed in power". | Yes |
| **Surplus Sensor Sign Convention** | Toggle ON if your sensor reports negative values when feeding to the grid (e.g. Huawei EMMA). Leave OFF where positive = feed-in. | No (default: OFF) |
| **Battery SOC Sensor** | Battery state of charge, 0–100%. For Huawei EMMA: "State of capacity". | Yes |
| **Grid Power Sensor** | Grid power for emergency shutdown. Convention: positive = import from grid. | Recommended |
| **Maximum Tolerated Grid Import** | Emergency shutdown threshold in watts. Default 150 W. | No |

### Heating Rods

| Input | Description | Required |
|-------|-------------|----------|
| **Switch — Rod 1** | Switch entity for the first heating rod. | Yes |
| **Rod 1 Capacity (kW)** | Power rating of rod 1. Default 2.0 kW. | Yes |
| **Switch — Rod 2** | Switch entity for the second rod. Leave empty if not present. | No |
| **Rod 2 Capacity (kW)** | Power rating of rod 2. Default 2.0 kW. Only used when Rod 2 switch is set. | No |
| **Switch — Rod 3** | Switch entity for the third rod. Leave empty if not present. | No |
| **Rod 3 Capacity (kW)** | Power rating of rod 3. Default 2.0 kW. Only used when Rod 3 switch is set. | No |

Stage thresholds are derived automatically from these capacities — no separate threshold configuration.

### Operation Settings

| Input | Default | Description |
|-------|---------|-------------|
| **Start Time** | 09:00 | Rods only operate after this time. |
| **End Time** | 18:00 | All rods shut down at this time (hard trigger). |
| **Minimum Battery SOC** | 60% | Rods disabled when battery drops below this. |
| **Battery Capacity (kWh)** | 10 kWh | Total usable battery capacity — shown in log messages alongside SOC%. Does not affect switching logic. |
| **Hysteresis** | 700 W | Deadband below threshold before switching down. Increase to reduce oscillation. |
| **Lock Time After Switching** | 5 min | New triggers ignored after a stage change (max 10 min). |

### Power Monitoring (Optional)

Enables buffer tank detection. Requires a smart plug with power monitoring (e.g. Nous D3T) on each rod.

| Input | Default | Description |
|-------|---------|-------------|
| **Power Sensor for Rod 1** | — | Power consumption sensor for rod 1. Leave empty if not available. |
| **Power Sensor for Rod 2** | — | Power consumption sensor for rod 2. |
| **Power Sensor for Rod 3** | — | Power consumption sensor for rod 3. |
| **Thermostat Cutoff Threshold** | 50 W | Rod is considered thermostated off when power drops below this value. |

### Buffer Tank Temperature (Optional)

Extends the retry wait after a thermostated shutdown when the buffer is hot. **Requires at least one Power Sensor to be configured** — this section has no effect without power monitoring.

| Input | Default | Description |
|-------|---------|-------------|
| **Buffer Tank Temperature Sensor** | — | Lowest temperature sensor on the buffer tank (e.g. "Pufferspeicher unten"). Leave empty to keep the standard 15-minute retry wait. |
| **Buffer Threshold Temperature** | 55 °C | Retry wait is extended to 60 minutes when the sensor reads at or above this value. Set to the temperature below which the buffer has cooled enough to re-attempt heating (typically 5–10 °C below the rod's thermostat cutoff). |

### Logging

| Input | Default | Description |
|-------|---------|-------------|
| **Enable Logging** | ON | Writes stage changes, buffer tank events, and shutdowns to the HA Logbook. |

---

## Sensor Sign Convention

Different inverter brands report grid power with different sign conventions:

| Sensor value | Positive convention | Negative convention |
|-------------|--------------------|--------------------|
| `2500` | 2500 W feeding to grid → rods can run | 2500 W imported from grid → rods must be OFF |
| `-2500` | 2500 W imported from grid | 2500 W feeding to grid → rods can run |

**Huawei EMMA** ("Feed in power") uses the **negative convention** — enable the **Surplus Sensor Sign Convention** toggle.

**SMA, SolarEdge, Fronius export sensors** typically use the **positive convention** — leave the toggle OFF.

If unsure: check the sensor value in **Developer Tools → States** while your system is clearly feeding to the grid. Negative value → enable the toggle.

---

## Grid Power Sensor Convention

The grid sensor (for emergency shutdown) always uses: **positive = importing from grid**.

For Huawei EMMA "Active power": positive = drawing from grid, negative = exporting. This matches the expected convention — no inversion needed.

---

## Buffer Tank Detection

When power sensors are configured, the blueprint detects when the buffer tank thermostat cuts the rods out:

1. Rod switch is ON but measured power stays below the cutoff threshold for 2 minutes → buffer tank full
2. All rods are turned off and a Logbook entry is written
3. After 15 minutes (or 60 minutes when the buffer temperature sensor reads at or above the threshold), the blueprint re-evaluates the surplus and turns rods back on if conditions are met
4. After 2 more minutes, it checks whether the rods are actually drawing power
5. If they are → Logbook: "retry successful, buffer cooling"
6. If not → rods turned off again; cycle repeats when power stays low for another 2 minutes

---

## Safety

### Notifications

The blueprint distinguishes between routine shutdowns and real problems:

| Event | Notification type |
|-------|-------------------|
| Daily end-time shutdown | Logbook entry only |
| Battery SOC below minimum | Logbook entry only |
| Buffer tank full / retry | Logbook entry only |
| Grid import exceeds threshold | Logbook entry only |
| Surplus sensor unavailable, rods ON | Logbook entry only |

All events write to the HA Logbook (visible under **History** for the automation entity).
Emergency shutdowns always log regardless of the Enable Logging setting; all other events
only log when Enable Logging is ON.

### Failsafe Shutdown

Rods are shut down silently (Logbook entry only) when:
- Current time is outside the configured time window (`end_time` fires an explicit trigger)
- Battery SOC drops below the configured minimum

### Emergency Grid-Import Shutdown

When a grid sensor is configured, an emergency shutdown triggers immediately if grid import exceeds the
threshold — regardless of lock delays or retry cycles. A Logbook entry is always written (even when
Enable Logging is OFF) because this indicates a configuration problem or unexpected behaviour.

**Note**: The emergency shutdown cannot interrupt an active lock delay because `mode: single` prevents
re-entry during delays. Keep the lock time low (default 5 min) to minimize this window. For a hard
real-time grid guard, add a separate automation outside this blueprint.

### Invalid Sensor Safety

If the surplus sensor reports `unavailable` or `unknown` and any rod is ON, all rods are immediately
shut down and a Logbook entry is written.

### Unrecognised Switch Combination

If rods are manually switched to a combination not in the stage_table (e.g. via the HA UI), the
blueprint detects this and turns everything off on the next run, restoring a known-good state.

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
   - Select your surplus sensor and configure the sign convention
   - Select your battery SOC sensor
   - Select your grid power sensor (strongly recommended)

   **Heating Rods section**
   - Assign the switch and capacity for each rod you have (Rod 2 and Rod 3 are optional)

   **Operation Settings section**
   - Set your start/end times and minimum battery SOC
   - Enter your battery capacity in kWh (for log display)
   - Adjust hysteresis and lock time if needed

   **Power Monitoring section** (collapsed, optional)
   - Assign power sensors if available (e.g. Nous D3T)
   - Leave empty to disable buffer tank detection

   **Buffer Tank Temperature section** (collapsed, optional)
   - Assign the lowest temperature sensor on your buffer tank
   - Set the threshold to the temperature at which your rod's thermostat cuts out (typically 55–60 °C)
   - Leave empty to keep the standard 15-minute retry wait

   **Logging section** (collapsed)
   - Enable to write stage changes and events to the HA Logbook

---

## Upgrading from v2.x

**Breaking change**: the Stage Thresholds section has been removed. Stage thresholds are now computed
automatically from the rod capacities you configure in the Heating Rods section.

When upgrading, create a new automation instance and reconfigure from scratch. The key difference:

| v2.x | v3.0 |
|------|------|
| 6 manual threshold inputs (W each) | Rod capacity inputs (kW each) per rod |
| All 3 rods required | Rod 2 and Rod 3 are optional |
| No battery kWh input | Battery Capacity (kWh) for log display |
| Lock time max 5 min | Lock time max 10 min |
| Fixed 15-min buffer tank retry | Configurable: 60 min when buffer temperature sensor ≥ threshold |
| Persistent notification popups | Logbook-only — no popups |

Major changes in earlier versions:
- v2.0: Single surplus sensor input, hysteresis, correct switching sequence, lock time, failsafe, buffer tank, grid kill-switch, logbook
- v2.1: Configurable sign convention — no template sensor needed for Huawei EMMA

---

## Supported Devices

- Any PV inverter or energy management system with a real-time feed-in power sensor
- Huawei SUN2000 / EMMA, SMA, SolarEdge, Fronius, Victron, and more
- Smart switches for heating rods: Shelly, Zigbee, Z-Wave, etc.
- Optional power monitoring: Nous D3T, Shelly Plug S, or any smart plug with power metering

---

## Known Limitations

- Overnight time windows (e.g. 23:00 to 01:00) are not supported
- The grid-import kill-switch cannot interrupt an active lock delay (see Safety section)
- Stage-down (Stage 2+) is held until SOC drops below 90% when battery is full — intentional, see Asymmetric Switching
- Wear leveling for equal-capacity rods: same combination always selected; rotate rods manually if needed

---

## License

MIT License

---

## Contribution

Feel free to submit improvements via pull request.
