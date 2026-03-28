# VisoMaster — Headless Cloud Edition

> A fork of [visomaster/VisoMaster](https://github.com/visomaster/VisoMaster) refactored for GPU-cloud deployment.  
> Run real-time AI face swapping on **Modal.com** serverless GPUs — no local GPU required.

---

## What This Fork Does Differently

The original VisoMaster is a PySide6 desktop app where the entire inference core (`ModelsProcessor`, `FrameWorker`) is tightly coupled to the GUI's `MainWindow`. This fork decouples that relationship and introduces a **clean shared processing core** that both the GUI and a headless cloud server can use without modification.

### Key Changes

| File | Change |
|---|---|
| `app/processors/processing_core.py` | **New.** Shared `ProcessingCore` class. Owns `ModelsProcessor` and exposes `embed_face()` and `process_frame()`. No UI imports. |
| `app/processors/models_processor.py` | Refactored. `__init__` now takes `controls: dict, parameters: dict` instead of `main_window: MainWindow` |
| `app/processors/workers/frame_worker.py` | Refactored. `__init__` now takes `control: dict, parameters: dict, models_processor` instead of `main_window` |
| `app/ui/main_ui.py` | Updated to instantiate `ProcessingCore(controls, parameters)` instead of `ModelsProcessor(self)` |
| `headless_engine.py` | Rewritten. Uses `ProcessingCore` directly. No Qt mocking. No `FrameWorker.__new__` hacks. |
| `modal_server.py` | FastAPI + WebSocket server. Deploys `HeadlessEngine` on Modal A10G GPU. |
| `desktop_client/` | Lightweight Python client. Captures webcam → streams to Modal → outputs to virtual camera. |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Desktop Client                        │
│  Webcam → JPEG encode → WebSocket → DroidCam/VirtualCam │
└───────────────────────┬─────────────────────────────────┘
                        │  WebSocket (JPEG frames)
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Modal GPU Server (A10G)                     │
│  FastAPI WebSocket → HeadlessEngine → ProcessingCore     │
│                                    → ModelsProcessor     │
│                                    → FrameWorker         │
└─────────────────────────────────────────────────────────┘

GUI path (unchanged UX):
  MainWindow → ProcessingCore(controls, parameters)
                    └── ModelsProcessor
                    └── FrameWorker
```

Both the GUI desktop app and the headless cloud server share **exactly the same** `ProcessingCore` — no divergence, no adapter hacks.

---

## Quick Start

### 1. Clone this fork

```bash
git clone https://github.com/Elavn/VisoMaster.git
cd VisoMaster
```

### 2. Install dependencies

```bash
conda create -n visomaster python=3.10.13
conda activate visomaster
conda install cuda cudnn -c nvidia
pip install -r requirements_cu124.txt
```

### 3. Download models

```bash
python download_models.py
```

### 4a. Run the desktop GUI (unchanged from original)

```bash
python main.py
```

### 4b. Deploy to Modal (headless cloud)

```bash
pip install modal
modal setup        # authenticate once
modal deploy modal_server.py
```

This gives you a `wss://` endpoint URL. Copy it.

### 5. Run the desktop client (connects to Modal)

```bash
cd desktop_client
pip install -r requirements.txt
python main.py --server wss://YOUR-APP.modal.run/swap
```

Your webcam feed is now face-swapped in real-time on a cloud GPU and output to a virtual camera — visible to WhatsApp, Zoom, Google Meet, or any app that reads your camera.

---

## Configuration

All inference settings are controlled through two plain dicts — no GUI required on the server side.

### `headless_config.py`

```python
DEFAULT_CONTROLS = {
    'ProvidersPrioritySelection': 'CUDA',
    'DetectorModelSelection': 'RetinaFace',
    'DetectorScoreSlider': 65,
    'LandmarkDetectToggle': True,
    'LandmarkDetectModelSelection': '2dfan4',
    'RecognitionModelSelection': 'CSCSArcFace',
    'SwapperModelSelection': 'Inswapper128',
    'RestorerToggle': False,       # enable for higher quality, more GPU cost
    'MaskTypeSelection': 'box',
    'MaskBlurSlider': 20,
    'ModelsDir': '/models',
}

DEFAULT_PARAMETERS = {
    'FaceSwapperToggle': True,
    'FaceSimilaritySlider': 60,
    'RestorerToggle': False,
    'FaceEditorToggle': False,     # LivePortrait — off for real-time speed
}
```

Swap `RestorerToggle: True` to enable GFPGAN enhancement at the cost of ~20ms extra per frame.

---

## GPU Cost on Modal

Modal bills per second, only while your WebSocket is active. The container idles (and stops billing) 5 minutes after you disconnect.

| Usage | GPU | Cost |
|---|---|---|
| 1 hr call/day | A10G | ~$2.10/day |
| 2 hrs call/day | A10G | ~$4.20/day |
| Casual use (~10 hrs/month) | A10G | ~$2.10/month |
| **Modal free tier** | — | **$30/month credit** |

The $30 monthly free credit covers approximately **14 hours of active GPU time** — enough for daily personal use.

---

## Desktop Client → Virtual Camera → WhatsApp

```
Webcam (your face)
    ↓
desktop_client/main.py    ← captures at 640×480, 15fps
    ↓ WebSocket JPEG
Modal GPU (VisoMaster inference)
    ↓ WebSocket JPEG (swapped face)
pyvirtualcam              ← pushes to virtual camera
    ↓
DroidCam Virtual Camera   ← WhatsApp, Zoom, Meet see this
```

### DroidCam Setup (Windows)

1. Install [DroidCam OBS](https://www.dev47apps.com/droidcam/obs/)
2. It registers as a system virtual camera
3. Select **DroidCam** as your camera in WhatsApp/Zoom
4. Start `desktop_client/main.py` — it writes to DroidCam automatically

---

## File Structure

```
VisoMaster/
│
├── main.py                          ← Original GUI entry point (unchanged)
├── modal_server.py                  ← Modal deployment + WebSocket API
├── headless_engine.py               ← Clean headless wrapper (no Qt)
├── headless_config.py               ← Default controls + parameters dicts
├── download_models.py               ← Model downloader
│
├── app/
│   ├── processors/
│   │   ├── processing_core.py       ← ★ NEW — shared inference core
│   │   ├── models_processor.py      ← Refactored (dict-based, no MainWindow)
│   │   ├── face_detectors.py
│   │   ├── face_swappers.py
│   │   ├── face_restorers.py
│   │   ├── face_editors.py          ← LivePortrait
│   │   ├── face_masks.py
│   │   ├── frame_enhancers.py
│   │   ├── models_data.py           ← Full model catalog
│   │   └── workers/
│   │       └── frame_worker.py      ← Refactored (dict-based, no MainWindow)
│   │
│   ├── ui/                          ← Original GUI (unchanged UX)
│   └── helpers/
│       ├── downloader.py
│       └── miscellaneous.py
│
├── desktop_client/
│   ├── main.py                      ← Webcam capture + WebSocket client
│   ├── streamer.py                  ← VisoStreamer class
│   └── requirements.txt
│
└── model_assets/                    ← ONNX model configs
```

---

## Supported Models

### Face Detection
- RetinaFace, SCRFD, YOLOv8, Yunet

### Face Swapping
- Inswapper128, InStyleSwapper, SimSwap, GhostFace

### Face Enhancement
- GFPGAN, CodeFormer

### Face Editing
- LivePortrait (expression/pose control)

### Landmark Detection
- 5-point, 68-point, 106-point, 203-point, 478-point

---

## Latency Expectations

Real-time performance depends on your distance to the Modal datacenter. Use the **EU region** for lowest latency from Africa and Europe.

| Component | Time |
|---|---|
| Frame encode (local) | ~5ms |
| Network (Lagos → EU Modal) | ~80–150ms |
| GPU inference (A10G) | ~30–60ms |
| Network return + decode | ~80–150ms |
| **Total round-trip** | **~200–400ms** |

This produces a slight but visible delay on video calls — comparable to a mildly laggy internet connection. Audio is unaffected.

---

## Credits

- **Original project**: [visomaster/VisoMaster](https://github.com/visomaster/VisoMaster) — GPL-3.0
- **Inference models**: InsightFace, GFPGAN, CodeFormer, LivePortrait
- **Cloud infrastructure**: [Modal.com](https://modal.com)

---

## License

GPL-3.0 — same as the original. See [LICENSE](./LICENSE).
