from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import re


CANCEL_WORDS = {"q", "quit", "cancel", "取消", "退出"}


@dataclass(slots=True)
class MediaCandidate:
    title: str
    year: str
    media_type: str
    label: str
    tmdb_id: str
    douban_id: str
    overview: str
    original_title: str = ""
    english_title: str = ""
    score: str = ""
    release_date: str = ""
    original_language: str = ""
    detail_link: str = ""


@dataclass(slots=True)
class ReleaseCandidate:
    release_id: str
    title: str
    site: str
    size: str
    seeders: int
    enclosure: str
    page_url: str
    resolution: str
    resource_type: str
    description: str = ""


@dataclass(slots=True)
class ConversationState:
    medias: list[MediaCandidate] = field(default_factory=list)
    selected_media: Optional[MediaCandidate] = None
    releases: list[ReleaseCandidate] = field(default_factory=list)
    search_query: Optional["SearchQuery"] = None


@dataclass(slots=True)
class SearchQuery:
    """解析后的搜索查询"""

    keyword: str
    resolution: str = ""  # 1080p, 4K, 2160p, etc.
    language: str = ""  # 粤语, 英语, 国语, etc.
    source: str = ""  # BluRay, WEB-DL, HDRip, etc.
    codec: str = ""  # x264, x265, HEVC, etc.
    group: str = ""  # 压制组
    skip_auto_download: bool = False  # 是否跳过自动下载，直接显示资源列表
    media_type: str = ""  # MOV, TV, 表示媒体类型
    resolution: str = ""  # 1080p, 4K, 2160p, etc.
    language: str = ""  # 粤语, 英语, 国语, etc.
    source: str = ""  # BluRay, WEB-DL, HDRip, etc.
    codec: str = ""  # x264, x265, HEVC, etc.
    group: str = ""  # 压制组

    def has_filters(self) -> bool:
        """是否有额外的过滤条件"""
        return bool(
            self.resolution or self.language or self.source or self.codec or self.group
        )

    def get_display_text(self) -> str:
        """获取用于显示的查询描述"""
        parts = [self.keyword]
        if self.resolution:
            parts.append(self.resolution)
        if self.language:
            parts.append(self.language)
        if self.source:
            parts.append(self.source)
        if self.codec:
            parts.append(self.codec)
        return " ".join(parts)


def normalize_media_type(raw_value: str) -> str:
    value = (raw_value or "").strip().upper()
    if value in {"MOV", "MOVIE", "电影"}:
        return "MOV"
    if value in {"TV", "SERIES", "电视剧"}:
        return "TV"
    return "MOV"


def extract_command_query(message_text: str, command_prefix: str = "") -> SearchQuery:
    """解析用户输入，提取搜索关键词和过滤条件

    Args:
        message_text: 用户输入的消息文本
        command_prefix: 命令前缀，如 "下载电影"、"下载电视剧"、"下载视频"

    示例：
    - "下载电影 功夫" -> SearchQuery(keyword="功夫")
    - "下载电视剧 权力的游戏" -> SearchQuery(keyword="权力的游戏")
    - "下载视频 功夫 1080p 粤语" -> SearchQuery(keyword="功夫", resolution="1080p", language="粤语")
    - "下载电影 Inception 4K BluRay" -> SearchQuery(keyword="Inception", resolution="4K", source="BluRay")
    """
    text = (message_text or "").strip()
    if not text:
        return SearchQuery(keyword="")

    # 移除触发词前缀
    # 支持多种命令前缀：下载电影、下载电视剧、下载视频、下载
    prefixes = [
        "下载电影",
        "/下载电影",
        "下载电视剧",
        "/下载电视剧",
        "下载视频",
        "/下载视频",
        "下载",
        "/下载",
    ]

    # 如果指定了特定的命令前缀，优先使用
    if command_prefix:
        specific_prefixes = [command_prefix, f"/{command_prefix}"]
        for prefix in specific_prefixes:
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix) :].strip()
                break
    else:
        # 否则尝试所有已知前缀
        for prefix in prefixes:
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix) :].strip()
                break

    if not text:
        return SearchQuery(keyword="")

    # 解析过滤条件
    query = SearchQuery(keyword=text)
    query = _parse_filters(query)

    return query


def _parse_filters(query: SearchQuery) -> SearchQuery:
    """从关键词中提取过滤条件"""
    text = query.keyword
    text_lower = text.lower()

    # 检测"不自动下载"相关关键字
    skip_auto_patterns = [
        r"不自动下载",
        r"不要自动下载",
        r"别自动下载",
        r"手动选择",
        r"手动下载",
        r"自己选",
        r"手动挑",
    ]
    for pattern in skip_auto_patterns:
        if re.search(pattern, text_lower):
            query.skip_auto_download = True
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
            text_lower = text.lower()
            break

    # 分辨率匹配模式
    resolution_patterns = [
        (r"\b(4k|2160p|uhd)\b", "4K"),
        (r"\b(1080p|fhd)\b", "1080p"),
        (r"\b(720p|hd)\b", "720p"),
        (r"\b(480p|sd)\b", "480p"),
    ]

    # 语言匹配模式
    language_patterns = [
        (r"\b(粤语|粤配|cantonese)\b", "粤语"),
        (r"\b(国语|国配|mandarin|chinese)\b", "国语"),
        (r"\b(英语|英配|english)\b", "英语"),
        (r"\b(日语|日配|japanese)\b", "日语"),
        (r"\b(韩语|韩配|korean)\b", "韩语"),
    ]

    # 片源匹配模式
    source_patterns = [
        (r"\b(blu-?ray|bdrip|brrip|蓝光)\b", "BluRay"),
        (r"\b(web-?dl|webdl)\b", "WEB-DL"),
        (r"\b(web-?rip|webrip)\b", "WEBRip"),
        (r"\b(hdrip|hd-rip)\b", "HDRip"),
        (r"\b(dvdrip|dvd-rip)\b", "DVDRip"),
        (r"\b(hdtv|hd-tv)\b", "HDTV"),
        (r"\b(remux)\b", "Remux"),
    ]

    # 编码格式匹配模式
    codec_patterns = [
        (r"\b(x265|hevc|h265)\b", "x265"),
        (r"\b(x264|h264|avc)\b", "x264"),
        (r"\b(av1)\b", "AV1"),
        (r"\b(vp9)\b", "VP9"),
    ]

    # 提取分辨率
    for pattern, value in resolution_patterns:
        if re.search(pattern, text_lower):
            query.resolution = value
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
            text_lower = text.lower()
            break

    # 提取语言
    for pattern, value in language_patterns:
        if re.search(pattern, text_lower):
            query.language = value
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
            text_lower = text.lower()
            break

    # 提取片源
    for pattern, value in source_patterns:
        if re.search(pattern, text_lower):
            query.source = value
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
            text_lower = text.lower()
            break

    # 提取编码
    for pattern, value in codec_patterns:
        if re.search(pattern, text_lower):
            query.codec = value
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
            text_lower = text.lower()
            break

    # 清理多余空格，剩余文本作为关键词
    query.keyword = " ".join(text.split())

    return query


def filter_releases_by_query(
    releases: list[ReleaseCandidate], query: SearchQuery
) -> list[ReleaseCandidate]:
    """根据搜索查询过滤资源列表"""
    if not query.has_filters():
        return releases

    filtered = []
    for release in releases:
        # 检查分辨率
        if query.resolution and query.resolution.lower() not in release.title.lower():
            # 特殊处理：4K 可能写作 2160p
            if query.resolution == "4K" and "2160p" in release.title.lower():
                pass  # 匹配成功
            elif query.resolution == "1080p" and (
                "1080" in release.title or "fhd" in release.title.lower()
            ):
                pass  # 匹配成功
            else:
                continue

        # 检查语言（在标题或描述中）
        if query.language:
            haystack = (release.title + " " + release.description).lower()
            language_keywords = {
                "粤语": ["粤语", "粤配", "cantonese", "yue"],
                "国语": ["国语", "国配", "mandarin", "国语中字"],
                "英语": ["英语", "英配", "english", "eng"],
                "日语": ["日语", "日配", "japanese", "jpn"],
                "韩语": ["韩语", "韩配", "korean", "kor"],
            }
            keywords = language_keywords.get(query.language, [query.language.lower()])
            if not any(kw in haystack for kw in keywords):
                continue

        # 检查片源
        if query.source:
            haystack = (release.title + " " + release.resource_type).lower()
            source_keywords = {
                "BluRay": ["blu-ray", "bluray", "bdrip", "brrip", "蓝光"],
                "WEB-DL": ["web-dl", "webdl"],
                "WEBRip": ["web-rip", "webrip"],
                "HDRip": ["hd-rip", "hdrip"],
                "Remux": ["remux"],
            }
            keywords = source_keywords.get(query.source, [query.source.lower()])
            if not any(kw in haystack for kw in keywords):
                continue

        # 检查编码
        if query.codec:
            haystack = release.title.lower()
            codec_keywords = {
                "x265": ["x265", "hevc", "h265", "h.265"],
                "x264": ["x264", "h264", "h.264", "avc"],
                "AV1": ["av1"],
                "VP9": ["vp9"],
            }
            keywords = codec_keywords.get(query.codec, [query.codec.lower()])
            if not any(kw in haystack for kw in keywords):
                continue

        filtered.append(release)

    return filtered


def pick_best_release(
    releases: list[ReleaseCandidate],
    *,
    return_top_n: int | None = None,
) -> Optional[ReleaseCandidate] | list[ReleaseCandidate]:
    """选择最佳资源。

    Args:
        releases: 资源列表
        return_top_n: 如果指定，返回前N个最佳资源而不是单个

    Returns:
        单个最佳资源，或前N个资源的列表
    """
    valid_releases = [
        release for release in releases if _has_non_zero_size(release.size)
    ]
    if not valid_releases:
        return [] if return_top_n else None

    # 按做种数降序排序
    sorted_releases = sorted(
        valid_releases, key=lambda release: release.seeders, reverse=True
    )

    if return_top_n:
        return sorted_releases[:return_top_n]
    return sorted_releases[0]


def _has_non_zero_size(size_text: str) -> bool:
    text = (size_text or "").strip().upper()
    if not text:
        return False
    if text in {"0", "0B", "0KB", "0MB", "0GB", "0TB"}:
        return False
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return False
    try:
        return float(match.group(1)) > 0
    except ValueError:
        return False


def parse_choice(raw_text: str, max_count: int) -> Optional[int]:
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("请输入编号。")
    if text.lower() in CANCEL_WORDS:
        return None
    if not text.isdigit():
        raise ValueError("请输入有效的编号，或回复“取消”。")

    index = int(text) - 1
    if index < 0 or index >= max_count:
        raise ValueError(f"编号超出范围，请输入 1 到 {max_count}。")
    return index


def build_media_choices_message(query: SearchQuery, state: ConversationState) -> str:
    display_text = query.get_display_text()
    lines = [f"搜索到以下媒体候选：{display_text}"]
    for idx, media in enumerate(state.medias, start=1):
        title_line = f"{idx}. {media.title} ({media.year or '未知年份'})"
        detail_parts = [media.label]
        if media.tmdb_id:
            detail_parts.append(f"TMDB: {media.tmdb_id}")
        if media.douban_id and media.douban_id != "0":
            detail_parts.append(f"豆瓣: {media.douban_id}")
        lines.append(f"{title_line}\n   {' | '.join(detail_parts)}")
        extra_parts = []
        if media.original_title or media.english_title:
            extra_parts.append(f"原名: {media.original_title or media.english_title}")
        if media.score:
            extra_parts.append(f"评分: {media.score}")
        if media.release_date:
            extra_parts.append(f"上映: {media.release_date}")
        if media.original_language:
            extra_parts.append(f"语言: {media.original_language}")
        if extra_parts:
            lines.append(f"   {' | '.join(extra_parts)}")
        if media.overview:
            overview = media.overview[:80] + ("..." if len(media.overview) > 80 else "")
            lines.append(f"   简介: {overview}")
        if media.detail_link:
            lines.append(f"   详情: {media.detail_link}")
    lines.append("请直接回复上面的编号继续，不用再输入“下载电影”。")
    lines.append("回复“取消”可结束当前流程。")
    return "\n".join(lines)


def build_release_choices_message(state: ConversationState) -> str:
    if state.selected_media is None:
        raise ValueError("selected_media is required")

    lines = [
        f"已选择媒体：{state.selected_media.title} ({state.selected_media.year or '未知年份'})"
    ]

    # 如果有过滤条件或跳过了自动下载，显示相应信息
    if state.search_query and state.search_query.skip_auto_download:
        lines.append("📋 已启用手动选择模式，为您展示按做种数排序的资源列表：")
    elif state.search_query and state.search_query.has_filters():
        filters = []
        if state.search_query.resolution:
            filters.append(f"分辨率：{state.search_query.resolution}")
        if state.search_query.language:
            filters.append(f"语言：{state.search_query.language}")
        if state.search_query.source:
            filters.append(f"片源：{state.search_query.source}")
        if state.search_query.codec:
            filters.append(f"编码：{state.search_query.codec}")
        if filters:
            lines.append(f"筛选条件：{' | '.join(filters)}")
        lines.append("找到以下资源：")
    else:
        lines.append("找到以下资源：")

    for idx, release in enumerate(state.releases, start=1):
        lines.append(
            f"{idx}. {release.title}\n   站点: {release.site or '未知'} | 大小: {release.size or '未知'} | 做种: {release.seeders} | 规格: {release.resolution or '未知'} {release.resource_type or ''}".rstrip()
        )
    lines.append('请直接回复资源编号开始下载，不用再输入"下载"。')
    lines.append('回复"取消"可结束当前流程。')
    return "\n".join(lines)


def build_fallback_releases_message(
    state: ConversationState, query: SearchQuery | None
) -> str:
    """构建备选资源列表消息（当过滤条件过严时使用）。"""
    if state.selected_media is None:
        raise ValueError("selected_media is required")

    lines = [
        f"已选择媒体：{state.selected_media.title} ({state.selected_media.year or '未知年份'})",
        "",
    ]

    # 显示过滤条件信息
    if query and query.has_filters():
        filters = []
        if query.resolution:
            filters.append(f"分辨率：{query.resolution}")
        if query.language:
            filters.append(f"语言：{query.language}")
        if query.source:
            filters.append(f"片源：{query.source}")
        if query.codec:
            filters.append(f"编码：{query.codec}")
        if filters:
            lines.append(f"筛选条件：{' | '.join(filters)}")
            lines.append("⚠️ 未找到符合筛选条件的资源，为您展示所有可用资源：")
    else:
        lines.append("未找到符合要求的资源，为您展示所有可用资源：")

    lines.append("")

    for idx, release in enumerate(state.releases, start=1):
        lines.append(
            f"{idx}. {release.title}\n   站点: {release.site or '未知'} | 大小: {release.size or '未知'} | 做种: {release.seeders} | 规格: {release.resolution or '未知'} {release.resource_type or ''}".rstrip()
        )

    lines.append("")
    lines.append("⚠️ 这些资源可能不符合您要求的筛选条件，但仍可下载。")
    lines.append("请直接回复资源编号开始下载，或回复“取消”结束流程。")

    return "\n".join(lines)
