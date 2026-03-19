#!/usr/bin/env python3
"""Multi-strategy solver: tries multiple ltlsynt configurations per instance."""

import csv
import sys
import time
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from library.solutions import update_solution, mark_unrealizable, load_solutions
from library.circuits import aiger_stats

INSTANCES_DIR = Path("benchmarks/syntcomp-2025/instances")
EXPERIMENTS_LOG = Path("experiments.log")

STRATEGIES = [
    ("lar", ["--algo=lar"]),
    ("sd", ["--algo=sd"]),
    ("ds", ["--algo=ds"]),
    ("ps", ["--algo=ps"]),
    ("acd", ["--algo=acd"]),
]


def solve_multi(instance_name, timeout=120):
    """Try multiple ltlsynt strategies on one instance."""
    tlsf_path = INSTANCES_DIR / f"{instance_name}.tlsf"
    if not tlsf_path.exists():
        return {"instance": instance_name, "status": "error"}

    per_strat_timeout = max(10, timeout // len(STRATEGIES))
    best_aiger = None
    best_gates = float("inf")
    best_strat = None
    is_unrealizable = False

    for strat_name, flags in STRATEGIES:
        remaining = timeout - (time.time() - time.time())  # reset per strategy
        start = time.time()
        try:
            result = subprocess.run(
                ["ltlsynt", f"--tlsf={tlsf_path}", "--aiger=both+ud+dc+sub2",
                 "--simplify=bwoa"] + flags,
                capture_output=True, text=True, timeout=per_strat_timeout
            )
            elapsed = time.time() - start
            output = result.stdout.strip()

            if "UNREALIZABLE" in output:
                is_unrealizable = True
                best_strat = strat_name
                break
            elif "REALIZABLE" in output:
                parts = output.split("\n", 1)
                aiger = parts[1] if len(parts) > 1 else None
                if aiger:
                    stats = aiger_stats(aiger)
                    gates = stats["and_gates"]
                    if gates < best_gates:
                        best_gates = gates
                        best_aiger = aiger
                        best_strat = strat_name
                # If we found a solution, try remaining strategies for smaller circuits
                # but with shorter timeouts
                per_strat_timeout = min(per_strat_timeout, max(5, int(elapsed * 2)))
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass

    if is_unrealizable:
        return {"instance": instance_name, "status": "unrealizable", "strategy": best_strat}
    elif best_aiger:
        return {
            "instance": instance_name, "status": "realizable",
            "aiger": best_aiger, "and_gates": best_gates, "strategy": best_strat
        }
    else:
        return {"instance": instance_name, "status": "timeout"}


def log_experiment(instance, approach, status, and_gates, elapsed, notes):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ag = and_gates if and_gates >= 0 else "N/A"
    line = f"[{ts}] instance: {instance} | approach: {approach} | status: {status} | and_gates: {ag} | time: {elapsed:.1f}s | notes: {notes}\n"
    with open(EXPERIMENTS_LOG, "a") as f:
        f.write(line)


def main():
    if len(sys.argv) < 2:
        print("Usage: solve_multi.py <max_signals> [timeout] [max_workers]")
        sys.exit(1)

    max_signals = int(sys.argv[1])
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    max_workers = int(sys.argv[3]) if len(sys.argv) > 3 else 4

    with open("benchmarks/syntcomp-2025/reference.csv") as f:
        rows = list(csv.DictReader(f))

    solved = load_solutions()
    to_solve = []
    for r in rows:
        inst = r["instance"]
        signals = int(r["n_inputs"]) + int(r["n_outputs"])
        if signals <= max_signals and inst not in solved:
            to_solve.append((signals, inst))

    to_solve.sort()  # Smallest first

    if not to_solve:
        print(f"No unsolved instances with <= {max_signals} signals!")
        return

    print(f"Multi-strategy solving {len(to_solve)} instances (max_signals={max_signals}, timeout={timeout}s, workers={max_workers})")

    solved_count = 0
    start_time = time.time()

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(solve_multi, inst, timeout): inst for _, inst in to_solve}

        for future in as_completed(futures):
            result = future.result()
            inst = result["instance"]

            if result["status"] == "realizable":
                updated = update_solution(inst, "realizable", result["aiger"],
                                          f"ltlsynt-multi-{result['strategy']}")
                if updated:
                    solved_count += 1
                    print(f"  REALIZABLE: {inst} ({result['and_gates']} AND, strat={result['strategy']})")
                log_experiment(inst, f"multi-{result['strategy']}", "realizable",
                               result["and_gates"], 0, f"strategy={result['strategy']}")

            elif result["status"] == "unrealizable":
                updated = mark_unrealizable(inst, f"ltlsynt-multi-{result['strategy']}")
                if updated:
                    solved_count += 1
                    print(f"  UNREALIZABLE: {inst} (strat={result['strategy']})")
                log_experiment(inst, f"multi-{result['strategy']}", "unrealizable", -1, 0,
                               f"strategy={result['strategy']}")

    total = time.time() - start_time
    print(f"\nDone in {total:.1f}s: {solved_count} new solutions")


if __name__ == "__main__":
    main()
