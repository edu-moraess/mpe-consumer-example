#!/usr/bin/env python3
"""Run temporal analysis over trackstates/ artifacts (consumer-only)."""
from __future__ import annotations
import json
import sys
from pathlib import Path

from consumer.temporal import write_temporal_artifacts

ROOT = Path(__file__).resolve().parent

def main() -> int:
    result = write_temporal_artifacts(ROOT / "trackstates", ROOT / "temporal")
    print(json.dumps({
        "trackstate_count": result["trackstate_count"],
        "track_count": result["track_count"],
        "tracks_with_multiple_states": result["tracks_with_multiple_states"],
        "temporal_pairs": result["temporal_pairs"],
        "notes": result["notes"],
    }, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
