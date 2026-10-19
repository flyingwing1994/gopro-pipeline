import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"

DEFAULT_CONFIG = {
    "directories": {
        "input": str(Path.home() / "Videos" / "GoPro" / "input"),
        "output": str(Path.home() / "Videos" / "GoPro" / "output"),
        "processed": str(Path.home() / "Videos" / "GoPro" / "processed")
    },
    "transcode": {
        "default_resolution": "1920:1080",
        "default_fps": 25,
        "nvenc_preset": "p4",
        "cq_value": 25,
        "lut_file": "GoPro_GP-Log_to_Rec709.cube"
    },
    "upload": {
        "default_album": "GoPro Exports",
        "chunk_size_mb": 8
    }
}

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return DEFAULT_CONFIG

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_CONFIG

CONFIG = load_config()

INPUT_DIR = Path(CONFIG["directories"]["input"])
OUTPUT_DIR = Path(CONFIG["directories"]["output"])
PROCESSED_DIR = Path(CONFIG["directories"]["processed"])
CACHE_DIR = BASE_DIR / ".cache"
STATUS_FILE = BASE_DIR / "batch_status.json"
LOG_FILE = BASE_DIR / "pipeline.log"
LUT_FILE = BASE_DIR / CONFIG["transcode"]["lut_file"]
CHUNK_SIZE = CONFIG["upload"]["chunk_size_mb"] * 1024 * 1024