#!/usr/bin/env python3
"""End-to-end microconsumer against installed MPE 0.3.0 (no PYTHONPATH to MPE)."""
from __future__ import annotations
import json, sys
from pathlib import Path
from mpe.domain.contracts import TrackState
from mpe.domain.serialization import deserialize, serialize
from mpe.tracking.mock import MockTracker
from consumer.detector import ColorBlobDetector
from consumer.frame_source import ConsumerFrameSource
from consumer.spatial_association import SpatialIdentityAssigner

ROOT = Path(__file__).resolve().parent
FRAMES = ROOT / "frames"
OUT = ROOT / "trackstates"

def compare(a: TrackState, b: TrackState) -> dict[str, tuple[bool, object, object]]:
    fields = {
        "track_id": (a.track_id, b.track_id),
        "stamp": (a.stamp, b.stamp),
        "geometry": (a.geometry, b.geometry),
        "source_detection_ids": (a.source_detection_ids, b.source_detection_ids),
        "evidence_kind": (a.evidence_kind, b.evidence_kind),
        "provenance": (a.provenance, b.provenance),
    }
    return {k: (ov == rv, ov, rv) for k, (ov, rv) in fields.items()}

def main() -> int:
    if not list(FRAMES.glob("frame_*.jpg")):
        print("ERROR: run fetch_frames.py first", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    source = ConsumerFrameSource(FRAMES)
    detector = ColorBlobDetector()
    assigner = SpatialIdentityAssigner(distance_threshold=150.0)
    tracker = MockTracker()
    n = w = 0
    all_ok = True
    field_ok = {k: True for k in (
        "track_id", "stamp", "geometry", "source_detection_ids", "evidence_kind", "provenance"
    )}
    for frame in source.frames():
        n += 1
        dets = detector.detect(frame)
        dets = assigner.assign(dets)
        states = tracker.update(dets, frame.stamp)
        if states:
            w += 1
        ser_list: list[str] = []
        for ts in states:
            s = serialize(ts)
            ser_list.append(s)
            rebuilt = deserialize(s, TrackState)
            for k, (ok, ov, rv) in compare(ts, rebuilt).items():
                if not ok:
                    all_ok = False
                    field_ok[k] = False
                    print(f"ROUNDTRIP FAIL field={k} original={ov!r} rebuilt={rv!r}", file=sys.stderr)
        (OUT / f"frame_{frame.sequence:03d}.json").write_text(
            json.dumps({
                "frame_filename": f"frame_{frame.sequence:03d}.jpg",
                "frame_index": frame.sequence,
                "trackstates_serialized": ser_list,
            }, indent=2) + "\n",
            encoding="utf-8",
        )
    pct = 100.0 * w / n if n else 0.0
    print(f"Frames processados: {n}")
    print(f"Frames com >=1 TrackState: {w}")
    print(f"Percentual: {pct:.1f}%")
    print(f"Roundtrip OK: {'SIM' if all_ok else 'NAO'}")
    print(f"Spatial associations: {assigner.associations}")
    print(f"New identities: {assigner.new_identities}")
    print(f"Distance threshold: {assigner.distance_threshold}")
    for k, v in field_ok.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
    if n < 10 or n > 60 or pct < 60.0 or not all_ok:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
