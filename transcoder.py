import subprocess
from pathlib import Path


def process_video(
    input_path: Path,
    output_path: Path,
    mode: str,
    lut_path: Path
) -> bool:
    """
    Processes a video file with FFmpeg using NVIDIA NVENC hardware acceleration.
    
    Modes:
      - 'GP-Log (LUT + 1080p)': Scales to 1080p and applies the 3D LUT (CST equivalent).
      - 'Standaard Rec.709 (Alleen 1080p)': Scales to 1080p without LUT adjustments.
      - 'Overslaan': Skips processing.
    """
    if mode == "Overslaan":
        return True

    input_path = Path(input_path)
    output_path = Path(output_path)
    lut_path = Path(lut_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Base scale filter
    scale_filter = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2"

    if "GP-Log" in mode:
        if not lut_path.exists():
            raise FileNotFoundError(f"LUT bestand niet gevonden op: {lut_path}")
        
        # Format the Windows path safely for FFmpeg filtergraphs (escape backslashes and colon)
        lut_str = str(lut_path.resolve()).replace("\\", "/").replace(":", "\\:")
        video_filter = f"{scale_filter},lut3d=file='{lut_str}'"
    else:
        video_filter = scale_filter

    cmd = [
        "ffmpeg", "-y",
        "-hwaccel", "cuda",
        "-i", str(input_path),
        "-vf", video_filter,
        "-c:v", "h264_nvenc",
        "-preset", "p6",
        "-cq", "20",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-colorspace", "bt709",
        "-c:a", "copy",
        str(output_path)
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Fout tijdens transcoderen van {input_path.name}:")
        print(e.stderr)
        return False