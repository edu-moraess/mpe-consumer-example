"""Deterministic spatial association of detections across consecutive frames.

Consumer-only. Does not modify MPE contracts or MockTracker.
Rewrites Detection.detection_id so that MockTracker maps
stable_id("track", detection_id) to a persistent track across frames.
"""
from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

from mpe.domain.contracts import Detection


def centroid_of(detection: Detection) -> tuple[float, float] | None:
    geom = detection.geometry
    if not isinstance(geom, dict):
        return None
    c = geom.get("centroid")
    if isinstance(c, (list, tuple)) and len(c) >= 2:
        try:
            return float(c[0]), float(c[1])
        except (TypeError, ValueError):
            return None
    return None


def euclidean(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class SpatialIdentityAssigner:
    """Greedy nearest-centroid association with a fixed distance threshold.

    Threshold default 150 px at 1080p / 1 fps:
    - empirical inter-frame nearest-centroid distances on BBB opening:
      p50≈47, p75≈136, p90≈528
    - 150 covers typical same-blob motion while rejecting large scene jumps.
    """

    def __init__(self, *, distance_threshold: float = 150.0) -> None:
        if distance_threshold <= 0:
            raise ValueError("distance_threshold must be positive")
        self.distance_threshold = distance_threshold
        self._next_index = 0
        self._previous: list[tuple[str, tuple[float, float]]] = []
        self.associations = 0
        self.new_identities = 0

    def _new_id(self) -> str:
        self._next_index += 1
        return f"object_{self._next_index:03d}"

    def assign(self, detections: tuple[Detection, ...] | list[Detection]) -> tuple[Detection, ...]:
        ordered = sorted(
            enumerate(detections),
            key=lambda iv: (-(iv[1].score if iv[1].score is not None else 0.0), iv[0]),
        )
        used_prev: set[int] = set()
        assigned: list[tuple[int, Detection, tuple[float, float] | None]] = []

        for orig_idx, det in ordered:
            pos = centroid_of(det)
            chosen_id: str | None = None
            if pos is not None and self._previous:
                best_j = None
                best_d = None
                for j, (pid, pcent) in enumerate(self._previous):
                    if j in used_prev:
                        continue
                    d = euclidean(pos, pcent)
                    if d <= self.distance_threshold and (best_d is None or d < best_d):
                        best_d = d
                        best_j = j
                if best_j is not None:
                    used_prev.add(best_j)
                    chosen_id = self._previous[best_j][0]
                    self.associations += 1
            if chosen_id is None:
                chosen_id = self._new_id()
                self.new_identities += 1
            new_det = replace(det, detection_id=chosen_id)
            assigned.append((orig_idx, new_det, pos))

        assigned.sort(key=lambda x: x[0])
        self._previous = [
            (d.detection_id, pos) for _, d, pos in assigned if pos is not None
        ]
        return tuple(d for _, d, _ in assigned)
