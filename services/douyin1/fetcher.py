"""
抖音内容获取器 (Douyin1)

负责从抖音URL中提取sec_user_id，调用API获取用户发布的视频内容。
支持短链接重定向处理和基础缓存机制。

主要功能：
1. URL解析和重定向处理
2. API调用和数据解析
3. 视频信息提取
4. 错误处理和日志记录
5. 基础缓存机制

作者: Assistant
创建时间: 2024年
"""

import logging
import requests
import hashlib
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs
import time
from services.common.cache import get_cache


class DouyinFetcher:
    """抖音内容获取器"""

    def __init__(self, cache_ttl: int = 3600):
        """
        初始化抖音获取器

        Args:
            cache_ttl: 缓存过期时间（秒），默认1小时
        """
        self.api_base = "https://api.douyin.wtf/api/douyin/web/fetch_user_post_videos"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
        }
        self.timeout = 30
        self.logger = logging.getLogger(__name__)

        # 初始化缓存（参考sitemap策略，存储原始数据）
        self.cache = get_cache("douyin1_api", ttl=cache_ttl, use_json=False, decode_responses=False)

        self.logger.info(f"抖音内容获取器初始化完成，缓存TTL: {cache_ttl}秒")

    def _generate_cache_key(self, douyin_url: str) -> str:
        """
        生成缓存键（参考sitemap策略）

        Args:
            douyin_url: 抖音URL

        Returns:
            str: 缓存键
        """
        # 使用抖音URL生成唯一的缓存键
        cache_key = hashlib.md5(douyin_url.encode('utf-8')).hexdigest()
        return f"douyin_api:{cache_key}"

    def extract_sec_user_id(self, douyin_url: str) -> Tuple[bool, str, Optional[str]]:
        """
        从抖音URL中提取sec_user_id

        Args:
            douyin_url: 抖音用户链接

        Returns:
            Tuple[bool, str, Optional[str]]: (是否成功, 错误信息, sec_user_id)
        """
        try:
            self.logger.info(f"开始解析抖音URL: {douyin_url}")

            # 处理短链接重定向
            final_url = self._resolve_redirect(douyin_url)
            if not final_url:
                return False, "无法解析重定向链接", None

            self.logger.info(f"重定向后的URL: {final_url}")

            # 从URL中提取sec_user_id
            sec_user_id = self._extract_user_id_from_url(final_url)
            if not sec_user_id:
                return False, "无法从URL中提取sec_user_id", None

            self.logger.info(f"成功提取sec_user_id: {sec_user_id}")
            return True, "", sec_user_id

        except Exception as e:
            self.logger.error(f"提取sec_user_id失败: {douyin_url}, 错误: {str(e)}", exc_info=True)
            return False, f"解析失败: {str(e)}", None

    def _resolve_redirect(self, url: str) -> Optional[str]:
        """
        解析URL重定向

        Args:
            url: 原始URL

        Returns:
            Optional[str]: 重定向后的最终URL
        """
        try:
            # 如果已经是完整的douyin.com URL，直接返回
            if "douyin.com/user/" in url:
                return url

            # 处理短链接重定向
            response = requests.head(
                url,
                headers=self.headers,
                timeout=10,
                allow_redirects=True
            )

            final_url = response.url
            self.logger.debug(f"重定向解析: {url} -> {final_url}")
            return final_url

        except Exception as e:
            self.logger.error(f"重定向解析失败: {url}, 错误: {str(e)}", exc_info=True)
            return None

    def _extract_user_id_from_url(self, url: str) -> Optional[str]:
        """
        从URL中提取sec_user_id

        Args:
            url: 抖音用户页面URL

        Returns:
            Optional[str]: 提取的sec_user_id
        """
        try:
            # 解析URL
            parsed = urlparse(url)

            # 方式1: 从路径中提取 /user/MS4wLjABAAAA...
            if "/user/" in parsed.path:
                user_id = parsed.path.split("/user/")[-1].split("/")[0].split("?")[0]
                if user_id and len(user_id) > 10:  # 基本长度检查
                    return user_id

            # 方式2: 从查询参数中提取
            query_params = parse_qs(parsed.query)
            if "sec_user_id" in query_params:
                return query_params["sec_user_id"][0]

            # 方式3: 使用正则表达式匹配
            # 匹配类似 MS4wLjABAAAA... 的格式
            pattern = r'MS4wLjABAAAA[A-Za-z0-9_-]+'
            match = re.search(pattern, url)
            if match:
                return match.group(0)

            return None

        except Exception as e:
            self.logger.error(f"从URL提取用户ID失败: {url}, 错误: {str(e)}", exc_info=True)
            return None

    def fetch_user_videos(self, sec_user_id: str, max_cursor: int = 0, count: int = 20) -> Tuple[bool, str, Optional[Dict]]:
        """
        获取用户发布的视频内容（内部方法）

        Args:
            sec_user_id: 用户ID
            max_cursor: 游标位置，用于分页
            count: 获取数量

        Returns:
            Tuple[bool, str, Optional[Dict]]: (是否成功, 错误信息, 原始API数据)
        """
        try:
            self.logger.info(f"开始获取用户视频: {sec_user_id}, cursor: {max_cursor}, count: {count}")

            # 构建请求参数
            params = {
                "sec_user_id": sec_user_id,
                "max_cursor": max_cursor,
                "count": count
            }

            # 发送API请求
            response = requests.get(
                self.api_base,
                params=params,
                headers=self.headers,
                timeout=self.timeout
            )
            response.raise_for_status()

            # 解析响应
            data = response.json()

            # 检查API响应格式
            if not isinstance(data, dict):
                return False, "API返回数据格式错误", None

            # 检查响应状态
            if data.get("code") != 200:
                error_msg = data.get("msg", "未知错误")
                return False, f"API返回错误: {error_msg}", None

            # 返回原始API数据
            self.logger.info(f"成功获取用户视频API数据")
            return True, "", data

        except requests.exceptions.RequestException as e:
            self.logger.error(f"请求抖音API失败: {sec_user_id}, 错误: {str(e)}", exc_info=True)
            return False, f"网络请求失败: {str(e)}", None
        except Exception as e:
            self.logger.error(f"获取用户视频失败: {sec_user_id}, 错误: {str(e)}", exc_info=True)
            return False, f"处理失败: {str(e)}", None

    def _extract_video_info(self, aweme_data: Dict) -> Optional[Dict]:
        """
        提取视频信息

        Args:
            aweme_data: API返回的单个视频数据

        Returns:
            Optional[Dict]: 提取的视频信息
        """
        try:
            # 提取基本信息
            video_info = {
                "aweme_id": aweme_data.get("aweme_id", ""),
                "desc": aweme_data.get("desc", ""),
                "caption": aweme_data.get("caption", ""),
                "create_time": aweme_data.get("create_time", 0),
                "duration": aweme_data.get("duration", 0),
                "aweme_type": aweme_data.get("aweme_type", 0),
                "is_top": aweme_data.get("is_top", 0),
            }

            # 提取作者信息
            author = aweme_data.get("author", {})
            if isinstance(author, dict):
                video_info["author"] = {
                    "uid": author.get("uid", ""),
                    "nickname": author.get("nickname", ""),
                    "signature": author.get("signature", ""),
                    "avatar_thumb": author.get("avatar_thumb", {}).get("url_list", [])
                }

            # 提取统计信息
            statistics = aweme_data.get("statistics", {})
            if isinstance(statistics, dict):
                video_info["statistics"] = {
                    "play_count": statistics.get("play_count", 0),
                    "digg_count": statistics.get("digg_count", 0),
                    "comment_count": statistics.get("comment_count", 0),
                    "share_count": statistics.get("share_count", 0),
                    "collect_count": statistics.get("collect_count", 0)
                }

            # 提取视频信息
            video = aweme_data.get("video", {})
            if isinstance(video, dict):
                play_addr = video.get("play_addr", {})
                if isinstance(play_addr, dict):
                    video_info["video"] = {
                        "uri": play_addr.get("uri", ""),
                        "url_list": play_addr.get("url_list", []),
                        "width": play_addr.get("width", 0),
                        "height": play_addr.get("height", 0),
                        "data_size": play_addr.get("data_size", 0),
                        "file_hash": play_addr.get("file_hash", ""),
                        "url_key": play_addr.get("url_key", "")
                    }

                # 提取封面信息
                cover = video.get("cover", {})
                if isinstance(cover, dict):
                    video_info["cover"] = {
                        "uri": cover.get("uri", ""),
                        "url_list": cover.get("url_list", [])
                    }

            # 提取音乐信息
            music = aweme_data.get("music", {})
            if isinstance(music, dict):
                video_info["music"] = {
                    "id": music.get("id", ""),
                    "title": music.get("title", ""),
                    "author": music.get("author", ""),
                    "play_url": music.get("play_url", {}).get("url_list", [])
                }

            # 提取分享信息
            share_info = aweme_data.get("share_info", {})
            if isinstance(share_info, dict):
                video_info["share_url"] = share_info.get("share_url", "")

            return video_info

        except Exception as e:
            self.logger.error(f"提取视频信息失败: {str(e)}", exc_info=True)
            return None

    def fetch_user_content(self, douyin_url: str, max_cursor: int = 0, count: int = 20) -> Tuple[bool, str, Optional[List[Dict]]]:
        """
        从抖音URL获取用户内容（完整流程）

        Args:
            douyin_url: 抖音用户链接
            max_cursor: 游标位置
            count: 获取数量

        Returns:
            Tuple[bool, str, Optional[List[Dict]]]: (是否成功, 错误信息, 视频列表)
        """
        try:
            # 生成缓存键（基于抖音URL）
            cache_key = self._generate_cache_key(douyin_url)

            # 尝试从缓存获取原始API数据
            cached_data = self.cache.get(cache_key)
            if cached_data is not None:
                self.logger.info(f"📦 从缓存获取抖音内容: {douyin_url}")
                # 将缓存的bytes数据转换回dict
                import json
                if isinstance(cached_data, bytes):
                    cached_data = json.loads(cached_data.decode('utf-8'))
                elif isinstance(cached_data, str):
                    cached_data = json.loads(cached_data)
                # 从缓存的原始API数据中提取视频列表
                return self._process_api_data(cached_data)

            # 步骤1: 提取sec_user_id
            success, message, sec_user_id = self.extract_sec_user_id(douyin_url)
            if not success:
                return False, message, None

            # 步骤2: 获取用户视频API数据
            success, message, api_data = self.fetch_user_videos(sec_user_id, max_cursor, count)
            if not success:
                return False, message, None

            # 缓存原始API数据（转换为JSON字符串）
            import json
            api_data_json = json.dumps(api_data, ensure_ascii=False)
            self.cache.set(cache_key, api_data_json.encode('utf-8'))
            self.logger.info(f"💾 抖音API数据已缓存: {douyin_url}")

            # 步骤3: 处理API数据并返回视频列表
            return self._process_api_data(api_data)

        except Exception as e:
            self.logger.error(f"获取用户内容失败: {douyin_url}, 错误: {str(e)}", exc_info=True)
            return False, f"处理失败: {str(e)}", None

    def _process_api_data(self, api_data: Dict) -> Tuple[bool, str, Optional[List[Dict]]]:
        """
        处理API数据，提取视频信息

        Args:
            api_data: 原始API数据

        Returns:
            Tuple[bool, str, Optional[List[Dict]]]: (是否成功, 错误信息, 视频列表)
        """
        try:
            # 获取data字段中的内容
            data = api_data.get("data", {})
            if not isinstance(data, dict):
                return False, "API返回的data字段格式错误", None

            # 获取视频列表
            aweme_list = data.get("aweme_list", [])
            if not isinstance(aweme_list, list):
                return False, "API返回的aweme_list字段格式错误", None

            # 解析视频信息
            video_list = []
            for aweme_data in aweme_list:
                video_info = self._extract_video_info(aweme_data)
                if video_info:
                    video_list.append(video_info)

            self.logger.info(f"成功处理API数据，共 {len(video_list)} 个视频")
            return True, "", video_list

        except Exception as e:
            self.logger.error(f"处理API数据失败: {str(e)}", exc_info=True)
            return False, f"处理失败: {str(e)}", None

    def generate_content_id(self, video_info: Dict) -> str:
        """
        生成内容ID

        Args:
            video_info: 视频信息

        Returns:
            str: 内容ID
        """
        return video_info.get("aweme_id", "unknown")

    def validate_douyin_url(self, url: str) -> bool:
        """
        验证抖音URL格式

        Args:
            url: 待验证的URL

        Returns:
            bool: 是否为有效的抖音URL
        """
        try:
            # 基本URL格式检查
            if not url or not isinstance(url, str):
                return False

            # 检查是否包含抖音域名
            douyin_domains = [
                "douyin.com",
                "v.douyin.com",
                "iesdouyin.com"
            ]

            return any(domain in url.lower() for domain in douyin_domains)

        except Exception as e:
            self.logger.error(f"验证抖音URL失败: {url}, 错误: {str(e)}", exc_info=True)
            return False

    def clear_cache(self, douyin_url: str = None) -> bool:
        """
        清除缓存

        Args:
            douyin_url: 指定抖音URL，如果为None则清除所有缓存

        Returns:
            bool: 是否成功
        """
        try:
            if douyin_url:
                # 清除特定URL的缓存
                cache_key = self._generate_cache_key(douyin_url)
                self.cache.delete(cache_key)
                self.logger.info(f"清除URL缓存: {douyin_url}")
            else:
                # 清除所有缓存
                self.cache.clear()
                self.logger.info("清除所有缓存")

            return True

        except Exception as e:
            self.logger.error(f"清除缓存失败: {str(e)}", exc_info=True)
            return False

    def get_cache_info(self) -> Dict:
        """
        获取缓存信息

        Returns:
            Dict: 缓存统计信息
        """
        try:
            return {
                "cache_type": "douyin1_api",
                "cache_size": len(self.cache._cache) if hasattr(self.cache, '_cache') else 0,
                "cache_ttl": self.cache.ttl if hasattr(self.cache, 'ttl') else 0
            }
        except Exception as e:
            self.logger.error(f"获取缓存信息失败: {str(e)}", exc_info=True)
            return {"error": str(e)}

    def is_cache_hit(self, douyin_url: str) -> bool:
        """
        检查缓存命中情况

        Args:
            douyin_url: 抖音URL

        Returns:
            bool: 是否命中缓存
        """
        try:
            cache_key = self._generate_cache_key(douyin_url)
            cached_data = self.cache.get(cache_key)
            return cached_data is not None
        except Exception as e:
            self.logger.error(f"检查缓存命中失败: {str(e)}", exc_info=True)
            return False


def test_douyin_fetcher(douyin_url: str = None):
    """
    测试抖音数据获取器功能

    输入抖音URL，经过API解析后，输出每个视频的必要信息

    Args:
        douyin_url: 抖音用户主页URL，如果为None则使用默认测试URL
    """
    import logging

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 默认测试URL
    if douyin_url is None:
        douyin_url = "https://www.douyin.com/user/MS4wLjABAAAA4dOPs2xB33L5Sc8YUO2gFq9U6x5LXFkJ8v15AqeIgc8"

    print("=" * 80)
    print("抖音数据获取器测试")
    print("=" * 80)
    print("📌 推荐测试方法：")
    print("   从项目根目录运行：python -m services.douyin1.fetcher")
    print("   自定义URL测试：python -m services.douyin1.fetcher 'https://www.douyin.com/user/YOUR_USER_ID'")
    print("=" * 80)
    print(f"测试URL: {douyin_url}")
    print()

    try:
        # 创建获取器实例
        fetcher = DouyinFetcher()

        # 步骤1: 验证URL格式
        print("步骤1: 验证URL格式")
        is_valid = fetcher.validate_douyin_url(douyin_url)
        print(f"URL格式验证: {'✅ 有效' if is_valid else '❌ 无效'}")

        if not is_valid:
            print("❌ URL格式无效，测试终止")
            return

        print()

        # 步骤2: 提取sec_user_id
        print("步骤2: 提取用户ID")
        success, message, sec_user_id = fetcher.extract_sec_user_id(douyin_url)

        if success:
            print(f"✅ 成功提取用户ID: {sec_user_id}")
        else:
            print(f"❌ 提取用户ID失败: {message}")
            return

        print()

                # 步骤3: 获取视频数据
        print("步骤3: 获取视频数据")

        # 检查缓存命中情况（获取前）
        cache_hit_before = fetcher.is_cache_hit(douyin_url)
        print(f"📦 获取前缓存状态: {'✅ 已缓存' if cache_hit_before else '❌ 未缓存'}")

        success, message, video_list = fetcher.fetch_user_content(douyin_url, count=10)

        # 检查缓存命中情况（获取后）
        cache_hit_after = fetcher.is_cache_hit(douyin_url)
        print(f"📦 获取后缓存状态: {'✅ 已缓存' if cache_hit_after else '❌ 未缓存'}")

        # 显示数据来源
        if cache_hit_before:
            print("📂 数据来源: 缓存")
        else:
            print("🌐 数据来源: API请求")

        if not success:
            print(f"❌ 获取视频数据失败: {message}")
            return

        if not video_list:
            print("⚠️ 没有获取到视频数据")
            return

        print(f"✅ 成功获取 {len(video_list)} 个视频")
        print()

        # 步骤4: 输出视频必要信息
        print("步骤4: 视频信息详情")
        print("=" * 80)

        for i, video in enumerate(video_list, 1):
            print(f"视频 {i}:")
            print(f"  📹 视频ID: {video.get('aweme_id', 'N/A')}")
            print(f"  📝 描述: {video.get('desc', 'N/A')[:100]}{'...' if len(video.get('desc', '')) > 100 else ''}")
            print(f"  📅 创建时间: {video.get('create_time', 'N/A')} ({_format_timestamp(video.get('create_time', 0))})")
            print(f"  ⏱️ 视频时长: {_format_duration(video.get('duration', 0))}")
            print(f"  📌 是否置顶: {'是' if video.get('is_top', 0) else '否'}")

            # 作者信息
            author = video.get('author', {})
            if author:
                print(f"  👤 作者昵称: {author.get('nickname', 'N/A')}")
                print(f"  🆔 作者UID: {author.get('uid', 'N/A')}")
                print(f"  ✍️ 作者签名: {author.get('signature', 'N/A')[:50]}{'...' if len(author.get('signature', '')) > 50 else ''}")

            # 统计信息
            stats = video.get('statistics', {})
            if stats:
                print(f"  📊 播放量: {_format_number(stats.get('play_count', 0))}")
                print(f"  👍 点赞量: {_format_number(stats.get('digg_count', 0))}")
                print(f"  💬 评论量: {_format_number(stats.get('comment_count', 0))}")
                print(f"  📤 分享量: {_format_number(stats.get('share_count', 0))}")
                print(f"  ⭐ 收藏量: {_format_number(stats.get('collect_count', 0))}")

            # 视频信息
            video_info = video.get('video', {})
            if video_info:
                print(f"  🎬 视频尺寸: {video_info.get('width', 0)}x{video_info.get('height', 0)}")
                print(f"  💾 文件大小: {_format_file_size(video_info.get('data_size', 0))}")
                print(f"  🔗 视频URI: {video_info.get('uri', 'N/A')}")

                # 显示第一个播放URL
                url_list = video_info.get('url_list', [])
                if url_list:
                    print(f"  🎥 播放链接: {url_list[0][:60]}{'...' if len(url_list[0]) > 60 else ''}")
                    print(f"  📱 可用链接数: {len(url_list)}")

            # 封面信息
            cover = video.get('cover', {})
            if cover and cover.get('url_list'):
                cover_urls = cover.get('url_list', [])
                print(f"  🖼️ 封面链接: {cover_urls[0][:60]}{'...' if len(cover_urls[0]) > 60 else ''}")

            # 音乐信息
            music = video.get('music', {})
            if music:
                print(f"  🎵 音乐标题: {music.get('title', 'N/A')}")
                print(f"  🎤 音乐作者: {music.get('author', 'N/A')}")

            # 分享链接
            share_url = video.get('share_url', '')
            if share_url:
                print(f"  🔗 分享链接: {share_url}")

            print("-" * 80)

                # 步骤5: 缓存详细信息
        print("\n步骤5: 缓存详细信息")
        print("=" * 40)

        # 缓存类型
        cache_type = type(fetcher.cache).__name__
        print(f"📋 缓存类型: {cache_type}")

        # 缓存状态
        is_cached = fetcher.is_cache_hit(douyin_url)
        print(f"📦 缓存状态: {'✅ 已缓存' if is_cached else '❌ 未缓存'}")

        # 缓存键
        cache_key = fetcher._generate_cache_key(douyin_url)
        print(f"🔑 缓存键: {cache_key}")

        # 详细缓存信息
        cache_info = fetcher.get_cache_info()
        print(f"📊 缓存详情:")
        for key, value in cache_info.items():
            print(f"   {key}: {value}")

        print("\n✅ 测试完成！")

    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()


def _format_timestamp(timestamp: int) -> str:
    """
    格式化时间戳为可读时间

    Args:
        timestamp: Unix时间戳

    Returns:
        str: 格式化的时间字符串
    """
    try:
        if timestamp <= 0:
            return "未知时间"

        from datetime import datetime
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return "时间格式错误"


def _format_duration(duration_ms: int) -> str:
    """
    格式化视频时长

    Args:
        duration_ms: 时长（毫秒）

    Returns:
        str: 格式化的时长字符串
    """
    try:
        if duration_ms <= 0:
            return "未知时长"

        seconds = duration_ms // 1000
        minutes = seconds // 60
        remaining_seconds = seconds % 60

        if minutes > 0:
            return f"{minutes}分{remaining_seconds}秒"
        else:
            return f"{remaining_seconds}秒"
    except:
        return "时长格式错误"


def _format_number(number: int) -> str:
    """
    格式化数字为可读格式

    Args:
        number: 数字

    Returns:
        str: 格式化的数字字符串
    """
    try:
        if number >= 100000000:  # 1亿
            return f"{number / 100000000:.1f}亿"
        elif number >= 10000:  # 1万
            return f"{number / 10000:.1f}万"
        else:
            return str(number)
    except:
        return "数字格式错误"


def _format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小

    Args:
        size_bytes: 文件大小（字节）

    Returns:
        str: 格式化的文件大小字符串
    """
    try:
        if size_bytes <= 0:
            return "未知大小"

        if size_bytes >= 1024 * 1024 * 1024:  # GB
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
        elif size_bytes >= 1024 * 1024:  # MB
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        elif size_bytes >= 1024:  # KB
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes} B"
    except:
        return "大小格式错误"


# 如果直接运行此文件，执行测试
if __name__ == "__main__":
    import sys
    import os
    from pathlib import Path
    from dotenv import load_dotenv

    # 加载环境变量
    load_dotenv()

    # 添加项目根目录到Python路径
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    print("抖音数据获取器测试")
    print("注意：建议从项目根目录运行: python -m services.douyin1.fetcher")
    print()

    # 检查是否提供了URL参数
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
        print(f"使用提供的URL: {test_url}")
        test_douyin_fetcher(test_url)
    else:
        print("使用默认测试URL")
        test_douyin_fetcher()