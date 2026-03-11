from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 将插件目录添加到 Python 路径，确保能正确导入本地模块
_plugin_dir = Path(__file__).parent
if str(_plugin_dir) not in sys.path:
    sys.path.insert(0, str(_plugin_dir))

from dataclasses import dataclass
from typing import Mapping, cast

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.utils.session_waiter import SessionController, session_waiter

from nastool_client import NasToolApiError, NasToolClient
from plugin_logic import (
    ConversationState,
    ReleaseCandidate,
    build_fallback_releases_message,
    build_media_choices_message,
    build_release_choices_message,  # 新增导入用于显示资源列表
    extract_command_query,
    filter_releases_by_query,
    parse_choice,
    pick_best_release,
)
@dataclass(slots=True)
class PluginSettings:
    base_url: str
    api_key: str
    request_timeout: int
    search_timeout: int
    poll_interval: float
    max_polls: int
    max_media_results: int
    max_release_results: int
    download_dir: str
    download_setting: str
    session_timeout: int


def _read_str(config: Mapping[str, object], key: str, default: str) -> str:
    value = config.get(key, default)
    return value if isinstance(value, str) else default


def _read_int(config: Mapping[str, object], key: str, default: int) -> int:
    value = config.get(key, default)
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _read_float(config: Mapping[str, object], key: str, default: float) -> float:
    value = config.get(key, default)
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


@register(
    "astrbot_plugin_nastool_downloader",
    "OpenCode",
    "通过对话搜索 NasTool 媒体并选择资源下载",
    "1.0.0",
)
class NasToolDownloaderPlugin(Star):
    config: PluginSettings

    def __init__(
        self, context: Context, config: dict[str, object] | None = None
    ) -> None:
        super().__init__(context)
        raw_config: Mapping[str, object] = config or {}
        self.config = PluginSettings(
            base_url=_read_str(raw_config, "base_url", "http://127.0.0.1:3000"),
            api_key=_read_str(raw_config, "api_key", ""),
            request_timeout=_read_int(raw_config, "request_timeout", 20),
            search_timeout=_read_int(raw_config, "search_timeout", 120),
            poll_interval=_read_float(raw_config, "poll_interval", 2.0),
            max_polls=_read_int(raw_config, "max_polls", 20),
            max_media_results=_read_int(raw_config, "max_media_results", 5),
            max_release_results=_read_int(raw_config, "max_release_results", 8),
            download_dir=_read_str(raw_config, "download_dir", ""),
            download_setting=_read_str(raw_config, "download_setting", ""),
            session_timeout=_read_int(raw_config, "session_timeout", 180),
        )

    @filter.command("下载电影")
    async def nastool(self, event: AstrMessageEvent):
        """搜索 NasTool 媒体，选择资源后下发下载。

        用法示例：
        - 下载电影 盗梦空间
        - 下载电影 功夫 1080p 粤语
        - 下载电影 Inception 4K
        """
        query = extract_command_query(event.message_str)
        if not query.keyword:
            yield event.plain_result(
                "用法：下载电影 电影名 [分辨率] [语言] [片源]\n\n"
                + "示例：\n"
                + "- 下载电影 盗梦空间\n"
                + "- 下载电影 功夫 1080p 粤语\n"
                + "- 下载电影 Inception 4K BluRay x265"
            )
            return

        if not self.config.api_key:
            yield event.plain_result("插件尚未配置 NasTool API Key。")
            return

        client = self._build_client()
        try:
            medias = await client.search_media(query.keyword)
        except NasToolApiError as exc:
            logger.error("NasTool media search failed: %s", exc)
            yield event.plain_result(f"媒体搜索失败：{exc}")
            return
        except Exception as exc:  # pragma: no cover - defensive path
            logger.exception("Unexpected media search error")
            yield event.plain_result(f"媒体搜索失败：{exc}")
            return

        if not medias:
            yield event.plain_result(f"没有找到与「{query.keyword}」相关的媒体。")
            return

        state = ConversationState(
            medias=medias[: self.config.max_media_results], search_query=query
        )
        yield event.plain_result(build_media_choices_message(query, state))

        @session_waiter(
            timeout=self.config.session_timeout, record_history_chains=False
        )
        async def choose_handler(
            controller: SessionController, next_event: AstrMessageEvent
        ) -> None:
            try:
                if state.selected_media is None:
                    choice = parse_choice(next_event.message_str, len(state.medias))
                    if choice is None:
                        await next_event.send(
                            next_event.plain_result("已取消 NasTool 下载流程。")
                        )
                        controller.stop()
                        return

                    state.selected_media = state.medias[choice]
                    await next_event.send(
                        next_event.plain_result(
                            f"已选择《{state.selected_media.title}》，正在检索可下载资源，请稍候..."
                        )
                    )
                    releases = await client.search_releases_for_media(
                        state.selected_media,
                        poll_interval=self.config.poll_interval,
                        max_polls=self.config.max_polls,
                    )

                    # 保存过滤前的原始资源
                    original_releases = releases
                    
                    # 应用过滤条件
                    if state.search_query and state.search_query.has_filters():
                        releases = filter_releases_by_query(
                            releases, state.search_query
                        )

                    # 检查是否需要跳过自动下载（显示资源列表让用户选择）
                    if state.search_query and state.search_query.skip_auto_download:
                        # 按做种数降序排序所有有效资源
                        sorted_releases = pick_best_release(
                            releases, return_top_n=self.config.max_release_results
                        )
                        if sorted_releases:
                            # sorted_releases 是列表
                            assert isinstance(sorted_releases, list)
                            state.releases = sorted_releases
                            await next_event.send(
                                next_event.plain_result(
                                    build_release_choices_message(state)
                                )
                            )
                            # 等待用户选择资源
                            return
                        else:
                            await next_event.send(
                                next_event.plain_result(
                                    "暂时没有检索到可下载资源，或检索结果的文件大小均为 0。"
                                )
                            )
                            controller.stop()
                            return

                    selected_release = pick_best_release(releases)
                    if selected_release is None:
                        # 检查原始资源是否有有效资源
                        fallback_result = pick_best_release(
                            original_releases, return_top_n=5
                        )
                        if fallback_result:
                            # fallback_result 是 list[ReleaseCandidate]
                            assert isinstance(fallback_result, list)
                            state.releases = fallback_result
                            await next_event.send(
                                next_event.plain_result(
                                    build_fallback_releases_message(
                                        state, state.search_query
                                    )
                                )
                            )
                            # 等待用户选择备选资源
                            return
                        else:
                            await next_event.send(
                                next_event.plain_result(
                                    "暂时没有检索到可下载资源，或检索结果的文件大小均为 0。"
                                )
                            )
                            controller.stop()
                            return
                    # selected_release 是单个 ReleaseCandidate
                    assert isinstance(selected_release, ReleaseCandidate)
                    state.releases = [selected_release]

                    result = await client.download_release_candidate(
                        selected_release,
                        save_dir=self.config.download_dir,
                        download_setting=self.config.download_setting,
                    )
                    await next_event.send(
                        next_event.plain_result(
                            "已自动选择做种数最高且文件大小有效的资源并提交下载："
                            + f"\n{selected_release.title}"
                            + f"\n站点：{selected_release.site or '未知'} | 大小：{selected_release.size or '未知'} | 做种：{selected_release.seeders}"
                            + f"\nNasTool 返回：{result.get('message') or '成功'}"
                        )
                    )
                    controller.stop()
                    return
                    state.releases = [selected_release]

                    result = await client.download_release_candidate(
                        selected_release,
                        save_dir=self.config.download_dir,
                        download_setting=self.config.download_setting,
                    )
                    await next_event.send(
                        next_event.plain_result(
                            "已自动选择做种数最高且文件大小有效的资源并提交下载："
                            + f"\n{selected_release.title}"
                            + f"\n站点：{selected_release.site or '未知'} | 大小：{selected_release.size or '未知'} | 做种：{selected_release.seeders}"
                            + f"\nNasTool 返回：{result.get('message') or '成功'}"
                        )
                    )
                    controller.stop()
                    return

                # 处理用户选择备选资源
                if state.releases:
                    choice = parse_choice(next_event.message_str, len(state.releases))
                    if choice is None:
                        await next_event.send(
                            next_event.plain_result("已取消 NasTool 下载流程。")
                        )
                        controller.stop()
                        return

                    selected_release = state.releases[choice]
                    result = await client.download_release_candidate(
                        selected_release,
                        save_dir=self.config.download_dir,
                        download_setting=self.config.download_setting,
                    )
                    await next_event.send(
                        next_event.plain_result(
                            "已提交下载："
                            + f"\n{selected_release.title}"
                            + f"\n站点：{selected_release.site or '未知'} | 大小：{selected_release.size or '未知'} | 做种：{selected_release.seeders}"
                            + f"\nNasTool 返回：{result.get('message') or '成功'}"
                        )
                    )
                    controller.stop()
                    return
            except ValueError as exc:
                await next_event.send(next_event.plain_result(str(exc)))
            except NasToolApiError as exc:
                await next_event.send(
                    next_event.plain_result(f"NasTool 请求失败：{exc}")
                )
                controller.stop()
            except Exception as exc:  # pragma: no cover - defensive path
                logger.exception("Unexpected session error")
                await next_event.send(next_event.plain_result(f"处理失败：{exc}"))
                controller.stop()

        async def session_runner() -> None:
            context = cast(Context, self.context)
            try:
                await choose_handler(event)
            except TimeoutError:
                _ = await context.send_message(
                    event.unified_msg_origin,
                    MessageChain().message("等待选择超时，已结束 NasTool 下载流程。"),
                )
            except Exception as exc:
                logger.exception("NasTool session runner failed")
                _ = await context.send_message(
                    event.unified_msg_origin,
                    MessageChain().message(f"处理失败：{exc}"),
                )

        _ = asyncio.create_task(session_runner())
        event.stop_event()
        return

    def _build_client(self) -> NasToolClient:
        return NasToolClient(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            request_timeout=self.config.request_timeout,
            search_timeout=self.config.search_timeout,
        )
