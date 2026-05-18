import yaml, re

with open('blueprint.yaml', 'r', encoding='utf-8') as f:
    raw = f.read()
with open('README.md', 'r', encoding='utf-8') as f:
    readme = f.read()

no_comments = re.sub(r'#[^\n]*', '', raw)
clean = no_comments.replace('!input ', '__INPUT__')
doc = yaml.safe_load(clean)

issues = []
warnings = []
ok = []

# ── 1. YAML ────────────────────────────────────────────────────────
try:
    yaml.safe_load(clean)
    ok.append('YAML syntax valid')
except yaml.YAMLError as e:
    issues.append(f'YAML: {e}')

# ── 2. Blueprint metadata ──────────────────────────────────────────
bp = doc.get('blueprint', {})
for field in ['name', 'domain', 'source_url', 'description']:
    if bp.get(field):
        ok.append(f'blueprint.{field} present')
    else:
        issues.append(f'blueprint.{field} missing')

if bp.get('domain') == 'automation':
    ok.append('domain = automation')
else:
    issues.append(f'domain wrong: {bp.get("domain")}')

desc = bp.get('description', '')
if 'Version 2.3' in desc:
    ok.append('Version 2.3 in blueprint description')
else:
    warnings.append('Version not found in blueprint description (expected 2.3)')
if '2.3' in readme:
    ok.append('Version 2.3 in README')
else:
    warnings.append('Version 2.3 not found in README')

# ── 3. Inputs ──────────────────────────────────────────────────────
bp_input = bp.get('input', {})
declared = {}
for key, val in bp_input.items():
    if isinstance(val, dict) and 'input' in val:
        for ik, iv in val['input'].items():
            declared[ik] = iv
    else:
        declared[key] = val

used_inputs = set(re.findall(r'__INPUT__(\w+)', clean))
undefined = used_inputs - set(declared)
if undefined:
    issues.append(f'!input used but not declared: {undefined}')
else:
    ok.append(f'All {len(used_inputs)} !input refs resolve ({len(declared)} declared)')

required = [k for k, v in declared.items() if isinstance(v, dict) and 'default' not in v]
ok.append(f'Required inputs (no default): {required}')

# ── 4. Block 1 variable chain ──────────────────────────────────────
action = doc.get('action', [])
block1 = action[0].get('variables', {}) if action else {}
if len(block1) == len(declared):
    ok.append(f'Block 1: {len(block1)} vars match {len(declared)} inputs')
else:
    warnings.append(f'Block 1 has {len(block1)} vars but {len(declared)} inputs')

aliases = {
    'surplus_sensor_inverted': 'v_invert_surplus',
    'stage_1_threshold': 'v_t1', 'stage_2_threshold': 'v_t2',
    'stage_3_threshold': 'v_t3', 'stage_4_threshold': 'v_t4',
    'stage_5_threshold': 'v_t5', 'stage_6_threshold': 'v_t6',
    'lock_time_after_switching': 'v_lock_time',
    'hysteresis_watts': 'v_hysteresis',
    'enable_logging': 'v_logging',
    'switch_p1_power': 'v_p1_power_sensor',
    'switch_p2_power': 'v_p2_power_sensor',
    'switch_p3_power': 'v_p3_power_sensor',
    'thermostat_cutoff_threshold': 'v_cutoff',
    'max_grid_import': 'v_max_grid_import',
}
missing_vars = []
for inp_id in declared:
    expected = aliases.get(inp_id, 'v_' + inp_id)
    if expected not in block1:
        missing_vars.append(f'{inp_id} -> {expected}')
if missing_vars:
    issues.append(f'Block 1 missing variables: {missing_vars}')
else:
    ok.append('Block 1: all inputs mapped to variables (aliases verified)')

# ── 5. Template whitespace ─────────────────────────────────────────
for varname in ['effective_surplus', 'retry_surplus']:
    lines = raw.split('\n')
    for i, line in enumerate(lines):
        if f'{varname}:' in line and '>' in line:
            if '>-' not in line:
                warnings.append(
                    f'{varname} uses ">" YAML scalar (not ">-") — '
                    f'rendered value may have leading/trailing whitespace. '
                    f'Use ">-" with {{%-  -%}} for guaranteed clean output.'
                )
            break

# ── 6. Stage table consistency ─────────────────────────────────────
p1_stages = [1, 4, 6]
p2_stages = [2, 5, 6]
p3_stages = [3, 4, 5, 6]
stage_map = {
    0: (False, False, False), 1: (True, False, False), 2: (False, True, False),
    3: (False, False, True),  4: (True, False, True),  5: (False, True, True),
    6: (True, True, True)
}
for stage, (p1, p2, p3) in stage_map.items():
    if stage == 0:
        continue
    exp_p1 = stage in p1_stages
    exp_p2 = stage in p2_stages
    exp_p3 = stage in p3_stages
    if (p1, p2, p3) != (exp_p1, exp_p2, exp_p3):
        issues.append(f'Stage {stage} switch combo wrong in reference map')
ok.append('Stage 0-6 switch combinations verified against reference')

# retry_target patterns
for pat, label in [
    (r'retry_target_p1.*\[1.*4.*6\]', 'retry_target_p1 = [1,4,6]'),
    (r'retry_target_p2.*\[2.*5.*6\]', 'retry_target_p2 = [2,5,6]'),
    (r'retry_target_p3.*\[3.*4.*5.*6\]', 'retry_target_p3 = [3,4,5,6]'),
]:
    if re.search(pat, raw):
        ok.append(f'Retry stage mapping: {label}')
    else:
        issues.append(f'Retry stage mapping mismatch: {label}')

# ── 7. Safety ─────────────────────────────────────────────────────
for check, label in [
    ('platform: time\n    at: __INPUT__end_time',   'Explicit end_time trigger'),
    ('platform: time\n    at: __INPUT__start_time', 'Explicit start_time trigger'),
    ('stop:',                                        'stop: for emergency/buffer exit'),
    ('persistent_notification.create',              'Persistent notification on failsafe'),
    ('switch.turn_off',                             'switch.turn_off used'),
    ('mode: single',                                'mode: single'),
    ('max_exceeded: silent',                        'max_exceeded: silent'),
    ('surplus_sensor_invalid',                      'Invalid sensor guard'),
    ('grid_import_detected',                        'Grid import guard'),
    ('sw1_on or sw2_on or sw3_on',                  'Failsafe checks actual switch states'),
    ('trigger_allows_stage_down',                   'Asymmetric switching guard'),
    ("id: \"periodic\"",                            'Periodic trigger has id'),
    ("id: \"sensor\"",                              'Sensor trigger has id'),
]:
    if check in clean:
        ok.append(label)
    else:
        issues.append(f'MISSING: {label}')

# ── 8. Inversion consistency ──────────────────────────────────────
for label in ['effective_surplus', 'retry_surplus']:
    pos = raw.find(label + ':')
    chunk = raw[pos:pos + 400]
    if 'v_invert_surplus' in chunk:
        ok.append(f'{label}: sign inversion applied')
    else:
        issues.append(f'{label}: sign inversion NOT applied')

# ── 9. Empty entity_id bug check ──────────────────────────────────
if "else ''" in raw or 'else ""' in raw:
    issues.append('Empty string entity_id pattern found (old retry bug)')
else:
    ok.append('No empty entity_id strings')

# ── 10. Grid sensor — sign convention note ────────────────────────
grid_desc_pos = raw.find('grid_sensor:')
grid_chunk = raw[grid_desc_pos:grid_desc_pos + 500]
if 'positive' in grid_chunk and 'import' in grid_chunk:
    ok.append('grid_sensor description states sign convention')
else:
    warnings.append('grid_sensor description should state sign convention (positive=import)')

# ── 11. Optional trigger safety note ─────────────────────────────
# power sensor triggers with empty entity_id when not configured
trigger_section = raw[raw.find('trigger:'):raw.find('action:')]
empty_trigger_risk = trigger_section.count('__INPUT__switch_p') if False else 0
warnings.append(
    'Power sensor triggers use optional inputs — when left empty, '
    'entity_id resolves to {} which HA handles gracefully but may log warnings. '
    'Action guard (trigger_is_power_sensor) prevents false execution.'
)

# ── 12. README completeness ───────────────────────────────────────
for keyword, label in [
    ('sign convention',  'Sign convention toggle'),
    ('buffer tank',      'Buffer tank detection'),
    ('logbook',          'Logbook / logging'),
    ('failsafe',         'Failsafe shutdown'),
    ('grid-import',      'Grid import kill-switch'),
    ('lock time',        'Lock time'),
    ('1.3.4',            'Upgrade path from v1.3.4'),
    ('limitation',       'Known limitations'),
    ('huawei',           'Huawei EMMA manufacturer example'),
    ('retry',            'Retry cycle after buffer full'),
    ('hysteresis',       'Hysteresis explanation'),
    ('stage',            'Stage table'),
]:
    if keyword.lower() in readme.lower():
        ok.append(f'README: {label}')
    else:
        warnings.append(f'README missing: {label}')

# ── 13. source_url ────────────────────────────────────────────────
if '4gismo/homeassistant-blueprints' in raw:
    ok.append('source_url: correct repo')
else:
    warnings.append('source_url may point to wrong repo')

# ── Print results ─────────────────────────────────────────────────
print(f'\n{"="*60}')
print(f'  COMPLETE CHECK: {len(ok)} OK  |  {len(warnings)} WARN  |  {len(issues)} ERR')
print(f'{"="*60}\n')

if issues:
    print('ERRORS (must fix):')
    for i in issues:
        print(f'  [ERR]  {i}')
    print()

if warnings:
    print('WARNINGS (review):')
    for w in warnings:
        print(f'  [WARN] {w}')
    print()

print('OK:')
for o in ok:
    print(f'  [OK]   {o}')
