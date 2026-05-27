# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Structure

Each blueprint lives in its own folder under `automation/<name>/`:
- `blueprint.yaml` — the Home Assistant blueprint (YAML + Jinja2 templates)
- `README.md` — user-facing documentation
- `validate.py` — structural correctness checker (run locally, not in HA)

## Validation

Each blueprint folder contains a `validate.py`. Run it from inside that folder:

```bash
python3 automation/pv_heating_rod/validate.py
```

Exit codes: 0 = clean, 1 = warnings only, 2 = errors. Target: 0 errors, 0 warnings.

Requires PyYAML: `pip install pyyaml --user`

## Deployment

Blueprints are deployed to Home Assistant via GitHub raw URL import. There is no CI pipeline. After pushing, the user imports or refreshes the blueprint in HA manually:
**Settings → Automations & Scenes → Blueprints → Import Blueprint**

The HA instance uses Nabu Casa (no direct file access).

## HA Blueprint YAML Constraints

These constraints apply to all blueprint files in this repo:

- **`!input` tags**: Standard YAML parsers reject them. `validate.py` registers a multi-constructor (`yaml.add_multi_constructor("!", ...)`) to handle them. Never use `!input` inside a Jinja2 expression — only as a bare YAML value.
- **Jinja2 loops**: Variables assigned inside `{% for %}` are not visible outside. Use `namespace()` to carry state across loop iterations.
- **`variables:` block ordering**: Variables in the same `variables:` block are resolved sequentially — a variable can reference earlier ones in the same block. Split into separate blocks when there is a multi-step dependency chain.
- **Optional entity inputs**: Use `default: {}` (empty dict) for optional switch/sensor inputs. Guard every reference with `v_switch not in [{}, '']` — not just a truthiness check, because `{}` is falsy but an empty string `''` is also possible.
- **`mode: single` + `max_exceeded: silent`**: Required on all blueprints to implement lock-time behaviour without error logs.

## pv_heating_rod Blueprint Architecture

The action executes in numbered blocks (1–11) with strict priority ordering:

1. **Block 1** — Resolve `!input` into variables (`v_*` prefix)
2. **Block 2** — Compute rod capacities in watts (`cap1_w`, `cap2_w`, `cap3_w`)
3. **Block 3** — Build `_raw_combos`: all 7 rod on/off combinations as dicts `{r1, r2, r3, power, rods}`
4. **Block 4** — Deduplicate into `stage_table`: compound sort `sort(attribute='rods') | sort(attribute='power')`, then keep first entry per power level → fewest rods wins for equal power
5. **Blocks 5–8** — Safety checks in priority order: Emergency shutdown → Failsafe → Buffer tank → Lock time guard
6. **Block 9** — Compute current state: `_current_stage` dict (single loop for both `current_stage_idx` and `current_stage_power_w`)
7. **Block 10** — Compute `desired_stage_idx` from effective surplus + hysteresis
8. **Block 11** — Execute stage change: turn OFF first, then ON (prevents momentary overshoot)

**Notification policy**: only `persistent_notification.create` (popup) for grid-import emergencies and sensor faults. Routine shutdowns (end_time, battery limit) use `logbook.log` only.

**Asymmetric switching**: `trigger_allows_stage_down` is false for non-periodic triggers when battery SOC ≥ 90% — stage-down is delayed to the 5-min periodic check so short cloud shadows don't cause unnecessary switching.
