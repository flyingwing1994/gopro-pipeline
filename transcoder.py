import os
import json
import logging
import subprocess
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Paden bepalen & config importeren met automatische fallback
BASE_DIR = Path(__file__).resolve().parent

try:
    from config import LOG_FILE, LUT_FILE
except ImportError:
    LOG_FILE = BASE_DIR / "pipeline.log"
    LUT_FILE = BASE_DIR / "GoPro_GP-Log_to_Rec709.cube"

# Automatische logrotatie: max 5 MB per bestand, bewaart maximaal 3 back-ups
logger = logging.getLogger("gopro_pipeline")
logger.setLevel(logging.INFO)

if not logger.handlers:
    file_handler = RotatingFileHandler(
        str(LOG_FILE), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(file_handler)


def detect_is_log(video_path: Path) -> bool:
    """Controleert via ffprobe of de clip 10-bit is (GP-Log gebruikt yuv420p10le)."""
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
                return "10" in pix_fmt
    except Exception as e:
        logger.warning(f"Detectiefout voor {video_path.name}: {e}")
    return True


def get_video_duration(video_path: Path) -> float:
    """Haalt de exacte speelduur in seconden op via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path)
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            return float(res.stdout.strip())
    except Exception:
        pass
    return 0.0


def transcode_clip(
    input_path: Path,
    output_path: Path,
    mode: str,
    lut_path: str = None,
    progress_callback=None
) -> bool:
    """
    Transcodeert een clip via de NVIDIA GPU (CUDA + NVENC).
    Behoudt originele metadata, QuickTime tags en fysieke aanmaaktijd.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if lut_path is None:
        lut_path = str(LUT_FILE)

    duration = get_video_duration(input_path)
    logger.info(f"Start GPU transcode: {input_path.name} (Modus: {mode}, Lengte: {duration:.1f}s)")

    # Hardwarematige GPU-schaling: scale_cuda verkleint direct op de videokaart naar 1080p
    if mode == "log":
        video_filter = f"scale_cuda=1920:1080,hwdownload,format=p010le,lut3d='{lut_path}',fps=25,format=yuv420p"
    elif mode == "standard":
        video_filter = "scale_cuda=1920:1080,hwdownload,format=nv12,fps=25,format=yuv420p"
    else:
        raise ValueError(f"Onbekende modus: {mode}")

    cmd = [
        "ffmpeg", "-y",
        "-hwaccel", "cuda",
        "-hwaccel_output_format", "cuda",
        "-i", str(input_path),
        "-map_metadata", "0",
        "-movflags", "+faststart+use_metadata_tags",
        "-vf", video_filter,
        "-c:v", "h264_nvenc",
        "-preset", "p4",
        "-cq", "25",
        "-pix_fmt", "yuv420p",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-colorspace", "bt709",
        "-c:a", "aac",
        "-b:a", "128k",
        "-progress", "pipe:1",
        "-nostats",
        str(output_path)
    ]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Voorkomt OS buffer deadlocks
            text=True,
            bufsize=1
        )

        error_lines = []
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
                elif any(err_word in line.lower() for err_word in ["error", "impossible", "failed"]):
                    error_lines.append(line)

        process.wait()
        if process.returncode != 0:
            err_msg = "\n".join(error_lines[-10:])
            logger.error(f"FFmpeg fout bij {input_path.name}:\n{err_msg}")
            return False

        # Zet fysieke bestandstijdstempels (created/modified) exact gelijk aan het origineel
        try:
            orig_stat = input_path.stat()
            os.utime(output_path, (orig_stat.st_atime, orig_stat.st_mtime))
        except Exception as e:
            logger.warning(f"Kon bestandstijd niet kopiëren naar {output_path.name}: {e}")

        logger.info(f"GPU Transcode voltooid (met originele datum): {input_path.name} -> {output_path.name}")
        return True

    except Exception as e:
        logger.error(f"Uitzondering bij renderen van {input_path.name}: {e}")
        return False


def extract_thumbnail(video_path: Path, thumb_path: Path) -> bool:
    """Genereert een lichte thumbnail van de eerste seconden voor weergave in de UI."""
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