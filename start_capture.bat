@echo off
chcp 65001 >nul
echo === 启动闲鱼数据采集环境 ===

REM 检查ADB连接
echo 1. 检查ADB连接...
adb devices | findstr "device$" >nul
if errorlevel 1 (
    echo 错误: 未检测到ADB设备
    pause
    exit /b 1
)

REM 检查Root权限
echo 2. 检查Root权限...
adb shell su -c "id" | findstr "uid=0" >nul
if errorlevel 1 (
    echo 错误: 设备未Root
    echo 请先运行 setup\root_setup.sh
    pause
    exit /b 1
)

REM 启动frida-server
echo 3. 启动frida-server...
adb shell su -c "pkill frida-server" 2>nul
adb shell su -c "/data/local/tmp/frida-server &"
timeout /t 2 >nul

REM 验证frida-server
frida-ps -U | findstr "frida-server" >nul
if errorlevel 1 (
    echo 错误: frida-server启动失败
    pause
    exit /b 1
)
echo    frida-server已启动

REM 启动mitmproxy
echo 4. 启动mitmproxy...
echo    代理端口: 8080

REM 启动mitmproxy
start "mitmproxy" mitmdump -s "%~dp0scripts\xianyu_intercept.py" -p 8080 --set block_global=false
timeout /t 2 >nul

echo.
echo === 采集环境已启动 ===
echo.
echo 请在手机上设置代理:
echo    WiFi设置 -^> 代理 -^> 手动
echo    主机名: [本机IP]
echo    端口: 8080
echo.
echo 然后在手机上操作闲鱼:
echo    1. 打开闲鱼App
echo    2. 搜索球拍型号
echo    3. 点击'行情'标签
echo    4. 滚动页面加载数据
echo.
echo 数据将保存到: %~dp0data\captured\
echo.
echo 按任意键停止采集
pause >nul

REM 停止采集
echo 停止采集...
taskkill /f /im mitmdump.exe 2>nul
adb shell su -c "pkill frida-server" 2>nul
echo 完成
