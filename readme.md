# GoPro Video Pipeline

Een geautomatiseerde batch-verwerker en uploader voor GoPro-videobestanden. Deze applicatie stelt je in staat om per clip te kiezen tussen een **GP-Log naar Rec.709 Color Space Transform (CST)** of een directe conversie naar 1080p, waarna de geëxporteerde clips optioneel direct worden geüpload naar een specifiek Google Photos-album.

De rendering maakt gebruik van lokale hardware-acceleratie via NVIDIA NVENC voor maximale verwerkingssnelheid.

---

## Functionaliteiten

- **Selectieve Kleurruimte Conversie:** Pas via een 3D LUT (`.cube`) wiskundig dezelfde transformatie toe als DaVinci Resolve's CST (GoPro Wide Gamut / GP-Log naar Rec.709).
- **Batch Keuzemenu:** Bepaal per gevonden clip in de inputmap of deze moet worden verwerkt als GP-Log, als standaard Rec.709 (zoals timelapses), of moet worden overgeslagen.
- **Hardware-acceleratie:** Volledige decoding via CUDA en encoding via NVIDIA NVENC (`h264_nvenc` met `p6` preset en Constant Quality instelling).
- **Rec.709 Metadata Tagging:** Voegt expliciet `bt709` kleurruimte-, transfer- en matrix-tags toe zodat video's in browsers en apps exact de juiste kleuren tonen.
- **Google Photos API Integratie:** Uploadt gerenderde 1080p-bestanden via resumable sessies direct naar een gekozen of nieuw album in Google Photos.

---

## Systeemvereisten

1. **Besturingssysteem:** Windows 10/11 met een moderne NVIDIA GPU.
2. **Python:** Versie 3.10 of nieuwer.
3. **FFmpeg:** Gecompileerd met NVENC-ondersteuning (controleerbaar via `ffmpeg -encoders | findstr nvenc`).
4. **GoPro GP-Log LUT:** Het officiële bestand `GoPro_GP-Log_to_Rec709.cube` geplaatst in de hoofdmap van het project.
5. **Google Cloud OAuth:** Een geldig `credentials.json` bestand voor de Google Photos Library API.

---

## Mappenstructuur

Standaard verwacht de applicatie de volgende mappen op het systeem:

- **Input:** `C:\Users\Admin\Videos\GoPro\input` (hier plaats je de ruwe SD-kaart bestanden)
- **Output:** `C:\Users\Admin\Videos\GoPro\output` (hier worden de 1080p exports opgeslagen)

---

## Installatie & Setup

1. **Repository klonen:**
   ```bash
   git clone [https://github.com/flyingwing1994/gopro-pipeline.git](https://github.com/flyingwing1994/gopro-pipeline.git)
   cd gopro-pipeline
Hier is het complete restant van de README.md vanaf stap 2 van de installatie tot en met het einde:

Markdown
2. **Virtuele omgeving aanmaken en activeren:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
Afhankelijkheden installeren:

PowerShell
pip install -r requirements.txt
Configuratiebestanden plaatsen:

Plaats credentials.json (Google OAuth Client ID voor Desktop App) in de hoofdmap.

Plaats de LUT GoPro_GP-Log_to_Rec709.cube in de hoofdmap.

Gebruik
Starten via de terminal
Zorg dat de virtuele omgeving actief is en voer uit:

PowerShell
streamlit run app.py
Starten via batch-bestand
Dubbelklik op start_app.bat om de omgeving automatisch te laden en het dashboard te openen op http://localhost:8501.

Kies in de linker zijbalk of automatische Google Photos-upload actief moet zijn en geef de gewenste doelalbumnaam op.

Selecteer per clip in het overzicht de gewenste actie:

GP-Log (LUT + 1080p): Voor clips gefilmd in GP-Log.

Standaard Rec.709 (Alleen 1080p): Voor timelapses of normale clips.

Overslaan: Negeert het bestand tijdens deze batch.

Klik op Start Batch Verwerking.

Beveiliging & Privacy
Gevoelige bestanden zoals credentials.json, geauthenticeerde tokens (token.json), LUTs en videobestanden worden uitgesloten via .gitignore en horen nooit in versiebeheer te worden opgenomen.