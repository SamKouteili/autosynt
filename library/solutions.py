"""Solution tracking for LTL synthesis — JSON index + individual AIGER files."""

import fcntl
import json
from datetime import datetime, timezone
from pathlib import Path

SOLUTIONS_DIR = Path(__file__).resolve().parent.parent / "solutions"
SOLUTIONS_FILE = Path(__file__).resolve().parent.parent / "best-solutions.json"
_LOCK_FILE = SOLUTIONS_FILE.with_suffix(".lock")


def _ensure_dirs():
    SOLUTIONS_DIR.mkdir(exist_ok=True)


def load_solutions() -> dict:
    """Load all best solutions from JSON index.

    Returns dict: {instance: {status, and_gates, method, timestamp, aiger_file}}
    """
    if not SOLUTIONS_FILE.exists():
        return {}
    text = SOLUTIONS_FILE.read_text().strip()
    if not text:
        return {}
    return json.loads(text)


def save_solutions(solutions: dict) -> None:
    """Save solutions index to JSON."""
    SOLUTIONS_FILE.write_text(json.dumps(solutions, indent=2) + "\n")


def update_solution(instance: str, status: str, aiger_text: str | None, method: str) -> bool:
    """Update solution for an instance if it improves on current best.

    Improvement means:
    - New status determination (was unknown, now realizable/unrealizable)
    - Fewer AND gates for a realizable instance

    Args:
        instance: instance name (without .tlsf)
        status: 'realizable', 'unrealizable', or 'unknown'
        aiger_text: AIGER circuit text (for realizable), None for unrealizable
        method: description of approach used

    Returns True if solution was updated.
    """
    _ensure_dirs()

    # Count AND gates if we have AIGER (before locking)
    and_gates = -1
    if aiger_text:
        from library.circuits import aiger_stats  # noqa: reportMissingImports
        stats = aiger_stats(aiger_text)
        and_gates = stats["and_gates"]

    # Use file lock for concurrent safety
    with open(_LOCK_FILE, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            solutions = load_solutions()
            current = solutions.get(instance)

            # Check if this is an improvement
            if current is not None:
                if current["status"] in ("realizable", "unrealizable") and status == "unknown":
                    return False
                if current["status"] == status == "realizable":
                    if current["and_gates"] >= 0 and and_gates >= current["and_gates"]:
                        return False
                elif current["status"] == status:
                    return False

            # Save AIGER file
            aiger_file = None
            if aiger_text:
                aiger_file = f"{instance}.aag"
                (SOLUTIONS_DIR / aiger_file).write_text(aiger_text)

            solutions[instance] = {
                "status": status,
                "and_gates": and_gates,
                "method": method,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "aiger_file": aiger_file,
            }
            save_solutions(solutions)
            return True
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def mark_unrealizable(instance: str, method: str) -> bool:
    """Record that an instance is unrealizable."""
    return update_solution(instance, "unrealizable", None, method)


def get_best_results() -> dict:
    """Quick lookup: {instance: {status, and_gates}}."""
    solutions = load_solutions()
    return {
        name: {"status": sol["status"], "and_gates": sol["and_gates"]}
        for name, sol in solutions.items()
    }
