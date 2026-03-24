#!/bin/bash
# AstrBot NasTool 插件手动安装脚本

set -e

echo "========================================"
echo "AstrBot NasTool 插件手动安装"
echo "========================================"
echo ""

# 获取 AstrBot 目录
if [ -z "$1" ]; then
    echo "用法: $0 <AstrBot数据目录>"
    echo "示例: $0 /opt/astrbot/data"
    echo ""
    echo "提示: AstrBot 数据目录通常在："
    echo "  - Docker: /app/data 或挂载的数据卷"
    echo "  - 本地安装: ./data 或 ~/AstrBot/data"
    exit 1
fi

DATA_DIR="$1"
PLUGIN_DIR="$DATA_DIR/plugins/astrbot_plugin_nastool_downloader"

echo "AstrBot 数据目录: $DATA_DIR"
echo "插件目录: $PLUGIN_DIR"
echo ""

# 检查目录
if [ ! -d "$DATA_DIR" ]; then
    echo "❌ 错误: 数据目录不存在: $DATA_DIR"
    exit 1
fi

if [ ! -d "$DATA_DIR/plugins" ]; then
    echo "📁 创建插件目录..."
    mkdir -p "$DATA_DIR/plugins"
fi

# 如果已存在，先备份
if [ -e "$PLUGIN_DIR" ]; then
    BACKUP_DIR="${PLUGIN_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
    echo "⚠️  检测到已有安装，备份到: $BACKUP_DIR"
    mv "$PLUGIN_DIR" "$BACKUP_DIR"
fi

# 创建插件目录
echo "📁 创建插件目录..."
mkdir -p "$PLUGIN_DIR"

# 复制文件
echo "📦 复制插件文件..."
cp main.py "$PLUGIN_DIR/"
cp nastool_client.py "$PLUGIN_DIR/"
cp plugin_logic.py "$PLUGIN_DIR/"
cp metadata.yaml "$PLUGIN_DIR/"
cp _conf_schema.json "$PLUGIN_DIR/"
cp requirements.txt "$PLUGIN_DIR/"
cp README.md "$PLUGIN_DIR/"

# 复制子目录
if [ -d "tests" ]; then
    cp -r tests "$PLUGIN_DIR/"
fi

echo ""
echo "✅ 安装完成！"
echo ""
echo "✅ 安装完成！"
echo ""
echo "下一步:"
echo "1. 重启 AstrBot"
echo "2. 在 WebUI 中配置插件参数"
echo "   - base_url: NasTool 服务地址"
echo "   - username: NasTool 登录账号"
echo "   - password: NasTool 登录密码"
echo ""
echo "目录结构:"
ls -la "$PLUGIN_DIR"
