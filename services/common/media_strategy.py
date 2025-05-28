"""
通用媒体发送策略模块
简化的媒体组发送策略：URL直接 -> 视频下载混合 -> 文本降级
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
    URL_DIRECT = "url_direct"           # 全部URL直接发送
    VIDEO_DOWNLOAD_MIX = "video_download_mix"  # 视频下载+图片URL混合
    TEXT_FALLBACK = "text_fallback"     # 降级到文本


class MediaAccessError(Exception):
    """媒体访问错误，用于触发文本降级"""
    pass


class MediaInfo:
    """媒体文件信息类"""
    def __init__(self, url: str, media_type: str, poster_url: str = None):
        self.url = url
        self.media_type = media_type  # 'image' or 'video'
        self.poster_url = poster_url  # 视频封面图URL（仅对视频有效）
        self.local_path: Optional[str] = None
        self.local_poster_path: Optional[str] = None  # 本地封面图路径


class MediaSendStrategyManager:
    """媒体发送策略管理器 - 简化版"""

    def __init__(self):
        """初始化媒体发送策略管理器"""
        logging.info(f"📋 媒体发送策略管理器初始化: 媒体组统一策略模式")

    def analyze_media_files(self, media_list: List[Dict]) -> List[MediaInfo]:
        """
        分析媒体文件列表，转换为MediaInfo对象

        Args:
            media_list: 媒体文件列表，每个元素包含 {'url': str, 'type': str, 'poster': str(可选)}

        Returns:
            List[MediaInfo]: 媒体信息列表
        """
        if not media_list:
            return []

        logging.info(f"🔍 分析媒体组: {len(media_list)} 个文件")

        analyzed_media = []
        video_count = 0
        image_count = 0

        for media_dict in media_list:
            media_url = media_dict['url']
            media_type = media_dict['type']
            poster_url = media_dict.get('poster')

            # 创建媒体信息对象
            media_info = MediaInfo(
                url=media_url,
                media_type=media_type,
                poster_url=poster_url
            )
            analyzed_media.append(media_info)

            # 统计媒体类型
            if media_type == 'video':
                video_count += 1
            else:
                image_count += 1

        logging.info(f"   📊 媒体组成: {image_count} 张图片, {video_count} 个视频")
        return analyzed_media

    def has_videos(self, media_list: List[MediaInfo]) -> bool:
        """
        检查媒体组是否包含视频

        Args:
            media_list: 媒体信息列表

        Returns:
            bool: 是否包含视频
        """
        return any(media.media_type == 'video' for media in media_list)


class MediaSender:
    """媒体发送器 - 简化版"""

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
        caption: str = "",
        parse_mode: Optional[str] = None
    ) -> List[Message]:
        """
        使用简化策略发送媒体组

        Args:
            chat_id: 目标聊天ID
            media_list: 媒体信息列表
            caption: 标题
            parse_mode: 解析模式

        Returns:
            List[Message]: 发送成功的消息列表

        Raises:
            MediaAccessError: 所有策略都失败时抛出，由调用方处理文本降级
        """
        if not media_list:
            logging.warning("没有媒体可发送")
            return []

        logging.info(f"🚀 开始发送媒体组: {len(media_list)} 个文件")

        # 策略1: 全部URL直接发送
        try:
            logging.info(f"📡 策略1: 尝试全部URL直接发送")
            messages = await self._send_all_url_direct(chat_id, media_list, caption, parse_mode)
            logging.info(f"✅ 策略1成功: 全部URL直接发送完成")
            return messages
        except Exception as e:
            logging.warning(f"⚠️ 策略1失败: {str(e)}")

        # 策略2: 视频下载+图片URL混合（仅当有视频时）
        if self.strategy_manager.has_videos(media_list):
            try:
                logging.info(f"📥 策略2: 尝试视频下载+图片URL混合发送")
                messages = await self._send_video_download_mix(chat_id, media_list, caption, parse_mode)
                logging.info(f"✅ 策略2成功: 视频下载混合发送完成")
                return messages
            except Exception as e:
                logging.warning(f"⚠️ 策略2失败: {str(e)}")
        else:
            logging.info(f"📝 跳过策略2: 媒体组无视频，直接降级到文本")

        # 策略3: 文本降级
        logging.error(f"❌ 所有媒体发送策略都失败，触发文本降级")
        raise MediaAccessError("所有媒体发送策略都失败")

    async def _send_all_url_direct(self, chat_id: str, media_list: List[MediaInfo], caption: str, parse_mode: Optional[str] = None) -> List[Message]:
        """
        策略1: 全部URL直接发送

        Args:
            chat_id: 目标聊天ID
            media_list: 媒体信息列表
            caption: 标题
            parse_mode: 解析模式

        Returns:
            List[Message]: 发送成功的消息列表
        """
        # 构建媒体组
        telegram_media = []
        for i, media_info in enumerate(media_list):
            if media_info.media_type == 'video':
                media_item = InputMediaVideo(
                    media=media_info.url,
                    caption=caption if i == 0 else None,
                    parse_mode=parse_mode
                )
            else:  # image
                media_item = InputMediaPhoto(
                    media=media_info.url,
                    caption=caption if i == 0 else None,
                    parse_mode=parse_mode
                )
            telegram_media.append(media_item)

        # 发送媒体组
        sent_messages = await self.bot.send_media_group(chat_id=chat_id, media=telegram_media)
        return sent_messages

    async def _send_video_download_mix(self, chat_id: str, media_list: List[MediaInfo], caption: str, parse_mode: Optional[str] = None) -> List[Message]:
        """
        策略2: 视频下载+图片URL混合发送

        Args:
            chat_id: 目标聊天ID
            media_list: 媒体信息列表
            caption: 标题
            parse_mode: 解析模式

        Returns:
            List[Message]: 发送成功的消息列表
        """
        downloaded_videos = []
        try:
            # 只下载视频文件
            video_list = [media for media in media_list if media.media_type == 'video']
            logging.info(f"📥 开始下载 {len(video_list)} 个视频文件...")

            for i, media_info in enumerate(video_list, 1):
                logging.info(f"📥 下载视频 {i}/{len(video_list)}: {media_info.url}")
                local_path = await self._download_media_file(media_info.url, media_info.media_type)
                if local_path:
                    media_info.local_path = local_path

                    # 如果有封面图，尝试下载封面图
                    if media_info.poster_url:
                        logging.info(f"📥 下载视频封面图: {media_info.poster_url}")
                        poster_path = await self._download_media_file(media_info.poster_url, 'image')
                        if poster_path:
                            media_info.local_poster_path = poster_path
                            logging.info(f"✅ 封面图下载成功")

                    downloaded_videos.append(media_info)
                    logging.info(f"✅ 视频 {i} 下载成功")
                else:
                    logging.error(f"❌ 视频 {i} 下载失败")
                    raise Exception(f"视频下载失败: {media_info.url}")

            # 构建混合媒体组（视频用本地文件，图片用URL）
            logging.info(f"📤 开始发送混合媒体组...")
            telegram_media = []

            for i, media_info in enumerate(media_list):
                if media_info.media_type == 'video':
                    # 视频使用本地文件
                    with open(media_info.local_path, 'rb') as f:
                        file_content = f.read()

                    video_kwargs = {
                        'media': file_content,
                        'caption': caption if i == 0 else None,
                        'parse_mode': parse_mode
                    }

                    # 如果有本地封面图，添加thumbnail参数
                    if media_info.local_poster_path and os.path.exists(media_info.local_poster_path):
                        with open(media_info.local_poster_path, 'rb') as poster_f:
                            video_kwargs['thumbnail'] = poster_f.read()
                        logging.info(f"📸 视频 {i} 使用自定义封面图")

                    media_item = InputMediaVideo(**video_kwargs)
                else:
                    # 图片使用URL
                    media_item = InputMediaPhoto(
                        media=media_info.url,
                        caption=caption if i == 0 else None,
                        parse_mode=parse_mode
                    )
                telegram_media.append(media_item)

            # 发送媒体组
            sent_messages = await self.bot.send_media_group(chat_id=chat_id, media=telegram_media)
            return sent_messages

        finally:
            # 清理临时文件
            self._cleanup_temp_files(downloaded_videos)

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
            logging.error(f"下载媒体文件失败: {url}, 错误: {str(e)}", exc_info=True)
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
    strategy_manager = MediaSendStrategyManager()
    media_sender = MediaSender(bot, strategy_manager)

    logging.info(f"✅ 媒体策略系统初始化完成: 媒体组统一策略模式")

    return strategy_manager, media_sender