#!/bin/bash
# Frida安装脚本

set -e

echo "=== Frida安装脚本 ==="

# 检查Python环境
echo "1. 检查Python环境..."
python3 --version || {
    echo "错误: 未找到Python3"
    exit 1
}

# 安装frida-tools
echo "2. 安装frida-tools..."
pip3 install frida-tools || {
    echo "错误: frida-tools安装失败"
    exit 1
}

# 获取Frida版本
FRIDA_VERSION=$(frida --version)
echo "   Frida版本: $FRIDA_VERSION"

# 检测手机架构
echo "3. 检测手机架构..."
ARCH=$(adb shell getprop ro.product.cpu.abi)
echo "   CPU架构: $ARCH"

# 确定frida-server文件名
case "$ARCH" in
    arm64-v8a)
        FRIDA_SERVER="frida-server-${FRIDA_VERSION}-android-arm64"
        ;;
    armeabi-v7a)
        FRIDA_SERVER="frida-server-${FRIDA_VERSION}-android-arm"
        ;;
    x86_64)
        FRIDA_SERVER="frida-server-${FRIDA_VERSION}-android-x86_64"
        ;;
    x86)
        FRIDA_SERVER="frida-server-${FRIDA_VERSION}-android-x86"
        ;;
    *)
        echo "错误: 不支持的架构 $ARCH"
        exit 1
        ;;
esac

# 下载frida-server
echo "4. 下载frida-server..."
FRIDA_SERVER_URL="https://github.com/frida/frida/releases/download/${FRIDA_VERSION}/${FRIDA_SERVER}.xz"

if [ ! -f "$FRIDA_SERVER" ]; then
    wget -q "$FRIDA_SERVER_URL" || {
        echo "下载失败，请手动下载: $FRIDA_SERVER_URL"
        exit 1
    }
    
    # 解压
    xz -d "${FRIDA_SERVER}.xz" 2>/dev/null || {
        echo "解压失败，请手动解压"
        exit 1
    }
fi

# 推送到手机
echo "5. 推送frida-server到手机..."
adb push "$FRIDA_SERVER" /data/local/tmp/frida-server
adb shell su -c "chmod 755 /data/local/tmp/frida-server"

echo ""
echo "=== 安装完成 ==="
echo "启动frida-server:"
echo "   adb shell su -c '/data/local/tmp/frida-server &'"
echo ""
echo "验证安装:"
echo "   frida-ps -U | grep -i xianyu"
