"""
Update the Rockchip armv8 GitHub Actions workflow from immortalwrt_info.json.

Reads:
  - immortalwrt_info.json (snapshots + latest_stable blocks)
Writes:
  - .github/workflows/Rockchip armv8.yml
    - device_profiles options list (union of snapshot + stable profiles)
    - SNAPSHOT_IMAGEBUILDER_URL env var
    - STABLE_IMAGEBUILDER_URL env var

Tries to preserve as much of the original file as possible via text-level
patching, so custom comments, formatting, and unrelated inputs are untouched.
PyYAML is intentionally NOT used because GitHub Actions workflows have a YAML
superset (`on:`, anchors, `>>-` literals, etc.) that breaks strict parsers.
"""
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INFO_PATH = REPO_ROOT / "immortalwrt_info.json"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "Rockchip armv8.yml"

# Match the device_profiles option block: everything between `options:` and the
# next top-level (6-space) key. Each option line is `          - <name>`.
DEVICE_PROFILES_BLOCK = re.compile(
    r"(device_profiles:\s*\n"
    r"\s+description:[^\n]*\n"
    r"\s+type:\s*choice\s*\n"
    r"\s+required:\s*true\s*\n"
    r"\s+default:\s*\"[^\"]*\"\s*\n"
    r"\s+options:\s*\n)"
    r"(?:[ \t]*-\s*\S+\s*\n)+",  # existing options (any number)
    re.MULTILINE,
)

# Match env vars SNAPSHOT_IMAGEBUILDER_URL / STABLE_IMAGEBUILDER_URL lines.
ENV_VAR_LINE = re.compile(
    r'^(\s{6}(?:SNAPSHOT_IMAGEBUILDER_URL|STABLE_IMAGEBUILDER_URL):\s*)"[^"]*"\s*$',
    re.MULTILINE,
)


def load_info() -> dict:
    with INFO_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def profile_union(info: dict) -> list[str]:
    snap = info.get("snapshots", {}).get("profiles", []) or []
    stable = info.get("latest_stable", {}).get("profiles", []) or []
    return sorted(set(snap) | set(stable))


def patch_workflow(text: str, profiles: list[str], snapshot_url: str, stable_url: str) -> str:
    new_options_block = "".join(f"          - {p}\n" for p in profiles)
    new_text, n_opts = DEVICE_PROFILES_BLOCK.subn(
        lambda m: m.group(1) + new_options_block, text, count=1
    )
    if n_opts != 1:
        raise RuntimeError(
            f"device_profiles options block not found (matched {n_opts} times)"
        )

    def _replace_env(m: re.Match) -> str:
        var = m.group(0).split(":", 1)[0].strip()
        url = snapshot_url if var == "SNAPSHOT_IMAGEBUILDER_URL" else stable_url
        return f'{m.group(1)}"{url}"'

    new_text, n_envs = ENV_VAR_LINE.subn(_replace_env, new_text)
    if n_envs != 2:
        raise RuntimeError(
            f"expected 2 IMAGEBUILDER_URL env vars, matched {n_envs}"
        )
    return new_text


def main() -> int:
    info = load_info()
    profiles = profile_union(info)
    snapshot_url = info.get("snapshots", {}).get("imagebuilder_url", "")
    stable_url = info.get("latest_stable", {}).get("imagebuilder_url", "")

    if not snapshot_url or not stable_url:
        print("ERROR: missing imagebuilder_url(s) in immortalwrt_info.json", file=sys.stderr)
        return 1

    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    new_text = patch_workflow(text, profiles, snapshot_url, stable_url)
    WORKFLOW_PATH.write_text(new_text, encoding="utf-8")

    print(f"Updated {WORKFLOW_PATH.relative_to(REPO_ROOT)}")
    print(f"  device_profiles options: {len(profiles)} profiles")
    print(f"  SNAPSHOT_IMAGEBUILDER_URL: {snapshot_url}")
    print(f"  STABLE_IMAGEBUILDER_URL:   {stable_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())