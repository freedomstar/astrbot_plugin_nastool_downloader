from __future__ import annotations

import asyncio
from typing import Any, Optional
import httpx

from plugin_logic import MediaCandidate, ReleaseCandidate, normalize_media_type


class NasToolApiError(RuntimeError):
    pass


class NasToolClient:
    def __init__(
        self,
        base_url: str,
        *,
        request_timeout: float = 20.0,
        search_timeout: float = 120.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        username: str = "",
        password: str = "",
    ) -> None:
        self.base_url = base_url.strip().rstrip("/")
        self.api_key = ""
        self.token = ""
        self.cookies: dict[str, str] = {}
        self.request_timeout = request_timeout
        self.search_timeout = search_timeout
        self.transport = transport
        self.username = username.strip()
        self.password = password.strip()

    async def search_media(self, keyword: str) -> list[MediaCandidate]:
        payload = await self._post_json("/api/v1/media/search", {"keyword": keyword})
        results = payload.get("data", {}).get("result", [])
        medias: list[MediaCandidate] = []
        for item in results:
            medias.append(
                MediaCandidate(
                    title=str(
                        item.get("title")
                        or item.get("cn_name")
                        or item.get("en_name")
                        or "未知标题"
                    ),
                    year=str(item.get("year") or ""),
                    media_type=normalize_media_type(
                        str(item.get("type") or item.get("media_type") or "")
                    ),
                    label=str(item.get("type") or item.get("media_type") or "未知类型"),
                    tmdb_id=str(item.get("tmdb_id") or item.get("tmdbid") or ""),
                    douban_id=str(item.get("douban_id") or item.get("doubanid") or ""),
                    overview=str(item.get("overview") or ""),
                    original_title=str(
                        item.get("original_title") or item.get("org_string") or ""
                    ),
                    english_title=str(item.get("en_name") or ""),
                    score=str(item.get("vote") or ""),
                    release_date=str(item.get("release_date") or ""),
                    original_language=str(item.get("original_language") or ""),
                    detail_link=str(item.get("link") or ""),
                )
            )
        return medias

    async def search_releases_for_media(
        self,
        media: MediaCandidate,
        *,
        poll_interval: float = 2.0,
        max_polls: int = 15,
    ) -> list[ReleaseCandidate]:
        search_word = media.original_title or media.english_title or media.title
        request_data = {
            "search_word": search_word,
            "tmdbid": media.tmdb_id,
            "media_type": media.label,
            "unident": 1,
        }
        try:
            await self._post_json(
                "/api/v1/search/keyword", request_data, timeout=self.search_timeout
            )
        except httpx.ReadTimeout:
            pass

        for attempt in range(max_polls):
            payload = await self._post_json("/api/v1/search/result", {})
            releases = self._extract_matching_releases(payload, media)
            if releases:
                return releases
            if attempt < max_polls - 1:
                await asyncio.sleep(poll_interval)
        return []

    async def download_release(
        self,
        release_id: str,
        *,
        save_dir: str = "",
        download_setting: str = "",
    ) -> dict[str, Any]:
        data = {"id": release_id}
        if save_dir:
            data["dir"] = save_dir
        if download_setting:
            data["setting"] = download_setting
        return await self._post_json("/api/v1/download/search", data)

    async def download_release_candidate(
        self,
        release: ReleaseCandidate,
        *,
        save_dir: str = "",
        download_setting: str = "",
    ) -> dict[str, Any]:
        try:
            return await self.download_release(
                release.release_id,
                save_dir=save_dir,
                download_setting=download_setting,
            )
        except (httpx.HTTPStatusError, NasToolApiError):
            try:
                return await self._download_via_nastool_item(release, save_dir=save_dir)
            except (httpx.HTTPStatusError, NasToolApiError):
                return await self._download_via_qbittorrent(release, save_dir=save_dir)

    async def get_current_downloads(self) -> dict[str, Any]:
        return await self._post_json("/api/v1/download/now", {})

    async def remove_download(self, download_id: str) -> dict[str, Any]:
        return await self._post_json("/api/v1/download/remove", {"id": download_id})

    async def get_download_history(self, page: int = 1) -> dict[str, Any]:
        return await self._post_json("/api/v1/download/history", {"page": str(page)})

    async def login_with_credentials(self) -> dict[str, Any]:
        """使用账号密码登录 NasTool 并获取 API Key。

        如果 username 和 password 已配置，尝试登录获取新的 API Key。
        登录成功后更新 self.api_key。

        Returns:
            dict: 包含 success 和 api_key 的字典
        """
        if not self.username or not self.password:
            raise NasToolApiError(
                "未配置账号密码，请先在插件设置中填写 username 和 password"
            )

        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.request_timeout,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    "/api/v1/user/login",
                    data={"username": self.username, "password": self.password},
                )
                response.raise_for_status()
                payload = response.json()

                if payload.get("code") not in {0, "0", None}:
                    error_msg = str(payload.get("message") or "登录失败")
                    raise NasToolApiError(f"登录失败：{error_msg}")

                data = payload.get("data", {})

                api_key = ""
                token = ""
                if isinstance(data, dict):
                    api_key = data.get("apikey") or data.get("api_key") or ""
                    token = data.get("token") or ""

                if not token and not api_key:
                    raise NasToolApiError(
                        f"登录成功但未获取到认证信息，data={data}, payload={payload}"
                    )

                self.api_key = api_key
                self.token = token
                self.cookies = dict(client.cookies)
                return {
                    "success": True,
                    "api_key": api_key,
                    "token": token,
                    "message": "登录成功",
                }

        except httpx.HTTPStatusError as exc:
            raise NasToolApiError(f"HTTP 错误 {exc.response.status_code}: {exc}")
        except NasToolApiError:
            raise
        except Exception as exc:
            raise NasToolApiError(f"登录失败：{exc}")

    async def verify_connection(self) -> dict[str, Any]:
        """验证与 NasTool 的连接是否有效。

        通过调用 /api/v1/media/search 接口并传入空关键词来验证 API Key 是否有效。
        如果认证失败，会抛出 NasToolApiError 异常。
        """
        try:
            # 使用空关键词测试连接，验证 API Key 是否有效
            result = await self._post_json(
                "/api/v1/media/search", {"keyword": "test_connection"}, timeout=10.0
            )
            return {"success": True, "message": "登录成功，NasTool 连接正常"}
        except NasToolApiError as exc:
            # 认证错误已经在 _post_json 中处理，这里直接向上抛出
            raise exc
        except Exception as exc:
            raise NasToolApiError(f"连接验证失败：{exc}")

    async def _download_via_nastool_item(
        self,
        release: ReleaseCandidate,
        *,
        save_dir: str = "",
    ) -> dict[str, Any]:
        data = {
            "enclosure": release.enclosure,
            "title": release.title,
            "site": release.site,
            "description": release.description,
            "page_url": release.page_url,
            "size": release.size,
            "seeders": str(release.seeders),
        }
        if save_dir:
            data["dl_dir"] = save_dir
        return await self._post_json("/api/v1/download/item", data)

    async def _download_via_qbittorrent(
        self,
        release: ReleaseCandidate,
        *,
        save_dir: str = "",
    ) -> dict[str, Any]:
        clients = await self._post_json("/api/v1/download/client/list", {})
        detail = clients.get("data", {}).get("detail", {})
        if not isinstance(detail, dict):
            raise NasToolApiError("未获取到 NasTool 下载器配置")

        downloader = None
        for item in detail.values():
            if not isinstance(item, dict):
                continue
            if int(item.get("enabled") or 0) != 1:
                continue
            if str(item.get("type") or "") != "qbittorrent":
                continue
            downloader = item
            break

        if downloader is None:
            raise NasToolApiError("未找到已启用的 qBittorrent 下载器")

        config = downloader.get("config", {})
        if not isinstance(config, dict):
            raise NasToolApiError("qBittorrent 配置格式无效")

        host = str(config.get("host") or "").rstrip("/")
        port = str(config.get("port") or "")
        username = str(config.get("username") or "")
        password = str(config.get("password") or "")
        if not host or not username or not password:
            raise NasToolApiError("qBittorrent 配置不完整")

        qb_url = host if host.endswith(f":{port}") or not port else f"{host}:{port}"
        target_save_dir = save_dir or self._pick_qb_save_path(config)

        async with httpx.AsyncClient(
            base_url=qb_url, timeout=self.request_timeout
        ) as client:
            login = await client.post(
                "/api/v2/auth/login",
                data={"username": username, "password": password},
            )
            login.raise_for_status()
            add_data = {"urls": release.enclosure}
            if target_save_dir:
                add_data["savepath"] = target_save_dir
            add = await client.post("/api/v2/torrents/add", data=add_data)
            add.raise_for_status()

        return {
            "code": 0,
            "success": True,
            "message": "submitted via qbittorrent fallback",
            "data": {"target": "qbittorrent", "save_path": target_save_dir},
        }

    async def _post_json(
        self,
        path: str,
        data: dict[str, Any],
        *,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        client_timeout = timeout if timeout is not None else self.request_timeout
        try:
            headers: dict[str, str] = {}
            auth_value = self.api_key or self.token
            if auth_value:
                headers["Authorization"] = auth_value

            async with httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                cookies=self.cookies,
                transport=self.transport,
                timeout=client_timeout,
            ) as client:
                response = await client.post(path, data=data)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                token_preview = self.token[:10] + "..." if self.token else "(空)"
                api_key_preview = self.api_key[:10] + "..." if self.api_key else "(空)"
                raise NasToolApiError(
                    self._format_auth_error(
                        f"安全认证未通过 (HTTP 401)，path={path}, token={token_preview}, api_key={api_key_preview}"
                    )
                )
            raise NasToolApiError(f"HTTP 错误 {exc.response.status_code}: {exc}")

        payload = response.json()
        if payload.get("code") not in {0, "0", None}:
            error_msg = str(payload.get("message") or "NasTool API 请求失败")
            if self._is_auth_error(error_msg):
                error_msg = self._format_auth_error(error_msg)
            raise NasToolApiError(error_msg)
        if payload.get("success") is False:
            error_msg = str(payload.get("message") or "NasTool API 请求失败")
            if self._is_auth_error(error_msg):
                error_msg = self._format_auth_error(error_msg)
            raise NasToolApiError(error_msg)
        return payload

    def _is_auth_error(self, error_msg: str) -> bool:
        """检查是否为认证错误"""
        auth_keywords = [
            "安全认证未通过",
            "token",
            "认证",
            "api key",
            "apikey",
            "unauthorized",
            "unauthenticated",
            "invalid key",
            "access denied",
        ]
        error_lower = error_msg.lower()
        return any(keyword in error_lower for keyword in auth_keywords)

    def _format_auth_error(self, error_msg: str) -> str:
        """格式化认证错误消息，提供解决建议"""
        return (
            f"{error_msg}\n\n"
            "解决建议：\n"
            "1. 检查 NasTool 登录账号和密码是否正确\n"
            "2. 确认 NasTool 服务版本支持 `/api/v1/user/login` 返回 token\n"
            "3. 确认 NasTool 服务正在运行且网络可访问\n"
            "4. 如网页 API 页可用但插件不可用，请检查 Authorization 认证方式是否被代理改写"
        )

    def _extract_matching_releases(
        self,
        payload: dict[str, Any],
        media: MediaCandidate,
    ) -> list[ReleaseCandidate]:
        raw_results = payload.get("data", {}).get("result", {})
        if not isinstance(raw_results, dict):
            return []

        matches: list[ReleaseCandidate] = []
        for key, entry in raw_results.items():
            if not isinstance(entry, dict):
                continue
            if not self._matches_media(entry, media, str(key)):
                continue
            matches.extend(self._flatten_torrents(entry, media))

        deduped: dict[str, ReleaseCandidate] = {}
        for item in matches:
            deduped[item.release_id] = item
        return sorted(deduped.values(), key=lambda item: item.seeders, reverse=True)

    def _matches_media(
        self, entry: dict[str, Any], media: MediaCandidate, key: str
    ) -> bool:
        tmdb_id = str(entry.get("tmdbid") or entry.get("tmdb_id") or "").strip()
        if media.tmdb_id and tmdb_id and media.tmdb_id == tmdb_id:
            return True

        entry_title = self._normalize_text(str(entry.get("title") or key))
        targets = [
            self._normalize_text(media.title),
            self._normalize_text(media.original_title),
            self._normalize_text(media.english_title),
        ]
        return any(
            target and target in entry_title for target in dict.fromkeys(targets)
        )

    def _flatten_torrents(
        self,
        entry: dict[str, Any],
        media: MediaCandidate,
    ) -> list[ReleaseCandidate]:
        torrent_dict = entry.get("torrent_dict", {})
        releases: list[ReleaseCandidate] = []

        for media_bucket in self._iter_bucket_values(torrent_dict):
            for group in self._iter_bucket_values(media_bucket):
                if not isinstance(group, dict):
                    continue
                group_info = group.get("group_info", {})
                resolution = str(group_info.get("respix") or "")
                resource_type = str(group_info.get("restype") or "")
                group_torrents = group.get("group_torrents", {})
                for torrent_group in self._iter_bucket_values(group_torrents):
                    if not isinstance(torrent_group, dict):
                        continue
                    torrent_list = torrent_group.get("torrent_list", [])
                    if not isinstance(torrent_list, list):
                        continue
                    for torrent in torrent_list:
                        if not isinstance(torrent, dict):
                            continue
                        if not self._torrent_matches_media(torrent, media):
                            continue
                        release_id = str(torrent.get("id") or "")
                        if not release_id:
                            continue
                        releases.append(
                            ReleaseCandidate(
                                release_id=release_id,
                                title=str(
                                    torrent.get("torrent_name")
                                    or torrent.get("title")
                                    or "未知资源"
                                ),
                                site=str(torrent.get("site") or ""),
                                size=str(torrent.get("size") or ""),
                                seeders=int(torrent.get("seeders") or 0),
                                enclosure=str(torrent.get("enclosure") or ""),
                                page_url=str(
                                    torrent.get("pageurl")
                                    or torrent.get("page_url")
                                    or ""
                                ),
                                resolution=resolution,
                                resource_type=resource_type,
                                description=str(torrent.get("description") or ""),
                            )
                        )
        return releases

    def _torrent_matches_media(
        self,
        torrent: dict[str, Any],
        media: MediaCandidate,
    ) -> bool:
        haystack = self._normalize_text(
            " ".join(
                [
                    str(torrent.get("torrent_name") or ""),
                    str(torrent.get("description") or ""),
                    str(torrent.get("pageurl") or torrent.get("page_url") or ""),
                ]
            )
        )
        keywords = [
            self._normalize_text(media.title),
            self._normalize_text(media.original_title),
            self._normalize_text(media.english_title),
        ]
        return any(
            keyword and keyword in haystack for keyword in dict.fromkeys(keywords)
        )

    def _iter_bucket_values(self, value: Any) -> list[Any]:
        if isinstance(value, dict):
            return list(value.values())
        if isinstance(value, list):
            values: list[Any] = []
            for item in value:
                if isinstance(item, list) and len(item) == 2:
                    values.append(item[1])
                else:
                    values.append(item)
            return values
        return []

    def _normalize_text(self, value: str) -> str:
        return "".join(ch for ch in value.lower() if ch.isalnum())

    def _pick_qb_save_path(self, config: dict[str, Any]) -> str:
        raw_paths = config.get("download_dir", [])
        if not isinstance(raw_paths, list):
            return ""
        for item in raw_paths:
            if isinstance(item, dict) and item.get("save_path"):
                return str(item["save_path"])
        return ""
