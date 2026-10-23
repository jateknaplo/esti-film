@echo off
rem Esti film: musor letoltese, oldal generalasa, kitetel a Cloudflare Pagesre.
rem Az utemezett feladat (14:00, 19:00) ezt futtatja; kezzel is indithato dupla kattintassal.
chcp 65001 >nul
cd /d "%~dp0"
if not exist logs mkdir logs
set PY=C:\Users\ayo\AppData\Local\Python\bin\python.exe
set PYTHONIOENCODING=utf-8
rem "ha-regi": bejelentkezes/feloldas utan csak akkor fut, ha az oldal 3 oranal regebbi
if /i "%~1"=="ha-regi" "%PY%" -c "import os,sys,time;sys.exit(0 if os.path.exists('site/index.html') and time.time()-os.path.getmtime('site/index.html')<10800 else 1)" && exit /b 0
rem TMDb-kulcs: egyetlen sor a config\tmdb_key.txt fajlban (nincs a gitben)
if exist config\tmdb_key.txt set /p TMDB_API_KEY=<config\tmdb_key.txt
echo ==== %date% %time% ==== >> logs\run.log
"%PY%" -c "import tzdata" 2>nul || "%PY%" -m pip install -q tzdata >> logs\run.log 2>&1
"%PY%" scripts\imdb_data.py --if-older 30 >> logs\run.log 2>&1
"%PY%" scripts\build.py >> logs\run.log 2>&1
if errorlevel 1 (
  echo BUILD HIBA >> logs\run.log
  exit /b 1
)
call "C:\Program Files\nodejs\npx.cmd" wrangler pages deploy site --project-name esti-film --branch main --commit-dirty=true >> logs\run.log 2>&1
if errorlevel 1 (
  echo DEPLOY HIBA >> logs\run.log
  exit /b 1
)
echo OK >> logs\run.log
