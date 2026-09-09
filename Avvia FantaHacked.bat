@echo off
title FantaHacked
cd /d "%~dp0"

rem ---------------------------------------------------------------------
rem  Se c'e' l'eseguibile, si usa quello: si porta dentro il suo Python e
rem  non chiede niente al computer che lo ospita. E' il caso di chi ha
rem  copiato il programma su un altro PC, dove Python non c'e' e non serve.
rem
rem  Prima questo file cercava Python e basta. Copiato altrove, il doppio
rem  clic sul lanciatore .vbs non faceva **niente**: il .vbs apre il .bat a
rem  finestra nascosta, quindi nemmeno il messaggio "non trovo Python" si
rem  vedeva.
rem ---------------------------------------------------------------------
if exist "%~dp0FantaHacked.exe" (
  echo Avvio di FantaHacked...
  start "" "%~dp0FantaHacked.exe"
  exit /b 0
)

rem ---------------------------------------------------------------------
rem  Niente eseguibile: si gira dal sorgente, e allora Python serve. Prima
rem  quello nel PATH, poi le posizioni standard di installazione. Se non lo
rem  trova lo dice chiaramente invece di chiudersi lasciando l'utente al buio.
rem ---------------------------------------------------------------------
set "PY="
for %%P in (python.exe) do if not defined PY set "PY=%%~$PATH:P"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PY if exist "%ProgramFiles%\Python312\python.exe" set "PY=%ProgramFiles%\Python312\python.exe"
if not defined PY if exist "C:\Python312\python.exe" set "PY=C:\Python312\python.exe"

if not defined PY (
  echo.
  echo   Non trovo Python su questo computer.
  echo.
  echo   Installalo da https://www.python.org/downloads/
  echo   ricordandoti di spuntare "Add Python to PATH" durante l'installazione,
  echo   poi riprova con un doppio clic su questo file.
  echo.
  pause
  exit /b 1
)

echo Avvio di FantaHacked...
echo Si apre una finestra dedicata: chiudila per uscire dal programma.
"%PY%" "app\server.py"
if errorlevel 1 (
  echo.
  echo   Il programma si e' chiuso con un errore. Il messaggio e' qui sopra.
  pause
)
