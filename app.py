import time
import json
import queue
import shutil
import logging
import threading
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
from transcoder import transcode_clip, extract_thumbnail, detect_is_log
from uploader import get_credentials, get_or_create_album, list_app_albums, upload_video_file

from config import (
    BASE_DIR, INPUT_DIR, OUTPUT_DIR, PROCESSED_DIR,
    CACHE_DIR, STATUS_FILE, LOG_FILE, LUT_FILE
)
CSS_FILE = BASE_DIR / "style.css"

st.set_page_config(page_title="GoPro Video Processor v2.0", layout="wide")

if CSS_FILE.exists():
    with open(CSS_FILE, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Heartbeat script voorkomt dat de browser de WebSocket bevriest bij inactiviteit
components.html(
    """
    <script>
    setInterval(() => {
        window.dispatchEvent(new Event('resize'));
    }, 15000);
    </script>
    """,
    height=0,
    width=0
)

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
    upload_state = {
        "clip": "Wachten op eerste render...",
        "bytes_done": 0,
        "bytes_total": 0,
        "percent": 0.0,
        "queue_count": 0
    }

    # Parallelle Uploader Worker Thread
    def uploader_worker():
        while True:
            task = upload_q.get()
            if task is None:
                break
            
            src_clip, rendered_file, task_idx = task
            upload_state["clip"] = rendered_file.name
            upload_state["queue_count"] = upload_q.qsize()

            def on_upload_progress(done, total_b):
                upload_state["bytes_done"] = done
                upload_state["bytes_total"] = total_b
                upload_state["percent"] = (done / max(1, total_b)) * 100.0
                st_data = get_batch_status() or {}
                st_data["upload_clip"] = rendered_file.name
                st_data["upload_pct"] = upload_state["percent"]
                st_data["upload_mb"] = f"{done / (1024*1024):.1f} / {total_b / (1024*1024):.1f} MB"
                st_data["upload_queue"] = upload_q.qsize()
                set_batch_status(st_data)

            upload_ok = True
            if enable_upload and album_id:
                upload_ok = upload_video_file(creds, rendered_file, album_id, progress_callback=on_upload_progress)

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
        "status": "Bezig",
        "clip_percent": 0.0,
        "upload_clip": "Wachten...",
        "upload_pct": 0.0,
        "upload_mb": "- / - MB",
        "upload_queue": 0,
        "eta": "Berekenen..."
    })

    # GPU Worker Loop (Rendert autonoom op maximale CUDA-snelheid)
    for idx, item in enumerate(active_jobs):
        state = get_batch_status() or {}
        if state.get("stop_requested", False):
            break

        while True:
            state = get_batch_status() or {}
            if state.get("stop_requested", False) or not state.get("paused", False):
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
            st_data = get_batch_status() or {}
            st_data.update({
                "running": True,
                "current_index": idx + 1,
                "total": total,
                "current_clip": clip_path.name,
                "status": f"Renderen ({pct:.0f}%)",
                "clip_percent": pct,
                "eta": eta_str
            })
            set_batch_status(st_data)

        # Resume check: als clip al gerenderd is in output, direct door naar upload
        if out_file.exists() and out_file.stat().st_size > 1024:
            on_clip_progress(100.0)
            upload_q.put((clip_path, out_file, idx))
            continue

        on_clip_progress(0.0)
        success = transcode_clip(clip_path, out_file, mode=mode, lut_path=lut_file, progress_callback=on_clip_progress)
        
        if success:
            upload_q.put((clip_path, out_file, idx))

    # Afronding
    upload_q.join()
    upload_q.put(None)
    uploader_thread.join()

    set_batch_status({
        "running": False,
        "current_index": total,
        "total": total,
        "current_clip": "Klaar",
        "status": "Voltooid",
        "upload_clip": "Alles voltooid",
        "upload_pct": 100.0,
        "upload_mb": "Gereed",
        "upload_queue": 0,
        "eta": "00:00:00"
    })

# --- STATUS VERIFICATIE VÓÓR HET RENDERN VAN DE PAGINA ---
batch_state = get_batch_status()
is_active = batch_state and batch_state.get("running", False)

# ZIJBALK
st.sidebar.header("GoPro Pipeline v2.0")

if is_active:
    is_paused = batch_state.get("paused", False)
    if is_paused:
        st.sidebar.warning("⏸️ **Pipeline gepauzeerd**")
    else:
        st.sidebar.info("🚀 **Pipeline actief**")

    curr_idx = batch_state.get("current_index", 0)
    total_items = max(1, batch_state.get("total", 1))
    clip_pct = batch_state.get("clip_percent", 0.0) / 100.0

    st.sidebar.markdown(f"📊 **Totale batch:** {curr_idx} / {total_items}")
    st.sidebar.progress(min(1.0, curr_idx / total_items))
    st.sidebar.caption(f"⏱️ **Resterende tijd (ETA):** `{batch_state.get('eta', 'Berekenen...')}`")
    st.sidebar.divider()

    st.sidebar.markdown("🎮 **GPU NVENC Engine**")
    st.sidebar.caption(f"Actief: `{batch_state.get('current_clip', '-')}`")
    st.sidebar.progress(min(1.0, max(0.0, clip_pct)))
    st.sidebar.caption(f"Status: {batch_state.get('status', '-')}")
    st.sidebar.divider()

    st.sidebar.markdown("☁️ **Google Photos Uploader**")
    st.sidebar.caption(f"Bestand: `{batch_state.get('upload_clip', '-')}`")
    up_pct = batch_state.get("upload_pct", 0.0) / 100.0
    st.sidebar.progress(min(1.0, max(0.0, up_pct)))
    st.sidebar.caption(f"Transfer: **{batch_state.get('upload_mb', '-')}** ({batch_state.get('upload_pct', 0.0):.0f}%)")
    st.sidebar.caption(f"Wachtrij: **{batch_state.get('upload_queue', 0)} clips**")
    st.sidebar.divider()

    col_p, col_s = st.sidebar.columns(2)
    with col_p:
        if is_paused:
            if st.button("▶️ Hervatten", use_container_width=True):
                batch_state["paused"] = False
                set_batch_status(batch_state)
                st.rerun()
        else:
            if st.button("⏸️ Pauzeren", use_container_width=True):
                batch_state["paused"] = True
                set_batch_status(batch_state)
                st.rerun()

    with col_s:
        if st.button("⏹️ Stoppen", use_container_width=True):
            batch_state["stop_requested"] = True
            batch_state["running"] = False
            set_batch_status(batch_state)
            import subprocess
            subprocess.run(["taskkill", "/F", "/IM", "ffmpeg.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            st.rerun()

else:
    enable_upload = st.sidebar.checkbox("Automatisch uploaden", value=True, key="cfg_upload")
    selected_album_id = None
    target_album_name = "GoPro Exports"

    if enable_upload:
        creds_sidebar = get_credentials()
        existing_albums = list_app_albums(creds_sidebar)
        if existing_albums:
            album_choice = st.sidebar.radio("Album:", options=["Bestaand album", "Nieuw album"], key="cfg_album_mode")
            if album_choice == "Bestaand album":
                chosen_title = st.sidebar.selectbox("Kies album:", options=list(existing_albums.keys()), key="cfg_album_select")
                selected_album_id = existing_albums[chosen_title]
                target_album_name = chosen_title
            else:
                target_album_name = st.sidebar.text_input("Nieuwe albumnaam:", value="GoPro Exports", key="cfg_album_new")
        else:
            target_album_name = st.sidebar.text_input("Nieuwe albumnaam:", value="GoPro Exports", key="cfg_album_new_empty")

    move_to_processed = st.sidebar.checkbox("Verplaats originelen naar 'processed'", value=True, key="cfg_move")
    st.sidebar.divider()
    start_batch = st.sidebar.button("🚀 Start Batch Verwerking", type="primary", use_container_width=True)

# Download Log Knop
# Onderhoud & Schijfruimte in de zijbalk
st.sidebar.divider()
st.sidebar.subheader("🧹 Onderhoud")

cache_files = list(CACHE_DIR.glob("*.jpg")) if CACHE_DIR.exists() else []
cache_size_mb = sum(f.stat().st_size for f in cache_files) / (1024 * 1024) if cache_files else 0

output_files = list(OUTPUT_DIR.glob("*_1080p.mp4")) if OUTPUT_DIR.exists() else []
output_size_mb = sum(f.stat().st_size for f in output_files) / (1024 * 1024) if output_files else 0

st.sidebar.caption(f"Cache: {len(cache_files)} previews ({cache_size_mb:.1f} MB)")
if st.sidebar.button("🗑️ Leeg Thumbnail Cache", use_container_width=True):
    for f in cache_files:
        try:
            f.unlink()
        except Exception:
            pass
    st.sidebar.success("Cache geleegd!")
    st.rerun()

st.sidebar.caption(f"Exports map: {len(output_files)} video's ({output_size_mb:.1f} MB)")
if st.sidebar.button("🗑️ Ruim Oude Exports Op", use_container_width=True):
    for f in output_files:
        try:
            f.unlink()
        except Exception:
            pass
    st.sidebar.success("Exports opgeruimd!")
    st.rerun()
if LOG_FILE.exists():
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        st.sidebar.download_button(
            label="📥 Download Pipeline Log",
            data=f.read(),
            file_name="pipeline.log",
            mime="text/plain",
            use_container_width=True
        )

# HOOFDSCHERM LOGICA
if is_active:
    # Dedicated Dashboard weergave (voorkomt dat DOM overbelast raakt door 171 thumbnails)
    st.title("🚀 Pipeline Uitvoering")
    st.info("De GPU transcodeert en uploadt continu op de achtergrond. Dit tabblad mag open blijven staan; de verbinding blijft actief.")
    
    col_g, col_u = st.columns(2)
    with col_g:
        st.subheader("🎮 GPU Rendering")
        st.metric("Huidige clip", batch_state.get('current_clip', '-'))
        st.metric("Status", batch_state.get('status', '-'))
        st.progress(min(1.0, max(0.0, clip_pct)))
    
    with col_u:
        st.subheader("☁️ Google Cloud Upload")
        st.metric("Uploadend bestand", batch_state.get('upload_clip', '-'))
        st.metric("Transfer", batch_state.get('upload_mb', '-'))
        st.progress(min(1.0, max(0.0, up_pct)))
        st.caption(f"Nog **{batch_state.get('upload_queue', 0)} clips** in de wachtrij.")

    if not batch_state.get("paused", False):
        time.sleep(3)
        st.rerun()

else:
    st.title("GoPro Video Batch Processor & Uploader")
    st.markdown("Verwerk GoPro clips naar **1080p Rec.709 (25fps)** met hardwarematige GPU-schaling.")

    if not INPUT_DIR.exists():
        st.error(f"Input map niet gevonden: {INPUT_DIR}")
        st.stop()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    video_files = sorted(list({p.resolve(): p for p in INPUT_DIR.iterdir() if p.suffix.lower() == ".mp4"}.values()))

    if not video_files:
        st.success("🎉 **Alles is verwerkt!** De input-map is leeg.")
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

    if start_batch:
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