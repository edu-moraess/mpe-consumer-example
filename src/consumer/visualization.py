"""Deterministic visualization of real TrackState overlays on frame images.

Consumer-only. Draws bbox, centroid, track_id, and previous	o current trajectory
from real pipeline artifacts (no invented data).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from mpe.domain.contracts import TrackState
from mpe.domain.serialization import deserialize


def load_frame_trackstates(path: Path) -> list[TrackState]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [deserialize(s, TrackState) for s in data.get("trackstates_serialized", [])]


def _centroid(geom: dict[str, Any]) -> tuple[float, float] | None:
    c = geom.get("centroid") if isinstance(geom, dict) else None
    if isinstance(c, (list, tuple)) and len(c) >= 2:
        try:
            return float(c[0]), float(c[1])
        except (TypeError, ValueError):
            return None
    return None


def _bbox(geom: dict[str, Any]) -> tuple[float, float, float, float] | None:
    b = geom.get("bbox") if isinstance(geom, dict) else None
    if isinstance(b, (list, tuple)) and len(b) >= 4:
        try:
            x, y, w, h = float(b[0]), float(b[1]), float(b[2]), float(b[3])
            return x, y, x + w, y + h
        except (TypeError, ValueError):
            return None
    return None


def build_history(
    trackstates_dir: Path,
) -> dict[str, list[tuple[int, tuple[float, float]]]]:
    hist: dict[str, list[tuple[int, tuple[float, float]]]] = {}
    for path in sorted(trackstates_dir.glob("frame_*.json")):
        for ts in load_frame_trackstates(path):
            pos = _centroid(ts.geometry if isinstance(ts.geometry, dict) else {})
            if pos is None:
                continue
            hist.setdefault(ts.track_id, []).append((ts.stamp.sequence, pos))
    for tid in hist:
        hist[tid].sort(key=lambda x: x[0])
    return hist


def render_frame(
    image_path: Path,
    trackstates: list[TrackState],
    history: dict[str, list[tuple[int, tuple[float, float]]]],
    *,
    out_path: Path,
) -> Path:
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for ts in trackstates:
        geom = ts.geometry if isinstance(ts.geometry, dict) else {}
        box = _bbox(geom)
        cent = _centroid(geom)
        short_id = ts.track_id[:8]
        if box is not None:
            draw.rectangle(box, outline=(0, 255, 0), width=3)
            label = f"{short_id} s={ts.stamp.sequence}"
            ty = max(0, box[1] - 14)
            draw.text((box[0], ty), label, fill=(255, 255, 0), font=font)
        if cent is not None:
            x, y = cent
            r = 6
            draw.ellipse((x - r, y - r, x + r, y + r), outline=(255, 0, 0), width=2)
            pts = history.get(ts.track_id, [])
            prev = None
            for seq, p in pts:
                if seq < ts.stamp.sequence:
                    prev = p
                elif seq == ts.stamp.sequence:
                    break
            if prev is not None:
                draw.line([prev, cent], fill=(0, 180, 255), width=2)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")
    return out_path


def select_sample_indices(n_frames: int) -> list[int]:
    if n_frames <= 0:
        return []
    candidates = [0, 5, 6, n_frames // 2, max(0, n_frames - 3), n_frames - 1]
    out: list[int] = []
    for i in candidates:
        if 0 <= i < n_frames and i not in out:
            out.append(i)
    return out


def generate_samples(
    frames_dir: Path,
    trackstates_dir: Path,
    out_dir: Path,
) -> list[Path]:
    frames = sorted(frames_dir.glob("frame_*.jpg"))
    history = build_history(trackstates_dir)
    written: list[Path] = []
    for idx in select_sample_indices(len(frames)):
        frame_path = frames[idx]
        ts_path = trackstates_dir / f"frame_{idx:03d}.json"
        states = load_frame_trackstates(ts_path) if ts_path.exists() else []
        out = out_dir / f"sample_frame_{idx:03d}.png"
        render_frame(frame_path, states, history, out_path=out)
        written.append(out)
    return written
