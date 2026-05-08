@echo off
setlocal enabledelayedexpansion

:: --- use script's own location, no hardcoded paths ---
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "SCRIPTS=%ROOT%\scripts"
set "DOCS=%ROOT%\docs"

:: --- find python ---
set "PY=python"
where python >nul 2>&1
if %errorlevel% neq 0 (
    for %%p in (
        "C:\Users\Gary\miniconda3\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    ) do (
        if exist %%p set "PY=%%p"
    )
)

:: --- verify main.py ---
if not exist "%SCRIPTS%\main.py" (
    echo [ERROR] main.py not found at: %SCRIPTS%
    pause
    exit /b 1
)

cd /d "%SCRIPTS%"

:menu
cls
echo ================================================================
echo   YANJIUYUAN Postclose Review System  v2.1
echo   %DATE% %TIME:~0,5%
echo ================================================================
echo.
echo   [1] Postclose Review (HTML + Feishu notify)
echo   [2] Postclose Review (HTML only, no AI)
echo   [3] Postclose Review (with DeepSeek AI)
echo   [4] Full Market Scan
echo   [5] Sector Analysis
echo   [6] Stock Analysis (K-line)
echo   [7] Opportunity Discovery
echo   [8] Stock Rating
echo   [9] LHB (Dragon-Tiger) Analysis
echo   [A] Fund Flow Analysis
echo   [B] STAR Market (KeChuangBan)
echo   [H] Hot Stocks Today
echo   [D] Deploy docs/ to GitHub Pages
echo   [Q] Quit
echo.
set /p choice="  Select [1-Q]: "

if "%choice%"=="1" ( call :run python main.py --postclose )
if "%choice%"=="2" ( call :run python main.py --postclose --no-ai )
if "%choice%"=="3" ( call :postclose_ai )
if "%choice%"=="4" ( call :run python main.py )
if "%choice%"=="5" ( call :sector )
if "%choice%"=="6" ( call :stock )
if "%choice%"=="7" ( call :run python main.py --opportunity )
if "%choice%"=="8" ( call :run python main.py --recommend )
if "%choice%"=="9" ( call :run python main.py --lhb )
if /i "%choice%"=="A" ( call :run python main.py --fund-flow )
if /i "%choice%"=="B" ( call :run python main.py --kcb )
if /i "%choice%"=="H" ( call :run python main.py --hot )
if /i "%choice%"=="D" ( call :deploy )
if /i "%choice%"=="Q" goto :end
echo Invalid choice.
timeout /t 1 >nul
goto :menu

:: ===== subroutines =====

:run
echo.
echo [RUN] %*
echo.
%PY% %*
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] exit code: %errorlevel%
)
echo.
pause
goto :menu

:postclose_ai
echo.
set /p dk="  DeepSeek API Key (press Enter to skip): "
if "%dk%"=="" (
    call :run python main.py --postclose --no-ai
) else (
    call :run python main.py --postclose --deepseek-key "%dk%"
)
goto :eof

:sector
echo.
set /p bn="  Sector name: "
if "%bn%"=="" goto :menu
call :run python main.py --sector "%bn%"
goto :eof

:stock
echo.
set /p sc="  Stock code: "
if "%sc%"=="" goto :menu
call :run python main.py --stock "%sc%" --kline
goto :eof

:deploy
echo.
echo [DEPLOY] Pushing docs/ to GitHub Pages...
cd /d "%ROOT%"
git add docs/
git commit -m "deploy: %DATE%" 2>nul

:: try proxy first
git -c http.proxy=http://127.0.0.1:7897 -c https.proxy=http://127.0.0.1:7897 push origin master 2>nul
if %errorlevel% equ 0 (
    echo [DEPLOY] OK  https://garyreni.github.io/stock-analysis/
    pause
    goto :menu
)

:: try gh CLI
gh repo sync 2>nul
if %errorlevel% equ 0 (
    echo [DEPLOY] OK via gh CLI
    pause
    goto :menu
)

:: try direct
git push origin master 2>nul
if %errorlevel% equ 0 (
    echo [DEPLOY] OK direct
) else (
    echo [DEPLOY] FAILED - check network
)
pause
goto :menu

:end
echo Done.
exit
