#!/usr/bin/env python3
"""Unit tests for flow config loader (batches + DAG)."""

import json
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.flow_engine.flow_config import load_flow_plan


ALLOWED_SCREENERS = [
    'er_ban_hui_tiao',
    'jin_feng_huang',
    'yin_feng_huang',
    'shi_pan_xian',
    'zhang_ting_bei_liang_yin'
]


def _write_json(tmp_path: Path, name: str, payload: dict) -> str:
    file_path = tmp_path / name
    file_path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    return str(file_path)


def test_load_batches_config(tmp_path: Path):
    payload = {
        "flow_id": "batches_ok",
        "batches": [
            ["er_ban_hui_tiao", "shi_pan_xian"],
            ["zhang_ting_bei_liang_yin"],
            ["jin_feng_huang", "yin_feng_huang"]
        ]
    }
    path = _write_json(tmp_path, "batches.json", payload)

    levels, flow_id, plan_type = load_flow_plan(path, ALLOWED_SCREENERS)

    assert flow_id == "batches_ok"
    assert plan_type == "batches"
    assert levels == payload["batches"]


def test_load_dag_config(tmp_path: Path):
    payload = {
        "flow_id": "dag_ok",
        "nodes": [
            {"id": "er_ban_hui_tiao", "depends_on": []},
            {"id": "shi_pan_xian", "depends_on": []},
            {"id": "zhang_ting_bei_liang_yin", "depends_on": ["er_ban_hui_tiao"]},
            {"id": "jin_feng_huang", "depends_on": ["zhang_ting_bei_liang_yin"]},
            {"id": "yin_feng_huang", "depends_on": ["shi_pan_xian", "zhang_ting_bei_liang_yin"]}
        ]
    }
    path = _write_json(tmp_path, "dag.json", payload)

    levels, flow_id, plan_type = load_flow_plan(path, ALLOWED_SCREENERS)

    assert flow_id == "dag_ok"
    assert plan_type == "dag"
    assert levels == [
        ["er_ban_hui_tiao", "shi_pan_xian"],
        ["zhang_ting_bei_liang_yin"],
        ["jin_feng_huang", "yin_feng_huang"]
    ]


def test_load_dag_cycle_should_fail(tmp_path: Path):
    payload = {
        "flow_id": "dag_cycle",
        "nodes": [
            {"id": "er_ban_hui_tiao", "depends_on": ["jin_feng_huang"]},
            {"id": "jin_feng_huang", "depends_on": ["er_ban_hui_tiao"]},
            {"id": "yin_feng_huang", "depends_on": []},
            {"id": "shi_pan_xian", "depends_on": []},
            {"id": "zhang_ting_bei_liang_yin", "depends_on": []}
        ]
    }
    path = _write_json(tmp_path, "dag_cycle.json", payload)

    with pytest.raises(ValueError, match="cycle detected"):
        load_flow_plan(path, ALLOWED_SCREENERS)


def test_load_config_missing_screener_should_fail(tmp_path: Path):
    payload = {
        "flow_id": "missing_one",
        "batches": [
            ["er_ban_hui_tiao", "shi_pan_xian"],
            ["zhang_ting_bei_liang_yin"],
            ["jin_feng_huang"]
        ]
    }
    path = _write_json(tmp_path, "missing.json", payload)

    with pytest.raises(ValueError, match="missing screeners"):
        load_flow_plan(path, ALLOWED_SCREENERS)
