# mpe-consumer-example

External **microconsumer validation probe** for [MPE](https://github.com/edu-moraess/multimodal-perception-engine) **contracts 0.3.0**.

> This repository is an external consumer validation probe for MPE 0.3.0. It is not part of the MPE architecture.

## Objective

Demonstrate that an independent project can:

1. install MPE as an **external dependency**;
2. ingest real public video frames;
3. produce real `Detection` values (HSV + connected components, no ML);
4. call `MockTracker` / `TrackingProtocol` from MPE;
5. obtain real `TrackState` values;
6. `serialize` → JSON → `deserialize` with field-level roundtrip checks.

## MPE relation

| Item | Value |
|------|--------|
| MPE repository | https://github.com/edu-moraess/multimodal-perception-engine |
| Target commit | `5b3970bcef2da6bc7b3e4993da928025b0eccc67` |
| CONTRACTS_VERSION | `0.3.0` |
| Install | `pip install -e /path/to/multimodal-perception-engine` |

Do **not** copy `src/mpe` into this repository.

## Video

| Field | Value |
|-------|--------|
| URL | https://download.blender.org/demo/movies/BBB/bbb_sunflower_1080p_30fps_normal.mp4.zip |
| Source | Blender Foundation — *Big Buck Bunny* (first 20 s, 1080p) |
| License | **CC BY 3.0** |
| Evidence | https://creativecommons.org/licenses/by/3.0/ ; https://archive.org/download/BigBuckBunny_124/License.txt |
| Duration | 20 s |
| Resolution | 1920×1080 |

Place the 20 s clip at `data/big_buck_bunny_20s_1080p.mp4` (gitignored).

## Install & run

```bash
pip install -e /path/to/multimodal-perception-engine
pip install -e .
python fetch_frames.py
python run.py
```

Expected: exit code 0, ≥60% frames with TrackState, explicit roundtrip PASS on track_id, stamp, geometry, source_detection_ids, evidence_kind, provenance.

## Detector

HSV H=35–95, S≥40, V≥40; min area 800 @ 0.5 scale; `evidence_kind=MEASURED`; Pillow + NumPy only.

## Limitations

- Colour-blob detector is a validation probe, not a production model.
- Tracking uses MPE `MockTracker` only (identity association, no motion model).
- Video binary is not stored in git (download + local 20 s clip).
