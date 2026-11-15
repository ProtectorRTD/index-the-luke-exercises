@echo off
rem Обёртка для Windows (cmd и PowerShell): .\lab.cmd check 1.1
setlocal
cd /d "%~dp0"
if /i "%~1"=="up" goto up
if /i "%~1"=="down" goto down
docker compose --profile tools run --rm lab %*
goto :eof
:up
docker compose up -d --wait db
docker compose --profile tools build lab
goto :eof
:down
docker compose down
goto :eof
