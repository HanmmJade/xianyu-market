#!/bin/bash
# Root环境搭建脚本
# 适用于小米 2211133C (Android 6.0.1)

set -e

echo "=== 闲鱼数据采集 - Root环境搭建 ==="

# 检查ADB连接
echo "1. 检查ADB连接..."
adb devices | grep -q "device$" || {
    echo "错误: 未检测到ADB设备"
    exit 1
}

DEVICE_ID=$(adb devices | grep "device$" | awk '{print $1}')
echo "   设备ID: $DEVICE_ID"

# 检查设备信息
echo "2. 检查设备信息..."
echo "   型号: $(adb shell getprop ro.product.model)"
echo "   Android版本: $(adb shell getprop ro.build.version.release)"
echo "   SDK版本: $(adb shell getprop ro.build.version.sdk)"

# 检查Bootloader状态
echo "3. 检查Bootloader状态..."
BOOTLOADER_STATUS=$(adb shell getprop ro.boot.verifiedbootstate 2>/dev/null || echo "unknown")
echo "   Bootloader状态: $BOOTLOADER_STATUS"

# 下载Magisk
echo "4. 准备Magisk..."
MAGISK_VERSION="27.0"
MAGISK_APK="Magisk-v${MAGISK_VERSION}.apk"

if [ ! -f "$MAGISK_APK" ]; then
    echo "   下载Magisk v${MAGISK_VERSION}..."
    wget -q "https://github.com/topjohnwu/Magisk/releases/download/v${MAGISK_VERSION}/${MAGISK_APK}" || {
        echo "   下载失败，请手动下载: https://github.com/topjohnwu/Magisk/releases"
        echo "   下载后重命名为 ${MAGISK_APK} 放到当前目录"
    }
fi

# 提取boot.img
echo "5. 提取boot.img..."
adb shell su -c "dd if=/dev/block/by-name/boot of=/sdcard/boot.img" 2>/dev/null || {
    echo "   警告: 无法直接提取boot.img"
    echo "   请从固件包中提取boot.img"
}

# 安装Magisk
echo "6. 安装Magisk..."
if [ -f "$MAGISK_APK" ]; then
    adb install "$MAGISK_APK" 2>/dev/null || {
        echo "   安装失败，请手动安装"
    }
fi

echo ""
echo "=== 后续步骤 ==="
echo "1. 在手机上打开Magisk应用"
echo "2. 点击 '安装' -> '选择并修补一个文件'"
echo "3. 选择 /sdcard/boot.img"
echo "4. 将修补后的boot.img刷入设备:"
echo "   adb pull /sdcard/Download/magisk_patched-*.boot.img"
echo "   adb reboot bootloader"
echo "   fastboot flash boot magisk_patched-*.boot.img"
echo "   fastboot reboot"
echo ""
echo "验证Root:"
echo "   adb shell su -c 'id'"
echo "   应该显示: uid=0(root) gid=0(root)
