# GoPro Video Pipeline

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B.svg)](https://streamlit.io/)
[![FFmpeg](https://img.shields.io/badge/Render-FFmpeg%20NVENC-007808.svg)](https://ffmpeg.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An automated, hardware-accelerated batch processing and cloud-sync pipeline designed for GoPro footage. This utility transforms high-bitrate raw GP-Log captures into standardized **1080p Rec.709** deliveries using dedicated GPU encoding (NVIDIA NVENC) and directly uploads organized collections to **Google Photos**.

---

## Key Features

- **Selective Color Pipeline:**
  - **GP-Log Mode:** Maps wide-gamut log curves to standardized Rec.709 via the official GoPro 3D LUT (`.cube`), preserving highlight rolloff and shadow detail.
  - **Standard Passthrough Mode:** Bypasses LUT operations for clips captured in standard profiles or Timelapses/TimeWarps, performing downscaling only.
  - **Skip Mode:** Exclude individual clips from the current processing batch without deleting files.
- **Hardware Acceleration (NVIDIA CUDA & NVENC):**
  - Utilizes `h264_nvenc` encoding with high-quality presets (`p6`) and Constant Quality rate control (`-cq 20`).
  - Offloads decoding to CUDA where available to keep host CPU usage low.
- **Color Metadata Enforcement:**
  - Explicitly injects `-color_primaries bt709`, `-color_trc bt709`, and `-colorspace bt709` tags into exported MP4 containers to ensure uniform reproduction across mobile devices, web browsers, and cloud decoders.
- **Automated Cloud Sync:**
  - Integrated with the **Google Photos Library API**.
  - Supports automated album creation and matching.
  - Employs resumable, chunk-ready uploads for large deliveries.
- **Interactive Web Interface:**
  - Fast, local Streamlit dashboard allowing users to audit source directories, assign per-clip export modes, toggle cloud sync, and monitor live progress meters.

---

## Pipeline Architecture

```text
[ GoPro SD Card / Local Storage ]
               │
               ▼
   [ Input Directory (Raw MP4s) ]
               │
               ▼
┌──────────────────────────────────────────────┐
│       Streamlit Dashboard (Local Web UI)     │
│  - File Discovery & Pre-flight Validation   │
│  - Per-clip Action Selection (Log/Std/Skip)  │
│  - Album Target & Upload Toggles             │
└──────────────────────┬───────────────────────┘
                       │ [Start Processing]
                       ▼
┌──────────────────────────────────────────────┐
│           FFmpeg Processing Core             │
│  ├── Hardware Decode (CUDA)                  │
│  ├── Filter Graph (Scale 1080p + 3D LUT)     │
│  ├── Tagging (Rec.709 container metadata)    │
│  └── Hardware Encode (NVENC h264_nvenc)      │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
  [ Output Directory (1080p Rec.709 MP4s) ]
                       │
                       ▼ [Optional Upload]
┌──────────────────────────────────────────────┐
│           Google Photos Uploader             │
│  ├── OAuth 2.0 Token Refresh / Handling      │
│  ├── Resumable Binary Byte Upload            │
│  └── Batch Item Assignment to Target Album   │
└──────────────────────────────────────────────┘
```

---

## Prerequisites

| Requirement | Specification | Purpose |
| :--- | :--- | :--- |
| **OS & GPU** | Windows 10/11 (64-bit) + NVIDIA GPU | NVENC / CUDA hardware pipeline |
| **Python** | 3.10 or higher | Runtime for Streamlit dashboard and API client |
| **FFmpeg** | Build with NVENC (`winget install Gyan.FFmpeg`) | Video decoding, scaling, 3D LUT filtering & encoding |
| **GoPro LUT** | `GoPro_GP-Log_to_Rec709.cube` | Official 3D LUT for GP-Log to Rec.709 transformation |
| **Google Cloud** | OAuth Desktop Client (`credentials.json`) | Photos Library API credentials |

---

## Default Directory Layout

| Component | Default Path | Description |
| :--- | :--- | :--- |
| **Input Directory** | `C:\\Users\\Admin\\Videos\\GoPro\\input` | Raw footage imported from the camera |
| **Output Directory** | `C:\\Users\\Admin\\Videos\\GoPro\\output` | Rendered 1080p Rec.709 deliverables |
| **Project Root** | `C:\\Users\\Admin\\Documents\\Code\\gopro-pipeline` | Application source, assets and virtual environment |

---

## Installation & Setup

### 1. Clone Repository & Setup Environment

```powershell
git clone https://github.com/flyingwing1994/gopro-pipeline.git
cd gopro-pipeline
python -m venv venv
.\\venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
```

### 2. Place Configuration Files

Ensure both required files are placed in the root directory:
- `credentials.json` (Google OAuth 2.0 Client ID)
- `GoPro_GP-Log_to_Rec709.cube` (GoPro Official GP-Log 3D LUT)

---

## Usage

### Launching the Dashboard

Execute the Windows batch helper:
```powershell
.\\start_app.bat
```
*Or via terminal:*
```powershell
streamlit run app.py
```

### Operational Workflow:
1. Transfer raw files into the input directory (`...\\GoPro\\input`).
2. Open the dashboard at `http://localhost:8501`.
3. In the sidebar:
   - Configure the target Google Photos album name.
   - Toggle automated upload on or off.
4. Set the processing action for each clip:
   - `GP-Log (LUT + 1080p)`: Transforms GP-Log gamma/gamut and scales to 1080p.
   - `Standaard Rec.709 (Alleen 1080p)`: Direct scale to 1080p without color transforms.
   - `Overslaan`: Excludes the file from batch execution.
5. Click **Start Batch Verwerking**.

---

## License

Distributed under the **MIT License**. See `LICENSE` for details.