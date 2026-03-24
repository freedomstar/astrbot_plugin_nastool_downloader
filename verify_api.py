#!/usr/bin/env python3
"""验证NasTool API连接脚本

用法：
    python verify_api.py --base-url http://192.168.1.100:3000 --username 你的账号 --password 你的密码

注意：此脚本会实际调用NasTool API，请确保：
1. NasTool服务正在运行
2. 网络可以访问NasTool服务
3. 账号密码正确
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 添加项目目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from nastool_client import NasToolApiError, NasToolClient


async def verify_connection(base_url: str, username: str, password: str) -> bool:
    """验证API连接"""
    print(f"🔍 正在测试连接到: {base_url}")
    print(f"👤 账号: {username}")
    print()

    client = NasToolClient(
        base_url=base_url,
        username=username,
        password=password,
        request_timeout=20.0,
    )

    try:
        # 测试1: 登录获取 API Key
        print("📡 测试1: 登录获取 API Key...")
        login_result = await client.login_with_credentials()
        print(f"   ✅ 登录成功: {login_result.get('message', 'OK')}")
        print()

        # 测试2: 媒体搜索
        print("📡 测试2: 媒体搜索...")
        medias = await client.search_media("测试")
        print(f"   ✅ 媒体搜索成功，返回 {len(medias)} 个结果")

        if medias:
            print(f"   📋 第一个结果: {medias[0].title}")
        print()

        # 测试3: 检查下载器配置
        print("📡 测试3: 检查下载器配置...")
        try:
            clients = await client._post_json("/api/v1/download/client/list", {})
            detail = clients.get("data", {}).get("detail", {})
            enabled_count = sum(
                1
                for item in detail.values()
                if isinstance(item, dict) and int(item.get("enabled") or 0) == 1
            )
            print(f"   ✅ 下载器配置获取成功")
            print(f"   📋 已启用的下载器: {enabled_count} 个")
        except NasToolApiError as e:
            print(f"   ⚠️  获取下载器配置失败: {e}")
        print()

        print("✅ 所有测试通过！API连接正常。")
        return True

    except NasToolApiError as e:
        print(f"❌ API错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 意外错误: {type(e).__name__}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="验证NasTool API连接")
    parser.add_argument(
        "--base-url",
        required=True,
        help="NasTool服务地址，例如: http://192.168.1.100:3000",
    )
    parser.add_argument(
        "--username",
        required=True,
        help="NasTool 登录账号",
    )
    parser.add_argument(
        "--password",
        required=True,
        help="NasTool 登录密码",
    )

    args = parser.parse_args()

    success = asyncio.run(
        verify_connection(args.base_url, args.username, args.password)
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
