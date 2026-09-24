"""Consumer FrameSource implementing MPE 0.3.0 public contracts."""
from __future__ import annotations
import hashlib
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from mpe.core.kinds import Determinism
from mpe.core.origin import Origin, OriginKind
from mpe.core.provenance import Provenance
from mpe.core.stamp import Stamp
from mpe.ingest.frame import FrameRecord

class ConsumerFrameSource:
    component_id = "consumer-frame-source"
    component_version = "0.1.0"
    def __init__(self, frames_dir: str | Path, *, source_id: str = "consumer-source",
                 clock_domain: str = "consumer", base_timestamp: datetime | None = None) -> None:
        self.frames_dir = Path(frames_dir)
        self.source_id = source_id
        self.clock_domain = clock_domain
        self.base_timestamp = base_timestamp or datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        if self.base_timestamp.tzinfo is None:
            raise ValueError("base_timestamp must be timezone-aware")
    def frames(self) -> Iterator[FrameRecord]:
        paths = sorted(self.frames_dir.glob("frame_*.jpg"))
        if not paths:
            raise FileNotFoundError(f"no frame_*.jpg under {self.frames_dir}")
        origin = Origin(OriginKind.SENSOR, self.source_id)
        for sequence, path in enumerate(paths):
            payload = path.read_bytes()
            h = hashlib.sha256(payload).hexdigest()
            ts = self.base_timestamp + timedelta(seconds=sequence)
            stamp = Stamp(self.source_id, sequence, ts, self.clock_domain)
            prov = Provenance(
                origin=origin, timestamp=ts, parent_artifact_ids=(h,),
                component_id=self.component_id, component_version=self.component_version,
                determinism=Determinism.STRICT,
            )
            yield FrameRecord(stamp, origin, sequence, payload, h, prov)
