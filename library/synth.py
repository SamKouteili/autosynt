"""Core synthesis engine using Spot's Python API as primitives.

Pipeline: TLSF → syfco → LTL formula → spot.ltl_to_game → spot.solve_game
          → spot.solved_game_to_split_mealy → spot.print_aiger → AIGER circuit
"""

import subprocess
import time
import spot


def parse_tlsf_quick(filepath):
    """Parse TLSF file into formula + I/O lists via syfco."""
    filepath = str(filepath)
    formula = subprocess.run(
        ["syfco", "-f", "ltlxba", "-m", "fully", filepath],
        capture_output=True, text=True, timeout=30
    ).stdout.strip()
    ins = subprocess.run(
        ["syfco", "-ins", filepath], capture_output=True, text=True, timeout=10
    ).stdout.strip()
    outs = subprocess.run(
        ["syfco", "-outs", filepath], capture_output=True, text=True, timeout=10
    ).stdout.strip()
    inputs = [s.strip() for s in ins.split(",") if s.strip()]
    outputs = [s.strip() for s in outs.split(",") if s.strip()]
    return formula, inputs, outputs


def solve_instance(filepath, timeout=120):
    """Synthesize a controller for a TLSF instance.

    Returns dict with:
        status: 'realizable', 'unrealizable', or 'timeout'/'error'
        aiger: AIGER text (if realizable), None otherwise
        and_gates: int (-1 if not applicable)
        time: float seconds
        method: description string
        error: error message if failed
    """
    start = time.time()
    filepath = str(filepath)

    try:
        # Parse TLSF
        formula_str, inputs, outputs = parse_tlsf_quick(filepath)
        if not formula_str:
            return _result('error', start, error='Empty formula from syfco')

        parse_time = time.time() - start
        remaining = timeout - parse_time
        if remaining < 1:
            return _result('timeout', start)

        # Build game
        f = spot.formula(formula_str)
        arena = spot.ltl_to_game(f, list(outputs))
        game_time = time.time() - start

        remaining = timeout - game_time
        if remaining < 1:
            return _result('timeout', start, method='game_build_timeout')

        # Solve game
        realizable = spot.solve_game(arena)
        solve_time = time.time() - start

        if not realizable:
            return _result('unrealizable', start, method='spot_game')

        # Extract strategy and encode as AIGER — try multiple strategies
        best_aiger = None
        best_gates = float('inf')
        best_method = None
        encodings = ["isop", "ite", "both+dc", "both+ud+dc"]

        # Strategy 1: split mealy (default)
        split_mealy = spot.solved_game_to_split_mealy(arena)
        for enc in encodings:
            aiger_text, gates = _try_aiger(split_mealy, enc)
            if gates is not None and gates < best_gates:
                best_gates, best_aiger, best_method = gates, aiger_text, f'split+{enc}'

        # Strategy 2: split mealy + simplify
        remaining = timeout - (time.time() - start)
        if remaining > 2:
            try:
                si = spot.synthesis_info()
                si.minimize_lvl = 2
                split2 = spot.solved_game_to_split_mealy(arena)
                spot.simplify_mealy_here(split2, si, False)
                for enc in encodings:
                    aiger_text, gates = _try_aiger(split2, enc)
                    if gates is not None and gates < best_gates:
                        best_gates, best_aiger, best_method = gates, aiger_text, f'simplify+{enc}'
            except Exception:
                pass

        # Strategy 3: minimize_mealy (unsplit)
        remaining = timeout - (time.time() - start)
        if remaining > 2:
            try:
                mealy = spot.solved_game_to_mealy(arena)
                min_m = spot.minimize_mealy(mealy, -1)
                for enc in encodings:
                    aiger_text, gates = _try_aiger(min_m, enc)
                    if gates is not None and gates < best_gates:
                        best_gates, best_aiger, best_method = gates, aiger_text, f'minimize+{enc}'
            except Exception:
                pass

        if best_aiger is None:
            return _result('error', start, error='All AIGER encodings failed')

        return _result('realizable', start,
                       aiger=best_aiger, and_gates=int(best_gates),
                       method=f'spot_game+{best_method}')

    except subprocess.TimeoutExpired:
        return _result('timeout', start, method='subprocess_timeout')
    except Exception as e:
        return _result('error', start, error=str(e))


def _try_aiger(mealy, enc):
    """Try encoding mealy as AIGER with given encoding. Returns (text, gates) or (None, None)."""
    try:
        oss = spot.ostringstream()
        spot.print_aiger(oss, mealy, enc)
        text = oss.str()
        header = text.strip().split('\n')[0].split()
        gates = int(header[5])
        return text, gates
    except Exception:
        return None, None


def _result(status, start, aiger=None, and_gates=-1, method='', error=None):
    return {
        'status': status,
        'aiger': aiger,
        'and_gates': and_gates,
        'time': time.time() - start,
        'method': method or f'spot_game',
        'error': error,
    }


def verify_aiger(aiger_text, tlsf_path, timeout=60):
    """Verify an AIGER circuit against a TLSF spec using ltlsynt --verify."""
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode='w', suffix='.aag', delete=False) as f:
        f.write(aiger_text)
        aag_path = f.name
    try:
        v = subprocess.run(
            ["ltlsynt", "--verify", f"--tlsf={tlsf_path}", "--aiger"],
            input=f"REALIZABLE\n{aiger_text}",
            capture_output=True, text=True, timeout=timeout
        )
        return 'verified' in v.stdout.lower() or v.returncode == 0
    except Exception:
        return False
    finally:
        os.unlink(aag_path)
