"""Two-player parity game construction and solving for reactive synthesis."""


def build_parity_game(automaton, inputs, outputs):
    """Build a 2-player parity game from a parity automaton.

    The game alternates between:
    - Environment (player 0): chooses input valuations
    - System (player 1): chooses output valuations

    Args:
        automaton: parsed HOA dict (must have parity acceptance)
        inputs: list of input AP names
        outputs: list of output AP names

    Returns dict with:
        n_nodes: total game nodes
        owner: list[int] — 0 (env) or 1 (sys) for each node
        priority: list[int] — parity priority for each node
        edges: list[list[int]] — successors for each node
        node_info: list[dict] — metadata (automaton state, valuation) per node
    """
    aps = automaton["aps"]
    n_states = automaton["n_states"]

    # Map AP names to indices
    ap_to_idx = {ap.lower(): i for i, ap in enumerate(aps)}
    input_idxs = [ap_to_idx[inp.lower()] for inp in inputs if inp.lower() in ap_to_idx]
    output_idxs = [ap_to_idx[out.lower()] for out in outputs if out.lower() in ap_to_idx]

    # Generate all valuations for a set of AP indices
    def all_valuations(idxs):
        n = len(idxs)
        for v in range(1 << n):
            yield {idxs[i]: bool(v & (1 << i)) for i in range(n)}

    # Build game graph
    # Each automaton state expands into intermediate nodes:
    # env_node (state, ?) -> sys_node (state, input_val) -> env_node (next_state, ?)

    nodes = []  # (type, state, info)
    owner = []
    priority = []
    edges = []
    node_info = []
    node_map = {}  # (type, state, key) -> node_id

    def get_or_create_node(ntype, state, key, prio=0):
        node_key = (ntype, state, key)
        if node_key not in node_map:
            nid = len(nodes)
            node_map[node_key] = nid
            nodes.append(node_key)
            owner.append(0 if ntype == "env" else 1)
            priority.append(prio)
            edges.append([])
            node_info.append({"type": ntype, "state": state, "key": key})
        return node_map[node_key]

    # Parse acceptance to get priorities per state/edge
    # For simplicity, extract priority from acceptance sets on edges
    def edge_priority(acc_sets):
        if not acc_sets:
            return 0
        return max(acc_sets) + 1  # Simple mapping

    # Create env nodes for each automaton state
    for s in range(n_states):
        env_nid = get_or_create_node("env", s, None)

    # For each automaton state, expand edges
    for s in range(n_states):
        env_nid = node_map[("env", s, None)]

        # Env chooses input valuation
        for in_val in all_valuations(input_idxs):
            in_key = tuple(sorted(in_val.items()))
            sys_nid = get_or_create_node("sys", s, in_key)
            edges[env_nid].append(sys_nid)

            # Sys chooses output valuation
            for out_val in all_valuations(output_idxs):
                # Combine valuations to check automaton edges
                full_val = {**in_val, **out_val}

                for src, dst, label, acc_sets in automaton["edges"]:
                    if src != s:
                        continue
                    if _label_matches(label, full_val, len(aps)):
                        prio = edge_priority(acc_sets)
                        next_env = get_or_create_node("env", dst, None, prio)
                        # Update priority to max seen
                        priority[next_env] = max(priority[next_env], prio)
                        if next_env not in edges[sys_nid]:
                            edges[sys_nid].append(next_env)

    return {
        "n_nodes": len(nodes),
        "owner": owner,
        "priority": priority,
        "edges": edges,
        "node_info": node_info,
        "start": [node_map.get(("env", s, None)) for s in automaton["start"]],
    }


def _label_matches(label_str, valuation, _n_aps=0):
    """Check if a HOA edge label matches a valuation.

    Label is a boolean expression over AP indices (e.g., "0&!1", "t" for true).
    Valuation maps AP index -> bool.
    """
    if label_str.strip() == "t":
        return True

    # Simple recursive parser for HOA label expressions
    def evaluate(expr):
        expr = expr.strip()
        if expr == "t":
            return True
        if expr == "f":
            return False

        # Handle OR (lowest precedence)
        depth = 0
        for i, c in enumerate(expr):
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
            elif c == '|' and depth == 0:
                return evaluate(expr[:i]) or evaluate(expr[i+1:])

        # Handle AND
        depth = 0
        for i, c in enumerate(expr):
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
            elif c == '&' and depth == 0:
                return evaluate(expr[:i]) and evaluate(expr[i+1:])

        # Handle NOT
        if expr.startswith("!"):
            return not evaluate(expr[1:])

        # Handle parentheses
        if expr.startswith("(") and expr.endswith(")"):
            return evaluate(expr[1:-1])

        # Atom: AP index
        idx = int(expr)
        return valuation.get(idx, False)

    return evaluate(label_str)


def zielonka_solve(game):
    """Zielonka's recursive algorithm for parity games.

    Returns (win0, win1): sets of node IDs won by player 0 (env) and player 1 (sys).
    """
    nodes = set(range(game["n_nodes"]))
    return _zielonka(game, nodes)


def _zielonka(game, nodes):
    if not nodes:
        return set(), set()

    priorities = {n: game["priority"][n] for n in nodes}
    d = max(priorities.values())
    player = d % 2  # 0 if even, 1 if odd

    u = {n for n in nodes if priorities[n] == d}
    a = _attractor(game, u, player, nodes)

    w0, w1 = _zielonka(game, nodes - a)

    opponent_win = w1 if player == 0 else w0
    if not opponent_win:
        # Player wins everything
        if player == 0:
            return nodes, set()
        else:
            return set(), nodes

    b = _attractor(game, opponent_win, 1 - player, nodes)
    w0_b, w1_b = _zielonka(game, nodes - b)

    if player == 0:
        return w0_b, w1_b | b
    else:
        return w0_b | b, w1_b


def _attractor(game, target, player, universe):
    """Compute attractor of target set for player within universe."""
    attractor = set(target)
    frontier = set(target)

    # Build reverse edges within universe
    rev_edges = {n: [] for n in universe}
    for n in universe:
        for succ in game["edges"][n]:
            if succ in universe:
                rev_edges[succ].append(n)

    # Count outgoing edges in universe for each node
    out_count = {}
    for n in universe:
        out_count[n] = sum(1 for s in game["edges"][n] if s in universe)

    while frontier:
        new_frontier = set()
        for v in frontier:
            for u in rev_edges.get(v, []):
                if u in attractor:
                    continue
                if game["owner"][u] == player:
                    # Player's node: can choose to go to attractor
                    attractor.add(u)
                    new_frontier.add(u)
                else:
                    # Opponent's node: must go to attractor (all successors in attractor)
                    out_count[u] -= 1
                    if out_count[u] == 0:
                        attractor.add(u)
                        new_frontier.add(u)
        frontier = new_frontier

    return attractor


def extract_strategy(game, winning_region, player):
    """Extract a memoryless strategy from the winning region.

    Returns dict: node_id -> chosen_successor for nodes owned by player.
    """
    strategy = {}
    for n in winning_region:
        if game["owner"][n] == player:
            for succ in game["edges"][n]:
                if succ in winning_region:
                    strategy[n] = succ
                    break
    return strategy


def strategy_to_mealy(strategy, game, inputs, outputs):
    """Convert a strategy to a Mealy machine representation.

    Returns dict with: states, initial, transitions
    where transitions maps (state, input_tuple) -> (next_state, output_tuple)
    """
    # Extract the relevant nodes and build a Mealy machine
    states = set()
    transitions = {}

    for node, successor in strategy.items():
        info = game["node_info"][node]
        if info["type"] == "sys":
            state = info["state"]
            states.add(state)

            succ_info = game["node_info"][successor]
            next_state = succ_info["state"]

            # Extract input/output from the node info
            if info["key"] is not None:
                input_val = dict(info["key"])
                transitions[(state, tuple(sorted(input_val.items())))] = (next_state, {})

    return {
        "states": sorted(states),
        "initial": game["start"][0] if game["start"] else 0,
        "transitions": transitions,
    }
