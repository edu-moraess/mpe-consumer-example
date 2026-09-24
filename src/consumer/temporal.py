"""Temporal analysis over persisted TrackStates (consumer-side only; no MPE changes)."""
from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from mpe.domain.contracts import TrackState
from mpe.domain.serialization import deserialize


def extract_position(geometry: dict[str, Any]) -> tuple[float, float] | None:
    """Extract (x, y) from TrackState.geometry without inventing structure.

    Supported:
      - geometry["centroid"] as [x, y] or (x, y)
    Returns None if position cannot be derived.
    """
    if not isinstance(geometry, dict):
        return None
    c = geometry.get("centroid")
    if isinstance(c, (list, tuple)) and len(c) >= 2:
        try:
            return float(c[0]), float(c[1])
        except (TypeError, ValueError):
            return None
    return None


def stamp_sort_key(ts: TrackState) -> tuple:
    """Deterministic temporal order: sequence, then capture_timestamp, then track_id."""
    stamp = ts.stamp
    ts_val = stamp.capture_timestamp.timestamp() if stamp.capture_timestamp else float("-inf")
    return (stamp.sequence, ts_val, ts.track_id)


def delta_t_seconds(prev: TrackState, curr: TrackState) -> float | None:
    """Compute delta_t from capture_timestamp when both present; else None."""
    a = prev.stamp.capture_timestamp
    b = curr.stamp.capture_timestamp
    if a is None or b is None:
        return None
    return (b - a).total_seconds()


@dataclass(frozen=True)
class TemporalPair:
    track_id: str
    previous_stamp_sequence: int
    current_stamp_sequence: int
    previous_timestamp: str | None
    current_timestamp: str | None
    delta_t: float | None
    previous_position: list[float] | None
    current_position: list[float] | None
    displacement: list[float] | None
    displacement_norm: float | None
    derived_velocity: list[float] | None
    derived_speed: float | None
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "previous_stamp_sequence": self.previous_stamp_sequence,
            "current_stamp_sequence": self.current_stamp_sequence,
            "previous_timestamp": self.previous_timestamp,
            "current_timestamp": self.current_timestamp,
            "delta_t": self.delta_t,
            "previous_position": self.previous_position,
            "current_position": self.current_position,
            "displacement": self.displacement,
            "displacement_norm": self.displacement_norm,
            "derived_velocity": self.derived_velocity,
            "derived_speed": self.derived_speed,
            "notes": list(self.notes),
        }


def load_trackstates(trackstates_dir: str | Path) -> list[tuple[int, TrackState]]:
    """Load all TrackStates from trackstates/frame_NNN.json artifacts."""
    root = Path(trackstates_dir)
    items: list[tuple[int, TrackState]] = []
    for path in sorted(root.glob("frame_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        frame_index = int(data["frame_index"])
        for s in data.get("trackstates_serialized", []):
            ts = deserialize(s, TrackState)
            items.append((frame_index, ts))
    return items


def group_by_track(items: list[tuple[int, TrackState]]) -> dict[str, list[TrackState]]:
    groups: dict[str, list[TrackState]] = defaultdict(list)
    for _, ts in items:
        groups[ts.track_id].append(ts)
    for tid in groups:
        groups[tid] = sorted(groups[tid], key=stamp_sort_key)
    return dict(groups)


def pair_consecutive(states: list[TrackState]) -> list[TemporalPair]:
    """Build consecutive temporal pairs for one track_id sequence."""
    pairs: list[TemporalPair] = []
    for i in range(len(states) - 1):
        prev, curr = states[i], states[i + 1]
        notes: list[str] = []
        if prev.track_id != curr.track_id:
            notes.append("track_id_mismatch")
            continue

        dt = delta_t_seconds(prev, curr)
        if dt is None:
            notes.append("delta_t_unavailable: missing capture_timestamp")

        ppos = extract_position(prev.geometry)
        cpos = extract_position(curr.geometry)
        if ppos is None:
            notes.append("previous_position_unavailable: geometry lacks usable centroid")
        if cpos is None:
            notes.append("current_position_unavailable: geometry lacks usable centroid")

        displacement = None
        displacement_norm = None
        velocity = None
        speed = None
        if ppos is not None and cpos is not None:
            displacement = [cpos[0] - ppos[0], cpos[1] - ppos[1]]
            displacement_norm = math.hypot(displacement[0], displacement[1])
            if dt is not None and dt > 0:
                velocity = [displacement[0] / dt, displacement[1] / dt]
                speed = math.hypot(velocity[0], velocity[1])
            elif dt is not None and dt == 0:
                notes.append("derived_velocity_unavailable: delta_t == 0")
            else:
                notes.append("derived_velocity_unavailable: no positive delta_t")
        else:
            notes.append("displacement_unavailable: need both positions")

        def ts_iso(ts: TrackState) -> str | None:
            t = ts.stamp.capture_timestamp
            return t.isoformat() if t is not None else None

        pairs.append(
            TemporalPair(
                track_id=prev.track_id,
                previous_stamp_sequence=prev.stamp.sequence,
                current_stamp_sequence=curr.stamp.sequence,
                previous_timestamp=ts_iso(prev),
                current_timestamp=ts_iso(curr),
                delta_t=dt,
                previous_position=list(ppos) if ppos else None,
                current_position=list(cpos) if cpos else None,
                displacement=displacement,
                displacement_norm=displacement_norm,
                derived_velocity=velocity,
                derived_speed=speed,
                notes=tuple(notes),
            )
        )
    return pairs


def analyze_trackstates(trackstates_dir: str | Path) -> dict[str, Any]:
    items = load_trackstates(trackstates_dir)
    groups = group_by_track(items)
    all_pairs: list[TemporalPair] = []
    for tid in sorted(groups.keys()):
        all_pairs.extend(pair_consecutive(groups[tid]))

    return {
        "frames_with_files": len({i for i, _ in items}),
        "trackstate_count": len(items),
        "track_count": len(groups),
        "tracks_with_multiple_states": sum(1 for s in groups.values() if len(s) > 1),
        "temporal_pairs": len(all_pairs),
        "pairs": [p.to_dict() for p in all_pairs],
        "notes": (
            "Association uses TrackState.track_id only. "
            "MockTracker maps detection_id\u2192track_id; unique detection_ids per frame "
            "yield one-shot tracks unless the consumer reuses detection_ids."
        ),
    }


def write_temporal_artifacts(trackstates_dir: str | Path, out_dir: str | Path) -> dict[str, Any]:
    """Write temporal/summary.json and temporal/pairs.json."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    result = analyze_trackstates(trackstates_dir)
    (out / "summary.json").write_text(json.dumps({
        k: result[k] for k in (
            "frames_with_files", "trackstate_count", "track_count",
            "tracks_with_multiple_states", "temporal_pairs", "notes",
        )
    }, indent=2) + "\n", encoding="utf-8")
    (out / "pairs.json").write_text(json.dumps(result["pairs"], indent=2) + "\n", encoding="utf-8")
    return result
