#!/bin/bash
# 启动数据采集环境

set -e

echo "=== 启动闲鱼数据采集环境 ==="

# 检查ADB连接
echo "1. 检查ADB连接..."
adb devices | grep -q "device$" || {
    echo "错误: 未检测到ADB设备"
    exit 1
}

DEVICE_ID=$(adb devices | grep "device$" | awk '{print $1}')
echo "   设备ID: $DEVICE_ID"

# 检查Root权限
echo "2. 检查Root权限..."
adb shell su -c "id" | grep -q "uid=0" || {
    echo "错误: 设备未Root"
    echo "请先运行 setup/root_setup.sh"
    exit 1
}

# 启动frida-server
echo "3. 启动frida-server..."
adb shell su -c "pkill frida-server" 2>/dev/null || true
adb shell su -c "/data/local/tmp/frida-server &"
sleep 2

# 验证frida-server
frida-ps -U | grep -q "frida-server" || {
    echo "错误: frida-server启动失败"
    exit 1
}
echo "   frida-server已启动"

# 启动mitmproxy
echo "4. 启动mitmproxy..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 获取本机IP
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I | awk '{print $1}')
echo "   本机IP: $LOCAL_IP"
echo "   代理端口: 8080"

# 启动mitmproxy
mitmdump -s "$SCRIPT_DIR/xianyu_intercept.py" -p 8080 --set block_global=false &
MITMPROXY_PID=$!
sleep 2

echo ""
echo "=== 采集环境已启动 ==="
echo ""
echo "请在手机上设置代理:"
echo "   WiFi设置 -> 代理 -> 手动"
echo "   主机名: $LOCAL_IP"
echo "   端口: 8080"
echo ""
echo "然后在手机上操作闲鱼:"
echo "   1. 打开闲鱼App"
echo "   2. 搜索球拍型号"
echo "   3. 点击'行情'标签"
echo "   4. 滚动页面加载数据"
echo ""
echo "数据将保存到: $PROJECT_DIR/data/captured/"
echo ""
echo "按 Ctrl+C 停止采集"

# 等待用户中断
trap "echo ''; echo '停止采集...'; kill $MITMPROXY_PID 2>/dev/null; adb shell su -c 'pkill frida-server' 2>/dev/null; exit 0" INT TERM

wait
