#!/usr/bin/env python3
"""Load and validate five-flags flow config."""

import json
from pathlib import Path
from typing import Dict, List, Tuple


def _validate_batches(
    batches: List[List[str]],
    flow_file: str,
    allowed_screeners: List[str]
) -> List[List[str]]:
    """Validate and normalize legacy batch config."""
    if not isinstance(batches, list) or not batches:
        raise ValueError(f"invalid flow config: empty batches in {flow_file}")

    normalized: List[List[str]] = []
    seen = set()
    allowed = set(allowed_screeners)
    for batch in batches:
        if not isinstance(batch, list) or not batch:
            raise ValueError(f"invalid flow config: empty batch in {flow_file}")
        one_batch = []
        for screener_id in batch:
            if screener_id not in allowed:
                raise ValueError(f"invalid screener_id in flow config: {screener_id}")
            if screener_id in seen:
                raise ValueError(f"duplicate screener in flow config: {screener_id}")
            seen.add(screener_id)
            one_batch.append(screener_id)
        normalized.append(one_batch)

    if seen != allowed:
        missing = sorted(list(allowed - seen))
        raise ValueError(f"flow config missing screeners: {', '.join(missing)}")
    return normalized


def _build_levels_from_nodes(
    nodes: List[Dict[str, object]],
    flow_file: str,
    allowed_screeners: List[str]
) -> List[List[str]]:
    """Build topological levels from DAG node definitions."""
    if not isinstance(nodes, list) or not nodes:
        raise ValueError(f"invalid flow config: empty nodes in {flow_file}")

    allowed = set(allowed_screeners)
    node_ids = []
    depends_map: Dict[str, List[str]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError(f"invalid flow config: node must be object in {flow_file}")
        node_id = str(node.get('id') or '').strip()
        if not node_id:
            raise ValueError(f"invalid flow config: node id missing in {flow_file}")
        if node_id in node_ids:
            raise ValueError(f"duplicate screener in flow config: {node_id}")
        if node_id not in allowed:
            raise ValueError(f"invalid screener_id in flow config: {node_id}")
        deps = node.get('depends_on') or []
        if not isinstance(deps, list):
            raise ValueError(f"invalid flow config: depends_on must be list for {node_id}")
        depends_map[node_id] = [str(x) for x in deps]
        node_ids.append(node_id)

    if set(node_ids) != allowed:
        missing = sorted(list(allowed - set(node_ids)))
        raise ValueError(f"flow config missing screeners: {', '.join(missing)}")

    indegree = {nid: 0 for nid in node_ids}
    outgoing: Dict[str, List[str]] = {nid: [] for nid in node_ids}
    for nid, deps in depends_map.items():
        for dep in deps:
            if dep not in allowed:
                raise ValueError(f"invalid dependency for {nid}: {dep}")
            if dep == nid:
                raise ValueError(f"self dependency not allowed: {nid}")
            indegree[nid] += 1
            outgoing[dep].append(nid)

    levels: List[List[str]] = []
    remaining = set(node_ids)
    while remaining:
        level = [nid for nid in node_ids if nid in remaining and indegree[nid] == 0]
        if not level:
            raise ValueError("invalid flow config: cycle detected")
        levels.append(level)
        for nid in level:
            remaining.remove(nid)
            for nxt in outgoing[nid]:
                indegree[nxt] -= 1

    return levels


def load_flow_plan(flow_file: str, allowed_screeners: List[str]) -> Tuple[List[List[str]], str, str]:
    """
    Load flow plan from JSON config file.
    Supports:
    - Legacy batches format
    - DAG nodes format (id + depends_on)

    Returns:
        (levels, flow_id, plan_type)
    """
    path = Path(flow_file)
    with open(path, 'r', encoding='utf-8') as f:
        payload = json.load(f)

    flow_id = str(payload.get('flow_id') or path.stem)
    if 'nodes' in payload:
        levels = _build_levels_from_nodes(payload.get('nodes'), flow_file, allowed_screeners)
        return levels, flow_id, 'dag'

    levels = _validate_batches(payload.get('batches'), flow_file, allowed_screeners)
    return levels, flow_id, 'batches'

def load_flow_batches(flow_file: str, allowed_screeners: List[str]) -> Tuple[List[List[str]], str]:
    """Backward-compatible helper: return levels + flow_id."""
    levels, flow_id, _ = load_flow_plan(flow_file, allowed_screeners)
    return levels, flow_id
