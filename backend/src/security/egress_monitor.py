"""
SENTINEL — Independent Network Egress Monitor (FR7.5).
Operational witness: samples host connection state and records NetworkEvent rows.
Not claimed as mathematical proof.
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
import struct
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import async_session_factory
from src.shared.models import NetworkEvent

logger = logging.getLogger(__name__)

# Well-known cloud inference endpoints we treat as unauthorized in Sovereign Mode.
WATCH_PORTS = {443, 80, 11434, 8001}


def _parse_ipv4_hex(addr: str) -> str:
    ip_hex, port_hex = addr.split(":")
    ip_int = int(ip_hex, 16)
    packed = struct.pack("<I", ip_int)
    return socket.inet_ntoa(packed), int(port_hex, 16)


def sample_proc_net_tcp(path: str = "/proc/net/tcp") -> list[dict]:
    events = []
    try:
        with open(path, encoding="utf-8") as handle:
            next(handle, None)
            for line in handle:
                parts = line.split()
                if len(parts) < 4:
                    continue
                dest_ip, dest_port = _parse_ipv4_hex(parts[2])
                state = parts[3]
                if dest_ip in ("0.0.0.0", "127.0.0.1"):
                    continue
                established = state == "01"
                events.append({
                    "dest_ip": dest_ip,
                    "dest_port": dest_port,
                    "protocol": "tcp",
                    "allowed": dest_port not in (443, 80) or dest_ip.startswith("10.") or dest_ip.startswith("172."),
                    "source_process": os.environ.get("HOSTNAME", "sentinel"),
                    "source_container": os.environ.get("SERVICE_ROLE", "unknown"),
                    "established": established,
                })
    except FileNotFoundError:
        logger.debug("%s not available", path)
    except Exception:
        logger.exception("Failed sampling %s", path)
    return events


async def persist_samples(db: AsyncSession, samples: list[dict]) -> int:
    written = 0
    for sample in samples:
        if not sample.get("established"):
            continue
        db.add(NetworkEvent(
            source_process=sample.get("source_process"),
            source_container=sample.get("source_container"),
            dest_ip=sample["dest_ip"],
            dest_port=sample["dest_port"],
            protocol=sample.get("protocol", "tcp"),
            allowed=bool(sample.get("allowed")),
            rule_matched="conntrack-sample",
            timestamp=datetime.now(timezone.utc),
        ))
        written += 1
    if written:
        await db.flush()
    return written


async def monitor_loop(stop_event: asyncio.Event, interval: float = 10.0) -> None:
    logger.info("Egress monitor sidecar started")
    while not stop_event.is_set():
        try:
            samples = sample_proc_net_tcp()
            async with async_session_factory() as db:
                await persist_samples(db, samples)
                await db.commit()
        except Exception:
            logger.exception("Egress monitor tick failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


async def run_sidecar() -> None:
    stop = asyncio.Event()
    await monitor_loop(stop)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_sidecar())
