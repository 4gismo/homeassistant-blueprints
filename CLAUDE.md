# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Structure

Each blueprint lives in its own folder under `automation/<name>/`:
- `blueprint.yaml` — the Home Assistant blueprint (YAML + Jinja2 templates)
- `README.md` — user-facing documentation
- `validate.py` — structural correctness checker (run locally, not in HA)

## Validation

Run from the repo root:

```bash
python3 automation/pv_heating_rod/validate.py
```

Exit codes: 0 = clean, 1 = warnings only, 2 = errors. Target: 0 errors, 0 warnings.

Requires PyYAML: `pip install pyyaml --user`

## Deployment

Blueprints are deployed via GitHub raw URL import — no CI pipeline. After pushing, the user imports or refreshes manually in HA:
**Settings → Automations & Scenes → Blueprints → Import Blueprint**

The HA instance uses Nabu Casa (no direct file access).

## HA Blueprint YAML Constraints

- **`!input` tags**: Standard YAML parsers reject them. `validate.py` registers `yaml.add_multi_constructor("!", ...)` to handle them. Never use `!input` inside a Jinja2 expression — only as a bare YAML value.
- **Jinja2 loops**: Variables assigned inside `{% for %}` are not visible outside. Use `namespace()` to carry state across loop iterations.
- **`variables:` block ordering**: Variables in the same `variables:` block are resolved sequentially — a variable can reference earlier ones in the same block. Split into separate blocks when there is a multi-step dependency chain.
- **Optional entity inputs**: Use `default: {}` for optional switch/sensor inputs. Guard every reference with `v_switch not in [{}, '']` — not just a truthiness check, because `{}` is falsy but an empty string `''` is also possible.
- **`mode: single` + `max_exceeded: silent`**: Required on all blueprints to implement lock-time behaviour without error logs.

## validate.py Structure

The validator is a flat script with numbered sections matching the blueprint blocks. Key patterns:
- `action_text = raw[raw.find("action:"):]` — all template checks run on this substring
- Region-based checks: `find(anchor)` → slice `[pos : pos + N]` → check for substring. Use this pattern when the target keyword appears before or after the anchor in YAML (e.g. `logbook.log` appears before its `name:` field).
- `REQUIRED_INPUTS` validates declaration in the blueprint, not user configuration — include optional inputs with defaults.
- `warn=True` for feature checks, no flag (error) for structural/safety invariants.

## pv_heating_rod Blueprint Architecture

The action executes as numbered `variables:` blocks followed by `if:` blocks, in strict priority order:

1. **Block 1** — Resolve every `!input` into a `v_*` variable (required because `!input` cannot appear inside Jinja2 expressions)
2. **Block 2** — Compute rod wattages: `cap1_w`, `cap2_w`, `cap3_w` (0 when the corresponding switch is not configured)
3. **Block 3** — Build `_raw_combos`: all valid rod on/off combinations as dicts `{r1, r2, r3, power, rods}`
4. **Block 4** — Deduplicate into `stage_table`: `sort(attribute='rods') | sort(attribute='power')` is a stable two-pass sort (power primary, rods secondary as tiebreak) — fewest rods wins for equal power; keep first entry per power level
5. **Block 5** — Read sensors: `effective_surplus`, `battery_soc`, `sw1_on`/`sw2_on`/`sw3_on`, thermostat detection, `battery_available_kwh`
6. **Block 6** — Read `grid_power` (separate block so Block 7 can reference it as a resolved variable; sentinel −9999 when not configured)
7. **Block 7** — Evaluate safety flags: `grid_import_detected`, `surplus_sensor_invalid`, `any_rod_on`
8. **Emergency shutdown `if`** — fires when `any_rod_on and (grid_import_detected or surplus_sensor_invalid)`; calls `logbook.log` (always, no `v_logging` guard) + `stop:`
9. **Block 8** — Thermostat monitoring: `any_on_monitored`, `all_on_monitored_thermostated`
10. **Block 9** — Derive current stage: single loop over `stage_table` populates `_current_stage` → `current_stage_idx` / `current_stage_power_w`; returns −1 when all rods are off OR the switch combination is not in the table
11. **Block 10** — Compute `raw_desired_stage_idx`: highest stage index where `effective_surplus >= stage.power`; −1 when surplus is below all thresholds
12. **Block 11** — Apply hysteresis + SOC buffer: `trigger_allows_stage_down = battery_soc < 90 or current_stage_idx | int <= 0`; resolve `desired_stage_idx`, `desired_stage_combo`, `target_p1/p2/p3`
13. **Safeguard `if`** — when `desired == −1 and current == −1 and any_rod_on` (unrecognised manual switch state): turns all rods off + `stop:`
14. **Power-monitor `if`** — buffer tank management with auto-retry cycle. CASE 1: all monitored rods thermostated → all off → wait `retry_wait_minutes` (15 min default; 60 min when `buffer_temp_sensor` ≥ `buffer_temp_threshold`) → re-read sensors → retry stage → 2-min check → log → `stop:`
15. **Failsafe / normal operation `if-else`** — failsafe (outside time window or low SOC) uses `logbook.log` only (no popup); normal operation applies the SOC buffer check, then executes the stage change (OFF first → 5 s delay → ON) and appends a lock-time delay

**Notification policy**: All shutdowns (emergency, failsafe, buffer tank) write to `logbook.log` only — no persistent notification popups. Emergency shutdown always logs regardless of `enable_logging`. Failsafe and buffer tank events log only when `enable_logging` is true.

**Asymmetric switching (v3.0)**: `trigger_allows_stage_down` is SOC- and stage-level-based, not trigger-type-based. Stage-down is suppressed when `battery_soc >= 90` AND `current_stage_idx > 0`. Stage 1 (idx=0) is always exempt — uses index comparison, not power, so it works correctly regardless of which rod has the lowest capacity.
