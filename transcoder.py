import json
import subprocess
from pathlib import Path

def detect_is_log(video_path: Path) -> bool:
    """
    Controleert via ffprobe of de clip 10-bit is (GP-Log gebruikt yuv420p10le).
    8-bit clips (timelapses / standard Rec.709) geven False terug.
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=pix_fmt",
        "-of", "json",
        str(video_path)
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            streams = data.get("streams", [])
            if streams:
                pix_fmt = streams[0].get("pix_fmt", "")
                return "10" in pix_fmt  # True als het 10-bit (yuv420p10le) is
    except Exception:
        pass
    return True  # Fallback naar GP-Log bij twijfel

def transcode_clip(input_path: Path, output_path: Path, mode: str, lut_path: str = "GoPro_GP-Log_to_Rec709.cube") -> bool:
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if mode == "log":
        video_filter = f"lut3d='{lut_path}',scale=-2:1080,fps=25"
    elif mode == "standard":
        video_filter = "scale=-2:1080,fps=25"
    else:
        raise ValueError(f"Onbekende modus: {mode}")

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
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    if thumb_path.exists() and thumb_path.stat().st_size > 0:
        return True

    cmd = [
        "ffmpeg", "-y",
        "-ss", "00:00:01",
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "3",
        str(thumb_path)
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if not thumb_path.exists() or thumb_path.stat().st_size == 0:
        cmd_fallback = [
            "ffmpeg", "-y",
            "-ss", "00:00:00",
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "3",
            str(thumb_path)
        ]
        subprocess.run(cmd_fallback, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return thumb_path.exists() and thumb_path.stat().st_size > 0