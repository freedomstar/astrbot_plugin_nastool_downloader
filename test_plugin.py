#!/usr/bin/env python3
"""
AstrBot NasTool 插件快速测试脚本

使用方法：
    python test_plugin.py --base-url http://127.0.0.1:3000 --username 你的账号 --password 你的密码

功能：
    1. 测试登录获取 API Key
    2. 测试媒体搜索
    3. 测试资源检索
    4. 测试下载提交（仅模拟，不实际下载）
"""

import argparse
import asyncio
import sys

from nastool_client import NasToolClient
from plugin_logic import MediaCandidate, ReleaseCandidate


async def test_login(client: NasToolClient) -> bool:
    """测试登录功能"""
    print("\n🔐 测试登录获取 API Key")
    print("-" * 50)

    try:
        result = await client.login_with_credentials()
        print(f"✅ 登录成功: {result.get('message', 'OK')}")
        return True
    except Exception as e:
        print(f"❌ 登录失败: {e}")
        return False


async def test_media_search(client: NasToolClient, query: str):
    """测试媒体搜索功能"""
    print(f"\n🔍 测试媒体搜索: {query}")
    print("-" * 50)

    try:
        medias = await client.search_media(query)
        print(f"✅ 成功找到 {len(medias)} 个媒体")

        for i, media in enumerate(medias[:5], 1):
            print(f"\n  {i}. {media.title} ({media.year})")
            print(f"     类型: {media.label}")
            print(f"     TMDB: {media.tmdb_id}")
            if media.original_title:
                print(f"     原名: {media.original_title}")

        return medias
    except Exception as e:
        print(f"❌ 媒体搜索失败: {e}")
        return []


async def test_release_search(client: NasToolClient, media):
    """测试资源检索功能"""
    print(f"\n📦 测试资源检索: {media.title}")
    print("-" * 50)

    try:
        releases = await client.search_releases_for_media(
            media, poll_interval=2, max_polls=5
        )
        print(f"✅ 成功找到 {len(releases)} 个资源")

        for i, release in enumerate(releases[:5], 1):
            print(f"\n  {i}. {release.title}")
            print(f"     站点: {release.site}")
            print(f"     大小: {release.size}")
            print(f"     做种: {release.seeders}")
            print(f"     规格: {release.resolution} {release.resource_type}")

        return releases
    except Exception as e:
        print(f"❌ 资源检索失败: {e}")
        return []


async def test_download_simulation(client: NasToolClient, release) -> None:
    """模拟测试下载流程（不实际添加任务）"""
    print(f"\n⬇️  测试下载流程: {release.title[:50]}...")
    print("-" * 50)

    try:
        # 获取下载器配置
        clients = await client._post_json("/api/v1/download/client/list", {})
        detail = clients.get("data", {}).get("detail", {})

        enabled_clients = [
            item
            for item in detail.values()
            if isinstance(item, dict) and int(item.get("enabled") or 0) == 1
        ]

        if enabled_clients:
            print(f"✅ 找到 {len(enabled_clients)} 个已启用的下载器:")
            for client_info in enabled_clients:
                print(f"   - {client_info.get('name')} ({client_info.get('type')})")
            print("\n✅ 下载流程测试通过（未实际添加任务）")
        else:
            print("⚠️  未找到已启用的下载器")

    except Exception as e:
        print(f"❌ 下载测试失败: {e}")


async def main():
    parser = argparse.ArgumentParser(description="AstrBot NasTool 插件快速测试")
    parser.add_argument(
        "--base-url",
        required=True,
        help="NasTool 服务地址，例如: http://127.0.0.1:3000",
    )
    parser.add_argument("--username", required=True, help="NasTool 登录账号")
    parser.add_argument("--password", required=True, help="NasTool 登录密码")
    parser.add_argument(
        "--query", default="盗梦空间", help="测试搜索的影片名称（默认: 盗梦空间）"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("AstrBot NasTool 插件测试脚本")
    print("=" * 60)

    # 创建客户端
    client = NasToolClient(
        base_url=args.base_url,
        username=args.username,
        password=args.password,
        request_timeout=20,
        search_timeout=120,
    )

    print(f"\n📍 NasTool 地址: {args.base_url}")
    print(f"👤 账号: {args.username}")

    try:
        # 测试 1: 登录
        if not await test_login(client):
            print("\n❌ 测试中止：登录失败")
            sys.exit(1)

        # 测试 2: 媒体搜索
        medias = await test_media_search(client, args.query)

        if not medias:
            print("\n❌ 测试中止：未找到媒体")
            sys.exit(1)

        # 测试 3: 资源检索
        releases = await test_release_search(client, medias[0])

        if not releases:
            print("\n⚠️  警告：未找到资源，跳过下载测试")
        else:
            # 测试 4: 下载流程（模拟）
            await test_download_simulation(client, releases[0])

        print("\n" + "=" * 60)
        print("✅ 所有测试完成")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
