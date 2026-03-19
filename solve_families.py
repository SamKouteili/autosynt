#!/usr/bin/env python3
"""Solve specific families with targeted strategies and longer timeouts."""

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


def solve_with_strategies(instance_name, strategies, timeout_per_strat=60):
    """Try multiple ltlsynt strategies on one instance."""
    tlsf_path = INSTANCES_DIR / f"{instance_name}.tlsf"
    if not tlsf_path.exists():
        return {"instance": instance_name, "status": "error"}

    best_aiger = None
    best_gates = float("inf")
    best_strat = None

    for strat_name, flags in strategies:
        start = time.time()
        try:
            result = subprocess.run(
                ["ltlsynt", f"--tlsf={tlsf_path}"] + flags,
                capture_output=True, text=True, timeout=timeout_per_strat
            )
            elapsed = time.time() - start
            output = result.stdout.strip()

            if "UNREALIZABLE" in output:
                return {"instance": instance_name, "status": "unrealizable",
                        "strategy": strat_name, "time": elapsed}
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
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass

    if best_aiger:
        return {"instance": instance_name, "status": "realizable",
                "aiger": best_aiger, "and_gates": best_gates, "strategy": best_strat}
    return {"instance": instance_name, "status": "timeout"}


def log_experiment(instance, approach, status, and_gates, elapsed, notes):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ag = and_gates if and_gates >= 0 else "N/A"
    line = f"[{ts}] instance: {instance} | approach: {approach} | status: {status} | and_gates: {ag} | time: {elapsed:.1f}s | notes: {notes}\n"
    with open(EXPERIMENTS_LOG, "a") as f:
        f.write(line)


def main():
    family_filter = sys.argv[1] if len(sys.argv) > 1 else None
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    max_workers = int(sys.argv[3]) if len(sys.argv) > 3 else 4

    with open("benchmarks/syntcomp-2025/reference.csv") as f:
        rows = list(csv.DictReader(f))

    solved = load_solutions()

    # Select instances
    to_solve = []
    for r in rows:
        inst = r["instance"]
        if inst in solved:
            continue
        if family_filter and family_filter not in r["family"]:
            continue
        signals = int(r["n_inputs"]) + int(r["n_outputs"])
        to_solve.append((signals, inst))

    to_solve.sort()

    if not to_solve:
        print(f"No unsolved instances matching filter '{family_filter}'")
        return

    # Define strategies based on expected status
    if family_filter and "unreal" in family_filter:
        strategies = [
            ("sd", ["--algo=sd", "--aiger"]),
            ("ds", ["--algo=ds", "--aiger"]),
            ("lar", ["--algo=lar", "--aiger"]),
        ]
    else:
        strategies = [
            ("lar-bwoa", ["--algo=lar", "--aiger=both+ud+dc+sub2", "--simplify=bwoa"]),
            ("sd-bwoa", ["--algo=sd", "--aiger=both+ud+dc+sub2", "--simplify=bwoa"]),
            ("ds", ["--algo=ds", "--aiger=both+ud+dc+sub2"]),
            ("acd", ["--algo=acd", "--aiger=both+ud+dc+sub2"]),
        ]

    timeout_per_strat = timeout // len(strategies)
    print(f"Solving {len(to_solve)} instances (family={family_filter}, {timeout_per_strat}s/strategy, workers={max_workers})")

    solved_count = 0
    start_time = time.time()

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(solve_with_strategies, inst, strategies, timeout_per_strat): inst
                   for _, inst in to_solve}

        for future in as_completed(futures):
            result = future.result()
            inst = result["instance"]

            if result["status"] == "realizable":
                updated = update_solution(inst, "realizable", result["aiger"],
                                          f"ltlsynt-{result['strategy']}")
                if updated:
                    solved_count += 1
                    print(f"  REALIZABLE: {inst} ({result['and_gates']} AND, strat={result['strategy']})")

            elif result["status"] == "unrealizable":
                updated = mark_unrealizable(inst, f"ltlsynt-{result['strategy']}")
                if updated:
                    solved_count += 1
                    print(f"  UNREALIZABLE: {inst} (strat={result['strategy']})")

    total = time.time() - start_time
    print(f"\nDone in {total:.1f}s: {solved_count} new solutions")


if __name__ == "__main__":
    main()
