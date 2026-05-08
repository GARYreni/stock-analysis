@echo off
chcp 65001 >nul
cd /d "D:\AI\股票分析\stock-analysis\scripts"

:menu
cls
echo ================================================================
echo   YANJIUYUAN A股收盘复盘分析系统  v2.1
echo ================================================================
echo.
echo   [1] 收盘复盘分析（生成HTML报告 + 飞书通知）
echo   [2] 收盘复盘分析（仅生成HTML，不发送飞书）
echo   [3] 收盘复盘分析（含DeepSeek AI分析）
echo   [4] 全市场全景分析
echo   [5] 板块深度分析
echo   [6] 个股深度分析（含K线）
echo   [7] 机会发现（技术选股+涨跌停）
echo   [8] 荐股评分（多维度加权）
echo   [9] 龙虎榜分析
echo   [A] 资金流分析
echo   [B] 科创板全景
echo   [H] 当日热门股票
echo   [D] 部署到GitHub Pages
echo   [Q] 退出
echo.
set /p choice="  请选择 [1-Q]: "

if "%choice%"=="1" goto postclose_full
if "%choice%"=="2" goto postclose_only
if "%choice%"=="3" goto postclose_ai
if "%choice%"=="4" goto market
if "%choice%"=="5" goto sector
if "%choice%"=="6" goto stock
if "%choice%"=="7" goto opportunity
if "%choice%"=="8" goto recommend
if "%choice%"=="9" goto lhb
if "%choice%"=="A" goto fundflow
if "%choice%"=="B" goto kcb
if "%choice%"=="H" goto hot
if "%choice%"=="D" goto deploy
if "%choice%"=="Q" goto end
if "%choice%"=="q" goto end
echo 无效选择，请重试
pause
goto menu

:postclose_full
echo.
echo [启动] 收盘复盘分析（含飞书通知）...
python main.py --postclose --feishu-webhook "%FEISHU_WEBHOOK_URL%"
echo.
pause
goto menu

:postclose_only
echo.
echo [启动] 收盘复盘分析（仅HTML）...
python main.py --postclose --no-ai
echo.
pause
goto menu

:postclose_ai
echo.
echo [启动] 收盘复盘分析（含AI分析）...
set /p dk="  DeepSeek API Key (留空跳过): "
if "%dk%"=="" (
    python main.py --postclose --no-ai
) else (
    python main.py --postclose --deepseek-key %dk%
)
echo.
pause
goto menu

:market
echo.
echo [启动] 全市场全景分析...
python main.py
echo.
pause
goto menu

:sector
echo.
set /p bn="  输入板块名称 (如 有色金属): "
echo [启动] 板块分析: %bn%...
python main.py --sector "%bn%"
echo.
pause
goto menu

:stock
echo.
set /p sc="  输入股票代码 (如 601899): "
echo [启动] 个股分析: %sc%...
python main.py --stock "%sc%" --kline
echo.
pause
goto menu

:opportunity
echo.
echo [启动] 机会发现...
python main.py --opportunity
echo.
pause
goto menu

:recommend
echo.
echo [启动] 荐股评分...
python main.py --recommend
echo.
pause
goto menu

:lhb
echo.
echo [启动] 龙虎榜分析...
python main.py --lhb
echo.
pause
goto menu

:fundflow
echo.
echo [启动] 资金流分析...
python main.py --fund-flow
echo.
pause
goto menu

:kcb
echo.
echo [启动] 科创板全景...
python main.py --kcb
echo.
pause
goto menu

:hot
echo.
echo [启动] 当日热门股票...
python main.py --hot
echo.
pause
goto menu

:deploy
echo.
echo [部署] 推送 docs/ 到 GitHub Pages...
cd /d "D:\AI\股票分析\stock-analysis"
git add docs/
git commit -m "deploy: manual push from BAT"
git -c http.proxy=http://127.0.0.1:7897 -c https.proxy=http://127.0.0.1:7897 push origin master
if %errorlevel% equ 0 (
    echo [部署] ✅ 推送成功 https://garyreni.github.io/stock-analysis/
) else (
    echo [部署] ❌ 推送失败，尝试 gh CLI...
    gh repo sync
)
echo.
pause
goto menu

:end
echo 再见!
exit
