# CLAUDE.md – gopro-pipeline

Taal: **Nederlands**.

## Werkwijze
Volg `WORKFLOW.md` en `skills/dev-workflow/SKILL.md` uit [flyingwing1994/.github](https://github.com/flyingwing1994/.github): elke wijziging via issue → branch → PR, nooit rechtstreeks naar `main`, Claude merget nooit zelf. Checks en review staan in `.github/workflows/pr.yml`.

## Deze repo
- Python 3.13, Streamlit-dashboard (`app.py`), transcoder (`transcoder.py`, ffmpeg/NVENC) en Google Photos-uploader (`uploader.py`). Draait lokaal op de Windows-pc, niet op de server.
- Checks: packages installeren en alle code compileren; nog geen tests (`test_google.py` is een handmatige OAuth-test, geen unittest).
- `credentials.json` en `token.json` (Google OAuth) staan nooit in git.
- `requirements.txt` is UTF-8 (niet opslaan als UTF-16 vanuit PowerShell: gebruik `pip freeze | Out-File -Encoding utf8` of een editor).
