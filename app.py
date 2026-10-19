import time
import json
import queue
import shutil
import threading
import streamlit as st
from pathlib import Path
from transcoder import transcode_clip, extract_thumbnail, detect_is_log
from uploader import get_credentials, get_or_create_album, list_app_albums, upload_video_file

BASE_DIR = Path(__file__).resolve().parent
STATUS_FILE = BASE_DIR / "batch_status.json"
CSS_FILE = BASE_DIR / "style.css"
LUT_FILE = "GoPro_GP-Log_to_Rec709.cube"

INPUT_DIR = Path(r"C:\Users\Admin\Videos\GoPro\input")
OUTPUT_DIR = Path(r"C:\Users\Admin\Videos\GoPro\output")
PROCESSED_DIR = Path(r"C:\Users\Admin\Videos\GoPro\processed")
CACHE_DIR = BASE_DIR / ".cache"

st.set_page_config(page_title="GoPro Video Processor", layout="wide")

# Externe styling inladen
if CSS_FILE.exists():
    with open(CSS_FILE, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# --- STATUS BEHEER VOOR ACHTERGRONDTAKEN ---
def get_batch_status():
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def set_batch_status(data):
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def run_batch_worker(job_items, enable_upload, album_id, target_album_name, move_to_processed, lut_file, output_dir, processed_dir):
    creds = get_credentials() if enable_upload else None
    active_jobs = [j for j in job_items if j["action"] != "Overslaan"]
    total = len(active_jobs)
    start_time = time.time()
    
    upload_q = queue.Queue()
    upload_status_msg = {"text": "Wachten op eerste render..."}

    # Parallelle uploader thread
    def uploader_worker():
        while True:
            task = upload_q.get()
            if task is None:
                break
            
            src_clip, rendered_file, task_idx = task
            if enable_upload and album_id:
                upload_status_msg["text"] = f"Uploaden: {rendered_file.name}"
                upload_ok = upload_video_file(creds, rendered_file, album_id)
            else:
                upload_ok = True

            if upload_ok and move_to_processed:
                target_dest = processed_dir / src_clip.name
                if target_dest.exists():
                    target_dest = processed_dir / f"{src_clip.stem}_dup_{task_idx}{src_clip.suffix}"
                try:
                    shutil.move(str(src_clip), str(target_dest))
                except Exception:
                    pass
            upload_q.task_done()

    uploader_thread = threading.Thread(target=uploader_worker, daemon=True)
    uploader_thread.start()

    set_batch_status({
        "running": True,
        "current_index": 0,
        "total": total,
        "current_clip": "Initialiseren...",
        "status": "Bezig met starten",
        "upload_status": "Klaarzetten",
        "eta": "Berekenen..."
    })

    for idx, item in enumerate(active_jobs):
        state = get_batch_status() or {}
        if state.get("stop_requested", False):
            break

        while True:
            state = get_batch_status() or {}
            if state.get("stop_requested", False):
                break
            if not state.get("paused", False):
                break
            time.sleep(1)

        if state.get("stop_requested", False):
            break

        clip_path = Path(item["path"])
        action = item["action"]
        mode = "log" if "GP-Log" in action else "standard"
        out_file = output_dir / f"{clip_path.stem}_1080p.mp4"

        elapsed = time.time() - start_time
        if idx > 0:
            avg_time = elapsed / idx
            remaining = avg_time * (total - idx)
            eta_str = time.strftime("%H:%M:%S", time.gmtime(remaining))
        else:
            eta_str = "Berekenen..."

        def on_clip_progress(pct):
            set_batch_status({
                "running": True,
                "current_index": idx + 1,
                "total": total,
                "current_clip": clip_path.name,
                "status": f"Renderen ({pct:.0f}%)",
                "upload_status": upload_status_msg["text"],
                "clip_percent": pct,
                "eta": eta_str
            })

        # Resume-controle: Bestaat de 1080p render al en is deze > 0 bytes?
        if out_file.exists() and out_file.stat().st_size > 1024:
            on_clip_progress(100.0)
            upload_q.put((clip_path, out_file, idx))
            continue

        on_clip_progress(0.0)
        success = transcode_clip(clip_path, out_file, mode=mode, lut_path=lut_file, progress_callback=on_clip_progress)
        
        if success:
            upload_q.put((clip_path, out_file, idx))

    # Wacht tot alle resterende uploads klaar zijn
    upload_status_msg["text"] = "Laatste uploads afronden..."
    upload_q.join()
    upload_q.put(None)
    uploader_thread.join()

    set_batch_status({
        "running": False,
        "current_index": total,
        "total": total,
        "current_clip": "Klaar",
        "status": "Voltooid",
        "upload_status": "Alles geüpload",
        "eta": "00:00:00"
    })

# --- UI OPBOUW ---
st.title("GoPro Video Batch Processor & Uploader")
st.markdown("Verwerk GoPro clips naar **1080p Rec.709 (25fps)** en upload optioneel direct naar Google Photos.")

# Sidebar
st.sidebar.header("Instellingen")
enable_upload = st.sidebar.checkbox("Automatisch uploaden naar Google Photos", value=True, key="cfg_upload")

selected_album_id = None
target_album_name = "GoPro Exports"

if enable_upload:
    st.sidebar.subheader("Doelalbum Selectie")
    creds_sidebar = get_credentials()
    existing_albums = list_app_albums(creds_sidebar)

    if existing_albums:
        album_choice = st.sidebar.radio(
            "Album bestemming:",
            options=["Bestaand album kiezen", "Nieuw album aanmaken"],
            key="cfg_album_mode"
        )
        if album_choice == "Bestaand album kiezen":
            chosen_title = st.sidebar.selectbox("Kies een album:", options=list(existing_albums.keys()), key="cfg_album_select")
            selected_album_id = existing_albums[chosen_title]
            target_album_name = chosen_title
        else:
            target_album_name = st.sidebar.text_input("Naam voor nieuw album:", value="GoPro Exports", key="cfg_album_new")
    else:
        st.sidebar.info("Nog geen albums geregistreerd. Geef hieronder een naam op:")
        target_album_name = st.sidebar.text_input("Naam voor nieuw album:", value="GoPro Exports", key="cfg_album_new_empty")

move_to_processed = st.sidebar.checkbox("Verplaats bronbestand naar 'processed' na succes", value=True, key="cfg_move")
st.sidebar.divider()

# Achtergrondtaak statusweergave & Startknop
batch_state = get_batch_status()
is_active = batch_state and batch_state.get("running", False)

if is_active:
    is_paused = batch_state.get("paused", False)
    
    if is_paused:
        st.sidebar.warning("⏸️ **Batch is gepauzeerd**")
    else:
        st.sidebar.info("⏳ **Batch draait op de achtergrond!**")

    curr_idx = batch_state.get("current_index", 0)
    total_items = max(1, batch_state.get("total", 1))
    clip_pct = batch_state.get("clip_percent", 0.0) / 100.0

# 1. Totale voortgang
    st.sidebar.markdown(f"📊 **Totale batch:** {curr_idx} / {total_items}")
    st.sidebar.progress(min(1.0, curr_idx / total_items))
    st.sidebar.caption(f"⏱️ **Resterende tijd (ETA):** `{batch_state.get('eta', 'Berekenen...')}`")
    st.sidebar.divider()

    # 2. GPU Render Monitor
    st.sidebar.markdown("🎮 **GPU Render Engine (NVENC)**")
    gpu_clip = batch_state.get('current_clip', '-')
    st.sidebar.caption(f"Actief: `{gpu_clip}`")
    st.sidebar.progress(min(1.0, max(0.0, clip_pct)))
    st.sidebar.caption(f"Status: {batch_state.get('status', '-')}")
    st.sidebar.divider()

    # 3. Cloud Upload Monitor
    st.sidebar.markdown("☁️ **Google Photos Uploader**")
    upload_msg = batch_state.get('upload_status', 'Wachten op eerste render...')
    st.sidebar.info(f"{upload_msg}")
    st.sidebar.divider()
    # Knoppen voor bediening
    col_p, col_s = st.sidebar.columns(2)
    with col_p:
        if is_paused:
            if st.button("▶️ Hervatten", use_container_width=True):
                batch_state["paused"] = False
                batch_state["status"] = "Hervatting..."
                set_batch_status(batch_state)
                st.rerun()
        else:
            if st.button("⏸️ Pauzeren", use_container_width=True):
                batch_state["paused"] = True
                batch_state["status"] = "Gepauzeerd"
                set_batch_status(batch_state)
                st.rerun()

    with col_s:
        if st.button("⏹️ Stoppen", use_container_width=True):
            batch_state["stop_requested"] = True
            batch_state["running"] = False
            batch_state["status"] = "Geannuleerd"
            set_batch_status(batch_state)
            # Sluit eventueel actief FFmpeg proces direct af
            import subprocess
            subprocess.run(["taskkill", "/F", "/IM", "ffmpeg.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            st.rerun()

    # Auto-refresh alleen actief laten lopen als niet gepauzeerd
    if not is_paused:
        time.sleep(4)
        st.rerun()
else:
    start_batch = st.sidebar.button("🚀 Start Batch Verwerking", type="primary", use_container_width=True)

if not INPUT_DIR.exists():
    st.error(f"Input map niet gevonden: {INPUT_DIR}")
    st.stop()

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Haal unieke MP4's op
video_files = sorted(list({p.resolve(): p for p in INPUT_DIR.iterdir() if p.suffix.lower() == ".mp4"}.values()))

if not video_files:
    st.info(f"Geen MP4-bestanden gevonden in `{INPUT_DIR}`. Alles is verwerkt of verplaatst!")
    st.stop()

choices = {}
st.subheader(f"Gevonden clips ({len(video_files)})")

for idx, clip in enumerate(video_files):
    col1, col2 = st.columns([1, 2])
    
    with col1:
        thumb_file = CACHE_DIR / f"{clip.stem}_thumb.jpg"
        if extract_thumbnail(clip, thumb_file) and thumb_file.is_file():
            st.image(str(thumb_file), use_container_width=True)
        else:
            st.caption("🎬 Geen preview beschikbaar")
        
        st.write(f"**{clip.name}**")
        size_mb = clip.stat().st_size / (1024 * 1024)
        st.caption(f"Grootte: {size_mb:.1f} MB")
        
    with col2:
        options = ["GP-Log (LUT + 1080p 25fps)", "Standaard Rec.709 (Alleen 1080p 25fps)", "Overslaan"]
        
        is_log = detect_is_log(clip)
        default_index = 0 if is_log else 1

        element_key = f"action_{clip.stem}"
        if element_key not in st.session_state:
            st.session_state[element_key] = options[default_index]

        choices[clip] = st.radio(
            f"Actie voor {clip.name}" + (" [Gedetecteerd: 10-bit GP-Log]" if is_log else " [Gedetecteerd: 8-bit Standaard]"),
            options=options,
            key=element_key,
            horizontal=True
        )
    st.divider()

# Start van de achtergrondtaak bij klik
if not is_active and start_batch:
    album_id = selected_album_id
    if enable_upload and not album_id:
        creds = get_credentials()
        album_id = get_or_create_album(creds, target_album_name)

    job_items = [{"path": str(clip), "action": choices.get(clip, "Overslaan")} for clip in video_files]

    worker_thread = threading.Thread(
        target=run_batch_worker,
        args=(job_items, enable_upload, album_id, target_album_name, move_to_processed, LUT_FILE, OUTPUT_DIR, PROCESSED_DIR),
        daemon=True
    )
    worker_thread.start()
    st.rerun()