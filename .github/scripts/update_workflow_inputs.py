import json

with open('immortalwrt_info.json', encoding='utf-8') as f:
    data = json.load(f)

profiles = data.get('snapshots', {}).get('profiles', [])
stable_profiles = data.get('latest_stable', {}).get('profiles', [])
all_profiles = sorted(set(profiles + stable_profiles))

profile_options = ['          - {}'.format(p) for p in all_profiles]
profile_yaml = '\n'.join(profile_options)

stabilities = ['snapshot', 'stable']
stability_options = ['          - {}'.format(s) for s in stabilities]
stability_yaml = '\n'.join(stability_options)

with open('profile_options.txt', 'w', encoding='utf-8') as f:
    f.write(profile_yaml)
with open('stability_options.txt', 'w', encoding='utf-8') as f:
    f.write(stability_yaml)