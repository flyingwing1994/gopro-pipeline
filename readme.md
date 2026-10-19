# GoPro Video Pipeline

Een geautomatiseerde batch-processor en uploader voor GoPro-videobestanden. Converteer raw GoPro GP-Log beelden direct naar 1080p Rec.709 via NVIDIA NVENC hardware-acceleratie en upload ze optioneel rechtstreeks naar Google Photos.

## Features
- GP-Log naar Rec.709 conversie via 3D LUT (identiek aan DaVinci Resolve CST).
- Ondersteuning voor niet-LOG video en timelapses (direct naar 1080p).
- Hardware decoding (CUDA) en encoding (NVENC) voor hoge verwerkingssnelheid.
- Rec.709 metadata tagging (bt709) voor correcte weergave in Google Photos.
- Direct uploaden via de officiële Google Photos API.
- Lokale Streamlit web-interface.

## Vereisten
- Windows PC met NVIDIA GPU
- Python 3.10+
- FFmpeg met NVENC ondersteuning
- GoPro GP-Log naar Rec.709 LUT (GoPro_GP-Log_to_Rec709.cube)
- Google Cloud OAuth desktop credentials (credentials.json)

## Snelle Start
1. Installeer dependencies: pip install -r requirements.txt
2. Plaats credentials.json en de .cube LUT in de hoofdmap
3. Plaats video\'s in C:\Users\Admin\Videos\GoPro\input
4. Start de app: streamlit run app.py
