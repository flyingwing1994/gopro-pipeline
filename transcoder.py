import subprocess
from pathlib import Path

def transcode_clip(input_path: Path, output_path: Path, mode: str, lut_path: str = "GoPro_GP-Log_to_Rec709.cube") -> bool:
    """
    mode:
      - 'log': Pas de GP-Log naar Rec.709 3D LUT toe, schaal naar 1080p en zet om naar 25fps.
      - 'standard': Geen kleurcorrectie, schaal naar 1080p en zet om naar 25fps.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if mode == "log":
        # LUT toepassen, schalen naar 1080p en forceren naar 25fps
        video_filter = f"lut3d='{lut_path}',scale=-2:1080,fps=25"
    elif mode == "standard":
        # Alleen schalen en forceren naar 25fps
        video_filter = "scale=-2:1080,fps=25"
    else:
        raise ValueError(f"Onbekende modus: {mode}")

    # FFmpeg commando: CUDA decode, NVENC encode (CQ 25), Rec.709 container metadata en AAC audio
    cmd = [
        "ffmpeg", "-y",
        "-hwaccel", "cuda",
        "-i", str(input_path),
        "-vf", video_filter,
        "-c:v", "h264_nvenc",
        "-preset", "p6",
        "-cq", "25",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-colorspace", "bt709",
        "-c:a", "aac",
        "-b:a", "128k",
        str(output_path)
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0

def extract_thumbnail(video_path: Path, thumb_path: Path) -> bool:
    """Genereert een snelle JPEG-thumbnail op 1 seconde in de video voor preview."""
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    if thumb_path.exists():
        return True

    cmd = [
        "ffmpeg", "-y",
        "-ss", "00:00:01",
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "3",
        str(thumb_path)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return res.returncode == 0