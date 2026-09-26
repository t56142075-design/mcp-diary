@echo off
REM ============================================================
REM One-click launcher: diary MCP server (HTTP mode) + Cloudflare
REM quick tunnel, for ChatGPT custom connector access.
REM
REM EDIT THESE TWO PATHS for your machine before first run:
REM   PY  = full path to the python.exe inside your venv
REM   CF  = full path to cloudflared.exe
REM ============================================================
setlocal
set "PY=C:\Users\26627\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
set "CF=C:\Users\26627\.workbuddy\binaries\cloudflared\cloudflared.exe"

REM Project root = parent of this script's folder
cd /d "%~dp0.."

if not exist data mkdir data
if not exist data\http_token.txt (
    %PY% -c "import secrets; print(secrets.token_urlsafe(32))" > data\http_token.txt
)
set /p TOKEN=<data\http_token.txt

set "DIARY_DATA_DIR=data"
set "DIARY_AI_KEY_FILE=data\keys\ai_private.key"
set "DIARY_HTTP_TOKEN=%TOKEN%"
set "DIARY_HTTP_HOST=127.0.0.1"
set "DIARY_HTTP_PORT=8080"

echo Starting diary MCP server on http://127.0.0.1:8080 ...
start "diary-server" cmd /k ""%PY%" -m mcp_diary.server"

timeout /t 3 /nobreak >nul

echo Starting Cloudflare quick tunnel ...
start "diary-tunnel" cmd /k ""%CF%" tunnel --url http://127.0.0.1:8080"

echo.
echo ==================================================================
echo Two windows just opened:
echo   [diary-server]  the MCP server. Keep it open.
echo   [diary-tunnel]  the tunnel. It prints a random URL like
echo                   https://xxxx.trycloudflare.com after ~10 sec.
echo                   Keep it open. URL changes on every restart.
echo
echo Give these to ChatGPT (Settings - Connectors - Create):
echo   MCP endpoint : https://YOUR-TUNNEL-URL/mcp
echo   Bearer token : %TOKEN%
echo ==================================================================
pause
