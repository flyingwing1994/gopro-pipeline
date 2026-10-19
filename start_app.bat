@echo off
title GoPro Video Pipeline
cd /d "C:\Users\Admin\Documents\Code\gopro-pipeline"
if exist "venv\Scripts\activate.bat" (
call .\venv\Scripts\activate.bat
)
echo Starten van Streamlit Dashboard...
streamlit run app.py
pause