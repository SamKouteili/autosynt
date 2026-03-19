#!/usr/bin/env python3.14
"""Attack unsolved instances with known status using multiple strategies."""

import csv
import json
import sys
import time
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

ROOT = Path(__file__).resolve().parent
INSTANCES_DIR = ROOT / "benchmarks" / "syntcomp-2025" / "instances"
REFERENCE_CSV = ROOT / "benchmarks" / "syntcomp-2025" / "reference.csv"
EXPERIMENTS_LOG = ROOT / "experiments.log"
PYTHON = "/opt/homebrew/bin/python3.14"

sys.path.insert(0, str(ROOT))


def solve_with_ltlsynt(instance_name, timeout=180):
    """Try ltlsynt with multiple strategies."""
    tlsf = f"{INSTANCES_DIR}/{instance_name}.tlsf"
    strategies = [
        ["ltlsynt", f"--tlsf={tlsf}", "--aiger", "--decompose=yes"],
        ["ltlsynt", f"--tlsf={tlsf}", "--aiger", "--algo=lar", "--decompose=yes"],
        ["ltlsynt", f"--tlsf={tlsf}", "--aiger", "--algo=sd", "--decompose=yes"],
        ["ltlsynt", f"--tlsf={tlsf}", "--aiger", "--algo=ds", "--decompose=yes"],
    ]
    per_timeout = timeout // len(strategies)

    for strat in strategies:
        algo = "ltlsynt-" + (strat[3].split("=")[1] if len(strat) > 3 and strat[3].startswith("--algo") else "default")
        t0 = time.time()
        try:
            proc = subprocess.run(strat, capture_output=True, text=True, timeout=per_timeout)
            elapsed = time.time() - t0
            output = proc.stdout.strip()
            if "UNREALIZABLE" in output:
                return {"status": "unrealizable", "and_gates": -1, "method": algo + "+decompose",
                        "time": elapsed, "aiger": None}
            elif "REALIZABLE" in output:
                parts = output.split("\n", 1)
                aiger = parts[1] if len(parts) > 1 else None
                gates = -1
                if aiger:
                    try:
                        gates = int(aiger.strip().split('\n')[0].split()[5])
                    except:
                        pass
                return {"status": "realizable", "and_gates": gates, "method": algo + "+decompose",
                        "time": elapsed, "aiger": aiger}
        except subprocess.TimeoutExpired:
            continue
        except Exception:
            continue

    return {"status": "timeout", "time": timeout}


def solve_with_spot(instance_name, timeout=180):
    """Try spot game approach via subprocess."""
    script = f'''
import sys, json
sys.path.insert(0, "{ROOT}")
from library.synth import solve_instance
result = solve_instance("{INSTANCES_DIR}/{instance_name}.tlsf", timeout={timeout})
print(json.dumps(result))
'''
    try:
        proc = subprocess.run(
            [PYTHON, "-c", script],
            capture_output=True, text=True, timeout=timeout + 15, cwd=str(ROOT)
        )
        if proc.returncode == 0 and proc.stdout.strip():
            lines = proc.stdout.strip().split('\n')
            return json.loads(lines[-1])
        return {"status": "error", "error": proc.stderr[:200] if proc.stderr else "?", "time": 0}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "time": timeout}
    except Exception as e:
        return {"status": "error", "error": str(e), "time": 0}


def solve_combined(instance_name, timeout=240):
    """Try spot first, then ltlsynt if spot fails."""
    t0 = time.time()

    # Try spot with 60% of budget
    spot_timeout = int(timeout * 0.6)
    result = solve_with_spot(instance_name, spot_timeout)
    if result['status'] in ('realizable', 'unrealizable'):
        return instance_name, result

    # Try ltlsynt with remaining budget
    remaining = timeout - (time.time() - t0)
    if remaining > 20:
        result = solve_with_ltlsynt(instance_name, int(remaining))
        if result['status'] in ('realizable', 'unrealizable'):
            return instance_name, result

    return instance_name, {"status": "timeout", "time": time.time() - t0}


def log_experiment(instance, result):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = result['status']
    gates = result.get('and_gates', -1)
    gates_str = str(gates) if gates and gates >= 0 else 'N/A'
    elapsed = result.get('time', 0)
    method = result.get('method', '?')
    line = f"[{ts}] instance: {instance} | approach: {method} | status: {status} | and_gates: {gates_str} | time: {elapsed:.1f}s | notes: {method}\n"
    with open(EXPERIMENTS_LOG, "a") as f:
        f.write(line)


def main():
    from library.solutions import load_solutions, update_solution, mark_unrealizable

    with open(REFERENCE_CSV) as f:
        reference = {r['instance']: r for r in csv.DictReader(f)}
    solutions = load_solutions()

    # Find unsolved with known status
    targets = []
    for name, info in reference.items():
        if name in solutions:
            continue
        if info['status'] in ('realizable', 'unrealizable'):
            ni, no = int(info['n_inputs']), int(info['n_outputs'])
            targets.append((name, ni + no))

    targets.sort(key=lambda x: x[1])
    names = [t[0] for t in targets]
    print(f"Attacking {len(names)} known-status unsolved instances")

    if not names:
        print("Nothing to do.")
        return

    new_solved = 0
    done = 0
    workers = min(3, len(names))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(solve_combined, name, 240): name for name in names}
        for future in as_completed(futures):
            name = futures[future]
            done += 1
            try:
                _, result = future.result(timeout=270)
                log_experiment(name, result)

                if result['status'] == 'realizable':
                    if update_solution(name, 'realizable', result.get('aiger'), result.get('method', '?')):
                        new_solved += 1
                        print(f"  [R] {name}: {result.get('and_gates', -1)} gates [{result.get('time',0):.1f}s]")
                    else:
                        print(f"  [=] {name}: already solved")
                elif result['status'] == 'unrealizable':
                    if mark_unrealizable(name, result.get('method', '?')):
                        new_solved += 1
                        print(f"  [U] {name} [{result.get('time',0):.1f}s]")
                    else:
                        print(f"  [=] {name}: already solved")
                else:
                    print(f"  [T] {name}")
            except Exception as e:
                print(f"  [X] {name}: {e}")

    print(f"\nDone: {done}/{len(names)}, +{new_solved} new solutions")


if __name__ == "__main__":
    main()
