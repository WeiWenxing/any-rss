"""
抖音内容获取器

负责调用第三方API获取抖音用户发布的内容
"""

import logging
import requests
import hashlib
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import time
from services.common.cache import get_cache


class DouyinFetcher:
    """抖音内容获取器"""

    def __init__(self, cache_ttl: int = 21600):
        """
        初始化抖音获取器

        Args:
            cache_ttl: 缓存过期时间（秒），默认6小时
        """
        self.api_base = "https://api.cenguigui.cn/api/douyin/user.php"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache"
        }
        self.timeout = 15

        # 初始化缓存
        self.cache = get_cache("douyin_api", ttl=cache_ttl)

        logging.info(f"抖音内容获取器初始化完成，缓存TTL: {cache_ttl}秒")

    def _generate_cache_key(self, douyin_url: str) -> str:
        """
        生成缓存键

        Args:
            douyin_url: 抖音用户主页链接

        Returns:
            str: 缓存键
        """
        # 使用URL生成唯一的缓存键
        cache_key = hashlib.md5(douyin_url.encode('utf-8')).hexdigest()
        return f"user_content:{cache_key}"

    def fetch_user_content(self, douyin_url: str, cookie: str = None) -> Tuple[bool, str, Optional[List[Dict]]]:
        """
        获取抖音用户发布的全部内容（带缓存）

        Args:
            douyin_url: 抖音用户主页链接
            cookie: 可选的cookie参数

        Returns:
            Tuple[bool, str, Optional[List[Dict]]]: (是否成功, 错误信息, 全部内容数据列表)
        """
        try:
            # 生成缓存键
            cache_key = self._generate_cache_key(douyin_url)

            # 尝试从缓存获取数据
            cached_data = self.cache.get(cache_key)
            if cached_data is not None:
                logging.info(f"从缓存获取抖音内容: {douyin_url}")
                return True, "", cached_data

            logging.info(f"开始获取抖音用户内容: {douyin_url}")

            # 构建请求参数
            params = {"url": douyin_url}
            if cookie:
                params["cookie"] = cookie

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

            # 获取data字段中的内容列表
            content_list = data.get("data", [])
            if not isinstance(content_list, list) or len(content_list) == 0:
                return False, "API返回的data字段为空或格式错误", None

            # 缓存成功的结果
            self.cache.set(cache_key, content_list)
            logging.info(f"成功获取并缓存抖音内容，共 {len(content_list)} 个")

            return True, "", content_list

        except requests.exceptions.RequestException as e:
            logging.error(f"请求抖音API失败: {douyin_url}, 错误: {str(e)}", exc_info=True)
            return False, f"网络请求失败: {str(e)}", None
        except Exception as e:
            logging.error(f"获取抖音内容失败: {douyin_url}, 错误: {str(e)}", exc_info=True)
            return False, f"处理失败: {str(e)}", None

    def download_media(self, media_url: str, save_path: str) -> Tuple[bool, str]:
        """
        下载媒体文件（视频或图片）

        Args:
            media_url: 媒体文件URL
            save_path: 保存路径

        Returns:
            Tuple[bool, str]: (是否成功, 错误信息)
        """
        try:
            logging.info(f"开始下载媒体文件: {media_url}")

            # 发送下载请求
            response = requests.get(
                media_url,
                headers=self.headers,
                timeout=30,  # 下载超时时间更长
                stream=True  # 流式下载
            )
            response.raise_for_status()

            # 写入文件
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            logging.info(f"媒体文件下载完成: {save_path}")
            return True, ""

        except requests.exceptions.RequestException as e:
            logging.error(f"下载媒体文件失败: {media_url}, 错误: {str(e)}", exc_info=True)
            return False, f"下载失败: {str(e)}"
        except Exception as e:
            logging.error(f"保存媒体文件失败: {save_path}, 错误: {str(e)}", exc_info=True)
            return False, f"保存失败: {str(e)}"

    def extract_content_info(self, content_data: Dict) -> Dict:
        """
        提取内容信息

        Args:
            content_data: API返回的内容数据（单个内容对象）

        Returns:
            Dict: 提取的内容信息
        """
        try:
            # content_data 现在直接是内容对象，不需要再获取data字段
            data = content_data

            # 提取基本信息
            content_info = {
                "aweme_id": data.get("aweme_id", ""),
                "title": data.get("title", ""),
                "author": data.get("author", ""),
                "nickname": data.get("nickname", ""),
                "avatar": data.get("avatar", ""),
                "share_url": data.get("share_url", ""),
                "type": data.get("type", ""),
                "time": data.get("time", ""),  # 注意：时间字段可能在根级别
                "comment": data.get("comment", 0),
                "play": data.get("play", 0),
                "like": data.get("like", 0),
            }

            # 优先使用API返回的type字段判断媒体类型
            api_type = data.get("type", "").lower()

            if api_type == "图片":
                # 图片内容：优先使用images_info，fallback到pic_list
                if "images_info" in data and data["images_info"] and data["images_info"].get("images"):
                    images_info = data["images_info"]
                    content_info.update({
                        "media_type": "images",
                        "images": images_info.get("images", []),
                        "width": images_info.get("width", 0),
                        "height": images_info.get("height", 0),
                    })
                elif "pic_list" in data and data["pic_list"]:
                    content_info.update({
                        "media_type": "images",
                        "images": data.get("pic_list", []),
                    })
                else:
                    # 使用封面图作为单张图片
                    content_info.update({
                        "media_type": "image",
                        "media_url": data.get("pic", ""),
                    })
            elif api_type == "视频" or api_type == "video":
                # 视频内容
                if "video_info" in data and data["video_info"]:
                    video_info = data["video_info"]
                    # 检查video_info是否有效（不是"不是视频没有信息"）
                    if (video_info.get("url") and video_info.get("url") != "不是视频没有信息") or \
                       (video_info.get("download")) or (video_info.get("download2")):
                        content_info.update({
                            "media_type": "video",
                            "media_url": video_info.get("url", ""),
                            "cover_url": video_info.get("pic", ""),
                            "width": video_info.get("width", 0),
                            "height": video_info.get("height", 0),
                            "size": video_info.get("size", ""),
                            "video_info": video_info,  # 保留完整的video_info对象
                        })
                    else:
                        # video_info无效，可能是图片内容被错误标记
                        logging.warning(f"API标记为视频但video_info无效，尝试作为图片处理: {content_info['title']}")
                        # 尝试作为图片处理
                        if "images_info" in data and data["images_info"] and data["images_info"].get("images"):
                            images_info = data["images_info"]
                            content_info.update({
                                "media_type": "images",
                                "images": images_info.get("images", []),
                                "width": images_info.get("width", 0),
                                "height": images_info.get("height", 0),
                            })
                        else:
                            content_info.update({
                                "media_type": "image",
                                "media_url": data.get("pic", ""),
                            })
                else:
                    logging.warning(f"API标记为视频但缺少video_info: {content_info['title']}")
                    content_info.update({
                        "media_type": "image",
                        "media_url": data.get("pic", ""),
                    })
            else:
                # API没有明确的type字段，使用原有的fallback逻辑
                logging.info(f"API未提供明确的type字段({api_type})，使用fallback逻辑: {content_info['title']}")

                # 检查是否有video_info字段（视频内容）
                if "video_info" in data and data["video_info"]:
                    video_info = data["video_info"]
                    # 检查video_info是否有效
                    if (video_info.get("url") and video_info.get("url") != "不是视频没有信息") or \
                       (video_info.get("download")) or (video_info.get("download2")):
                        content_info.update({
                            "media_type": "video",
                            "media_url": video_info.get("url", ""),
                            "cover_url": video_info.get("pic", ""),
                            "width": video_info.get("width", 0),
                            "height": video_info.get("height", 0),
                            "size": video_info.get("size", ""),
                            "video_info": video_info,  # 保留完整的video_info对象
                        })
                    else:
                        # video_info无效，尝试图片
                        if "images_info" in data and data["images_info"] and data["images_info"].get("images"):
                            images_info = data["images_info"]
                            content_info.update({
                                "media_type": "images",
                                "images": images_info.get("images", []),
                                "width": images_info.get("width", 0),
                                "height": images_info.get("height", 0),
                            })
                        else:
                            content_info.update({
                                "media_type": "image",
                                "media_url": data.get("pic", ""),
                            })
                # 检查是否有images_info字段（图片内容）
                elif "images_info" in data and data["images_info"] and data["images_info"].get("images"):
                    images_info = data["images_info"]
                    content_info.update({
                        "media_type": "images",
                        "images": images_info.get("images", []),
                        "width": images_info.get("width", 0),
                        "height": images_info.get("height", 0),
                    })
                # 检查是否有pic_list字段（多张图片）
                elif "pic_list" in data and data["pic_list"]:
                    content_info.update({
                        "media_type": "images",
                        "images": data.get("pic_list", []),
                    })
                else:
                    # 使用封面图作为默认媒体
                    content_info.update({
                        "media_type": "image",
                        "media_url": data.get("pic", ""),
                    })

            # 提取音乐信息（如果有）
            if "music_info" in data and data["music_info"]:
                music_info = data["music_info"]
                content_info["music"] = {
                    "title": music_info.get("title", ""),
                    "author": music_info.get("author", ""),
                    "url": music_info.get("url", ""),
                    "duration": music_info.get("duration", ""),
                }

            logging.info(f"内容信息提取完成: {content_info['title']}, 媒体类型: {content_info.get('media_type', 'unknown')}")
            return content_info

        except Exception as e:
            logging.error(f"提取内容信息失败: {str(e)}", exc_info=True)
            return {}

    def generate_content_id(self, content_info: Dict) -> str:
        """
        生成内容的唯一标识

        Args:
            content_info: 内容信息

        Returns:
            str: 唯一标识
        """
        # 优先使用aweme_id，其次使用share_url的哈希值
        if content_info.get("aweme_id"):
            return content_info["aweme_id"]
        elif content_info.get("share_url"):
            return hashlib.md5(content_info["share_url"].encode()).hexdigest()
        else:
            # 使用标题和时间的组合作为fallback
            fallback_str = f"{content_info.get('title', '')}{content_info.get('time', '')}"
            return hashlib.md5(fallback_str.encode()).hexdigest()

    def validate_douyin_url(self, url: str) -> bool:
        """
        验证抖音URL格式

        Args:
            url: 待验证的URL

        Returns:
            bool: 是否为有效的抖音URL
        """
        try:
            parsed = urlparse(url)
            # 检查域名
            valid_domains = ['douyin.com', 'www.douyin.com', 'v.douyin.com']
            if parsed.netloc not in valid_domains:
                return False

            # 检查路径
            if not parsed.path or parsed.path == '/':
                return False

            return True

        except Exception as e:
            logging.error(f"验证抖音URL失败: {url}, 错误: {str(e)}")
            return False

    def clear_cache(self, douyin_url: str = None) -> bool:
        """
        清除缓存

        Args:
            douyin_url: 指定URL的缓存，如果为None则清除所有缓存

        Returns:
            bool: 是否成功
        """
        try:
            if douyin_url:
                # 清除指定URL的缓存
                cache_key = self._generate_cache_key(douyin_url)
                success = self.cache.delete(cache_key)
                logging.info(f"清除指定URL缓存: {douyin_url}, 成功: {success}")
                return success
            else:
                # 清除所有缓存
                success = self.cache.clear()
                logging.info(f"清除所有抖音API缓存, 成功: {success}")
                return success
        except Exception as e:
            logging.error(f"清除缓存失败: {str(e)}")
            return False

    def get_cache_info(self) -> Dict:
        """
        获取缓存信息

        Returns:
            Dict: 缓存统计信息
        """
        try:
            return self.cache.get_info()
        except Exception as e:
            logging.error(f"获取缓存信息失败: {str(e)}")
            return {"error": str(e)}

    def is_cache_hit(self, douyin_url: str) -> bool:
        """
        检查指定URL是否有缓存

        Args:
            douyin_url: 抖音用户主页链接

        Returns:
            bool: 是否有缓存
        """
        try:
            cache_key = self._generate_cache_key(douyin_url)
            return self.cache.exists(cache_key)
        except Exception as e:
            logging.error(f"检查缓存失败: {str(e)}")
            return False