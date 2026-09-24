"""Real HSV + connected-components Detector (no ML, no MockA/MockB)."""
from __future__ import annotations
from io import BytesIO
import numpy as np
from PIL import Image
from mpe.core.kinds import Determinism, EvidenceKind
from mpe.core.origin import Origin, OriginKind
from mpe.core.provenance import Provenance
from mpe.domain.contracts import Detection
from mpe.ingest.frame import FrameRecord

# Tuned for Big Buck Bunny opening (saturated green landscape / characters)
HSV_LOW = (35, 40, 40)
HSV_HIGH = (95, 255, 255)
MIN_AREA = 800  # on 0.5-scale image

def _rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    return np.array(Image.fromarray(rgb, mode="RGB").convert("HSV"))

def _cc(mask: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    h, w = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    out: list[tuple[int, int, int, int, int]] = []
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or visited[y, x]:
                continue
            stack = [(x, y)]; visited[y, x] = True
            min_x = max_x = x; min_y = max_y = y; area = 0
            while stack:
                cx, cy = stack.pop(); area += 1
                min_x, max_x = min(min_x, cx), max(max_x, cx)
                min_y, max_y = min(min_y, cy), max(max_y, cy)
                for nx, ny in ((cx-1,cy),(cx+1,cy),(cx,cy-1),(cx,cy+1)):
                    if 0 <= nx < w and 0 <= ny < h and mask[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True; stack.append((nx, ny))
            out.append((min_x, min_y, max_x-min_x+1, max_y-min_y+1, area))
    return out

class ColorBlobDetector:
    determinism_class = Determinism.STRICT
    component_id = "consumer-detector"
    component_version = "0.1.0"
    class_label = "target"
    def detect(self, frame: FrameRecord) -> tuple[Detection, ...]:
        if frame.stamp.capture_timestamp is None:
            raise ValueError("ColorBlobDetector requires stamp.capture_timestamp")
        img = Image.open(BytesIO(frame.payload_bytes)).convert("RGB")
        fw, fh = img.size
        scale = 0.5
        img = img.resize((int(fw * scale), int(fh * scale)))
        inv = 1.0 / scale
        rgb = np.array(img)
        hsv = _rgb_to_hsv(rgb)
        h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
        mask = (
            (h >= HSV_LOW[0]) & (h <= HSV_HIGH[0])
            & (s >= HSV_LOW[1]) & (s <= HSV_HIGH[1])
            & (v >= HSV_LOW[2]) & (v <= HSV_HIGH[2])
        )
        comps = [c for c in _cc(mask) if c[4] >= MIN_AREA]
        comps.sort(key=lambda c: c[4], reverse=True)
        origin = Origin(OriginKind.ALGORITHM, self.component_id)
        ts = frame.stamp.capture_timestamp
        prov = Provenance(
            origin=origin, timestamp=ts, parent_artifact_ids=(frame.hash,),
            input_artifact_hashes=((frame.hash, frame.hash),),
            component_id=self.component_id, component_version=self.component_version,
            determinism=Determinism.STRICT,
        )
        detections: list[Detection] = []
        fa = float(rgb.shape[0] * rgb.shape[1])
        for idx, (x, y, bw, bh, area) in enumerate(comps[:3]):
            score = min(1.0, area / max(fa * 0.05, 1.0))
            detections.append(Detection(
                detection_id=f"{frame.sequence:03d}-{idx}",
                stamp=frame.stamp,
                class_label=self.class_label,
                geometry={
                    "bbox": [int(x * inv), int(y * inv), int(bw * inv), int(bh * inv)],
                    "centroid": [(x + bw / 2) * inv, (y + bh / 2) * inv],
                },
                score=score,
                provenance=prov,
                evidence_kind=EvidenceKind.MEASURED,
                model_ref=None,
                quality="valid",
            ))
        return tuple(detections)
