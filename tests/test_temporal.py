"""Deterministic tests for consumer-side temporal analysis."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from mpe.core.kinds import Determinism, EvidenceKind
from mpe.core.origin import Origin, OriginKind
from mpe.core.provenance import Provenance
from mpe.core.stamp import Stamp
from mpe.domain.contracts import TrackState
from mpe.domain.serialization import serialize

from consumer.temporal import (
    analyze_trackstates,
    delta_t_seconds,
    extract_position,
    group_by_track,
    pair_consecutive,
    stamp_sort_key,
    write_temporal_artifacts,
)


def _prov(ts: datetime) -> Provenance:
    return Provenance(
        origin=Origin(OriginKind.ALGORITHM, "test"),
        timestamp=ts,
        component_id="test",
        determinism=Determinism.STRICT,
    )


def _ts(track_id: str, seq: int, t0: datetime, x: float, y: float) -> TrackState:
    stamp = Stamp("consumer-source", seq, t0 + timedelta(seconds=seq), "consumer")
    return TrackState(
        track_id=track_id,
        stamp=stamp,
        state={},
        status="confirmed",
        provenance=_prov(stamp.capture_timestamp),
        geometry={"bbox": [0, 0, 10, 10], "centroid": [x, y]},
        source_detection_ids=(f"{seq:03d}-0",),
        evidence_kind=EvidenceKind.INFERRED,
    )


def test_extract_position_centroid():
    assert extract_position({"centroid": [1.5, 2.5]}) == (1.5, 2.5)


def test_extract_position_missing():
    assert extract_position({}) is None
    assert extract_position({"bbox": [0, 0, 1, 1]}) is None


def test_stamp_ordering():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = _ts("T1", 2, t0, 0, 0)
    b = _ts("T1", 1, t0, 0, 0)
    assert stamp_sort_key(b) < stamp_sort_key(a)


def test_delta_t():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = _ts("T1", 0, t0, 0, 0)
    b = _ts("T1", 1, t0, 0, 0)
    assert delta_t_seconds(a, b) == pytest.approx(1.0)


def test_displacement_and_velocity():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = _ts("T1", 0, t0, 10.0, 20.0)
    b = _ts("T1", 1, t0, 13.0, 24.0)
    pairs = pair_consecutive([a, b])
    assert len(pairs) == 1
    p = pairs[0]
    assert p.displacement == pytest.approx([3.0, 4.0])
    assert p.displacement_norm == pytest.approx(5.0)
    assert p.derived_velocity == pytest.approx([3.0, 4.0])
    assert p.derived_speed == pytest.approx(5.0)
    assert p.track_id == "T1"


def test_no_position():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = _ts("T1", 0, t0, 0, 0)
    b = _ts("T1", 1, t0, 1, 1)
    a2 = TrackState(
        track_id=a.track_id, stamp=a.stamp, state={}, status="confirmed",
        provenance=a.provenance, geometry={"bbox": [0, 0, 1, 1]},
        source_detection_ids=a.source_detection_ids, evidence_kind=a.evidence_kind,
    )
    pairs = pair_consecutive([a2, b])
    assert pairs[0].previous_position is None
    assert pairs[0].displacement is None
    assert pairs[0].derived_velocity is None
    assert any("previous_position_unavailable" in n for n in pairs[0].notes)


def test_single_trackstate_no_pair():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = _ts("T1", 0, t0, 0, 0)
    assert pair_consecutive([a]) == []


def test_track_id_preserved():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    states = [_ts("ABC", i, t0, float(i), 0.0) for i in range(3)]
    pairs = pair_consecutive(states)
    assert all(p.track_id == "ABC" for p in pairs)
    assert len(pairs) == 2


def test_group_by_track_and_analyze(tmp_path: Path):
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for seq, (x, y) in enumerate([(0.0, 0.0), (10.0, 0.0)]):
        ts = _ts("SAME", seq, t0, x, y)
        payload = {
            "frame_filename": f"frame_{seq:03d}.jpg",
            "frame_index": seq,
            "trackstates_serialized": [serialize(ts)],
        }
        (tmp_path / f"frame_{seq:03d}.json").write_text(
            __import__("json").dumps(payload), encoding="utf-8"
        )
    result = analyze_trackstates(tmp_path)
    assert result["track_count"] == 1
    assert result["tracks_with_multiple_states"] == 1
    assert result["temporal_pairs"] == 1
    p = result["pairs"][0]
    assert p["displacement"] == [10.0, 0.0]
    assert p["delta_t"] == 1.0


def test_write_artifacts(tmp_path: Path):
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ts = _ts("ONLY", 0, t0, 1.0, 2.0)
    payload = {
        "frame_filename": "frame_000.jpg",
        "frame_index": 0,
        "trackstates_serialized": [serialize(ts)],
    }
    ts_dir = tmp_path / "trackstates"
    ts_dir.mkdir()
    (ts_dir / "frame_000.json").write_text(__import__("json").dumps(payload))
    out = tmp_path / "temporal"
    result = write_temporal_artifacts(ts_dir, out)
    assert (out / "summary.json").exists()
    assert (out / "pairs.json").exists()
    assert result["temporal_pairs"] == 0
