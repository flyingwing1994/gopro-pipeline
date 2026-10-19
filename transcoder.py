import json
import subprocess
from pathlib import Path


def detect_is_log(video_path: Path) -> bool:
    """Controleert via ffprobe of de clip 10-bit is (GP-Log gebruikt yuv420p10le).

    8-bit clips (timelapses / standard Rec.709) geven False terug.
    """
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=pix_fmt",
        "-of",
        "json",
        str(video_path),
    ]
    try:
        res = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if res.returncode == 0:
            data = json.loads(res.stdout)
            streams = data.get("streams", [])
            if streams:
                pix_fmt = streams[0].get("pix_fmt", "")
                return "10" in pix_fmt
    except Exception:
        pass
    return True


def get_video_duration(video_path: Path) -> float:
    """Haalt de totale duur van de video in seconden op via ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        res = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if res.returncode == 0:
            return float(res.stdout.strip())
    except Exception:
        pass
    return 0.0


def transcode_clip(
    input_path: Path,
    output_path: Path,
    mode: str,
    lut_path: str = "GoPro_GP-Log_to_Rec709.cube",
    progress_callback=None,
) -> bool:
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    duration = get_video_duration(input_path)

    if mode == "log":
        video_filter = f"lut3d='{lut_path}',scale=-2:1080,fps=25,format=yuv420p"
    elif mode == "standard":
        video_filter = "scale=-2:1080,fps=25,format=yuv420p"
    else:
        raise ValueError(f"Onbekende modus: {mode}")

    cmd = [
        "ffmpeg",
        "-y",
        "-hwaccel",
        "cuda",
        "-i",
        str(input_path),
        "-vf",
        video_filter,
        "-c:v",
        "h264_nvenc",
        "-preset",
        "p4",
        "-cq",
        "25",
        "-pix_fmt",
        "yuv420p",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-colorspace",
        "bt709",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        str(output_path),
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )

    if process.stdout:
        for line in process.stdout:
            line = line.strip()
            if line.startswith("out_time_us="):
                try:
                    micros = int(line.split("=")[1])
                    secs = micros / 1_000_000.0
                    if duration > 0 and progress_callback:
                        pct = min(100.0, max(0.0, (secs / duration) * 100.0))
                        progress_callback(pct)
                except ValueError:
                    pass

    process.wait()
    return process.returncode == 0


def extract_thumbnail(video_path: Path, thumb_path: Path) -> bool:
    """Genereert een JPEG-thumbnail voor preview."""
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    if thumb_path.exists() and thumb_path.stat().st_size > 0:
        return True

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        "00:00:01",
        "-i",
        str(video_path),
        "-vframes",
        "1",
        "-q:v",
        "3",
        str(thumb_path),
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if not thumb_path.exists() or thumb_path.stat().st_size == 0:
        cmd_fallback = [
            "ffmpeg",
            "-y",
            "-ss",
            "00:00:00",
            "-i",
            str(video_path),
            "-vframes",
            "1",
            "-q:v",
            "3",
            str(thumb_path),
        ]
        subprocess.run(
            cmd_fallback, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

    return thumb_path.exists() and thumb_path.stat().st_size > 0