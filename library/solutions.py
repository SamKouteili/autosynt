"""Compressed storage for best solutions. Bit-packs configurations + lzma for ~1200x compression."""

import gzip
import json
import lzma
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SOLUTIONS_FILE = Path(__file__).resolve().parent.parent / "best-solutions.bin"


def load_solutions() -> dict:
    """Load best solutions from compressed binary file.

    Returns dict: {instance_name: {cost, configuration, method, timestamp}}
    where configuration is a list of signed literals [1, -2, 3, ...].
    Returns empty dict if file doesn't exist.
    """
    if not SOLUTIONS_FILE.exists():
        return {}

    data = SOLUTIONS_FILE.read_bytes()

    # Format: 4 bytes meta length (big endian) | gzip meta json | lzma packed bits
    meta_len = int.from_bytes(data[:4], "big")
    meta = json.loads(gzip.decompress(data[4 : 4 + meta_len]))
    packed = np.frombuffer(lzma.decompress(data[4 + meta_len :]), dtype=np.uint8)
    bits = np.unpackbits(packed)

    result = {}
    for name, info in meta.items():
        offset, length = info["offset"], info["length"]
        signs = bits[offset : offset + length]
        config = [(i + 1) if s else -(i + 1) for i, s in enumerate(signs)]
        result[name] = {
            "cost": info["cost"],
            "configuration": config,
            "method": info.get("method", ""),
            "timestamp": info.get("timestamp", ""),
        }
    return result


def save_solutions(solutions: dict) -> None:
    """Save all solutions to compressed binary file."""
    meta = {}
    all_signs = []
    for name, sol in solutions.items():
        config = sol["configuration"]
        signs = [1 if x > 0 else 0 for x in config]
        meta[name] = {
            "cost": sol["cost"],
            "offset": len(all_signs),
            "length": len(config),
            "method": sol.get("method", ""),
            "timestamp": sol.get("timestamp", ""),
        }
        all_signs.extend(signs)

    packed = np.packbits(np.array(all_signs, dtype=np.uint8)).tobytes()
    meta_gz = gzip.compress(json.dumps(meta).encode(), compresslevel=9)
    bits_lzma = lzma.compress(packed, preset=9)

    SOLUTIONS_FILE.write_bytes(
        len(meta_gz).to_bytes(4, "big") + meta_gz + bits_lzma
    )


def update_solution(instance: str, cost: int, configuration: list[int], method: str) -> bool:
    """Update solution for an instance if it improves on the current best.

    Returns True if the solution was updated (new best found).
    """
    solutions = load_solutions()
    current = solutions.get(instance)
    if current is not None and current["cost"] <= cost:
        return False

    solutions[instance] = {
        "cost": cost,
        "configuration": configuration,
        "method": method,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    save_solutions(solutions)
    return True


def get_best_costs() -> dict[str, int]:
    """Return {instance_name: best_cost} for all solved instances."""
    if not SOLUTIONS_FILE.exists():
        return {}
    data = SOLUTIONS_FILE.read_bytes()
    meta_len = int.from_bytes(data[:4], "big")
    meta = json.loads(gzip.decompress(data[4 : 4 + meta_len]))
    return {name: info["cost"] for name, info in meta.items()}
