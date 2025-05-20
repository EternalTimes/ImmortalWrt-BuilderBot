import yaml
import json
import re
import os

workflow_path = '.github/workflows/Rockchip armv8.yml'

# 1. 读取 profiles、url 等
with open('immortalwrt_info.json', encoding='utf-8') as f:
    info = json.load(f)
profiles = sorted(set(info.get('snapshots', {}).get('profiles', []) + info.get('latest_stable', {}).get('profiles', [])))
snapshot_url = info.get('snapshots', {}).get('imagebuilder_url', '')
stable_url = info.get('latest_stable', {}).get('imagebuilder_url', '')

# 2. 先用 PyYAML 尝试解析
try:
    with open(workflow_path, encoding='utf-8') as f:
        data = yaml.safe_load(f)
    if True in data and 'workflow_dispatch' in data[True]:  # 'on' 被错误识别成 True
        raise ValueError("on parsed as True")
    # 正常情况，继续原有yaml处理
    ... # 你的原有流程
except Exception as e:
    # YAML 失败，降级为正则文本操作
    with open(workflow_path, encoding='utf-8') as f:
        text = f.read()
    # 替换 device_profiles
    text = re.sub(
        r'(device_profiles:\s*[\s\S]+?options:\s*\n)(\s*-.*\n)+',
        lambda m: f"{m.group(1)}" + ''.join([f"          - {p}\n" for p in profiles]),
        text
    )
    # 替换 env 部分 snapshot/stable url
    text = re.sub(
        r'(SNAPSHOT_IMAGEBUILDER_URL:\s*).*',
        f'\\1"{snapshot_url}"',
        text
    )
    text = re.sub(
        r'(STABLE_IMAGEBUILDER_URL:\s*).*',
        f'\\1"{stable_url}"',
        text
    )
    with open(workflow_path, 'w', encoding='utf-8') as f:
        f.write(text)
