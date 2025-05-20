import yaml
import json

# 读取 immortalwrt_info.json
with open('immortalwrt_info.json', encoding='utf-8') as f:
    data = json.load(f)

# 获取 snapshot 和 stable profiles
snapshot_profiles = data.get('snapshots', {}).get('profiles', [])
stable_profiles = data.get('latest_stable', {}).get('profiles', [])
all_profiles = sorted(set(snapshot_profiles + stable_profiles))

# 获取 imagebuilder url
snapshot_ib_url = data.get('snapshots', {}).get('imagebuilder_url', '')
stable_ib_url = data.get('latest_stable', {}).get('imagebuilder_url', '')

# 读取 workflow yml
with open('.github/workflows/Rockchip armv8.yml', encoding='utf-8') as f:
    workflow = yaml.safe_load(f)

# 更新 device_profiles 菜单
inputs = workflow['on']['workflow_dispatch']['inputs']
if 'device_profiles' in inputs:
    inputs['device_profiles']['options'] = all_profiles

# 更新 url 变量（写入 jobs.build_firmware.env 内，确保后续 steps 可直接用）
if 'jobs' in workflow and 'build_firmware' in workflow['jobs']:
    job = workflow['jobs']['build_firmware']
    if 'env' not in job:
        job['env'] = {}
    job['env']['SNAPSHOT_IMAGEBUILDER_URL'] = snapshot_ib_url
    job['env']['STABLE_IMAGEBUILDER_URL'] = stable_ib_url

# 保存回 workflow
with open('.github/workflows/Rockchip armv8.yml', 'w', encoding='utf-8') as f:
    yaml.dump(workflow, f, allow_unicode=True, sort_keys=False)
