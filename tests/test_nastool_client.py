import unittest
from unittest.mock import AsyncMock, patch

import httpx

from nastool_client import NasToolApiError, NasToolClient
from plugin_logic import MediaCandidate, ReleaseCandidate


class NasToolClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_media_returns_candidates(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["Authorization"], "token-123")
            self.assertNotIn("apikey=", str(request.url))
            self.assertEqual(request.url.path, "/api/v1/media/search")
            body = request.content.decode("utf-8")
            self.assertIn("keyword=%E7%9B%97%E6%A2%A6%E7%A9%BA%E9%97%B4", body)
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "success": True,
                    "data": {
                        "result": [
                            {
                                "title": "盗梦空间",
                                "year": "2010",
                                "type": "电影",
                                "tmdb_id": 27205,
                                "douban_id": 0,
                                "overview": "dreams",
                            },
                            {
                                "title": "Bikini Inception",
                                "year": "2015",
                                "type": "电影",
                                "tmdb_id": 542438,
                                "douban_id": 0,
                                "overview": "other",
                            },
                        ]
                    },
                },
            )

        client = NasToolClient(
            base_url="http://nastool.local",
            transport=httpx.MockTransport(handler),
        )
        client.api_key = "token-123"

        results = await client.search_media("盗梦空间")

        self.assertEqual(
            [item.title for item in results], ["盗梦空间", "Bikini Inception"]
        )
        self.assertEqual(results[0].tmdb_id, "27205")
        self.assertEqual(results[0].media_type, "MOV")
        self.assertEqual(results[0].score, "")

    async def test_search_media_strips_whitespace_from_auth_inputs(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["Authorization"], "token-123")
            self.assertNotIn("apikey=", str(request.url))
            return httpx.Response(
                200,
                json={"code": 0, "success": True, "data": {"result": []}},
            )

        client = NasToolClient(
            base_url="  http://nastool.local/ \n",
            transport=httpx.MockTransport(handler),
        )
        client.api_key = "token-123"

        results = await client.search_media("盗梦空间")

        self.assertEqual(results, [])

    async def test_login_with_credentials_stores_token_and_api_key(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/api/v1/user/login")
            self.assertIn("username=tester", request.content.decode("utf-8"))
            self.assertIn("password=secret", request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "success": True,
                    "data": {
                        "token": "jwt-token-123",
                        "apikey": "api-key-123",
                    },
                },
            )

        client = NasToolClient(
            base_url="http://nastool.local",
            transport=httpx.MockTransport(handler),
            username="tester",
            password="secret",
        )

        result = await client.login_with_credentials()

        self.assertEqual(result["token"], "jwt-token-123")
        self.assertEqual(result["api_key"], "api-key-123")
        self.assertEqual(client.token, "jwt-token-123")
        self.assertEqual(client.api_key, "api-key-123")

    async def test_login_preserves_session_cookie_for_followup_requests(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/v1/user/login":
                return httpx.Response(
                    200,
                    headers={"set-cookie": "session=abc123; Path=/; HttpOnly"},
                    json={
                        "code": 0,
                        "success": True,
                        "data": {
                            "token": "jwt-token-123",
                            "apikey": "api-key-123",
                        },
                    },
                )

            self.assertEqual(request.url.path, "/api/v1/media/search")
            self.assertEqual(request.headers["Authorization"], "api-key-123")
            self.assertIn("session=abc123", request.headers.get("Cookie", ""))
            return httpx.Response(
                200,
                json={"code": 0, "success": True, "data": {"result": []}},
            )

        client = NasToolClient(
            base_url="http://nastool.local",
            transport=httpx.MockTransport(handler),
            username="tester",
            password="secret",
        )

        await client.login_with_credentials()
        results = await client.search_media("盗梦空间")

        self.assertEqual(results, [])

    async def test_search_releases_polls_results_after_search_timeout(self) -> None:
        media = MediaCandidate(
            title="盗梦空间",
            year="2010",
            media_type="MOV",
            label="电影",
            tmdb_id="27205",
            douban_id="0",
            overview="dreams",
            original_title="Inception",
            english_title="Inception",
        )
        calls = {"search_result": 0}

        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/v1/search/keyword":
                raise httpx.ReadTimeout("search still running")
            if request.url.path == "/api/v1/search/result":
                calls["search_result"] += 1
                if calls["search_result"] == 1:
                    return httpx.Response(
                        200, json={"code": 0, "success": True, "data": {"result": {}}}
                    )
                return httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "success": True,
                        "data": {
                            "result": {
                                "盗梦空间 (2010)": {
                                    "title": "盗梦空间",
                                    "year": "2010",
                                    "type": "电影",
                                    "tmdbid": "27205",
                                    "torrent_dict": [
                                        [
                                            "MOV",
                                            {
                                                "1080p_bluray": {
                                                    "group_info": {
                                                        "respix": "1080p",
                                                        "restype": "BluRay",
                                                    },
                                                    "group_torrents": {
                                                        "1080p_bluray___123": {
                                                            "torrent_list": [
                                                                {
                                                                    "id": 987,
                                                                    "site": "PTSite",
                                                                    "torrent_name": "Inception.2010.1080p.BluRay.x265",
                                                                    "size": "12.3GB",
                                                                    "seeders": 88,
                                                                    "enclosure": "magnet:?xt=urn:btih:123",
                                                                    "pageurl": "https://example.invalid/details/987",
                                                                }
                                                            ]
                                                        }
                                                    },
                                                }
                                            },
                                        ]
                                    ],
                                }
                            }
                        },
                    },
                )
            raise AssertionError(f"unexpected path: {request.url.path}")

        client = NasToolClient(
            base_url="http://nastool.local",
            transport=httpx.MockTransport(handler),
        )

        releases = await client.search_releases_for_media(
            media, poll_interval=0, max_polls=2
        )

        self.assertEqual(len(releases), 1)
        self.assertEqual(releases[0].release_id, "987")
        self.assertEqual(releases[0].site, "PTSite")
        self.assertEqual(releases[0].resolution, "1080p")
        self.assertEqual(calls["search_result"], 2)

    async def test_search_media_maps_detailed_fields(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "success": True,
                    "data": {
                        "result": [
                            {
                                "title": "功夫",
                                "year": "2004",
                                "type": "电影",
                                "tmdb_id": 9470,
                                "douban_id": 1291543,
                                "overview": "Long overview text",
                                "original_title": "功夫",
                                "en_name": "Kung Fu Hustle",
                                "vote": 7.5,
                                "release_date": "2004-02-10",
                                "original_language": "cn",
                                "link": "https://www.themoviedb.org/movie/9470",
                            }
                        ]
                    },
                },
            )

        client = NasToolClient(
            base_url="http://nastool.local",
            transport=httpx.MockTransport(handler),
        )

        results = await client.search_media("功夫")

        self.assertEqual(results[0].score, "7.5")
        self.assertEqual(results[0].release_date, "2004-02-10")
        self.assertEqual(results[0].original_language, "cn")
        self.assertEqual(
            results[0].detail_link, "https://www.themoviedb.org/movie/9470"
        )

    async def test_download_release_posts_release_id(self) -> None:
        seen = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            seen["path"] = request.url.path
            seen["body"] = request.content.decode("utf-8")
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "success": True,
                    "message": "ok",
                    "data": {"id": "task-1"},
                },
            )

        client = NasToolClient(
            base_url="http://nastool.local",
            transport=httpx.MockTransport(handler),
        )

        response = await client.download_release(
            "987", save_dir="/movies", download_setting="qb"
        )

        self.assertEqual(seen["path"], "/api/v1/download/search")
        self.assertIn("id=987", seen["body"])
        self.assertIn("dir=%2Fmovies", seen["body"])
        self.assertIn("setting=qb", seen["body"])
        self.assertEqual(response["data"]["id"], "task-1")

    async def test_download_candidate_falls_back_to_download_item(self) -> None:
        calls = []

        async def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.url.path, request.content.decode("utf-8")))
            if request.url.path == "/api/v1/download/search":
                return httpx.Response(500, text="boom")
            if request.url.path == "/api/v1/download/item":
                return httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "success": True,
                        "message": "ok",
                        "data": {"id": "task-2"},
                    },
                )
            raise AssertionError(f"unexpected path: {request.url.path}")

        client = NasToolClient(
            base_url="http://nastool.local",
            transport=httpx.MockTransport(handler),
        )
        release = ReleaseCandidate(
            release_id="987",
            title="Inception.2010.1080p.BluRay.x265",
            site="PTSite",
            size="12.3GB",
            seeders=88,
            enclosure="magnet:?xt=urn:btih:123",
            page_url="https://example.invalid/details/987",
            resolution="1080p",
            resource_type="BluRay",
        )

        response = await client.download_release_candidate(release, save_dir="/movies")

        self.assertEqual(calls[0][0], "/api/v1/download/search")
        self.assertEqual(calls[1][0], "/api/v1/download/item")
        self.assertIn("enclosure=magnet%3A%3Fxt%3Durn%3Abtih%3A123", calls[1][1])
        self.assertEqual(response["data"]["id"], "task-2")

    async def test_download_candidate_falls_back_to_qbittorrent(self) -> None:
        client = NasToolClient(base_url="http://nastool.local")
        client.api_key = "token-123"
        release = ReleaseCandidate(
            release_id="987",
            title="Inception.2010.1080p.BluRay.x265",
            site="PTSite",
            size="12.3GB",
            seeders=88,
            enclosure="magnet:?xt=urn:btih:123",
            page_url="https://example.invalid/details/987",
            resolution="1080p",
            resource_type="BluRay",
        )

        http_error = httpx.HTTPStatusError(
            "boom",
            request=httpx.Request(
                "POST", "http://nastool.local/api/v1/download/search"
            ),
            response=httpx.Response(500),
        )

        with (
            patch.object(client, "download_release", AsyncMock(side_effect=http_error)),
            patch.object(
                client, "_download_via_nastool_item", AsyncMock(side_effect=http_error)
            ),
            patch.object(
                client,
                "_download_via_qbittorrent",
                AsyncMock(
                    return_value={
                        "code": 0,
                        "success": True,
                        "data": {"target": "qbittorrent"},
                    }
                ),
            ) as qb_mock,
        ):
            response = await client.download_release_candidate(
                release, save_dir="/movies"
            )

        qb_mock.assert_awaited_once()
        self.assertEqual(response["data"]["target"], "qbittorrent")

    async def test_auth_error_provides_helpful_message(self) -> None:
        """测试认证错误时提供有用的错误消息"""

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "code": 401,
                    "success": False,
                    "message": "安全认证未通过，请检查Token",
                },
            )

        client = NasToolClient(
            base_url="http://nastool.local",
            transport=httpx.MockTransport(handler),
        )

        with self.assertRaises(NasToolApiError) as ctx:
            await client.search_media("test")

        error_msg = str(ctx.exception)
        self.assertIn("安全认证未通过", error_msg)
        self.assertIn("解决建议", error_msg)
        self.assertIn("检查 NasTool 登录账号和密码", error_msg)

    async def test_http_401_error_provides_helpful_message(self) -> None:
        """测试HTTP 401错误时提供有用的错误消息"""

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="Unauthorized")

        client = NasToolClient(
            base_url="http://nastool.local",
            transport=httpx.MockTransport(handler),
        )

        with self.assertRaises(NasToolApiError) as ctx:
            await client.search_media("test")

        error_msg = str(ctx.exception)
        self.assertIn("安全认证未通过", error_msg)
        self.assertIn("HTTP 401", error_msg)
        self.assertIn("解决建议", error_msg)


if __name__ == "__main__":
    unittest.main()
