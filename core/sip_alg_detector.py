"""SIP ALG detector: receiver + sender threads, UDP loopback compare (fixed 192.81.82.254 target)."""

from __future__ import annotations

import re
import socket
import threading
import time

from PySide6.QtCore import QThread, Signal

TARGET_HOST = "192.81.82.254"
TARGET_PORT = 5060
RECV_BIND = ("0.0.0.0", 5060)
_RECEIVER_DEADLINE_SEC = 5.0
_SENDER_DELAY_SEC = 0.5

_IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
_VIA_SENT_BY = re.compile(
    r"Via:\s*SIP/\S+\s+([^;\s]+)",
    re.IGNORECASE,
)
_CONTACT_HOST = re.compile(
    r"<sip:[^@>]+@(\d{1,3}(?:\.\d{1,3}){3})",
    re.IGNORECASE,
)
_SDP_C = re.compile(r"^c\s*=\s*IN\s+IP4\s+(\S+)", re.IGNORECASE | re.MULTILINE)
_SDP_M = re.compile(r"^m=audio\s+(\d+)", re.IGNORECASE | re.MULTILINE)


def _local_ip_toward_target() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((TARGET_HOST, TARGET_PORT))
        return s.getsockname()[0]
    finally:
        s.close()


def _build_invite_packet(local_ip: str) -> bytes:
    sdp = (
        f"v=0\r\n"
        f"o=- 123456 123456 IN IP4 {local_ip}\r\n"
        f"s=-\r\n"
        f"c=IN IP4 {local_ip}\r\n"
        f"t=0 0\r\n"
        f"m=audio 49170 RTP/AVP 0\r\n"
    )
    body = sdp.encode("utf-8")
    clen = len(body)
    headers = (
        f"INVITE sip:7635551213@{TARGET_HOST} SIP/2.0\r\n"
        f"Via: SIP/2.0/UDP {local_ip}:5060;branch=z9hG4bK123456\r\n"
        f"Max-Forwards: 70\r\n"
        f'From: "Test" <sip:test@{local_ip}>;tag=12345\r\n'
        f"To: <sip:7635551213@{TARGET_HOST}>\r\n"
        f"Call-ID: 123456789\r\n"
        f"CSeq: 10 INVITE\r\n"
        f"Contact: <sip:test@{local_ip}>\r\n"
        f"User-Agent: Grandstream HT801 1.0.0.85\r\n"
        f"Content-Type: application/sdp\r\n"
        f"Content-Length: {clen}\r\n"
        f"\r\n"
    )
    return headers.encode("ascii", errors="strict") + body


def _split_message(raw: str) -> tuple[str, str]:
    if "\r\n\r\n" in raw:
        h, b = raw.split("\r\n\r\n", 1)
        return h, b
    if "\n\n" in raw:
        h, b = raw.split("\n\n", 1)
        return h, b
    return raw, ""


def _parse_via_ip_port(hdrs: str) -> tuple[str | None, int | None]:
    for line in hdrs.splitlines():
        if not line.lower().startswith("via:"):
            continue
        if "z9hG4bK123456" not in line:
            continue
        m = _VIA_SENT_BY.match(line.strip())
        if not m:
            continue
        sent = m.group(1).strip().strip('"')
        if ":" in sent:
            host, p = sent.rsplit(":", 1)
            if _IPV4_RE.fullmatch(host):
                try:
                    return host, int(p)
                except ValueError:
                    return host, None
        if _IPV4_RE.fullmatch(sent):
            return sent, 5060
    return None, None


def _parse_contact_ip(hdrs: str) -> str | None:
    for line in hdrs.splitlines():
        if line.lower().startswith("contact:"):
            m = _CONTACT_HOST.search(line)
            if m:
                return m.group(1)
    return None


def _parse_sdp_c_and_m(sdp: str) -> tuple[str | None, int | None]:
    cm = _SDP_C.search(sdp)
    mm = _SDP_M.search(sdp)
    c_ip = cm.group(1).strip() if cm else None
    m_port = int(mm.group(1)) if mm else None
    return c_ip, m_port


def _extract_compare_fields(
    packet_bytes: bytes,
) -> tuple[str | None, int | None, str | None, str | None, int | None]:
    try:
        text = packet_bytes.decode("utf-8", errors="replace")
    except Exception:
        return None, None, None, None, None
    hdrs, body = _split_message(text)
    vh, vp = _parse_via_ip_port(hdrs)
    ctip = _parse_contact_ip(hdrs)
    c_ip, m_port = _parse_sdp_c_and_m(body)
    return vh, vp, ctip, c_ip, m_port


def _unable(sub: str) -> dict[str, str]:
    return {
        "state": "orange",
        "headline": "UNABLE TO DETERMINE",
        "subtext": sub,
    }


def _detected(sub: str) -> dict[str, str]:
    return {"state": "red", "headline": "DETECTED", "subtext": sub}


def _not_detected(sub: str) -> dict[str, str]:
    return {"state": "green", "headline": "NOT DETECTED", "subtext": sub}


class _RecvState:
    __slots__ = ("lock", "data", "error")

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.data: bytes | None = None
        self.error: str | None = None


def _is_sip_datagram(data: bytes) -> bool:
    return b"SIP/2.0" in data or (b"INVITE" in data and b"sip:" in data.lower())


def _receiver_thread(state: _RecvState) -> None:
    sock: socket.socket | None = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(RECV_BIND)
        deadline = time.monotonic() + _RECEIVER_DEADLINE_SEC
        while time.monotonic() < deadline:
            sock.settimeout(max(0.02, deadline - time.monotonic()))
            try:
                data, _ = sock.recvfrom(65535)
                if _is_sip_datagram(data):
                    with state.lock:
                        state.data = data
                    return
            except TimeoutError:
                continue
            except socket.timeout:
                continue
    except OSError as e:
        with state.lock:
            state.error = str(e)
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def _sender_thread(packet: bytes) -> None:
    sock: socket.socket | None = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(packet, (TARGET_HOST, TARGET_PORT))
    except OSError:
        pass
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def run_sip_alg_detection() -> dict[str, str]:
    try:
        local_ip = _local_ip_toward_target()
    except OSError:
        return _unable("Could not determine local IP (socket error).")

    original = _build_invite_packet(local_ip)

    ov_via_ip, ov_via_port, ov_ct_ip, ov_sdp_c, ov_sdp_m = _extract_compare_fields(
        original
    )
    if ov_via_ip != local_ip or ov_via_port != 5060:
        return _unable("Internal INVITE build mismatch.")
    if ov_ct_ip != local_ip or ov_sdp_c != local_ip or ov_sdp_m != 49170:
        return _unable("Internal INVITE build mismatch.")

    rstate = _RecvState()
    t_recv = threading.Thread(target=_receiver_thread, args=(rstate,), daemon=True)
    t_recv.start()
    time.sleep(_SENDER_DELAY_SEC)
    t_send = threading.Thread(target=_sender_thread, args=(original,), daemon=True)
    t_send.start()
    t_send.join()
    t_recv.join()

    with rstate.lock:
        err = rstate.error
        received = rstate.data

    if err is not None:
        return _unable(f"Receiver could not bind or listen on UDP 5060 ({err}).")

    if received is None:
        return _unable("No packet received within timeout (loopback or firewall).")

    if received == original:
        return _not_detected("Received packet matches the original INVITE exactly.")

    rv_via_ip, rv_via_port, rv_ct_ip, rv_sdp_c, rv_sdp_m = _extract_compare_fields(
        received
    )

    if rv_via_ip != ov_via_ip or rv_via_port != ov_via_port:
        return _detected("Via IP or port differs from the original packet.")

    if rv_ct_ip != ov_ct_ip:
        return _detected("Contact header IP differs from the original packet.")

    if rv_sdp_c != ov_sdp_c:
        return _detected("SDP c= IN IP4 address differs from the original packet.")

    if rv_sdp_m != ov_sdp_m:
        return _detected("SDP m= audio port differs from the original packet.")

    return _detected("Packet differs from original (headers or body modified).")


class SipAlgDetector(QThread):
    result_signal = Signal(dict)
    finished_signal = Signal()

    def run(self) -> None:
        try:
            try:
                out = run_sip_alg_detection()
            except Exception:
                out = _unable("No packet received within timeout (loopback or firewall).")
            self.result_signal.emit(out)
        finally:
            self.finished_signal.emit()
