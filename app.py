import shutil
import streamlit as st
from pathlib import Path
from transcoder import transcode_clip, extract_thumbnail, detect_is_log
from uploader import get_credentials, get_or_create_album, list_app_albums, upload_video_file

INPUT_DIR = Path(r"C:\Users\Admin\Videos\GoPro\input")
OUTPUT_DIR = Path(r"C:\Users\Admin\Videos\GoPro\output")
PROCESSED_DIR = Path(r"C:\Users\Admin\Videos\GoPro\processed")
CACHE_DIR = Path(r"C:\Users\Admin\Documents\Code\gopro-pipeline\.cache")
LUT_FILE = "GoPro_GP-Log_to_Rec709.cube"

st.set_page_config(page_title="GoPro Video Processor", layout="wide")

# CSS om de radio-opties om te toveren in grote, duidelijke kaarten/knoppen
st.markdown("""
<style>
div[role="radiogroup"] {
    display: flex;
    flex-direction: row;
    gap: 12px;
    align-items: stretch;
}
div[role="radiogroup"] > label {
    flex: 1;
    background-color: #1e2129;
    border: 1px solid #3b4252;
    border-radius: 8px;
    padding: 16px 12px;
    cursor: pointer;
    transition: all 0.2s ease-in-out;
    text-align: center;
    font-weight: 500;
}
div[role="radiogroup"] > label:hover {
    border-color: #4CAF50;
    background-color: #252a36;
}
div[role="radiogroup"] > label[data-checked="true"],
div[role="radiogroup"] > label:has(input:checked) {
    border-color: #4CAF50 !important;
    background-color: rgba(76, 175, 80, 0.15) !important;
}
</style>
""", unsafe_allow_html=True)

st.title("GoPro Video Batch Processor & Uploader")
st.markdown("Verwerk GoPro clips naar **1080p Rec.709 (25fps)** en upload optioneel naar Google Photos.")

# Sidebar instellingen
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

if not INPUT_DIR.exists():
    st.error(f"Input map niet gevonden: {INPUT_DIR}")
    st.stop()

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

video_files = sorted(list({p.resolve(): p for p in INPUT_DIR.iterdir() if p.suffix.lower() == ".mp4"}.values()))

if not video_files:
    st.info(f"Geen MP4-bestanden in `{INPUT_DIR}`. Alles is verwerkt of verplaatst!")
    st.stop()

with st.form("batch_form"):
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
            
            # Automatische detectie: 10-bit = GP-Log (index 0), 8-bit = Standaard (index 1)
            is_log = detect_is_log(clip)
            default_index = 0 if is_log else 1

            element_key = f"action_{clip.stem}"
            
            # Als de gebruiker eerder al een keuze had gemaakt in de sessie, behoud die
            if element_key not in st.session_state:
                st.session_state[element_key] = options[default_index]

            choices[clip] = st.radio(
                f"Actie voor {clip.name}" + (" [Gedetecteerd: 10-bit GP-Log]" if is_log else " [Gedetecteerd: 8-bit Standaard]"),
                options=options,
                key=element_key,
                horizontal=True
            )
        st.divider()

    submitted = st.form_submit_button("Start Batch Verwerking", type="primary")

if submitted:
    creds = None
    album_id = selected_album_id

    if enable_upload:
        with st.spinner("Album gereedmaken..."):
            creds = get_credentials()
            if not album_id:
                album_id = get_or_create_album(creds, target_album_name)
            
            if not album_id:
                st.error("Kon doelalbum in Google Photos niet aanmaken of selecteren.")
                st.stop()

    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(choices)

    for idx, (clip, action) in enumerate(choices.items()):
        if action == "Overslaan":
            st.write(f"⏩ **{clip.name}** overgeslagen.")
        else:
            status_text.text(f"[{idx+1}/{total}] Renderen van {clip.name}...")
            mode = "log" if "GP-Log" in action else "standard"
            out_file = OUTPUT_DIR / f"{clip.stem}_1080p.mp4"

            success = transcode_clip(clip, out_file, mode=mode, lut_path=LUT_FILE)
            if success:
                st.write(f"✅ **{clip.name}** gerenderd naar `{out_file.name}`")
                
                upload_ok = True
                if enable_upload and album_id:
                    status_text.text(f"[{idx+1}/{total}] Uploaden van {out_file.name} naar Google Photos...")
                    upload_ok = upload_video_file(creds, out_file, album_id)
                    if upload_ok:
                        st.write(f"☁️ Geüpload naar album **'{target_album_name}'**.")
                    else:
                        st.warning(f"⚠️ Renderen geslaagd, maar upload mislukt voor {out_file.name}.")

                if upload_ok and move_to_processed:
                    target_dest = PROCESSED_DIR / clip.name
                    if target_dest.exists():
                        target_dest = PROCESSED_DIR / f"{clip.stem}_dup_{idx}{clip.suffix}"
                    try:
                        shutil.move(str(clip), str(target_dest))
                        st.caption(f"📦 Bronbestand verplaatst naar `{target_dest.parent.name}\\{target_dest.name}`.")
                    except Exception as e:
                        st.warning(f"Kon bronbestand niet verplaatsen: {e}")
            else:
                st.error(f"❌ Fout bij verwerken van **{clip.name}**.")

        progress_bar.progress((idx + 1) / total)

    status_text.text("Batch verwerking en upload voltooid!")