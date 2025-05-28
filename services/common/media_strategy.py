"""
通用媒体发送策略模块
定义清晰的媒体发送策略和降级机制
"""

import logging
import os
import tempfile
import asyncio
from enum import Enum
from typing import List, Dict, Tuple, Optional
from telegram import Bot, InputMediaPhoto, InputMediaVideo, Message


class MediaSendStrategy(Enum):
    """媒体发送策略枚举"""
    URL_DIRECT = "url_direct"           # 直接URL发送
    DOWNLOAD_UPLOAD = "download_upload" # 下载后上传
    TEXT_FALLBACK = "text_fallback"     # 降级到文本


class MediaSendResult(Enum):
    """媒体发送结果枚举"""
    SUCCESS = "success"                 # 发送成功
    FAILED_RETRY = "failed_retry"       # 失败，可重试
    FAILED_FALLBACK = "failed_fallback" # 失败，需降级


class MediaInfo:
    """媒体文件信息类"""
    def __init__(self, url: str, media_type: str, size_mb: float = 0, accessible: bool = True, poster_url: str = None):
        self.url = url
        self.media_type = media_type  # 'image' or 'video'
        self.size_mb = size_mb
        self.accessible = accessible
        self.poster_url = poster_url  # 视频封面图URL（仅对视频有效）
        self.local_path: Optional[str] = None
        self.local_poster_path: Optional[str] = None  # 本地封面图路径
        self.send_strategy: Optional[MediaSendStrategy] = None


class MediaSendStrategyManager:
    """媒体发送策略管理器"""

    def __init__(self, use_local_api: bool = False):
        """
        初始化策略管理器

        Args:
            use_local_api: 是否使用本地API（影响大文件阈值）
        """
        self.use_local_api = use_local_api
        # TODO: 需要从RSS模块的config中获取配置，暂时使用硬编码
        self.large_file_threshold_mb = 20 if use_local_api else 10
        logging.info(f"📋 媒体发送策略管理器初始化: 本地API={use_local_api}, 大文件阈值={self.large_file_threshold_mb}MB")

    def analyze_media_files(self, media_list: List[Dict]) -> List[MediaInfo]:
        """
        分析媒体文件列表，确定发送策略

        Args:
            media_list: 媒体信息列表 [{'url': str, 'type': str, 'poster': str}, ...]

        Returns:
            List[MediaInfo]: 分析后的媒体信息列表
        """
        logging.info(f"🔍 开始分析 {len(media_list)} 个媒体文件...")

        analyzed_media = []
        for i, media_dict in enumerate(media_list, 1):
            media_url = media_dict['url']
            media_type = media_dict['type']
            poster_url = media_dict.get('poster')  # 提取封面图URL

            # 检查文件可访问性和大小
            accessible, error_msg, size_mb = self._check_media_accessibility(media_url)

            # 创建媒体信息对象
            media_info = MediaInfo(
                url=media_url,
                media_type=media_type,
                size_mb=size_mb,
                accessible=accessible,
                poster_url=poster_url
            )

            # 确定发送策略
            media_info.send_strategy = self._determine_send_strategy(media_info)

            analyzed_media.append(media_info)

            # 记录分析结果
            strategy_name = media_info.send_strategy.value
            poster_info = f" (封面: {poster_url})" if poster_url else ""
            if accessible:
                logging.info(f"   📁 {media_type}{i}: {size_mb:.1f}MB → 策略: {strategy_name}{poster_info}")
            else:
                logging.warning(f"   ❌ {media_type}{i}: 无法访问 ({error_msg}) → 策略: {strategy_name}{poster_info}")

        return analyzed_media

    def _determine_send_strategy(self, media_info: MediaInfo) -> MediaSendStrategy:
        """
        确定单个媒体文件的发送策略

        Args:
            media_info: 媒体文件信息

        Returns:
            MediaSendStrategy: 发送策略
        """
        # 如果文件无法访问，直接降级到文本
        if not media_info.accessible:
            return MediaSendStrategy.TEXT_FALLBACK

        # 如果文件大小超过阈值，直接使用下载上传策略
        if media_info.size_mb > self.large_file_threshold_mb:
            logging.debug(f"文件 {media_info.url} 大小 {media_info.size_mb:.1f}MB 超过阈值 {self.large_file_threshold_mb}MB，使用下载上传策略")
            return MediaSendStrategy.DOWNLOAD_UPLOAD

        # 默认使用URL直接发送
        return MediaSendStrategy.URL_DIRECT

    def _check_media_accessibility(self, media_url: str) -> Tuple[bool, str, float]:
        """
        检查媒体文件的可访问性和大小

        Args:
            media_url: 媒体URL

        Returns:
            Tuple[bool, str, float]: (是否可访问, 错误信息, 文件大小MB)
        """
        # TODO: 需要实现网络检查逻辑，暂时返回默认值
        try:
            import requests
            response = requests.head(media_url, timeout=10)
            if response.status_code == 200:
                content_length = response.headers.get('content-length')
                size_mb = int(content_length) / (1024 * 1024) if content_length else 0
                return True, "", size_mb
            else:
                return False, f"HTTP {response.status_code}", 0
        except Exception as e:
            return False, str(e), 0


class MediaSender:
    """媒体发送器"""

    def __init__(self, bot: Bot, strategy_manager: MediaSendStrategyManager):
        """
        初始化媒体发送器

        Args:
            bot: Telegram Bot实例
            strategy_manager: 策略管理器
        """
        self.bot = bot
        self.strategy_manager = strategy_manager

    async def send_media_group_with_strategy(
        self,
        chat_id: str,
        media_list: List[MediaInfo],
        caption: str = ""
    ) -> List[Message]:
        """
        使用策略发送媒体组

        Args:
            chat_id: 目标聊天ID
            media_list: 媒体信息列表
            caption: 标题

        Returns:
            List[Message]: 发送成功的消息列表，失败返回空列表
        """
        if not media_list:
            logging.warning("没有媒体可发送")
            return []

        logging.info(f"🚀 开始发送媒体组: {len(media_list)} 个文件")

        # 按策略分组
        url_direct_media = [m for m in media_list if m.send_strategy == MediaSendStrategy.URL_DIRECT]
        download_upload_media = [m for m in media_list if m.send_strategy == MediaSendStrategy.DOWNLOAD_UPLOAD]

        sent_messages = []

        # 1. 先尝试URL直接发送的媒体
        if url_direct_media:
            url_messages = await self._send_url_direct_group(chat_id, url_direct_media, caption)

            # 如果URL发送成功，记录消息
            if url_messages:
                sent_messages.extend(url_messages)
            else:
                # 如果URL发送失败，将这些媒体改为下载上传策略
                logging.info("URL直接发送失败，将这些媒体改为下载上传策略")
                for media in url_direct_media:
                    media.send_strategy = MediaSendStrategy.DOWNLOAD_UPLOAD
                download_upload_media.extend(url_direct_media)

        # 2. 处理需要下载上传的媒体
        if download_upload_media:
            download_messages = await self._send_download_upload_group(chat_id, download_upload_media, caption if not sent_messages else "")
            if download_messages:
                sent_messages.extend(download_messages)

        return sent_messages

    async def _send_url_direct_group(self, chat_id: str, media_list: List[MediaInfo], caption: str) -> List[Message]:
        """
        直接使用URL发送媒体组

        Args:
            chat_id: 目标聊天ID
            media_list: 媒体信息列表
            caption: 标题

        Returns:
            List[Message]: 发送成功的消息列表，失败返回空列表
        """
        try:
            logging.info(f"📡 尝试URL直接发送 {len(media_list)} 个媒体文件")

            # 构建媒体组
            telegram_media = []
            for i, media_info in enumerate(media_list):
                if media_info.media_type == 'video':
                    media_item = InputMediaVideo(
                        media=media_info.url,
                        caption=caption if i == 0 else None
                    )
                else:  # image
                    media_item = InputMediaPhoto(
                        media=media_info.url,
                        caption=caption if i == 0 else None
                    )
                telegram_media.append(media_item)

            # 发送媒体组
            sent_messages = await self.bot.send_media_group(chat_id=chat_id, media=telegram_media)
            logging.info(f"✅ URL直接发送成功: {len(media_list)} 个文件")
            return sent_messages

        except Exception as e:
            logging.error(f"❌ URL直接发送失败: {str(e)}")
            return []

    async def _send_download_upload_group(self, chat_id: str, media_list: List[MediaInfo], caption: str) -> List[Message]:
        """
        下载后上传发送媒体组

        Args:
            chat_id: 目标聊天ID
            media_list: 媒体信息列表
            caption: 标题

        Returns:
            List[Message]: 发送成功的消息列表，失败返回空列表
        """
        downloaded_files = []
        try:
            logging.info(f"📥 开始下载 {len(media_list)} 个媒体文件...")

            # 下载所有文件
            for i, media_info in enumerate(media_list, 1):
                logging.info(f"📥 下载文件 {i}/{len(media_list)}: {media_info.url}")
                local_path = await self._download_media_file(media_info.url, media_info.media_type)
                if local_path:
                    media_info.local_path = local_path

                    # 如果是视频且有封面图，尝试下载封面图
                    if media_info.media_type == 'video' and media_info.poster_url:
                        logging.info(f"📥 下载视频封面图: {media_info.poster_url}")
                        poster_path = await self._download_media_file(media_info.poster_url, 'image')
                        if poster_path:
                            media_info.local_poster_path = poster_path
                            logging.info(f"✅ 封面图下载成功")
                        else:
                            logging.warning(f"❌ 封面图下载失败，将使用默认封面")

                    downloaded_files.append(media_info)
                    logging.info(f"✅ 文件 {i} 下载成功")
                else:
                    logging.error(f"❌ 文件 {i} 下载失败")

            if not downloaded_files:
                logging.error("所有文件下载失败")
                return []

            # 构建媒体组
            logging.info(f"📤 开始上传 {len(downloaded_files)} 个文件...")
            telegram_media = []
            for i, media_info in enumerate(downloaded_files):
                with open(media_info.local_path, 'rb') as f:
                    file_content = f.read()

                if media_info.media_type == 'video':
                    # 构建视频媒体项，如果有封面图则使用
                    video_kwargs = {
                        'media': file_content,
                        'caption': caption if i == 0 else None
                    }

                    # 如果有本地封面图，添加thumbnail参数
                    if media_info.local_poster_path and os.path.exists(media_info.local_poster_path):
                        with open(media_info.local_poster_path, 'rb') as poster_f:
                            video_kwargs['thumbnail'] = poster_f.read()
                        logging.info(f"📸 视频 {i} 使用自定义封面图")

                    media_item = InputMediaVideo(**video_kwargs)
                else:  # image
                    media_item = InputMediaPhoto(
                        media=file_content,
                        caption=caption if i == 0 else None
                    )
                telegram_media.append(media_item)

            # 发送媒体组
            sent_messages = await self.bot.send_media_group(chat_id=chat_id, media=telegram_media)
            logging.info(f"✅ 下载上传发送成功: {len(downloaded_files)} 个文件")
            return sent_messages

        except Exception as e:
            logging.error(f"❌ 下载上传发送失败: {str(e)}", exc_info=True)
            return []
        finally:
            # 清理临时文件
            self._cleanup_temp_files(downloaded_files)

    async def _download_media_file(self, url: str, media_type: str) -> Optional[str]:
        """
        下载媒体文件到临时目录

        Args:
            url: 媒体URL
            media_type: 媒体类型

        Returns:
            Optional[str]: 下载的文件路径，失败返回None
        """
        try:
            # 解析URL获取文件扩展名
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            path_parts = parsed_url.path.split('.')

            if len(path_parts) > 1:
                extension = path_parts[-1].split('?')[0]  # 去掉查询参数
            else:
                # 根据媒体类型设置默认扩展名
                extension = 'mp4' if media_type == 'video' else 'jpg'

            # 创建临时文件
            temp_dir = tempfile.gettempdir()
            temp_filename = f"telegram_media_{os.getpid()}_{id(url)}.{extension}"
            temp_path = os.path.join(temp_dir, temp_filename)

            # 下载文件
            import requests
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            with open(temp_path, 'wb') as f:
                f.write(response.content)

            file_size = os.path.getsize(temp_path)
            logging.info(f"文件下载完成: {temp_path}, 大小: {file_size / (1024*1024):.2f}MB")
            return temp_path

        except Exception as e:
            logging.error(f"下载媒体文件失败: {url}, 错误: {str(e)}")
            return None

    def _cleanup_temp_files(self, media_list: List[MediaInfo]) -> None:
        """
        清理临时文件

        Args:
            media_list: 媒体信息列表
        """
        for media_info in media_list:
            # 清理主媒体文件
            if media_info.local_path and os.path.exists(media_info.local_path):
                try:
                    os.remove(media_info.local_path)
                    logging.info(f"🗑️ 清理临时文件: {media_info.local_path}")
                except Exception as e:
                    logging.error(f"清理临时文件失败: {str(e)}")

            # 清理封面图文件
            if media_info.local_poster_path and os.path.exists(media_info.local_poster_path):
                try:
                    os.remove(media_info.local_poster_path)
                    logging.info(f"🗑️ 清理封面图临时文件: {media_info.local_poster_path}")
                except Exception as e:
                    logging.error(f"清理封面图临时文件失败: {str(e)}")


# 工厂函数
def create_media_strategy_manager(bot: Bot) -> Tuple[MediaSendStrategyManager, MediaSender]:
    """
    创建媒体策略管理器和发送器

    Args:
        bot: Telegram Bot实例

    Returns:
        Tuple[MediaSendStrategyManager, MediaSender]: 策略管理器和发送器
    """
    # 检测是否使用本地API
    use_local_api = False
    if hasattr(bot, '_base_url') and bot._base_url:
        use_local_api = "localhost" in bot._base_url or "127.0.0.1" in bot._base_url

    strategy_manager = MediaSendStrategyManager(use_local_api=use_local_api)
    media_sender = MediaSender(bot, strategy_manager)

    logging.info(f"✅ 媒体策略系统初始化完成: 本地API={use_local_api}")

    return strategy_manager, media_sender 