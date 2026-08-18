@echo off
REM Backend'i baslatir -- Windows oturum acilisinda Gorev Zamanlayicisi
REM (Task Scheduler) tarafindan otomatik cagrilir, bkz. start_backend_gizli.vbs.
REM Elle de cift tiklayarak calistirabilirsin (konsol penceresi acik kalir).
cd /d "%~dp0"
python -m uvicorn main:app --host 0.0.0.0 --port 10000
