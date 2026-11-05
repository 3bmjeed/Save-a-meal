@echo off
setlocal
cd /d "%~dp0"

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "PYTHON="

echo Happy Meal - local launcher
echo.

where node >nul 2>nul
if errorlevel 1 (
    echo ERROR: Node.js 20 or newer is required. Install it from https://nodejs.org/
    pause
    exit /b 1
)
node -e "process.exit(Number(process.versions.node.split('.')[0]) >= 20 ? 0 : 1)" >nul 2>nul
if errorlevel 1 (
    echo ERROR: Node.js 20 or newer is required.
    pause
    exit /b 1
)
where npm.cmd >nul 2>nul
if errorlevel 1 (
    echo ERROR: npm was not found. Reinstall Node.js with npm included.
    pause
    exit /b 1
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 set "PYTHON=python"
if not defined PYTHON (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON=py -3"
)
if not defined PYTHON (
    echo ERROR: Python 3.10 or newer is required. Install it from https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist "%BACKEND%\.venv\Scripts\python.exe" (
    echo Creating the backend Python environment...
    %PYTHON% -m venv "%BACKEND%\.venv"
    if errorlevel 1 goto setup_failed
)

"%BACKEND%\.venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if errorlevel 1 (
    echo ERROR: The existing backend .venv uses Python older than 3.10.
    echo Remove backend\.venv and run this launcher again.
    pause
    exit /b 1
)

echo Installing or checking backend packages...
"%BACKEND%\.venv\Scripts\python.exe" -m pip install -r "%BACKEND%\requirements.txt"
if errorlevel 1 goto setup_failed

if not exist "%BACKEND%\.env" (
    echo Creating backend\.env from backend\.env.example...
    copy "%BACKEND%\.env.example" "%BACKEND%\.env" >nul
    if errorlevel 1 goto setup_failed
)

"%BACKEND%\.venv\Scripts\python.exe" -c "from pathlib import Path; import sys; sys.exit(0 if any(x.strip() == 'DATABASE_URL=sqlite:///save_a_meal.db' for x in Path(sys.argv[1]).read_text().splitlines()) else 1)" "%BACKEND%\.env"
if not errorlevel 1 (
    echo Checking local demo data...
    pushd "%BACKEND%"
    "%BACKEND%\.venv\Scripts\python.exe" seed.py
    if errorlevel 1 (
        popd
        goto setup_failed
    )
    popd
) else (
    echo Skipping demo seeding because DATABASE_URL is not the default local SQLite database.
)

if not exist "%FRONTEND%\node_modules" (
    echo Installing frontend packages...
    pushd "%FRONTEND%"
    call npm.cmd install --no-audit --no-fund
    if errorlevel 1 (
        popd
        goto setup_failed
    )
    popd
)

echo Starting the API and frontend in separate windows...
start "Happy Meal API" /D "%BACKEND%" cmd /k ""%BACKEND%\.venv\Scripts\python.exe" app.py"
start "Happy Meal Frontend" /D "%FRONTEND%" cmd /k "npm.cmd run dev"
ping 127.0.0.1 -n 5 >nul
start "" "http://127.0.0.1:5173"
echo.
echo Happy Meal is starting at http://127.0.0.1:5173
echo Keep both server windows open while using the app.
exit /b 0

:setup_failed
echo.
echo ERROR: Setup failed. Check the message above, then run start.bat again.
pause
exit /b 1
