#!/usr/bin/env python3
"""Optimize existing solutions by re-solving with better ltlsynt options."""

import csv
import sys
import time
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from library.solutions import update_solution, load_solutions
from library.circuits import aiger_stats

INSTANCES_DIR = Path("benchmarks/syntcomp-2025/instances")
EXPERIMENTS_LOG = Path("experiments.log")


def optimize_one(instance_name, timeout=120):
    """Try ltlsynt with optimization flags."""
    tlsf_path = INSTANCES_DIR / f"{instance_name}.tlsf"
    if not tlsf_path.exists():
        return {"instance": instance_name, "status": "error", "results": []}

    configs = [
        ("bwoa-sat+both", ["--simplify=bwoa-sat", "--aiger=both+ud+dc+sub2"]),
        ("bisim-sat+both", ["--simplify=bisim-sat", "--aiger=both+ud+dc+sub2"]),
        ("sat+isop", ["--simplify=sat", "--aiger=isop+ud+dc+sub2"]),
    ]

    best_aiger = None
    best_gates = float("inf")
    best_config = None
    results = []

    per_config_timeout = timeout // len(configs)

    for config_name, flags in configs:
        start = time.time()
        try:
            result = subprocess.run(
                ["ltlsynt", f"--tlsf={tlsf_path}"] + flags,
                capture_output=True, text=True, timeout=per_config_timeout
            )
            elapsed = time.time() - start
            output = result.stdout.strip()

            if "REALIZABLE" in output and "UNREALIZABLE" not in output:
                parts = output.split("\n", 1)
                aiger = parts[1] if len(parts) > 1 else None
                if aiger:
                    stats = aiger_stats(aiger)
                    gates = stats["and_gates"]
                    results.append({"config": config_name, "gates": gates, "time": elapsed})
                    if gates < best_gates:
                        best_gates = gates
                        best_aiger = aiger
                        best_config = config_name
        except subprocess.TimeoutExpired:
            results.append({"config": config_name, "gates": -1, "time": per_config_timeout, "timeout": True})
        except Exception as e:
            results.append({"config": config_name, "gates": -1, "error": str(e)})

    return {
        "instance": instance_name,
        "status": "realizable" if best_aiger else "no_improvement",
        "aiger": best_aiger,
        "and_gates": best_gates if best_gates < float("inf") else -1,
        "config": best_config,
        "results": results,
    }


def log_experiment(instance, approach, status, and_gates, elapsed, notes):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ag = and_gates if and_gates >= 0 else "N/A"
    line = f"[{ts}] instance: {instance} | approach: {approach} | status: {status} | and_gates: {ag} | time: {elapsed:.1f}s | notes: {notes}\n"
    with open(EXPERIMENTS_LOG, "a") as f:
        f.write(line)


def main():
    timeout = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    max_workers = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    min_gates = int(sys.argv[3]) if len(sys.argv) > 3 else 1  # only optimize if current >= this

    solutions = load_solutions()

    # Find realizable solutions that might be improvable
    to_optimize = []
    for inst, sol in solutions.items():
        if sol["status"] == "realizable" and sol["and_gates"] >= min_gates:
            to_optimize.append((sol["and_gates"], inst))

    to_optimize.sort(reverse=True)  # Biggest circuits first (most room for improvement)

    if not to_optimize:
        print("No instances to optimize!")
        return

    print(f"Optimizing {len(to_optimize)} instances (timeout={timeout}s, workers={max_workers})")

    improved = 0
    total_saved = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(optimize_one, inst, timeout): (inst, gates)
                   for gates, inst in to_optimize}

        for future in as_completed(futures):
            inst, old_gates = futures[future]
            result = future.result()

            if result["status"] == "realizable" and result["and_gates"] < old_gates:
                updated = update_solution(inst, "realizable", result["aiger"],
                                          f"ltlsynt-{result['config']}")
                if updated:
                    improved += 1
                    saved = old_gates - result["and_gates"]
                    total_saved += saved
                    print(f"  IMPROVED: {inst} {old_gates} -> {result['and_gates']} AND gates (-{saved}, config={result['config']})")
                    log_experiment(inst, f"ltlsynt-optimize-{result['config']}", "realizable",
                                  result["and_gates"], sum(r.get("time", 0) for r in result["results"]),
                                  f"improved from {old_gates} to {result['and_gates']} AND gates")

    print(f"\nDone: {improved} improved, {total_saved} total AND gates saved")


if __name__ == "__main__":
    main()
