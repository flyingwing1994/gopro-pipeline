# GoPro Video Pipeline v2.0

Geautomatiseerde, hardware-geaccelereerde verwerkings- en uploadpipeline voor GoPro-videobestanden. Converteert hoge resolutie beelden (4K/5.3K) naar 1080p Rec.709 (25 fps), past automatisch de officiële GP-Log LUT toe, behoudt originele opnamedata en synchroniseert rechtstreeks naar Google Photos.

---

## Belangrijkste functionaliteiten

* **Volledige GPU-acceleratie (Zero-Copy CUDA):** Schalen naar 1080p gebeurt rechtstreeks op de videokaart via `scale_cuda`. De CPU blijft ontlast (<15%), waardoor rendering op meervoudige realtime-snelheid draait via NVIDIA NVENC.
* **Automatische GP-Log detectie:** Detecteert 10-bit kleurprofielen (`yuv420p10le`) via `ffprobe` en past automatisch de officiële GoPro GP-Log naar Rec.709 3D LUT toe.
* **Metadata & datumbehoud:** Behoudt interne QuickTime-tags (`-map_metadata 0`) en synchroniseert fysieke bestandstijdstempels via `os.utime()`, zodat video's chronologisch correct in de tijdlijn van Google Photos verschijnen.
* **Ontkoppelde parallelle upload:** Zodra een clip klaar is met renderen, wordt deze op de achtergrond geüpload in blokken van 8 MB. Inclusief API-verificatie via `mediaItemId` en een automatische fallback naar de hoofdbibliotheek als een album geweigerd wordt.
* **Robuust dashboard (Streamlit):** Toont live render- en uploadvoortgang (MB's, percentages, ETA en resterende wachtrij). Bevat een client-side heartbeat tegen het bevriezen van de browser bij inactiviteit.
* **Configuratie & onderhoud:** Paden en instellingen zijn ontkoppeld via `config.json`. Inclusief automatische logrotatie (max. 5 MB) en opschoonknoppen voor cache en oude exports.

---

## Systeemvereisten

* **Besturingssysteem:** Windows 10 of Windows 11 (64-bit)
* **Grafische kaart:** NVIDIA GeForce RTX met recente Game Ready of Studio drivers (met NVENC- en CUDA-ondersteuning)
* **Python:** Versie 3.10 of nieuwer
* **FFmpeg:** Recente build met `--enable-cuda-llvm`, `--enable-nvdec` en `--enable-nvenc` toegevoegd aan het Windows PATH

---

## Installatie & Setup

### 1. Repository klonen & Virtual Environment inrichten
```powershell
git clone https://github.com/flyingwing1994/gopro-pipeline.git
cd gopro-pipeline
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Google Photos API configureren
1. Ga naar de Google Cloud Console (https://console.cloud.google.com/).
2. Maak een project aan en activeer de Photos Library API.
3. Configureer het OAuth-toestemmingsscherm (type: Extern, voeg je eigen Google-account toe als testgebruiker).
4. Maak onder Inloggegevens een OAuth 2.0-client-ID aan (type: Desktop-app).
5. Download het client-geheimenbestand, hernoem het naar `credentials.json` en plaats het in de hoofdmap van het project.

### 3. Paden en instellingen instellen (`config.json`)
Controleer of pas de gewenste mappen aan in `config.json`:
```json
{
  "directories": {
    "input": "C:\\Users\\Admin\\Videos\\GoPro\\input",
    "output": "C:\\Users\\Admin\\Videos\\GoPro\\output",
    "processed": "C:\\Users\\Admin\\Videos\\GoPro\\processed"
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
```

---

## Gebruik

Start de pipeline via het meegeleverde script:
```powershell
.\start_app.bat
```
Of direct via Streamlit:
```powershell
streamlit run app.py
```

### Workflow
1. Plaats ruwe GoPro-videobestanden in de map `input/`.
2. Open het dashboard in de browser (`http://localhost:8501`).
3. Controleer de automatisch gedetecteerde kleurprofielen per clip (GP-Log vs. Standaard).
4. Selecteer of maak een Google Photos-album aan in de zijbalk en klik op Start Batch Verwerking.
5. Zodra een clip succesvol is geëxporteerd en geverifieerd door Google Photos, wordt het bronbestand automatisch verplaatst naar `processed/`.

---

## Mapstructuur

```text
gopro-pipeline/
├── .cache/              # Lokale videothumbnails voor het dashboard
├── app.py               # Streamlit gebruikersinterface en pipeline-coördinatie
├── config.py            # Centrale configuratie-inlezer en paddefinities
├── config.json          # Aanpasbare directory- en rendervoorkeuren
├── transcoder.py        # CUDA/NVENC FFmpeg engine met rotatielogging
├── uploader.py          # Google Photos resumable chunked upload met verificatie
├── style.css            # Custom dashboardstyling
├── start_app.bat        # Automatische launcher voor Windows
├── pipeline.log         # Actueel roterend logbestand
├── requirements.txt     # Python afhankelijkheden
└── README.md
```