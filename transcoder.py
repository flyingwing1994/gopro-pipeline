import subprocess
from pathlib import Path

def transcode_clip(input_path: Path, output_path: Path, mode: str, lut_path: str = "GoPro_GP-Log_to_Rec709.cube") -> bool:
    """
    mode:
      - 'log': Pas de GP-Log naar Rec.709 3D LUT toe en schaal naar 1080p
      - 'standard': Geen kleurcorrectie, puur schalen naar 1080p
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if mode == "log":
        video_filter = f"lut3d='{lut_path}',scale=-2:1080"
    elif mode == "standard":
        video_filter = "scale=-2:1080"
    else:
        raise ValueError(f"Onbekende modus: {mode}")

    # FFmpeg commando met CUDA hardware decode en NVENC hardware encode
    cmd = [
        "ffmpeg", "-y",
        "-hwaccel", "cuda",
        "-i", str(input_path),
        "-vf", video_filter,
        "-c:v", "h264_nvenc",
        "-preset", "p6",
        "-cq", "20",
        "-c:a", "copy",
        str(output_path)
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0