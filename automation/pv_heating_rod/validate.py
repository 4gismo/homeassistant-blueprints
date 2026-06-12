"""
Validator for PV Heating Rod Blueprint v3.0

Checks structural correctness, safety features, and cross-file consistency.
Run from the blueprint directory:
    python3 validate.py

Exit codes: 0 = OK, 1 = warnings only, 2 = errors present.
"""

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml")
    sys.exit(2)

BLUEPRINT_FILE = Path(__file__).parent / "blueprint.yaml"
README_FILE = Path(__file__).parent / "README.md"
EXPECTED_VERSION = "3.1"

ok = []
warnings = []
errors = []


def _print_summary():
    print("\n" + "=" * 60)
    print("PV Heating Rod Blueprint Validator — v{}".format(EXPECTED_VERSION))
    print("=" * 60)
    for msg in ok:
        print("  OK   {}".format(msg))
    for msg in warnings:
        print("  WARN {}".format(msg))
    for msg in errors:
        print("  ERR  {}".format(msg))
    print("=" * 60)
    print("  {} OK  |  {} warnings  |  {} errors".format(len(ok), len(warnings), len(errors)))
    print("=" * 60 + "\n")


def check(condition, msg_ok, msg_fail, *, warn=False):
    if condition:
        ok.append(msg_ok)
    elif warn:
        warnings.append(msg_fail)
    else:
        errors.append(msg_fail)


# ---------------------------------------------------------------------------
# 1. Load and parse YAML
# ---------------------------------------------------------------------------
# HA blueprints use !input tags that standard YAML parsers reject.
# Register a constructor that converts them to plain string values.
def _input_constructor(loader, tag_suffix, node):
    return loader.construct_scalar(node)

yaml.add_multi_constructor("!", _input_constructor, Loader=yaml.SafeLoader)

try:
    raw = BLUEPRINT_FILE.read_text()
    bp = yaml.safe_load(raw)
    ok.append("YAML syntax valid")
except yaml.YAMLError as exc:
    errors.append("YAML parse error: {}".format(exc))
    bp = None
except FileNotFoundError:
    errors.append("Blueprint file not found: {}".format(BLUEPRINT_FILE))
    bp = None

if bp is None:
    _print_summary()
    sys.exit(2)

# ---------------------------------------------------------------------------
# 2. Blueprint metadata
# ---------------------------------------------------------------------------
meta = bp.get("blueprint", {})
check(bool(meta.get("name")), "blueprint.name present", "blueprint.name missing")
check(meta.get("domain") == "automation", "blueprint.domain = automation", "blueprint.domain != automation")
check(bool(meta.get("source_url")), "blueprint.source_url present", "blueprint.source_url missing")

desc = meta.get("description", "")
check(
    EXPECTED_VERSION in desc,
    f"blueprint description contains Version {EXPECTED_VERSION}",
    f"blueprint description does not contain 'Version {EXPECTED_VERSION}' — found: {desc[:60]!r}",
)

# ---------------------------------------------------------------------------
# 3. Input declarations
# ---------------------------------------------------------------------------
def _collect_inputs(sections):
    names: set[str] = set()
    for section in sections.values():
        if isinstance(section, dict) and "input" in section:
            names.update(section["input"].keys())
    return names


declared_inputs = _collect_inputs(meta.get("input", {}))

REQUIRED_INPUTS = {
    "surplus_sensor", "surplus_sensor_inverted",
    "battery_soc_sensor", "battery_capacity_kwh",
    "grid_sensor", "max_grid_import",
    "switch_p1", "rod_1_capacity_kw",
    "switch_p2", "rod_2_capacity_kw",
    "switch_p3", "rod_3_capacity_kw",
    "start_time", "end_time",
    "battery_limit", "hysteresis_watts", "lock_time_after_switching",
    "switch_p1_power", "switch_p2_power", "switch_p3_power",
    "thermostat_cutoff_threshold", "enable_logging",
    "buffer_temp_sensor", "buffer_temp_threshold",
}
missing_inputs = REQUIRED_INPUTS - declared_inputs
check(not missing_inputs, "All required inputs declared", f"Missing inputs: {missing_inputs}")

OBSOLETE_INPUTS = {
    "stage_1_threshold", "stage_2_threshold", "stage_3_threshold",
    "stage_4_threshold", "stage_5_threshold", "stage_6_threshold",
}
leftover = OBSOLETE_INPUTS & declared_inputs
check(
    not leftover,
    "No obsolete v2.x stage threshold inputs present",
    f"Obsolete stage threshold inputs still declared (remove them): {leftover}",
)

# 3b. Optional rod switches must have default: {}
all_inputs = {}
for section in meta.get("input", {}).values():
    if isinstance(section, dict) and "input" in section:
        all_inputs.update(section["input"])

for opt_switch in ("switch_p2", "switch_p3"):
    if opt_switch in all_inputs:
        check(
            all_inputs[opt_switch].get("default") == {},
            f"{opt_switch} has default: {{}} (optional)",
            f"{opt_switch} should have 'default: {{}}' to be optional",
        )

# ---------------------------------------------------------------------------
# 4. !input usage — Block 1 must resolve all declared inputs
# ---------------------------------------------------------------------------
action_text = raw[raw.find("action:"):]
used_in_action = set(re.findall(r"!input\s+(\S+)", action_text))
unresolved = declared_inputs - used_in_action
check(
    not unresolved,
    "All declared inputs referenced via !input in action",
    f"Inputs declared but never used via !input: {unresolved}",
    warn=True,
)

# ---------------------------------------------------------------------------
# 5. Obsolete v2.x variables must not appear in the action
# ---------------------------------------------------------------------------
for obsolete_var in ("v_t1", "v_t2", "v_t3", "v_t4", "v_t5", "v_t6"):
    check(
        obsolete_var not in action_text,
        f"Obsolete variable {obsolete_var!r} absent",
        f"Obsolete variable {obsolete_var!r} still referenced — remove it",
    )

# ---------------------------------------------------------------------------
# 6. Dynamic stage table presence
# ---------------------------------------------------------------------------
check("stage_table" in action_text, "stage_table variable present", "stage_table variable missing from action")
check("_raw_combos" in action_text, "_raw_combos (stage builder) present", "_raw_combos missing from action")
check(
    "cap1_w" in action_text and "cap2_w" in action_text and "cap3_w" in action_text,
    "Rod capacity variables cap1_w / cap2_w / cap3_w present",
    "One or more rod capacity variables (cap1_w, cap2_w, cap3_w) missing",
)
check(
    "sort(attribute='rods')" in action_text and "sort(attribute='power')" in action_text,
    "Compound sort (rods, power) present in stage builder",
    "Compound sort missing from stage builder — tie-breaker for equal-power deduplication absent",
)

# ---------------------------------------------------------------------------
# 7. Safety features
# ---------------------------------------------------------------------------
triggers = bp.get("trigger", [])
trigger_ids = {t.get("id") for t in triggers}
check("sensor" in trigger_ids, "Trigger id='sensor' present", "Trigger id='sensor' missing")
check("periodic" in trigger_ids, "Trigger id='periodic' present", "Trigger id='periodic' missing")
check("grid_import" in trigger_ids, "Trigger id='grid_import' present", "Trigger id='grid_import' missing")
check("boundary" in trigger_ids, "Trigger id='boundary' present", "Trigger id='boundary' missing")
check("power_monitor" in trigger_ids, "Trigger id='power_monitor' present", "Trigger id='power_monitor' missing")

time_pattern_triggers = [t for t in triggers if t.get("platform") == "time_pattern"]
check(
    any("/5" in str(t.get("minutes", "")) for t in time_pattern_triggers),
    "5-minute periodic trigger configured",
    "5-minute periodic trigger missing",
)

check("Emergency Shutdown" in action_text, "Emergency shutdown log entry present", "Emergency shutdown log entry missing")
check("Failsafe" in action_text, "Failsafe shutdown present", "Failsafe shutdown missing from action")
check(
    "persistent_notification.create" not in action_text,
    "No persistent_notification popup (logbook only, no intrusive notifications)",
    "persistent_notification.create still present — replace with logbook.log",
    warn=True,
)
emergency_block_start = action_text.find("# Emergency safety shutdown")
emergency_region = action_text[emergency_block_start:emergency_block_start + 800] if emergency_block_start >= 0 else ""
check(
    emergency_block_start >= 0 and "logbook.log" in emergency_region,
    "Emergency shutdown uses logbook.log",
    "Emergency shutdown logbook.log entry missing",
)
failsafe_comment_pos = action_text.find("# FAILSAFE:")
failsafe_region = action_text[failsafe_comment_pos:failsafe_comment_pos + 2000] if failsafe_comment_pos >= 0 else ""
check(
    failsafe_comment_pos >= 0 and "logbook.log" in failsafe_region,
    "Failsafe shutdown uses logbook.log",
    "Failsafe logbook.log entry missing from failsafe section",
    warn=True,
)
check(
    "retry_wait_minutes" in action_text,
    "Temperature-based retry wait (retry_wait_minutes) present in power monitor",
    "retry_wait_minutes missing — buffer tank retry always uses fixed 15-min wait",
    warn=True,
)
check("switch.turn_off" in action_text, "switch.turn_off present", "switch.turn_off missing")
check("mode: single" in raw, "mode: single set", "mode: single missing")
check("max_exceeded: silent" in raw, "max_exceeded: silent set", "max_exceeded: silent missing")

check(
    "trigger_allows_stage_down" in action_text,
    "Asymmetric switching guard (trigger_allows_stage_down) present",
    "Asymmetric switching guard missing",
)

stop_count = action_text.count("- stop:")
check(stop_count >= 2, f"At least 2 stop actions present ({stop_count} found)", "Fewer than 2 stop actions — check safety shutdown paths")

check(
    "current_stage_idx | int == -1" in action_text,
    "Safeguard for unrecognised switch combination present",
    "Safeguard for unrecognised switch combination missing (desired=-1 and current=-1 and any_rod_on)",
    warn=True,
)
# Safeguard must have its own stop: to prevent fallthrough into the power-monitor branch
safeguard_start = action_text.find("current_stage_idx | int == -1")
safeguard_region = action_text[safeguard_start:safeguard_start + 600] if safeguard_start >= 0 else ""
check(
    "- stop:" in safeguard_region,
    "Safeguard block has stop: action (prevents power-monitor fallthrough)",
    "Safeguard block missing stop: — execution falls through to power-monitor branch after rods turned off",
)

# ---------------------------------------------------------------------------
# 8. Sign inversion consistency (must appear in both main and retry surplus calc)
# ---------------------------------------------------------------------------
inversion_pattern = r"\[raw \* -1, 0\] \| max if v_invert_surplus else \[raw, 0\] \| max"
matches = re.findall(inversion_pattern, action_text)
check(
    len(matches) >= 2,
    f"Sign inversion applied consistently ({len(matches)} occurrences: main + retry)",
    f"Sign inversion inconsistent — expected ≥2 occurrences, found {len(matches)}",
)

# ---------------------------------------------------------------------------
# 9. Optional switch entity_id guard
# ---------------------------------------------------------------------------
# Template conditions that turn on/off optional switches must not reference v_switch_p2/p3
# as a bare entity_id without first checking the switch is configured.
# Look for the safe guard pattern used throughout the blueprint.
safe_guard_count = raw.count("not in [{}, '']")
check(
    safe_guard_count >= 4,
    f"Optional switch guard 'not in [{{}}]' used consistently ({safe_guard_count} occurrences)",
    f"Optional switch guard used only {safe_guard_count} times — some turn_on/turn_off may lack guard",
    warn=True,
)

# ---------------------------------------------------------------------------
# 10. README checks
# ---------------------------------------------------------------------------
try:
    readme = README_FILE.read_text()
    ok.append("README.md found")
except FileNotFoundError:
    warnings.append("README.md not found")
    readme = ""

if readme:
    check(
        EXPECTED_VERSION in readme,
        f"README contains Version {EXPECTED_VERSION}",
        f"README does not contain 'Version {EXPECTED_VERSION}' — still on old version?",
    )
    for keyword in (
        "stage_table", "capacity", "kWh", "optional",
        "hysteresis", "lock time", "failsafe", "grid",
        "buffer tank", "logbook", "sign convention",
        "wear", "upgrad",
    ):
        check(
            keyword.lower() in readme.lower(),
            f"README contains keyword '{keyword}'",
            f"README missing keyword '{keyword}'",
            warn=True,
        )

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
_print_summary()

if errors:
    sys.exit(2)
elif warnings:
    sys.exit(1)
else:
    sys.exit(0)
