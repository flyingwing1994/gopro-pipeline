GoPro Video PipelineAn automated, hardware-accelerated batch processing and cloud-sync pipeline designed for GoPro footage. This utility transforms high-bitrate raw GP-Log captures into standardized 1080p Rec.709 deliveries using dedicated GPU encoding (NVIDIA NVENC) and directly uploads organized collections to Google Photos.💡 Overview & Problem StatementShooting in GP-Log unlocks maximum dynamic range and 10-bit color depth on modern GoPro action cameras (Hero 11, 12, 13). However, GP-Log footage presents distinct workflow bottlenecks:Flat Log Profile: Unprocessed clips look washed-out, desaturated, and lack proper contrast when previewed outside specialized NLE suites.Heavy File Sizes: 4K and 5.3K files quickly saturate local storage and require substantial bandwidth to share.Color Tag Mismatch: Without explicit Rec.709 matrix and transfer characteristics metadata, video players and cloud platforms (such as Google Photos) frequently misinterpret gamma curves.GoPro Video Pipeline solves this by providing a streamlined, local graphical web dashboard powered by Streamlit. It applies official mathematical Color Space Transformations (CST) through 3D LUTs, scales media efficiently using hardware-accelerated NVENC pipelines, and uploads batches directly to designated albums via the Google Photos Library API.🚀 Key FeaturesSelective Color Pipeline:GP-Log Mode: Maps wide-gamut log curves to standardized Rec.709 via the official GoPro 3D LUT (.cube), preserving highlight rolloff and shadow detail.Standard Passthrough Mode: Bypasses LUT operations for clips captured in standard profiles or Timelapses/TimeWarps, performing downscaling only.Skip Mode: Exclude individual clips from the current processing batch without deleting files.Hardware Acceleration (NVIDIA CUDA & NVENC):Utilizes h264_nvenc encoding with high-quality presets (p6) and Constant Quality rate control (-cq 20).Offloads decoding to CUDA where available to keep host CPU usage low.Color Metadata Enforcement:Explicitly injects -color_primaries bt709, -color_trc bt709, and -colorspace bt709 tags into exported MP4 containers to ensure uniform reproduction across mobile devices, web browsers, and cloud decoders.Automated Cloud Sync:Integrated with the Google Photos Library API.Supports automated album creation and matching.Employs resumable, chunk-ready uploads for large deliveries.Interactive Web Interface:Fast, local Streamlit dashboard allowing users to audit source directories, assign per-clip export modes, toggle cloud sync, and monitor live progress meters.🏗 Pipeline Architecture[ GoPro SD Card / Local Storage ]
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
📋 Prerequisites1. Hardware & Operating SystemOS: Windows 10/11 (64-bit).GPU: Dedicated NVIDIA GeForce or RTX graphics card supporting NVENC encoding (Pascal architecture or newer recommended).2. Software DependenciesPython: Version 3.10 or higher.FFmpeg: Compiled with h264_nvenc and LUT filter support.Easily installed via Windows Package Manager:winget install Gyan.FFmpeg
Verify your installation by running:ffmpeg -encoders | findstr nvenc
3. External AssetsGoPro GP-Log 3D LUT: Place GoPro_GP-Log_to_Rec709.cube in the project root directory. (Provided by GoPro for GP-Log cameras).Google Cloud OAuth Credentials: Place credentials.json in the project root directory (see Google Cloud Setup).📁 Default Directory LayoutBy default, the script targets the following directories:ComponentDefault PathDescriptionInput DirectoryC:\Users\Admin\Videos\GoPro\inputRaw footage imported from the cameraOutput DirectoryC:\Users\Admin\Videos\GoPro\outputRendered 1080p Rec.709 deliverablesProject RootC:\Users\Admin\Documents\Code\gopro-pipelinePython source code, configs, and assets⚙️ Installation & Setup1. Clone the Repositorygit clone https://github.com/flyingwing1994/gopro-pipeline.git
cd gopro-pipeline
2. Set Up Virtual Environmentpython -m venv venv
.\venv\Scripts\Activate.ps1
3. Install Python Dependenciespip install -r requirements.txt
4. Provide Configuration FilesEnsure both configuration files are present in the root folder:credentials.jsonGoPro_GP-Log_to_Rec709.cube🔑 Google Cloud SetupTo enable automated uploads to Google Photos:Visit the Google Cloud Console.Create a new project (e.g., GoPro-Pipeline-Sync).Navigate to APIs & Services > Library, search for Photos Library API, and click Enable.Navigate to APIs & Services > OAuth consent screen:User Type: External.Fill in mandatory support emails.Add the test scope: https://www.googleapis.com/auth/photoslibrary.Add your own Google account as a Test User (under the Test Users tab).Navigate to APIs & Services > Credentials:Click Create Credentials > OAuth client ID.Application Type: Desktop App.Download the generated JSON file, rename it to credentials.json, and place it in the project root.On the first upload run, your web browser will prompt you to authenticate and authorize access. An active token is saved locally as token.json for subsequent unattended runs.🖥️ UsageRunning the Web DashboardEnsure your virtual environment is active, then execute:streamlit run app.py
Or execute the provided batch helper:.\start_app.bat
Workflow Steps:Copy raw GoPro files (.mp4) into C:\Users\Admin\Videos\GoPro\input.Access the dashboard at http://localhost:8501.In the sidebar:Toggle Upload naar Google Photos on or off.Specify the target Albumnaam (the album will be created automatically if it does not exist).Review the auto-detected clips table:GP-Log (LUT + 1080p): Converts GP-Log color space and scales to 1920x1080.Standaard Rec.709 (Alleen 1080p): Scales to 1080p without applying color transforms.Overslaan: Ignores the clip.Click Start Batch Verwerking. Processing logs and progress bars will report render and upload states in real time.🔒 Security & Safe VersioningThis project adheres to strict isolation of sensitive credentials:credentials.json and token.json contain sensitive OAuth secrets and refresh tokens; both are explicitly ignored via .gitignore.Video binary assets (*.mp4, *.mov, *.lrv, *.thm) and custom LUT files (*.cube) are excluded from tracking to keep the repository lightweight.Refer to credentials.json.example for the expected schema when deploying on a new machine.📄 LicenseDistributed under the MIT License. See LICENSE for further details.