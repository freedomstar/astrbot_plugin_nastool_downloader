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
    SearchQuery,
    build_fallback_releases_message,
    build_media_choices_message,
    build_release_choices_message,
    extract_command_query,
    filter_releases_by_query,
    parse_choice,
    pick_best_release,
)


@dataclass(slots=True)
class PluginSettings:
    base_url: str
    username: str
    password: str
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
    "1.1.0",
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
            username=_read_str(raw_config, "username", ""),
            password=_read_str(raw_config, "password", ""),
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

    def _build_client(self) -> NasToolClient:
        return NasToolClient(
            base_url=self.config.base_url,
            request_timeout=self.config.request_timeout,
            search_timeout=self.config.search_timeout,
            username=self.config.username,
            password=self.config.password,
        )

    async def _verify_login(self) -> tuple[bool, str, NasToolClient | None]:
        if not self.config.username or not self.config.password:
            return (
                False,
                "插件尚未配置 NasTool 登录信息。\n\n解决建议：\n1. 在插件配置中填写 username（登录账号）\n2. 在插件配置中填写 password（登录密码）\n3. 插件会自动登录获取 API Key\n\n提示：使用 NasTool 的 Web 界面登录账号密码",
                None,
            )

        client = self._build_client()
        try:
            result = await client.login_with_credentials()
            return True, f"登录成功：{result.get('message', 'OK')}", client
        except NasToolApiError as exc:
            return (
                False,
                f"登录失败：{exc}\n\n请检查：\n1. 账号密码是否正确\n2. NasTool 服务是否正常运行",
                None,
            )
        except Exception as exc:
            return (
                False,
                f"登录异常：{exc}\n\n请检查网络连接和 NasTool 服务状态",
                None,
            )

    async def _handle_download(
        self,
        event: AstrMessageEvent,
        query: SearchQuery,
        media_type_label: str,
    ):
        login_success, login_msg, client = await self._verify_login()
        if not login_success:
            yield event.plain_result(f"❌ 登录失败\n\n{login_msg}")
            return

        assert client is not None
        try:
            medias = await client.search_media(query.keyword)
        except NasToolApiError as exc:
            logger.error("NasTool media search failed: %s", exc)
            yield event.plain_result(f"媒体搜索失败：{exc}")
            return
        except Exception as exc:
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

                    original_releases = releases

                    if state.search_query and state.search_query.has_filters():
                        releases = filter_releases_by_query(
                            releases, state.search_query
                        )

                    if state.search_query and state.search_query.skip_auto_download:
                        sorted_releases = pick_best_release(
                            releases, return_top_n=self.config.max_release_results
                        )
                        if sorted_releases:
                            assert isinstance(sorted_releases, list)
                            state.releases = sorted_releases
                            await next_event.send(
                                next_event.plain_result(
                                    build_release_choices_message(state)
                                )
                            )
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
                        fallback_result = pick_best_release(
                            original_releases, return_top_n=5
                        )
                        if fallback_result:
                            assert isinstance(fallback_result, list)
                            state.releases = fallback_result
                            await next_event.send(
                                next_event.plain_result(
                                    build_fallback_releases_message(
                                        state, state.search_query
                                    )
                                )
                            )
                            return
                        else:
                            await next_event.send(
                                next_event.plain_result(
                                    "暂时没有检索到可下载资源，或检索结果的文件大小均为 0。"
                                )
                            )
                            controller.stop()
                            return
                    assert isinstance(selected_release, ReleaseCandidate)
                    state.releases = [selected_release]

                    media_type = (
                        state.selected_media.media_type if state.selected_media else ""
                    )
                    result = await client.download_release_candidate(
                        selected_release,
                        save_dir=self.config.download_dir,
                        download_setting=self.config.download_setting,
                        media_type=media_type,
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

                if state.releases:
                    choice = parse_choice(next_event.message_str, len(state.releases))
                    if choice is None:
                        await next_event.send(
                            next_event.plain_result("已取消 NasTool 下载流程。")
                        )
                        controller.stop()
                        return

                    selected_release = state.releases[choice]
                    media_type = (
                        state.selected_media.media_type if state.selected_media else ""
                    )
                    result = await client.download_release_candidate(
                        selected_release,
                        save_dir=self.config.download_dir,
                        download_setting=self.config.download_setting,
                        media_type=media_type,
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
            except Exception as exc:
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

    @filter.command("下载电影")
    async def download_movie(self, event: AstrMessageEvent):
        """搜索 NasTool 电影，选择资源后下发下载。

        用法示例：
        - 下载电影 盗梦空间
        - 下载电影 功夫 1080p 粤语
        - 下载电影 Inception 4K
        """
        query = extract_command_query(event.message_str, "下载电影")
        if not query.keyword:
            yield event.plain_result(
                "用法：下载电影 电影名 [分辨率] [语言] [片源]\n\n"
                + "示例：\n"
                + "- 下载电影 盗梦空间\n"
                + "- 下载电影 功夫 1080p 粤语\n"
                + "- 下载电影 Inception 4K BluRay x265"
            )
            return

        query.media_type = "MOV"
        async for result in self._handle_download(event, query, "电影"):
            yield result

    @filter.command("下载电视剧")
    async def download_tv(self, event: AstrMessageEvent):
        """搜索 NasTool 电视剧，选择资源后下发下载。

        用法示例：
        - 下载电视剧 权力的游戏
        - 下载电视剧 黑镜 1080p
        - 下载电视剧 Breaking Bad 4K
        """
        query = extract_command_query(event.message_str, "下载电视剧")
        if not query.keyword:
            yield event.plain_result(
                "用法：下载电视剧 剧集名 [分辨率] [语言] [片源]\n\n"
                + "示例：\n"
                + "- 下载电视剧 权力的游戏\n"
                + "- 下载电视剧 黑镜 1080p 英语\n"
                + "- 下载电视剧 Breaking Bad 4K BluRay"
            )
            return

        query.media_type = "TV"
        async for result in self._handle_download(event, query, "电视剧"):
            yield result

    @filter.command("下载视频")
    async def download_video(self, event: AstrMessageEvent):
        """搜索 NasTool 视频（电影/剧集），选择资源后下发下载。

        用法示例：
        - 下载视频 盗梦空间
        - 下载视频 黑镜 1080p
        - 下载视频 Inception 4K
        """
        query = extract_command_query(event.message_str, "下载视频")
        if not query.keyword:
            yield event.plain_result(
                "用法：下载视频 视频名 [分辨率] [语言] [片源]\n\n"
                + "示例：\n"
                + "- 下载视频 盗梦空间\n"
                + "- 下载视频 权力的游戏 1080p 英语\n"
                + "- 下载视频 Inception 4K BluRay"
            )
            return

        query.media_type = ""
        async for result in self._handle_download(event, query, "视频"):
            yield result
