#!/usr/bin/env python3.14
"""Attack medium-signal unsolved instances with multi-strategy approach."""

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


def solve_spot(instance_name, timeout=120):
    """Spot game approach via subprocess."""
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
        return {"status": "error", "error": (proc.stderr or "")[:200], "time": 0}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "time": timeout}
    except Exception as e:
        return {"status": "error", "error": str(e), "time": 0}


def solve_ltlsynt_multi(instance_name, timeout=120):
    """Try ltlsynt with multiple algorithm/option combos."""
    tlsf = f"{INSTANCES_DIR}/{instance_name}.tlsf"
    combos = [
        ["ltlsynt", f"--tlsf={tlsf}", "--aiger", "--decompose=yes"],
        ["ltlsynt", f"--tlsf={tlsf}", "--aiger", "--algo=lar", "--decompose=yes"],
        ["ltlsynt", f"--tlsf={tlsf}", "--aiger", "--algo=sd", "--decompose=yes"],
        ["ltlsynt", f"--tlsf={tlsf}", "--aiger", "--algo=ds"],
        ["ltlsynt", f"--tlsf={tlsf}", "--aiger", "--algo=ps", "--decompose=yes"],
    ]
    per_timeout = max(15, timeout // len(combos))

    for cmd in combos:
        algo = "-".join(c.split("=")[1] for c in cmd if c.startswith("--algo"))
        method = f"ltlsynt-{algo or 'default'}+decompose"
        t0 = time.time()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=per_timeout)
            elapsed = time.time() - t0
            output = proc.stdout.strip()
            if "UNREALIZABLE" in output:
                return {"status": "unrealizable", "and_gates": -1, "method": method,
                        "time": elapsed, "aiger": None}
            elif "REALIZABLE" in output and "UNREALIZABLE" not in output:
                parts = output.split("\n", 1)
                aiger = parts[1] if len(parts) > 1 else None
                gates = -1
                if aiger:
                    try:
                        gates = int(aiger.strip().split('\n')[0].split()[5])
                    except:
                        pass
                return {"status": "realizable", "and_gates": gates, "method": method,
                        "time": elapsed, "aiger": aiger}
        except subprocess.TimeoutExpired:
            continue
        except Exception:
            continue

    return {"status": "timeout", "time": timeout}


def solve_combined(instance_name, timeout=200):
    """Try spot then ltlsynt."""
    t0 = time.time()

    # Spot: 50% budget
    result = solve_spot(instance_name, int(timeout * 0.5))
    if result['status'] in ('realizable', 'unrealizable'):
        return instance_name, result

    # ltlsynt: remaining budget
    remaining = timeout - (time.time() - t0)
    if remaining > 20:
        result = solve_ltlsynt_multi(instance_name, int(remaining))
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

    min_sig = int(sys.argv[1]) if len(sys.argv) > 1 else 9
    max_sig = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 200

    # Prioritize families with many unsolved instances
    targets = []
    for name, info in reference.items():
        if name in solutions:
            continue
        ni, no = int(info['n_inputs']), int(info['n_outputs'])
        if min_sig <= ni + no <= max_sig:
            targets.append(name)

    targets.sort(key=lambda n: int(reference[n]['n_inputs']) + int(reference[n]['n_outputs']))
    print(f"Attacking {len(targets)} medium unsolved instances (signals {min_sig}-{max_sig}, timeout={timeout}s)")

    if not targets:
        print("Nothing to do.")
        return

    new_solved = 0
    done = 0
    workers = min(3, len(targets))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(solve_combined, name, timeout): name for name in targets}
        for future in as_completed(futures):
            name = futures[future]
            done += 1
            try:
                _, result = future.result(timeout=timeout + 30)
                log_experiment(name, result)

                if result['status'] == 'realizable':
                    if update_solution(name, 'realizable', result.get('aiger'), result.get('method', '?')):
                        new_solved += 1
                        print(f"  [R] {name}: {result.get('and_gates', -1)} gates [{result.get('time',0):.1f}s]")
                elif result['status'] == 'unrealizable':
                    if mark_unrealizable(name, result.get('method', '?')):
                        new_solved += 1
                        print(f"  [U] {name} [{result.get('time',0):.1f}s]")
                elif result['status'] == 'timeout':
                    print(f"  [T] {name}")
                else:
                    print(f"  [E] {name}: {result.get('error', '?')[:60]}")
            except Exception as e:
                print(f"  [X] {name}: {e}")

            if done % 10 == 0:
                print(f"  --- {done}/{len(targets)}, +{new_solved} new ---")

    print(f"\nDone: {done}/{len(targets)}, +{new_solved} new solutions")


if __name__ == "__main__":
    main()
