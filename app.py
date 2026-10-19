import streamlit as st
from pathlib import Path
from transcoder import transcode_clip
from uploader import get_credentials, get_or_create_album, upload_video_file

INPUT_DIR = Path(r"C:\Users\Admin\Videos\GoPro\input")
OUTPUT_DIR = Path(r"C:\Users\Admin\Videos\GoPro\output")
LUT_FILE = "GoPro_GP-Log_to_Rec709.cube"

st.set_page_config(page_title="GoPro Video Processor", layout="wide")
st.title("GoPro Video Batch Processor & Uploader")
st.markdown("Verwerk GoPro clips naar **1080p Rec.709** en upload optioneel direct naar Google Photos.")

# Sidebar instellingen
st.sidebar.header("Google Photos Instellingen")
enable_upload = st.sidebar.checkbox("Automatisch uploaden naar Google Photos", value=True)
album_name = st.sidebar.text_input("Doelalbum naam", value="GoPro Exports")

if not INPUT_DIR.exists():
    st.error(f"Input map niet gevonden: {INPUT_DIR}")
    st.stop()

# Zoek alle unieke MP4 video's (voorkom dubbelingen door hoofdletterongevoeligheid van Windows)
video_files = sorted(list({p.resolve(): p for p in INPUT_DIR.iterdir() if p.suffix.lower() == ".mp4"}.values()))

if not video_files:
    st.info(f"Geen MP4-bestanden gevonden in `{INPUT_DIR}`.")
    st.stop()

with st.form("batch_form"):
    choices = {}
    st.subheader(f"Gevonden clips ({len(video_files)})")

    for idx, clip in enumerate(video_files):
        col1, col2 = st.columns([1, 2])
        with col1:
            st.write(f"**{clip.name}**")
            size_mb = clip.stat().st_size / (1024 * 1024)
            st.caption(f"Grootte: {size_mb:.1f} MB")
        with col2:
            choices[clip] = st.radio(
                f"Actie voor {clip.name}",
                options=["GP-Log (LUT + 1080p)", "Standaard Rec.709 (Alleen 1080p)", "Overslaan"],
                index=0,
                key=f"{clip.name}_{idx}",
                horizontal=True
            )
        st.divider()

    submitted = st.form_submit_button("Start Batch Verwerking", type="primary")

if submitted:
    creds = None
    album_id = None

    if enable_upload:
        with st.spinner("Verbinden met Google Photos..."):
            creds = get_credentials()
            album_id = get_or_create_album(creds, album_name)
            if not album_id:
                st.error("Kon doelalbum in Google Photos niet aanmaken of vinden.")
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

            # 1. Transcode via NVENC
            success = transcode_clip(clip, out_file, mode=mode, lut_path=LUT_FILE)
            if success:
                st.write(f"✅ **{clip.name}** gerenderd naar `{out_file.name}`")
                
                # 2. Upload indien ingeschakeld
                if enable_upload and album_id:
                    status_text.text(f"[{idx+1}/{total}] Uploaden van {out_file.name} naar Google Photos...")
                    upload_success = upload_video_file(creds, out_file, album_id)
                    if upload_success:
                        st.write(f"☁️ Geüpload naar album **'{album_name}'**.")
                    else:
                        st.warning(f"⚠️ Renderen geslaagd, maar upload mislukt voor {out_file.name}.")
            else:
                st.error(f"❌ Fout bij verwerken van **{clip.name}**.")

        progress_bar.progress((idx + 1) / total)

    status_text.text("Batch verwerking en upload voltooid!")