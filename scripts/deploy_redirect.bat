@echo off
cd /d "%~dp0"
if not exist logs mkdir logs
call "C:\Program Files\nodejs\npx.cmd" wrangler pages deploy redirect --project-name esti-film --branch main --commit-dirty=true > logs\redirect.log 2>&1
echo KESZ >> logs\redirect.log
