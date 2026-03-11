import unittest

from plugin_logic import (
    ConversationState,
    MediaCandidate,
    ReleaseCandidate,
    SearchQuery,
    build_media_choices_message,
    build_release_choices_message,
    extract_command_query,
    filter_releases_by_query,
    parse_choice,
    pick_best_release,
)


class PluginLogicTests(unittest.TestCase):
    def test_extract_command_query_basic(self) -> None:
        """测试基本的命令解析"""
        query = extract_command_query("下载电影 盗梦空间")
        self.assertEqual(query.keyword, "盗梦空间")
        self.assertFalse(query.has_filters())

    def test_extract_command_query_with_resolution(self) -> None:
        """测试带分辨率的解析"""
        query = extract_command_query("下载电影 功夫 1080p")
        self.assertEqual(query.keyword, "功夫")
        self.assertEqual(query.resolution, "1080p")

    def test_extract_command_query_with_multiple_filters(self) -> None:
        """测试带多个过滤条件的解析"""
        query = extract_command_query("下载电影 功夫 1080p 粤语")
        self.assertEqual(query.keyword, "功夫")
        self.assertEqual(query.resolution, "1080p")
        self.assertEqual(query.language, "粤语")
        self.assertTrue(query.has_filters())

    def test_extract_command_query_with_all_filters(self) -> None:
        """测试带所有过滤条件的解析"""
        query = extract_command_query("下载电影 Inception 4K BluRay x265")
        self.assertEqual(query.keyword, "Inception")
        self.assertEqual(query.resolution, "4K")
        self.assertEqual(query.source, "BluRay")
        self.assertEqual(query.codec, "x265")

    def test_extract_command_query_4k_alias(self) -> None:
        """测试 4K 分辨率别名"""
        query = extract_command_query("下载电影 电影名 2160p")
        self.assertEqual(query.resolution, "4K")

    def test_extract_command_query_language_aliases(self) -> None:
        """测试语言别名"""
        test_cases = [
            ("粤语", "粤语"),
            ("粤配", "粤语"),
            ("国语", "国语"),
            ("国配", "国语"),
            ("英语", "英语"),
            ("英配", "英语"),
        ]
        for input_lang, expected in test_cases:
            query = extract_command_query(f"下载电影 电影名 {input_lang}")
            self.assertEqual(query.language, expected, f"Failed for {input_lang}")

    def test_search_query_display_text(self) -> None:
        """测试搜索查询的显示文本"""
        query = SearchQuery(keyword="功夫", resolution="1080p", language="粤语")
        self.assertEqual(query.get_display_text(), "功夫 1080p 粤语")

    def test_parse_choice_accepts_cancel_and_valid_numbers(self) -> None:
        self.assertEqual(parse_choice("2", 3), 1)
        self.assertIsNone(parse_choice("取消", 3))
        with self.assertRaises(ValueError):
            parse_choice("4", 3)

    def test_build_media_choices_message_lists_candidates(self) -> None:
        query = SearchQuery(keyword="盗梦空间")
        state = ConversationState(
            medias=[
                MediaCandidate(
                    title="盗梦空间",
                    year="2010",
                    media_type="MOV",
                    label="电影",
                    tmdb_id="27205",
                    douban_id="0",
                    overview="dreams",
                    original_title="Inception",
                    english_title="Inception",
                    score="8.8",
                    release_date="2010-07-15",
                    original_language="en",
                    detail_link="https://example.invalid/movie/27205",
                )
            ]
        )

        message = build_media_choices_message(query, state)

        self.assertIn("搜索到以下媒体候选", message)
        self.assertIn("1. 盗梦空间 (2010)", message)
        self.assertIn("TMDB: 27205", message)
        self.assertIn("原名: Inception", message)
        self.assertIn("评分: 8.8", message)
        self.assertIn("上映: 2010-07-15", message)
        self.assertIn("语言: en", message)
        self.assertIn("请直接回复上面的编号继续", message)

    def test_build_media_choices_message_with_filters(self) -> None:
        """测试带过滤条件的媒体选择消息"""
        query = SearchQuery(keyword="功夫", resolution="1080p", language="粤语")
        state = ConversationState(
            medias=[
                MediaCandidate(
                    title="功夫",
                    year="2004",
                    media_type="MOV",
                    label="电影",
                    tmdb_id="11111",
                    douban_id="0",
                    overview="kung fu",
                )
            ]
        )

        message = build_media_choices_message(query, state)

        self.assertIn("功夫 1080p 粤语", message)

    def test_build_release_choices_message_lists_releases(self) -> None:
        state = ConversationState(
            selected_media=MediaCandidate(
                title="盗梦空间",
                year="2010",
                media_type="MOV",
                label="电影",
                tmdb_id="27205",
                douban_id="0",
                overview="dreams",
                original_title="Inception",
                english_title="Inception",
            ),
            releases=[
                ReleaseCandidate(
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
            ],
        )

        message = build_release_choices_message(state)

        self.assertIn("已选择媒体：盗梦空间 (2010)", message)
        self.assertIn("1. Inception.2010.1080p.BluRay.x265", message)
        self.assertIn("站点: PTSite", message)
        self.assertIn("请直接回复资源编号开始下载", message)

    def test_build_release_choices_message_with_filters(self) -> None:
        """测试带过滤条件的资源选择消息"""
        state = ConversationState(
            selected_media=MediaCandidate(
                title="功夫",
                year="2004",
                media_type="MOV",
                label="电影",
                tmdb_id="11111",
                douban_id="0",
                overview="kung fu",
            ),
            releases=[],
            search_query=SearchQuery(
                keyword="功夫", resolution="1080p", language="粤语"
            ),
        )

        message = build_release_choices_message(state)

        self.assertIn("筛选条件：", message)
        self.assertIn("分辨率：1080p", message)
        self.assertIn("语言：粤语", message)

    def test_filter_releases_by_resolution(self) -> None:
        """测试按分辨率过滤"""
        releases = [
            ReleaseCandidate(
                "1",
                "Movie.1080p.mkv",
                "Site1",
                "5GB",
                100,
                "magnet:?xt=urn:btih:1",
                "url1",
                "1080p",
                "WEB-DL",
            ),
            ReleaseCandidate(
                "2",
                "Movie.720p.mkv",
                "Site2",
                "3GB",
                80,
                "magnet:?xt=urn:btih:2",
                "url2",
                "720p",
                "WEB-DL",
            ),
            ReleaseCandidate(
                "3",
                "Movie.2160p.mkv",
                "Site3",
                "15GB",
                50,
                "magnet:?xt=urn:btih:3",
                "url3",
                "2160p",
                "WEB-DL",
            ),
        ]
        query = SearchQuery(keyword="Movie", resolution="1080p")
        filtered = filter_releases_by_query(releases, query)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].release_id, "1")

    def test_filter_releases_by_language(self) -> None:
        """测试按语言过滤"""
        releases = [
            ReleaseCandidate(
                "1",
                "Movie 粤语.mkv",
                "Site1",
                "5GB",
                100,
                "magnet:?xt=urn:btih:1",
                "url1",
                "1080p",
                "WEB-DL",
                description="粤语中字",
            ),
            ReleaseCandidate(
                "2",
                "Movie 国语.mkv",
                "Site2",
                "3GB",
                80,
                "magnet:?xt=urn:btih:2",
                "url2",
                "1080p",
                "WEB-DL",
            ),
        ]
        query = SearchQuery(keyword="Movie", language="粤语")
        filtered = filter_releases_by_query(releases, query)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].release_id, "1")

    def test_filter_releases_no_filters(self) -> None:
        """测试无过滤条件时返回全部"""
        releases = [
            ReleaseCandidate(
                "1",
                "Movie.1080p.mkv",
                "Site1",
                "5GB",
                100,
                "magnet:?xt=urn:btih:1",
                "url1",
                "1080p",
                "WEB-DL",
            ),
            ReleaseCandidate(
                "2",
                "Movie.720p.mkv",
                "Site2",
                "3GB",
                80,
                "magnet:?xt=urn:btih:2",
                "url2",
                "720p",
                "WEB-DL",
            ),
        ]
        query = SearchQuery(keyword="Movie")
        filtered = filter_releases_by_query(releases, query)

        self.assertEqual(len(filtered), 2)

    def test_pick_best_release_prefers_highest_seeders_and_skips_zero_size(
        self,
    ) -> None:
        releases = [
            ReleaseCandidate(
                "1",
                "Movie.zero.size",
                "Site1",
                "0",
                999,
                "magnet:?xt=urn:btih:1",
                "url1",
                "1080p",
                "WEB-DL",
            ),
            ReleaseCandidate(
                "2",
                "Movie.good",
                "Site2",
                "8.5GB",
                120,
                "magnet:?xt=urn:btih:2",
                "url2",
                "1080p",
                "BluRay",
            ),
            ReleaseCandidate(
                "3",
                "Movie.best",
                "Site3",
                "10.2GB",
                350,
                "magnet:?xt=urn:btih:3",
                "url3",
                "2160p",
                "BluRay",
            ),
        ]

        selected = pick_best_release(releases)

        self.assertIsNotNone(selected)
        self.assertEqual(selected.release_id, "3")

    def test_pick_best_release_returns_none_when_all_sizes_zero(self) -> None:
        releases = [
            ReleaseCandidate(
                "1",
                "Movie.zero.1",
                "Site1",
                "0",
                999,
                "magnet:?xt=urn:btih:1",
                "url1",
                "1080p",
                "WEB-DL",
            ),
            ReleaseCandidate(
                "2",
                "Movie.zero.2",
                "Site2",
                "0B",
                100,
                "magnet:?xt=urn:btih:2",
                "url2",
                "720p",
                "WEB-DL",
            ),
        ]

        selected = pick_best_release(releases)

        self.assertIsNone(selected)

    def test_extract_command_query_skip_auto_download_patterns(self) -> None:
        """测试'不自动下载'关键字的解析"""
        # 测试各种'不自动下载'关键字模式
        test_cases = [
            '下载电影 盗梦空间 不自动下载',
            '下载电影 盗梦空间 不要自动下载',
            '下载电影 盗梦空间 别自动下载',
            '下载电影 盗梦空间 手动选择',
            '下载电影 盗梦空间 手动下载',
            '下载电影 盗梦空间 自己选',
            '下载电影 盗梦空间 手动挑',
        ]
        for cmd in test_cases:
            query = extract_command_query(cmd)
            self.assertTrue(query.skip_auto_download, f"'{cmd}' 应该设置 skip_auto_download 为 True")
            self.assertEqual(query.keyword, "盗梦空间")

        # 测试正常情况
        query = extract_command_query('下载电影 盗梦空间')
        self.assertFalse(query.skip_auto_download)
        self.assertEqual(query.keyword, '盗梦空间')

    def test_extract_command_query_skip_auto_download_with_filters(self) -> None:
        """测试'不自动下载'与其他过滤条件一起使用"""
        query = extract_command_query('下载电影 盗梦空间 1080p 不自动下载')
        self.assertTrue(query.skip_auto_download)
        self.assertEqual(query.keyword, '盗梦空间')
        self.assertEqual(query.resolution, '1080p')

        query = extract_command_query('下载电影 功夫 4K 粤语 手动选择')
        self.assertTrue(query.skip_auto_download)
        self.assertEqual(query.keyword, '功夫')
        self.assertEqual(query.resolution, '4K')
        self.assertEqual(query.language, '粤语')


if __name__ == "__main__":
    unittest.main()
