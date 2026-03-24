#!/bin/bash
# AstrBot NasTool 插件安装脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "AstrBot NasTool 插件安装脚本"
echo "========================================"
echo ""

# 检查参数
if [ -z "$1" ]; then
    echo "用法: $0 <AstrBot安装目录>"
    echo "示例: $0 /opt/astrbot"
    exit 1
fi

ASTRBOT_DIR="$1"
PLUGIN_DIR="$ASTRBOT_DIR/data/plugins/astrbot_plugin_nastool_downloader"

# 检查 AstrBot 目录是否存在
if [ ! -d "$ASTRBOT_DIR" ]; then
    echo -e "${RED}错误: AstrBot 目录不存在: $ASTRBOT_DIR${NC}"
    exit 1
fi

echo "AstrBot 目录: $ASTRBOT_DIR"
echo "插件目录: $PLUGIN_DIR"
echo ""

# 创建插件目录
echo "📁 创建插件目录..."
mkdir -p "$PLUGIN_DIR"

# 复制文件
echo "📦 复制插件文件..."
cp -r . "$PLUGIN_DIR/"

# 进入插件目录
cd "$PLUGIN_DIR"

# 安装依赖
echo "📥 安装 Python 依赖..."
if command -v pip3 &> /dev/null; then
    pip3 install -r requirements.txt
elif command -v pip &> /dev/null; then
    pip install -r requirements.txt
else
    echo -e "${YELLOW}警告: 未找到 pip，请手动安装依赖: pip install -r requirements.txt${NC}"
fi

# 检查安装结果
echo ""
echo "🔍 检查安装结果..."

REQUIRED_FILES=("main.py" "metadata.yaml" "_conf_schema.json")
ALL_OK=true

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ✅ $file"
    else
        echo -e "  ❌ $file (缺失)"
        ALL_OK=false
    fi
done

echo ""
if [ "$ALL_OK" = true ]; then
    echo -e "${GREEN}✅ 插件安装成功！${NC}"
    echo ""
    echo "下一步操作:"
    echo "1. 重启 AstrBot"
    echo "2. 在 WebUI 中配置插件参数:"
    echo "   - base_url: NasTool 服务地址"
    echo "   - username: NasTool 登录账号"
    echo "   - password: NasTool 登录密码"
    echo "3. 在聊天中使用 下载电影/电视剧/视频 命令开始搜索"
    echo ""
    echo "详细文档: $PLUGIN_DIR/README.md"
else
    echo -e "${RED}❌ 安装可能存在问题，请检查文件完整性${NC}"
    exit 1
fi
