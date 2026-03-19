#!/usr/bin/env python3
"""Batch solver: run ltlsynt on many instances in parallel."""

import csv
import sys
import time
import signal
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# Add library to path
sys.path.insert(0, str(Path(__file__).parent))
from library.solutions import update_solution, mark_unrealizable, load_solutions
from library.circuits import aiger_stats

INSTANCES_DIR = Path("benchmarks/syntcomp-2025/instances")
EXPERIMENTS_LOG = Path("experiments.log")

def solve_one(instance_name, timeout=60):
    """Run ltlsynt on one instance. Returns result dict."""
    tlsf_path = INSTANCES_DIR / f"{instance_name}.tlsf"
    if not tlsf_path.exists():
        return {"instance": instance_name, "status": "error", "error": "file not found"}

    start = time.time()
    try:
        result = subprocess.run(
            ["ltlsynt", f"--tlsf={tlsf_path}", "--aiger"],
            capture_output=True, text=True, timeout=timeout
        )
        elapsed = time.time() - start
        output = result.stdout.strip()

        if "REALIZABLE" in output and "UNREALIZABLE" not in output:
            parts = output.split("\n", 1)
            aiger = parts[1] if len(parts) > 1 else None
            and_gates = -1
            if aiger:
                try:
                    stats = aiger_stats(aiger)
                    and_gates = stats["and_gates"]
                except:
                    pass
            return {
                "instance": instance_name,
                "status": "realizable",
                "aiger": aiger,
                "and_gates": and_gates,
                "time": elapsed,
            }
        elif "UNREALIZABLE" in output:
            return {
                "instance": instance_name,
                "status": "unrealizable",
                "aiger": None,
                "and_gates": -1,
                "time": elapsed,
            }
        else:
            return {
                "instance": instance_name,
                "status": "unknown",
                "error": output[:200],
                "time": elapsed,
            }
    except subprocess.TimeoutExpired:
        return {
            "instance": instance_name,
            "status": "timeout",
            "time": timeout,
        }
    except Exception as e:
        return {
            "instance": instance_name,
            "status": "error",
            "error": str(e),
            "time": time.time() - start,
        }


def log_experiment(instance, approach, status, and_gates, elapsed, notes):
    """Append to experiments.log."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ag = and_gates if and_gates >= 0 else "N/A"
    line = f"[{ts}] instance: {instance} | approach: {approach} | status: {status} | and_gates: {ag} | time: {elapsed:.1f}s | notes: {notes}\n"
    with open(EXPERIMENTS_LOG, "a") as f:
        f.write(line)


def main():
    if len(sys.argv) < 2:
        print("Usage: solve_batch.py <category> [timeout] [max_workers]")
        print("Categories: unrealizable, realizable_small, realizable_medium, tiny_unknown, all_small, unknown_medium, family:<name>")
        sys.exit(1)

    category = sys.argv[1]
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    max_workers = int(sys.argv[3]) if len(sys.argv) > 3 else 8

    # Load reference data
    with open("benchmarks/syntcomp-2025/reference.csv") as f:
        rows = list(csv.DictReader(f))

    # Load already-solved instances
    solved = load_solutions()
    solved_names = set(solved.keys())

    # Select instances based on category
    instances = []
    if category == "unrealizable":
        instances = [r["instance"] for r in rows if r["status"] == "unrealizable"]
    elif category == "realizable_small":
        instances = [r["instance"] for r in rows
                     if r["status"] == "realizable" and int(r["ref_size"]) <= 100
                     and int(r["n_inputs"]) + int(r["n_outputs"]) <= 10]
    elif category == "realizable_medium":
        instances = [r["instance"] for r in rows
                     if r["status"] == "realizable"
                     and (int(r["ref_size"]) > 100 or int(r["ref_size"]) <= 0)
                     and int(r["n_inputs"]) + int(r["n_outputs"]) <= 15]
    elif category == "tiny_unknown":
        instances = [r["instance"] for r in rows
                     if r["status"] == "unknown"
                     and int(r["n_inputs"]) + int(r["n_outputs"]) <= 4]
    elif category == "all_small":
        instances = [r["instance"] for r in rows
                     if int(r["n_inputs"]) + int(r["n_outputs"]) <= 6]
    elif category == "unknown_medium":
        instances = [r["instance"] for r in rows
                     if r["status"] == "unknown"
                     and int(r["n_inputs"]) + int(r["n_outputs"]) <= 8]
    elif category.startswith("family:"):
        fam = category[7:]
        instances = [r["instance"] for r in rows if r["family"] == fam]
    elif category == "all_realizable":
        instances = [r["instance"] for r in rows if r["status"] == "realizable"]
    elif category == "all_known":
        instances = [r["instance"] for r in rows if r["status"] != "unknown"]
    else:
        print(f"Unknown category: {category}")
        sys.exit(1)

    # Filter out already solved (unless we might improve)
    to_solve = []
    for inst in instances:
        if inst not in solved_names:
            to_solve.append(inst)
        elif solved[inst]["status"] == "realizable" and category in ("realizable_small", "realizable_medium", "all_realizable"):
            # Maybe we can improve gate count - skip for now in baseline
            pass

    if not to_solve:
        print(f"All {len(instances)} instances in '{category}' already solved!")
        return

    print(f"Solving {len(to_solve)} instances (category={category}, timeout={timeout}s, workers={max_workers})")

    solved_count = 0
    real_count = 0
    unreal_count = 0
    timeout_count = 0

    start_time = time.time()

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(solve_one, inst, timeout): inst for inst in to_solve}

        for future in as_completed(futures):
            result = future.result()
            inst = result["instance"]
            elapsed = result.get("time", 0)

            if result["status"] == "realizable":
                updated = update_solution(inst, "realizable", result["aiger"], f"ltlsynt-baseline-{timeout}s")
                if updated:
                    solved_count += 1
                    real_count += 1
                    print(f"  REALIZABLE: {inst} ({result['and_gates']} AND gates, {elapsed:.1f}s)")
                log_experiment(inst, f"ltlsynt-{timeout}s", "realizable", result["and_gates"], elapsed, "baseline ltlsynt")

            elif result["status"] == "unrealizable":
                updated = mark_unrealizable(inst, f"ltlsynt-baseline-{timeout}s")
                if updated:
                    solved_count += 1
                    unreal_count += 1
                    print(f"  UNREALIZABLE: {inst} ({elapsed:.1f}s)")
                log_experiment(inst, f"ltlsynt-{timeout}s", "unrealizable", -1, elapsed, "baseline ltlsynt")

            elif result["status"] == "timeout":
                timeout_count += 1
                log_experiment(inst, f"ltlsynt-{timeout}s", "timeout", -1, timeout, f"timed out after {timeout}s")

            else:
                log_experiment(inst, f"ltlsynt-{timeout}s", "error", -1, elapsed, result.get("error", "unknown error")[:100])

    total_time = time.time() - start_time
    print(f"\nDone in {total_time:.1f}s: {solved_count} new solutions ({real_count} realizable, {unreal_count} unrealizable), {timeout_count} timeouts")


if __name__ == "__main__":
    main()
