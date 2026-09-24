#!/usr/bin/env python3
"""Acquire frames from Blender Foundation Big Buck Bunny (CC BY 3.0), first 20s @ 1080p."""
from __future__ import annotations
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRAMES = ROOT / "frames"
VIDEO = ROOT / "data" / "big_buck_bunny_20s_1080p.mp4"

VIDEO_URL = "https://download.blender.org/demo/movies/BBB/bbb_sunflower_1080p_30fps_normal.mp4.zip"
VIDEO_LICENSE = "CC BY 3.0 (Creative Commons Attribution 3.0 Unported)"
VIDEO_LICENSE_EVIDENCE = (
    "https://creativecommons.org/licenses/by/3.0/ ; "
    "https://archive.org/download/BigBuckBunny_124/License.txt ; "
    "Blender Foundation / Peach Open Movie Project"
)
VIDEO_SOURCE = "Blender Foundation — Big Buck Bunny (sunflower 1080p); local = first 20 seconds"
DURATION_S = 20.0
RESOLUTION = "1920x1080"

def main() -> int:
    existing = sorted(FRAMES.glob("frame_*.jpg"))
    if len(existing) >= 10:
        print(f"frames already present: {len(existing)}")
        return 0
    if not VIDEO.exists():
        print(f"ERROR: place CC-BY BBB 20s 1080p clip at {VIDEO}", file=sys.stderr)
        print(f"Source URL: {VIDEO_URL}", file=sys.stderr)
        return 1
    FRAMES.mkdir(parents=True, exist_ok=True)
    for p in FRAMES.glob("tmp_*.jpg"):
        p.unlink()
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(VIDEO), "-vf", "fps=1", str(FRAMES / "tmp_%03d.jpg")],
        check=True, capture_output=True,
    )
    tmp = sorted(FRAMES.glob("tmp_*.jpg"))[:60]
    for i, p in enumerate(tmp):
        p.rename(FRAMES / f"frame_{i:03d}.jpg")
    n = len(list(FRAMES.glob("frame_*.jpg")))
    print(f"extracted {n} frames")
    print(f"URL: {VIDEO_URL}")
    print(f"License: {VIDEO_LICENSE}")
    print(f"Evidence: {VIDEO_LICENSE_EVIDENCE}")
    print(f"Duration: {DURATION_S}s")
    print(f"Resolution: {RESOLUTION}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
