@echo off
rem Egyszeri: Cloudflare-bejelentkezés (a böngészőben az "Allow" gombra kell kattintani),
rem majd a Pages-projekt létrehozása. A kimenet a logs\login.log fájlba is megy.
cd /d "%~dp0"
if not exist logs mkdir logs
call "C:\Program Files\nodejs\npx.cmd" wrangler login
call "C:\Program Files\nodejs\npx.cmd" wrangler whoami > logs\login.log 2>&1
call "C:\Program Files\nodejs\npx.cmd" wrangler pages project create esti-film --production-branch main >> logs\login.log 2>&1
echo KESZ >> logs\login.log
type logs\login.log
pause
