import yaml
import json

# 读取 device profiles/stabilities
with open('immortalwrt_info.json', encoding='utf-8') as f:
    data = json.load(f)

profiles = data.get('snapshots', {}).get('profiles', [])
stable_profiles = data.get('latest_stable', {}).get('profiles', [])
all_profiles = sorted(set(profiles + stable_profiles))
stabilities = ['snapshot', 'stable']

# 读取并修改 workflow yml
with open('.github/workflows/Rockchip armv8.yml', encoding='utf-8') as f:
    workflow = yaml.safe_load(f)

inputs = workflow['on']['workflow_dispatch']['inputs']
if 'device_profiles' in inputs:
    inputs['device_profiles']['options'] = all_profiles
if 'build_stability' in inputs:
    inputs['build_stability']['options'] = stabilities

with open('.github/workflows/Rockchip armv8.yml', 'w', encoding='utf-8') as f:
    yaml.dump(workflow, f, allow_unicode=True, sort_keys=False)
