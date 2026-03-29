from __future__ import annotations

import ipaddress
import json
from pathlib import Path

from scapy.all import ARP, Ether, conf, srp  # type: ignore


def _normalize_mac(mac: str) -> str:
    mac = (mac or "").strip().replace("-", ":").upper()
    return mac


def _load_vendor_db() -> dict[str, str]:
    """
    Loads mac_vendors.json once and builds an OUI->vendor dict.

    Input JSON format:
        {
          "Vendor Name": ["AABBCC", "DDEEFF"]
        }

    Dict format (lookup):
        {"AABBCC": "Vendor Name", ...}
    """
    candidates = [
        # Prefer project root (cwd) when running app.
        Path.cwd() / "mac_vendors.json",
        # Also support being run from other working dirs.
        Path(__file__).resolve().parents[1] / "mac_vendors.json",
        Path(__file__).resolve().parent / "mac_vendors.json",
    ]

    data = None
    for p in candidates:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            break
        except Exception:
            continue

    if not isinstance(data, dict):
        return {}

    vendor_by_oui: dict[str, str] = {}
    for vendor, prefixes in data.items():
        if not vendor:
            continue
        if not isinstance(prefixes, list):
            continue
        vendor_name = str(vendor)
        for prefix in prefixes:
            key = str(prefix).replace(":", "").replace("-", "").strip().upper()
            if len(key) >= 6:
                vendor_by_oui[key[:6]] = vendor_name
    return vendor_by_oui


_VENDOR_BY_OUI: dict[str, str] = _load_vendor_db()


def lookup_vendor(mac: str) -> str:
    mac_hex = (mac or "").replace(":", "").replace("-", "").strip().upper()
    if len(mac_hex) < 6:
        return mac
    return _VENDOR_BY_OUI.get(mac_hex[:6], mac)


def scan_network(cidr: str):
    """
    ARP-based network scan using Scapy.

    Yields devices as they are discovered:
        yield {"ip": str, "mac": str}
    """
    network = ipaddress.ip_network(cidr, strict=False)

    # Scapy can take CIDR directly as pdst; using the normalized string is fine.
    target = str(network)

    # Keep Scapy quiet (especially important for library usage).
    prev_verb = conf.verb
    conf.verb = 0
    try:
        pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=target)

        # scapy's srp() returns answers after each receive window; to provide
        # "live-ish" updates, we do a couple short receive windows and yield new
        # devices after each window. This stays Scapy-only and Windows/Npcap-friendly.
        seen: set[str] = set()
        for _round in range(2):
            answered, _ = srp(pkt, timeout=1, retry=0)
            for _, resp in answered:
                ip = getattr(resp, "psrc", None)
                mac = getattr(resp, "hwsrc", None)
                if not ip or not mac:
                    continue
                mac_n = _normalize_mac(mac)
                key = f"{ip}|{mac_n}"
                if key in seen:
                    continue
                seen.add(key)
                yield {"ip": str(ip), "mac": mac_n, "vendor": lookup_vendor(mac_n)}
    finally:
        conf.verb = prev_verb
