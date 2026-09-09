@echo off
rem Llançador local de Sistemes de Mesura. Doble clic per obrir l'app.
title Sistemes de Mesura
cd /d "%~dp0.."

rem Crea els directoris de dades/config/logs si no existeixen (idempotent).
python -m app.cli init >nul 2>&1

rem Obre el navegador uns segons després, quan el servidor ja escolta.
start "" /min cmd /c "timeout /t 3 /nobreak >nul & start "" http://127.0.0.1:8901"

echo.
echo   Sistemes de Mesura  -  http://127.0.0.1:8901
echo   Tanca aquesta finestra per aturar el servidor.
echo.
python -m app.cli serve

rem Si serve acaba amb error, deixa la finestra oberta per veure el missatge.
if errorlevel 1 pause
