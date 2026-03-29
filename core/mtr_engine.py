from __future__ import annotations

import socket
import subprocess
import re
import time

from PySide6.QtCore import QThread, Signal

try:
    from scapy.all import IP, ICMP, sr1  # type: ignore
except Exception:  # pragma: no cover
    IP = None  # type: ignore[assignment]
    ICMP = None  # type: ignore[assignment]
    sr1 = None  # type: ignore[assignment]


class MTRWorker(QThread):
    update_signal = Signal(list)
    status_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        self.target = None

    def start_mtr(self, target):
        self.target = target
        self.running = True
        self.start()

    def stop(self):
        self.running = False

    def run(self):
        max_hops = 20
        hops: dict[int, dict] = {}
        destination_ttl: int | None = None
        ttl_list = list(range(1, max_hops + 1))

        while self.running:
            try:
                target_ip: str | None = socket.gethostbyname(self.target)
            except Exception:
                target_ip = None

            active_max_hops = destination_ttl if destination_ttl is not None else max_hops

            for ttl in ttl_list:
                if not self.running:
                    break

                # Safe initialization (prevents KeyError on access/append).
                if ttl not in hops:
                    hops[ttl] = {
                        "host": "",
                        "ip": "",
                        "loss": 0.0,
                        "sent": 0,
                        "recv": 0,
                        "best": 0.0,
                        "avg": 0.0,
                        "worst": 0.0,
                        "last": 0.0,
                    }
                # STEP 5: increment once per ttl per pass
                hops[ttl]["sent"] += 1

                reply = None
                rtt_ms: float | None = None
                try:
                    if sr1 is not None and IP is not None and ICMP is not None:
                        pkt = IP(dst=self.target, ttl=ttl) / ICMP()
                        t0 = time.time()
                        reply = sr1(pkt, timeout=0.2, verbose=0)
                        t1 = time.time()
                        if reply is not None:
                            rtt_ms = (t1 - t0) * 1000.0
                except Exception:
                    reply = None
                    rtt_ms = None

                hop_ip: str | None = None
                icmp_type: int | None = None
                if reply is not None and ICMP is not None and reply.haslayer(ICMP):
                    icmp_type = int(reply.getlayer(ICMP).type)
                    if icmp_type in (11, 0):
                        hop_ip = getattr(reply, "src", "") or None

                if hop_ip is not None and rtt_ms is not None:
                    prev_recv = hops[ttl]["recv"]
                    prev_avg = hops[ttl]["avg"]
                    hops[ttl]["recv"] = prev_recv + 1
                    recv = hops[ttl]["recv"]
                    hops[ttl]["ip"] = str(hop_ip)

                    # Update last always on success.
                    hops[ttl]["last"] = rtt_ms
                    if hops[ttl]["best"] is None or rtt_ms < hops[ttl]["best"]:
                        hops[ttl]["best"] = rtt_ms
                    if rtt_ms > hops[ttl]["worst"]:
                        hops[ttl]["worst"] = rtt_ms
                    hops[ttl]["avg"] = (
                        (prev_avg * prev_recv) + rtt_ms
                    ) / recv if recv > 0 else hops[ttl]["avg"]

                    # STEP 7/8: hostname resolution and destination label
                    try:
                        hostname = socket.gethostbyaddr(str(hop_ip))[0]
                    except Exception:
                        hostname = str(hop_ip)
                    hops[ttl]["host"] = hostname
                    if target_ip is not None and str(hop_ip) == target_ip:
                        hops[ttl]["host"] = str(self.target)

                    # Destination reached: truncate ttl_list
                    if icmp_type == 0 and target_ip is not None and str(hop_ip) == target_ip:
                        destination_ttl = ttl
                        ttl_list = list(range(1, destination_ttl + 1))
                        active_max_hops = destination_ttl

                else:
                    # Timeout: keep host/ip empty
                    hops[ttl]["host"] = ""
                    hops[ttl]["ip"] = ""

                sent = hops[ttl]["sent"]
                recv_ct = hops[ttl]["recv"]
                hops[ttl]["loss"] = ((sent - recv_ct) / sent) * 100.0 if sent > 0 else 0.0

                # Normalize types for UI consumption
                hop = hops[ttl]
                hop["sent"] = int(hop.get("sent") or 0)
                hop["recv"] = int(hop.get("recv") or 0)
                hop["loss"] = float(hop.get("loss") or 0.0)
                hop["best"] = hop["best"]
                hop["avg"] = float(hop.get("avg") or 0.0)
                hop["worst"] = float(hop.get("worst") or 0.0)
                hop["last"] = float(hop.get("last") or 0.0)

                # STEP 9: emit after each ttl
                hop_list = []
                for t in ttl_list:
                    if t > active_max_hops:
                        continue
                    if t not in hops:
                        hops[t] = {
                            "host": "",
                            "ip": "",
                            "loss": 0.0,
                            "sent": 0,
                            "recv": 0,
                            "best": 0.0,
                            "avg": 0.0,
                            "worst": 0.0,
                            "last": 0.0,
                        }
                    hop_list.append(hops[t])
                self.update_signal.emit(hop_list)

                # STEP 10: small delay
                time.sleep(0.01)

        self.status_signal.emit("Stopped")


def run_mtr_loop(
    target: str,
    hop_updated_callback,
    should_stop,
) -> None:
    """
    Minimal MTR loop used by the existing UI.

    Phase 2: send exactly one probe (TTL=1) per iteration and emit hop_index=1.
    """

    max_hops = 30
    hops: dict[int, dict] = {}
    # Keep behavior deterministic and stable: one probe per 1-second tick.
    while not should_stop():
        try:
            ip = socket.gethostbyname(target)

            for ttl in range(1, max_hops + 1):
                if ttl not in hops:
                    hops[ttl] = {
                        "host": "",
                        "ip": "",
                        "sent": 0,
                        "recv": 0,
                        "loss": 0.0,
                        "best": None,
                        "avg": 0.0,
                        "worst": 0.0,
                        "last": 0.0,
                    }

                hops[ttl]["sent"] += 1
                prev_recv = hops[ttl]["recv"]
                prev_avg = hops[ttl]["avg"]

                # Fast single packet probe: Windows ping.
                rtt_ms: float | None = None
                try:
                    cmd = ["ping", "-n", "1", "-w", "500", str(target)]
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=1.0,
                    )
                    out = result.stdout or ""
                    m = re.search(
                        r"time(?P<cmp><|=)(?P<val>\d+(?:\.\d+)?)\s*ms",
                        out,
                        flags=re.IGNORECASE,
                    )
                    if m:
                        val = float(m.group("val"))
                        rtt_ms = val
                except Exception:
                    rtt_ms = None

                try:
                    if rtt_ms is not None:
                        print(f"[MTR PROBE] Hop {ttl}: {ip} | RTT: {rtt_ms:.2f} ms")
                        hops[ttl]["recv"] = prev_recv + 1
                        hops[ttl]["ip"] = ip
                        hops[ttl]["last"] = rtt_ms

                        # Keep host stable for now.
                        hops[ttl]["host"] = hops[ttl]["host"] or target

                        if hops[ttl]["best"] is None or rtt_ms < hops[ttl]["best"]:
                            hops[ttl]["best"] = rtt_ms
                        if rtt_ms > hops[ttl]["worst"]:
                            hops[ttl]["worst"] = rtt_ms

                        recv = hops[ttl]["recv"]
                        hops[ttl]["avg"] = (
                            (prev_avg * prev_recv) + rtt_ms
                        ) / recv if recv > 0 else hops[ttl]["avg"]
                    else:
                        print(f"[MTR PROBE] Hop {ttl}: timeout")
                        hops[ttl]["ip"] = ip
                except Exception:
                    print(f"[MTR PROBE] Hop {ttl}: timeout")
                    hops[ttl]["ip"] = ip

                # Calculate loss after each probe (success or timeout).
                sent = hops[ttl]["sent"]
                recv = hops[ttl]["recv"]
                hops[ttl]["loss"] = ((sent - recv) / sent) * 100.0 if sent > 0 else 0.0

                # Convert internal stats to UI-friendly strings.
                if hops[ttl]["recv"] > 0:
                    best_val = hops[ttl]["best"]
                    hop_data = {
                        "host": hops[ttl]["host"] or target,
                        "ip": hops[ttl]["ip"],
                        "loss": hops[ttl]["loss"],
                        "sent": hops[ttl]["sent"],
                        "recv": hops[ttl]["recv"],
                        "best": "" if best_val is None else f"{best_val:.2f} ms",
                        "avg": f"{hops[ttl]['avg']:.2f} ms",
                        "worst": f"{hops[ttl]['worst']:.2f} ms",
                        "last": f"{hops[ttl]['last']:.2f} ms",
                    }
                else:
                    hop_data = {
                        "host": hops[ttl]["host"] or target,
                        "ip": hops[ttl]["ip"],
                        "loss": hops[ttl]["loss"],
                        "sent": hops[ttl]["sent"],
                        "recv": hops[ttl]["recv"],
                        "best": "",
                        "avg": "",
                        "worst": "",
                        "last": "",
                    }

                hop_updated_callback(ttl, hop_data)
        except Exception as exc:
            # Never let the UI thread crash; report an error as a 100% loss hop.
            print(f"[MTR PROBE] Hop 1: error: {exc}")
            hop_updated_callback(
                1,
                {
                    "host": target,
                    "ip": "",
                    "loss": 100.0,
                    "sent": 1,
                    "recv": 0,
                    "best": "",
                    "avg": "",
                    "worst": "",
                    "last": "",
                },
            )

        time.sleep(0.2)
