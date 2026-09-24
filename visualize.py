#!/usr/bin/env python3
"""Generate representative visualization samples from real pipeline artifacts."""
from __future__ import annotations
import sys
from pathlib import Path
from consumer.visualization import generate_samples

ROOT = Path(__file__).resolve().parent

def main() -> int:
    frames = ROOT / "frames"
    trackstates = ROOT / "trackstates"
    out = ROOT / "visualizations" / "samples"
    if not list(frames.glob("frame_*.jpg")):
        print("ERROR: no frames; run fetch_frames.py first", file=sys.stderr)
        return 1
    paths = generate_samples(frames, trackstates, out)
    for p in paths:
        print(p)
    print(f"generated {len(paths)} samples")
    return 0

if __name__ == "__main__":
    sys.exit(main())
