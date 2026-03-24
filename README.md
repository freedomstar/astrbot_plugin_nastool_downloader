# AstrBot NasTool Downloader Plugin

通过对话控制 NasTool 搜索媒体并下载资源的 AstrBot 插件。

## 功能特性

- 🔍 **媒体搜索**：通过电影/剧集名称搜索 TMDB/豆瓣媒体信息
- 📺 **多类型支持**：支持电影、电视剧、视频的搜索和下载
- 📋 **交互式选择**：支持多轮对话选择目标媒体和具体资源
- ⬇️ **智能下载**：优先使用 NasTool API，异常时自动回退到 qBittorrent
- 🔐 **自动登录**：执行操作前自动验证 NasTool 连接状态
- ⚙️ **灵活配置**：支持自定义超时、轮询策略、下载目录等
- 🛡️ **错误处理**：完善的异常处理和用户友好的错误提示

## 安装方法

### 1. 安装插件

将本插件目录复制到 AstrBot 的插件目录：

```bash
# 进入 AstrBot 安装目录
cd /path/to/astrbot

# 创建插件目录（如不存在）
mkdir -p data/plugins/astrbot_plugin_nastool_downloader

# 复制插件文件
cp -r /path/to/nastool_skill/* data/plugins/astrbot_plugin_nastool_downloader/
```

### 2. 安装依赖

```bash
cd data/plugins/astrbot_plugin_nastool_downloader
pip install -r requirements.txt
```

或者直接在 AstrBot 环境中安装：

```bash
pip install httpx>=0.27,<1
```

### 3. 配置插件

在 AstrBot WebUI 的插件管理页面，找到 "NasTool Downloader" 插件，配置以下参数：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `base_url` | NasTool 服务地址（含协议和端口） | `http://127.0.0.1:3000` |
| `username` | NasTool 登录账号（必填） | （空） |
| `password` | NasTool 登录密码（必填） | （空） |
| `request_timeout` | 普通接口超时时间（秒） | `20` |
| `search_timeout` | 资源站检索超时时间（秒） | `120` |
| `poll_interval` | 轮询结果间隔（秒） | `2` |
| `max_polls` | 最大轮询次数 | `20` |
| `max_media_results` | 显示媒体候选数量 | `5` |
| `max_release_results` | 显示资源候选数量 | `8` |
| `download_dir` | 下载保存目录（可选） | （空） |
| `download_setting` | 下载设置ID（可选） | （空） |
| `session_timeout` | 对话等待超时时间（秒） | `180` |

### 配置登录信息

插件使用 NasTool 的账号密码自动登录获取 API Key：

1. 在插件配置中填写 `username`（你的 NasTool 登录账号）
2. 在插件配置中填写 `password`（你的 NasTool 登录密码）
3. 保存配置后，插件会在每次操作时自动登录并获取 API Key

## 使用方法

### 基本命令

在聊天中发送：

```
下载电影 电影名称
下载电视剧 剧集名称
下载视频 视频名称
```

支持的命令：
- `下载电影` - 搜索并下载电影
- `下载电视剧` - 搜索并下载电视剧/剧集
- `下载视频` - 搜索并下载视频（支持电影和剧集）

### 登录验证

插件在执行下载操作前会自动验证与 NasTool 的连接：
- 如果未配置 API Key，会提示配置方法
- 如果连接失败，会提示检查服务状态和配置

### 高级用法（带筛选条件）

支持指定分辨率、语言、片源等条件：

```
下载电影 电影名 [分辨率] [语言] [片源] [编码]
```

支持的筛选条件：

| 类型 | 可选项 | 示例 |
|------|--------|------|
| **分辨率** | 4K / 2160p / 1080p / 720p / 480p | `1080p`, `4K` |
| **语言** | 粤语 / 国语 / 英语 / 日语 / 韩语 | `粤语`, `国语中字` |
| **片源** | BluRay / WEB-DL / WEBRip / HDRip / Remux | `BluRay`, `WEB-DL` |
| **编码** | x265 / x264 / AV1 / VP9 | `x265`, `HEVC` |

### 手动选择资源下载

默认情况下，插件会自动选择**做种数最高且文件大小有效**的资源进行下载。如果你想手动查看和选择资源，可以在命令中添加以下任意关键词：

| 触发关键词 | 说明 |
|-----------|------|
| `手动选择`、`手动下载` | 显示资源列表供手动选择 |
| `不自动下载`、`不要自动下载`、`别自动下载` | 跳过自动选择 |
| `自己选`、`手动挑` | 启用手动模式 |

**使用示例：**

```
下载电影 盗梦空间 手动选择
下载电视剧 权力的游戏 不自动下载
下载视频 黑镜 手动挑
```

**手动选择流程：**

1. 用户发送带手动选择关键词的命令
2. Bot 搜索媒体并显示候选列表
3. 用户回复媒体编号
4. Bot 显示**所有可用资源**（按做种数排序）
5. 用户回复资源编号进行下载

### 交互流程示例

**示例 1：搜索并下载电影**

```
用户: 下载电影 盗梦空间
Bot: 搜索到以下媒体候选：盗梦空间
     1. 盗梦空间 (2010) | 电影 | TMDB: 27205
     2. Bikini Inception (2015) | 电影 | TMDB: 542438
     回复编号继续，或回复"取消"结束。

用户: 1
Bot: 已选择《盗梦空间》，正在检索可下载资源，请稍候...
     找到以下资源：
     1. Inception 2010 1080p BluRay x265 | 站点: PTSite | 大小: 12.3GB | 做种: 88 | 规格: 1080p BluRay
     2. Inception (2010) 1080p BrRip x264 - 1.85GB | 站点: The Pirate Bay | 大小: 1.85G | 做种: 624
     回复资源编号开始下载，或回复"取消"结束。


### 交互流程示例

**示例 1：搜索并下载电影（基础用法）**

```
用户: 下载电影 盗梦空间
Bot: 搜索到以下媒体候选：盗梦空间
     1. 盗梦空间 (2010) | 电影 | TMDB: 27205
     2. Bikini Inception (2015) | 电影 | TMDB: 542438
     回复编号继续，或回复"取消"结束。

用户: 1
Bot: 已选择《盗梦空间》，正在检索可下载资源，请稍候...
     找到以下资源：
     1. Inception 2010 1080p BluRay x265 | 站点: PTSite | 大小: 12.3GB | 做种: 88 | 规格: 1080p BluRay
     2. Inception (2010) 1080p BrRip x264 - 1.85GB | 站点: The Pirate Bay | 大小: 1.85G | 做种: 624
     回复资源编号开始下载，或回复"取消"结束。

用户: 1
Bot: 已提交下载：Inception 2010 1080p BluRay x265
     NasTool 返回：成功
```

**示例 2：带筛选条件的搜索**

```
用户: 下载电影 功夫 1080p 粤语
Bot: 搜索到以下媒体候选：功夫 1080p 粤语
     1. 功夫 (2004) | 电影 | TMDB: 11123
     回复编号继续，或回复"取消"结束。

用户: 1
Bot: 已选择《功夫》，正在检索可下载资源，请稍候...
     筛选条件：分辨率：1080p | 语言：粤语
     找到以下资源（已按筛选条件过滤）：
     1. Kung.Fu.Hustle.2004.1080p.Cantonese.DD5.1.x264 | 站点: PTSite | 大小: 8.5GB | 做种: 45
     2. 功夫 2004 1080p 国粤双语 | 站点: AnotherSite | 大小: 12.1GB | 做种: 23
     回复资源编号开始下载，或回复"取消"结束。
```

**示例 3：多条件组合筛选**

```
用户: 下载电影 Inception 4K BluRay x265
Bot: 搜索到以下媒体候选：Inception 4K BluRay x265
     1. 盗梦空间 (2010) | 电影 | TMDB: 27205
     回复编号继续，或回复"取消"结束。

用户: 1
Bot: 已选择《盗梦空间》，正在检索可下载资源，请稍候...
     筛选条件：分辨率：4K | 片源：BluRay | 编码：x265
     ...
```

**示例 4：下载电视剧**

```
用户: 下载电视剧 权力的游戏
Bot: 搜索到以下媒体候选：权力的游戏
     1. 权力的游戏 (2011) | 电视剧 | TMDB: 1399
     2. 权力的游戏：最后的守望 (2019) | 电影 | TMDB: 633224
     回复编号继续，或回复"取消"结束。

用户: 1
Bot: 已选择《权力的游戏》，正在检索可下载资源，请稍候...
     找到以下资源：
     1. Game.of.Thrones.S01-08.1080p.BluRay.x265 | 站点: PTSite | 大小: 156.2GB | 做种: 42
     2. Game of Thrones Season 1 Complete 1080p WEB-DL | 站点: AnotherSite | 大小: 23.1GB | 做种: 18
     回复资源编号开始下载，或回复"取消"结束。

用户: 1
Bot: 已提交下载：Game.of.Thrones.S01-08.1080p.BluRay.x265
     NasTool 返回：成功
```

**示例 5：手动选择资源（不自动下载）**

```
用户: 下载电影 盗梦空间 手动选择
Bot: 搜索到以下媒体候选：盗梦空间
     1. 盗梦空间 (2010) | 电影 | TMDB: 27205
     2. Bikini Inception (2015) | 电影 | TMDB: 542438
     回复编号继续，或回复"取消"结束。

用户: 1
Bot: 已选择《盗梦空间》，正在检索可下载资源，请稍候...
     📋 已启用手动选择模式，为您展示按做种数排序的资源列表：
     1. Inception 2010 2160p BluRay REMUX | 站点: PTSite | 大小: 84.2GB | 做种: 88 | 规格: 4K BluRay
     2. Inception 2010 1080p BluRay x265 | 站点: PTSite | 大小: 12.3GB | 做种: 65 | 规格: 1080p BluRay
     3. Inception (2010) 1080p BrRip x264 - 1.85GB | 站点: AnotherSite | 大小: 1.85G | 做种: 42 | 规格: 1080p WEB-DL
     4. Inception.2010.720p.BluRay.x264 | 站点: Site3 | 大小: 6.8GB | 做种: 18 | 规格: 720p BluRay
     请直接回复资源编号开始下载，不用再输入"下载"。
     回复"取消"可结束当前流程。

用户: 2
Bot: 已提交下载：Inception 2010 1080p BluRay x265
     站点：PTSite | 大小：12.3GB | 做种：65
     NasTool 返回：成功
```

**示例 6：下载视频（通用命令）**

```
用户: 下载视频 黑镜
Bot: 搜索到以下媒体候选：黑镜
     1. 黑镜 (2011) | 电视剧 | TMDB: 42009
     2. 黑镜：潘达斯奈基 (2018) | 电影 | TMDB: 505906
     回复编号继续，或回复"取消"结束。

用户: 1
Bot: 已选择《黑镜》，正在检索可下载资源，请稍候...
     ...
```

**示例 7：取消操作**

```
用户: 下载电影 盗梦空间
Bot: [显示媒体列表]

用户: 取消
Bot: 已取消 NasTool 下载流程。
```

**示例 8：超时处理**

如果用户在选择界面超过 `session_timeout` 秒（默认180秒）未回复：

```
Bot: 等待选择超时，已结束 NasTool 下载流程。
```

## 工作流程

```
用户输入 -> 媒体搜索 -> 显示候选列表 -> 用户选择媒体
                                            |
                                            v
显示资源列表 <- 资源检索 <- 启动站点搜索 <- 用户选择
      |
      v
自动选择下载方式 -> 提交下载任务 -> 返回结果
      |
      +-- NasTool /download/search (优先)
      +-- NasTool /download/item (回退)
      +-- qBittorrent Web API (最终回退)
```

## 技术细节

### 下载优先级

1. **NasTool API**（首选）
   - 调用 `/api/v1/download/search`
   - 适用于 NasTool 搜索结果的直接下载

2. **NasTool 直接链接**（第一回退）
   - 调用 `/api/v1/download/item`
   - 使用资源的 enclosure/magnet 链接下载

3. **qBittorrent**（最终回退）
   - 自动从 NasTool 获取已配置的 qBittorrent 信息
   - 直接调用 qBittorrent Web API 添加任务
   - 保持与 NasTool 相同的保存路径策略

### 资源匹配策略

为避免返回无关资源，插件采用多层匹配：

- **TMDB ID 匹配**：优先匹配相同的 TMDB ID
- **标题关键词匹配**：匹配中文名、英文名、原名
- **资源内容匹配**：检查资源文件名、描述、页面链接

### 轮询机制

NasTool 的站点搜索是异步的：

1. 发送搜索请求（可能超时，属正常情况）
2. 轮询 `/api/v1/search/result` 获取结果
3. 根据 `poll_interval` 和 `max_polls` 控制轮询频率
4. 获取结果后立即返回，无需等待全部轮询完成

## 故障排除

### 插件无法加载

**现象**：AstrBot 启动时插件加载失败

**解决方案**：
1. 检查 `requirements.txt` 中的依赖是否已安装
2. 确认文件结构完整（`main.py`、`metadata.yaml` 等必需文件存在）
3. 查看 AstrBot 日志获取具体错误信息

### 登录失败

**现象**：返回 "❌ 登录失败" 或 "账号登录失败"

**可能原因及解决方案**：

| 错误信息 | 原因 | 解决方案 |
|---------|------|---------|
| 插件尚未配置 NasTool 登录信息 | 没有配置账号密码 | 在插件配置中填写 `username` 和 `password` |
| 账号登录失败 | 账号密码错误 | 检查 `username` 和 `password` 是否正确 |
| Connection refused | NasTool 服务未启动或地址错误 | 检查 `base_url` 和 NasTool 服务状态 |

### 媒体搜索失败

**现象**：返回 "媒体搜索失败：..."

**可能原因及解决方案**：

| 错误信息 | 原因 | 解决方案 |
|---------|------|---------|
| 安全认证未通过 | 登录失效 | 重新登录获取 API Key，检查账号密码是否正确 |
| Connection refused | NasTool 服务未启动或地址错误 | 检查 `base_url` 和 NasTool 服务状态 |
| Timeout | 网络延迟或服务响应慢 | 增加 `request_timeout` 配置 |

### 没有返回资源

**现象**：显示 "暂时没有检索到可下载资源"

**解决方案**：
1. 检查 NasTool 中配置的索引站点是否正常工作
2. 增加 `search_timeout` 和 `max_polls` 以延长搜索时间
3. 尝试使用更精确的片名（如英文名）

### 下载提交失败

**现象**：返回 "NasTool 请求失败"

**说明**：
- 插件会自动尝试三种下载方式，只要其中一种成功即可
- 如果最终返回失败，请检查：
  1. qBittorrent 是否已配置并启用
  2. 下载目录是否有写入权限
  3. 磁盘空间是否充足

### 会话超时

**现象**：长时间未回复后提示超时

**解决方案**：
- 增加 `session_timeout` 配置（默认180秒）
- 在超时前回复编号或"取消"

## 文件结构

```
.
├── __init__.py              # 包初始化
├── main.py                  # 插件主入口
├── nastool_client.py        # NasTool API 客户端
├── plugin_logic.py          # 业务逻辑和模型
├── metadata.yaml            # 插件元数据
├── _conf_schema.json        # 配置项定义
├── requirements.txt         # Python 依赖
├── pyrightconfig.json       # 类型检查配置
├── tests/                   # 单元测试
│   ├── __init__.py
│   ├── test_nastool_client.py
│   └── test_plugin_logic.py
```

## 开发与测试

### 运行测试

```bash
# 在项目根目录执行
PYTHONPATH=. python -m unittest discover -s tests -v
```

### 类型检查

```bash
python -m basedpyright main.py nastool_client.py plugin_logic.py
```

### 手动测试 NasTool API

```python
import asyncio
from nastool_client import NasToolClient

async def test():
    client = NasToolClient(
        base_url='http://yourip:port',
        username='你的账号',
        password='你的密码',
    )

    # 先登录获取 API Key
    login_result = await client.login_with_credentials()
    print(f"登录结果: {login_result}")

    # 搜索媒体
    medias = await client.search_media('盗梦空间')
    print(f"找到 {len(medias)} 个媒体")

    # 搜索资源
    releases = await client.search_releases_for_media(medias[0])
    print(f"找到 {len(releases)} 个资源")

    # 提交下载
    result = await client.download_release_candidate(releases[0])
    print(f"下载结果: {result}")

asyncio.run(test())
```

## 注意事项

1. **隐私安全**：账号密码仅用于登录获取 API Key，不会被保存
2. **网络要求**：确保 AstrBot 服务器能访问 NasTool 和 qBittorrent
3. **版权合规**：本插件仅用于管理个人合法拥有的媒体资源
4. **站点策略**：部分 PT 站点可能有下载频率限制，请合理使用

## 更新日志

### v1.1.0 (2026-03-24)

- ✨ 新增 `下载电视剧` 命令，支持搜索和下载电视剧/剧集
- ✨ 新增 `下载视频` 命令，通用命令支持电影和剧集
- 🔐 新增自动登录验证，操作前自动检查 NasTool 连接状态
- 👤 统一使用账号密码登录获取 API Key，删除手动配置 API Key 方式
- 📝 完善帮助信息，提供清晰的配置指导

### v1.0.0 (2026-03-11)

- ✨ 初始版本发布
- 🔍 支持 TMDB/豆瓣媒体搜索
- 📋 支持交互式媒体和资源选择
- ⬇️ 支持 NasTool API 和 qBittorrent 双下载通道
- ⚙️ 完整的配置项支持
- 🧪 完整的单元测试覆盖

## 开源协议

MIT License

## 相关链接

- [AstrBot 官方文档](https://docs.astrbot.app/)
- [NasTool GitHub](https://github.com/NAStool/nas-tools)
- [qBittorrent Web API 文档](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1))

---

如有问题或建议，欢迎提交 Issue 或 Pull Request。
