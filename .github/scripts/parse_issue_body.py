#!/usr/bin/env python3
"""
Parse an ImmortalWrt BuilderBot build-request issue body into a JSON
build config usable by the Build-from-Issue workflow.

GitHub renders issue form submissions as markdown with hidden HTML comment
markers around each field. We extract values from:

  - input/textarea fields:
      <!-- name: field_id, type: input -->
      <!-- value being submitted: ... -->
  - dropdown:
      <!-- name: field_id, type: dropdown -->
      <!-- items: [...] -->
      <!-- value being submitted: ... -->
      (and a markdown bullet for the selected option, **bolded**)
  - checkboxes:
      <!-- name: field_id, type: checkboxes -->
      <!-- items: [...] -->
      (followed by markdown bullets: `- [x] label` = checked, `- [ ] label` = unchecked)

Robustness notes:
  * We DO NOT depend on parsing the items JSON block (its key casing has
    changed across GitHub's renderer versions). For dropdowns we trust the
    bold-bullet OR the "value being submitted" marker; for checkboxes we
    trust the rendered markdown bullets.
  * If a marker is missing, that field is silently absent from the output
    and `build_config()` falls back to a sane default.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any


_MARKER_RE = re.compile(r"<!--\s*(.*?)\s*-->", re.DOTALL)


def _scan_markers(body: str) -> tuple[list[str], list[str]]:
    """Return ([line_contents...], [marker_text...]) from body.

    Note: GitHub may emit multi-line HTML comments for textarea fields
    whose value contains newlines (e.g.
    `<!-- value being submitted: line1\nline2\nline3 -->`). We therefore
    scan the whole body in one pass with re.DOTALL, but still track the
    line number on which each marker *starts* (for finding bullets below
    checkbox markers)."""
    lines = body.splitlines()
    marker_line_indices: list[int] = []
    marker_contents: list[str] = []
    for m in _MARKER_RE.finditer(body):
        # Compute the starting line number of this marker in `body`
        start_line = body.count("\n", 0, m.start())
        marker_line_indices.append(start_line)
        marker_contents.append(m.group(1))
    return lines, marker_contents, marker_line_indices


def _find_value_marker(markers: list[str], start_idx: int) -> str | None:
    for s in markers[start_idx:start_idx + 6]:
        m = re.match(r"value being submitted:\s*(.*)", s, re.DOTALL)
        if m:
            return m.group(1).strip()
    return None


def _find_dropdown_selection(lines: list[str], after_line_idx: int) -> str | None:
    """Find the bold markdown bullet on a line after `after_line_idx`."""
    for k in range(after_line_idx + 1, min(after_line_idx + 30, len(lines))):
        sel = re.match(r"\s*-\s*\*\*(.+?)\*\*", lines[k])
        if sel:
            return sel.group(1).strip()
    return None


def _find_checked_labels(lines: list[str], marker_line_indices: list[int], idx: int) -> list[str]:
    """Find `- [x] label` bullets between the checkbox marker (idx) and the
    next field-start marker (idx+N that contains `name:` and `type:`).

    The renderer usually emits:
        <!-- name: foo, type: checkboxes -->
        <!-- items: [...] -->

    So the immediately-following marker is items, NOT a new field. We must
    skip past it to find bullets.
    """
    # The bullets are after the items marker (idx+1) up to before the next
    # field-start marker. Find the line where the items marker lives.
    items_marker_idx = idx + 1
    if items_marker_idx >= len(marker_line_indices):
        return []
    # Skip past all consecutive items markers (some fields have several)
    while items_marker_idx < len(marker_line_indices):
        content_idx = items_marker_idx
        # If next marker doesn't look like an items marker (i.e. it's a field
        # marker with "name:" and "type:"), we stop skipping
        # We don't have access to marker_contents here, so we just guess: the
        # items marker appears on the line right after the field marker. If
        # items_marker_idx == idx+1, assume it's the items marker; else stop.
        break
    start_line = marker_line_indices[items_marker_idx] + 1
    # End at the next field-start marker (a marker containing both "name:" and "type:")
    # We approximate by walking forward through lines until we hit another
    # `<!-- name:` pattern.
    end_line = len(lines)
    for k in range(start_line, len(lines)):
        if _MARKER_RE.search(lines[k]) and ("name:" in lines[k] and "type:" in lines[k]):
            end_line = k
            break

    block = lines[start_line:end_line]
    checked: list[str] = []
    for bullet_line in block:
        bm = re.match(r"\s*-\s*\[(x|X)\]\s*(.+)", bullet_line)
        if bm:
            checked.append(bm.group(2).strip())
    return checked


def extract_fields(body: str) -> dict[str, Any]:
    """Walk hidden markers and pull out each form field's value."""
    lines, marker_contents, marker_line_indices = _scan_markers(body)

    fields: dict[str, Any] = {}
    i = 0
    while i < len(marker_contents):
        content = marker_contents[i]
        name_m = re.search(r"name:\s*([^,]+?)(?:\s*,\s*type:|\s*$)", content)
        type_m = re.search(r"type:\s*(\w+)", content)
        if not name_m or not type_m:
            i += 1
            continue
        name = name_m.group(1).strip()
        ftype = type_m.group(1).strip()

        if ftype in ("input", "textarea"):
            value = _find_value_marker(marker_contents, i + 1)
            if value is not None:
                fields[name] = value
            i += 1
        elif ftype == "dropdown":
            sel = _find_dropdown_selection(lines, marker_line_indices[i])
            if sel is not None:
                fields[name] = sel
            else:
                value = _find_value_marker(marker_contents, i + 1)
                if value is not None:
                    fields[name] = value
            i += 1
        elif ftype == "checkboxes":
            checked = _find_checked_labels(lines, marker_line_indices, i)
            fields[name] = {"checked": checked}
            i += 1
        else:
            i += 1

    return fields


# ----------------------------- preset mapping ------------------------------

PRESET_PACKAGES: dict[str, list[str]] = {
    "WiFi 支持 (wpad-openssl + kmod-mt76xx-common 等)": [
        "wpad-openssl",
    ],
    "USB 存储 (kmod-usb-storage + 相关工具)": [
        "kmod-usb-storage",
        "kmod-usb-storage-uas",
        "kmod-usb-ohci",
        "kmod-usb-uhci",
        "kmod-usb3",
        "block-mount",
    ],
    "文件系统工具 (e2fsprogs + fdisk + dosfstools)": [
        "e2fsprogs",
        "fdisk",
        "dosfstools",
    ],
    "UPnP (luci-app-upnp + miniupnpd)": [
        "luci-app-upnp",
        "miniupnpd",
    ],
    "动态 DNS (ddns-scripts + luci-app-ddns)": [
        "ddns-scripts",
        "luci-app-ddns",
    ],
    "SQM QoS (luci-app-sqm + sqm-scripts)": [
        "luci-app-sqm",
        "sqm-scripts",
    ],
    "WireGuard VPN (wireguard-tools + luci-app-wireguard)": [
        "luci-app-wireguard",
        "wireguard-tools",
    ],
    "OpenVPN (openvpn-openssl + luci-app-openvpn)": [
        "luci-app-openvpn",
        "openvpn-openssl",
    ],
    "Tailscale (tailscale)": [
        "tailscale",
    ],
    "AdGuardHome (adguardhome)": [
        "adguardhome",
    ],
    "Samba 网络共享 (luci-app-samba + samba4-server)": [
        "luci-app-samba4",
        "samba4-server",
    ],
    "NFS 服务器 (luci-app-nfs + nfs-kernel-server)": [
        "luci-app-nfs",
        "nfs-kernel-server",
        "nfs-kernel-server-utils",
    ],
    "miniDLNA (minidlna)": [
        "luci-app-minidlna",
        "minidlna",
    ],
    "ZeroTier (zerotier)": [
        "zerotier",
    ],
    "Docker (docker + dockerd)": [
        "docker",
        "dockerd",
        "luci-app-dockerman",
    ],
    "Prometheus node exporter (prometheus-node-exporter-lua)": [
        "prometheus-node-exporter-lua",
    ],
}


# ----------------------------- main pipeline -------------------------------

def build_config(fields: dict[str, Any]) -> dict[str, Any]:
    """Translate raw form fields into a normalized build config dict."""
    device = (fields.get("device_profile") or "").strip()
    if not device:
        raise SystemExit("FAIL: device_profile is required and missing")

    stability = (fields.get("build_stability") or "stable").strip()
    if stability not in ("snapshot", "stable"):
        raise SystemExit(
            f"FAIL: build_stability must be snapshot or stable, got {stability!r}"
        )

    selected: list[str] = []
    extra_features = fields.get("extra_features", {})
    if isinstance(extra_features, dict):
        for label in extra_features.get("checked", []):
            selected.extend(PRESET_PACKAGES.get(label, []))

    custom = (fields.get("custom_packages") or "").strip()
    additions = " ".join(selected)
    merged = (additions + " " + custom).strip()
    merged = re.sub(r"\s+", " ", merged).strip()

    acknowledged = False
    ack = fields.get("acknowledge", {})
    if isinstance(ack, dict):
        acknowledged = bool(ack.get("checked"))

    config = {
        "device_profile": device,
        "build_stability": stability,
        "rootfs_size_mb": (fields.get("rootfs_size_mb") or "").strip() or "8192",
        "preinit_ip": (fields.get("preinit_ip") or "").strip() or "192.168.1.1",
        "preinit_netmask": (fields.get("preinit_netmask") or "").strip() or "255.255.255.0",
        "preinit_broadcast": (fields.get("preinit_broadcast") or "").strip() or "192.168.1.255",
        "release_tag_suffix": (fields.get("release_tag_suffix") or "").strip(),
        "custom_packages": merged,
        "feature_packages": list(dict.fromkeys(selected)),
        "acknowledged": acknowledged,
    }
    return config


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--body-file", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--debug", action="store_true")
    args = p.parse_args()

    body = open(args.body_file, encoding="utf-8").read()
    fields = extract_fields(body)
    config = build_config(fields)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"Wrote {args.out}")

    if args.debug:
        with open(args.out + ".fields.json", "w", encoding="utf-8") as f:
            json.dump(fields, f, indent=2, ensure_ascii=False)
        print(f"Wrote {args.out}.fields.json (raw field dump)")
    return 0


if __name__ == "__main__":
    sys.exit(main())