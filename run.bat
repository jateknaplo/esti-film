@echo off
rem Esti film: műsor letöltése, oldal generálása, kitétel a Cloudflare Pagesre.
rem Az ütemezett feladat (14:00, 19:00) ezt futtatja; kézzel is indítható dupla kattintással.
chcp 65001 >nul
cd /d "%~dp0"
if not exist logs mkdir logs
set PY=C:\Users\ayo\AppData\Local\Python\bin\python.exe
set PYTHONIOENCODING=utf-8
rem TMDb-kulcs: egyetlen sor a config\tmdb_key.txt fájlban (nincs a gitben)
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
