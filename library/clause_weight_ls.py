"""Clause-weighting local search for MaxSAT (SATLike-inspired).

Key idea: dynamically adjust clause weights to escape local optima.
When stuck, increase weights of unsatisfied soft clauses, making them
more attractive to satisfy. Periodically smooth weights back toward
original values to prevent weight explosion.

This is one of the most effective incomplete MaxSAT techniques,
used by competition winners like SATLike, NuWLS, etc.
"""

import random
import time
from library.solvers import (build_occurrence_lists, compute_sat_counts,
                              flip_variable, flip_preserves_hard, assignment_to_lits)


def clause_weight_local_search(assignment, soft_clauses, hard_clauses, occ_lists,
                                timeout=240, smooth_probability=0.01, weight_inc=1):
    """Clause-weighting local search for MaxSAT.

    At each step:
    1. Pick a random unsatisfied soft clause
    2. Find the best variable to flip in that clause (preserving hard feasibility)
    3. If no improving flip exists, increase weights of all unsatisfied soft clauses
    4. With some probability, smooth weights back toward original values

    Args:
        assignment: bytearray, initial feasible assignment
        soft_clauses: list of (weight, clause)
        hard_clauses: list of clauses
        occ_lists: from build_occurrence_lists
        timeout: seconds
        smooth_probability: probability of smoothing per non-improving step
        weight_inc: weight increment for unsatisfied clauses

    Returns (best_assignment, best_cost) using ORIGINAL weights.
    """
    hard_pos, hard_neg, soft_pos, soft_neg, soft_weights_orig, soft_vars = occ_lists
    nvars = len(assignment) - 1
    nsoft = len(soft_clauses)

    # Dynamic weights (start from original)
    dyn_weights = list(soft_weights_orig)

    hard_sat_count, soft_sat_count = compute_sat_counts(assignment, hard_clauses, soft_clauses)

    # Track original cost
    orig_cost = sum(soft_weights_orig[i] for i in range(nsoft) if soft_sat_count[i] == 0)
    best_cost = orig_cost
    best_assign = bytearray(assignment)

    # Score array: delta in dynamic weight if we flip v
    # score[v] = sum of dyn_weights of soft clauses that would become satisfied
    #          - sum of dyn_weights of soft clauses that would become unsatisfied
    score = [0] * (nvars + 1)
    for v in soft_vars:
        s = 0
        if assignment[v]:
            for ci in soft_pos[v]:
                if soft_sat_count[ci] == 1: s += dyn_weights[ci]
            for ci in soft_neg[v]:
                if soft_sat_count[ci] == 0: s -= dyn_weights[ci]
        else:
            for ci in soft_pos[v]:
                if soft_sat_count[ci] == 0: s -= dyn_weights[ci]
            for ci in soft_neg[v]:
                if soft_sat_count[ci] == 1: s += dyn_weights[ci]
        score[v] = s

    t0 = time.time()
    steps = 0

    while time.time() - t0 < timeout:
        # Find unsatisfied soft clauses
        unsat = [i for i in range(nsoft) if soft_sat_count[i] == 0]
        if not unsat:
            break

        # Pick random unsatisfied soft clause
        ci = random.choice(unsat)
        w_orig, clause = soft_clauses[ci]

        # Find best variable to flip in this clause
        best_v = -1
        best_score = float('inf')

        for lit in clause:
            v = abs(lit)
            # Check if flipping v would satisfy this clause
            would_satisfy = (lit > 0 and not assignment[v]) or (lit < 0 and assignment[v])
            if not would_satisfy:
                continue
            if not flip_preserves_hard(v, assignment, hard_pos, hard_neg, hard_sat_count):
                continue
            if score[v] < best_score:
                best_score = score[v]
                best_v = v

        if best_v != -1 and best_score < 0:
            # Improving flip found - do it
            _do_flip(best_v, assignment, hard_pos, hard_neg, soft_pos, soft_neg,
                    hard_sat_count, soft_sat_count, dyn_weights, score, soft_clauses)

            # Check original cost
            orig_cost_new = sum(soft_weights_orig[i] for i in range(nsoft) if soft_sat_count[i] == 0)
            if orig_cost_new < best_cost:
                best_cost = orig_cost_new
                best_assign = bytearray(assignment)
            steps += 1
        elif best_v != -1:
            # Non-improving but feasible flip - do it anyway (exploration)
            _do_flip(best_v, assignment, hard_pos, hard_neg, soft_pos, soft_neg,
                    hard_sat_count, soft_sat_count, dyn_weights, score, soft_clauses)

            orig_cost_new = sum(soft_weights_orig[i] for i in range(nsoft) if soft_sat_count[i] == 0)
            if orig_cost_new < best_cost:
                best_cost = orig_cost_new
                best_assign = bytearray(assignment)
            steps += 1

            # Increase weights of unsatisfied clauses
            for ui in unsat:
                old_w = dyn_weights[ui]
                dyn_weights[ui] = old_w + weight_inc
                diff = weight_inc
                # Update scores for variables in this clause
                _, ucl = soft_clauses[ui]
                for lit in ucl:
                    vv = abs(lit)
                    would_satisfy = (lit > 0 and not assignment[vv]) or (lit < 0 and assignment[vv])
                    if would_satisfy:
                        score[vv] -= diff  # More incentive to flip
                    else:
                        pass  # Doesn't affect score since clause is already unsat

            # Smooth weights with probability
            if random.random() < smooth_probability:
                for i in range(nsoft):
                    if dyn_weights[i] > soft_weights_orig[i]:
                        old_w = dyn_weights[i]
                        dyn_weights[i] = max(soft_weights_orig[i], dyn_weights[i] - 1)
                        if dyn_weights[i] != old_w:
                            diff = dyn_weights[i] - old_w  # negative
                            if soft_sat_count[i] == 0:
                                _, cl = soft_clauses[i]
                                for lit in cl:
                                    vv = abs(lit)
                                    would_satisfy = (lit > 0 and not assignment[vv]) or (lit < 0 and assignment[vv])
                                    if would_satisfy:
                                        score[vv] -= diff
        else:
            # No feasible flip in this clause, just increase weights
            for ui in unsat:
                old_w = dyn_weights[ui]
                dyn_weights[ui] = old_w + weight_inc
                diff = weight_inc
                _, ucl = soft_clauses[ui]
                for lit in ucl:
                    vv = abs(lit)
                    would_satisfy = (lit > 0 and not assignment[vv]) or (lit < 0 and assignment[vv])
                    if would_satisfy:
                        score[vv] -= diff

    return best_assign, best_cost


def _do_flip(v, assignment, hard_pos, hard_neg, soft_pos, soft_neg,
             hard_sat_count, soft_sat_count, dyn_weights, score, soft_clauses):
    """Flip v and update scores incrementally."""
    # Update scores for neighbors before flipping
    if assignment[v]:
        # v going from 1 to 0
        for ci in soft_pos[v]:
            w = dyn_weights[ci]
            if soft_sat_count[ci] == 1:
                # This clause becomes unsatisfied
                for lit in soft_clauses[ci][1]:
                    vv = abs(lit)
                    if (lit > 0 and not assignment[vv]) or (lit < 0 and assignment[vv]):
                        score[vv] -= w  # Now they can satisfy it
            elif soft_sat_count[ci] == 2:
                for lit in soft_clauses[ci][1]:
                    vv = abs(lit)
                    if vv != v and ((lit > 0 and assignment[vv]) or (lit < 0 and not assignment[vv])):
                        score[vv] += w  # They become the only satisfier
                        break
        for ci in soft_neg[v]:
            w = dyn_weights[ci]
            if soft_sat_count[ci] == 0:
                for lit in soft_clauses[ci][1]:
                    vv = abs(lit)
                    if (lit > 0 and not assignment[vv]) or (lit < 0 and assignment[vv]):
                        score[vv] += w
            elif soft_sat_count[ci] == 1:
                for lit in soft_clauses[ci][1]:
                    vv = abs(lit)
                    if vv != v and ((lit > 0 and assignment[vv]) or (lit < 0 and not assignment[vv])):
                        score[vv] -= w
                        break
    else:
        # v going from 0 to 1
        for ci in soft_pos[v]:
            w = dyn_weights[ci]
            if soft_sat_count[ci] == 0:
                for lit in soft_clauses[ci][1]:
                    vv = abs(lit)
                    if (lit > 0 and not assignment[vv]) or (lit < 0 and assignment[vv]):
                        score[vv] += w
            elif soft_sat_count[ci] == 1:
                for lit in soft_clauses[ci][1]:
                    vv = abs(lit)
                    if vv != v and ((lit > 0 and assignment[vv]) or (lit < 0 and not assignment[vv])):
                        score[vv] -= w
                        break
        for ci in soft_neg[v]:
            w = dyn_weights[ci]
            if soft_sat_count[ci] == 1:
                for lit in soft_clauses[ci][1]:
                    vv = abs(lit)
                    if (lit > 0 and not assignment[vv]) or (lit < 0 and assignment[vv]):
                        score[vv] -= w
            elif soft_sat_count[ci] == 2:
                for lit in soft_clauses[ci][1]:
                    vv = abs(lit)
                    if vv != v and ((lit > 0 and assignment[vv]) or (lit < 0 and not assignment[vv])):
                        score[vv] += w
                        break

    # Now flip
    flip_variable(v, assignment, hard_pos, hard_neg, soft_pos, soft_neg,
                  hard_sat_count, soft_sat_count)

    # Recompute score[v] from scratch
    s = 0
    if assignment[v]:
        for ci in soft_pos[v]:
            if soft_sat_count[ci] == 1: s += dyn_weights[ci]
        for ci in soft_neg[v]:
            if soft_sat_count[ci] == 0: s -= dyn_weights[ci]
    else:
        for ci in soft_pos[v]:
            if soft_sat_count[ci] == 0: s -= dyn_weights[ci]
        for ci in soft_neg[v]:
            if soft_sat_count[ci] == 1: s += dyn_weights[ci]
    score[v] = s
