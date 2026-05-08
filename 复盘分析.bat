@echo off
setlocal

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "SCRIPTS=%ROOT%\scripts"

cd /d "%SCRIPTS%"

echo ================================================================
echo   YANJIUYUAN Postclose Review  v2.1
echo   %DATE% %TIME:~0,5%
echo ================================================================
echo.
echo [1/3] Running postclose review...
python main.py --postclose

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] postclose review failed
    pause
    exit /b 1
)

echo.
echo [2/3] Deploying to GitHub Pages...
cd /d "%ROOT%"

git add docs/ 2>nul
git commit -m "deploy: %DATE%" 2>nul

git -c http.proxy=http://127.0.0.1:7897 -c https.proxy=http://127.0.0.1:7897 push origin master 2>nul
if %errorlevel% equ 0 (
    echo [DEPLOY] OK  https://garyreni.github.io/stock-analysis/
    goto done
)

gh repo sync 2>nul
if %errorlevel% equ 0 (
    echo [DEPLOY] OK via gh CLI
    goto done
)

git push origin master 2>nul
if %errorlevel% equ 0 (
    echo [DEPLOY] OK direct
) else (
    echo [DEPLOY] FAILED - check network
)

:done
echo.
echo [3/3] Done.
echo Report: C:\Users\Gary\Desktop\收盘复盘_%DATE:~0,4%-%DATE:~5,2%-%DATE:~8,2%.html
echo Online:  https://garyreni.github.io/stock-analysis/
pause
exit
