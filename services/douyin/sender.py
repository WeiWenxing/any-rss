"""
抖音内容发送模块
专门处理抖音内容的发送逻辑，包括媒体下载、容错机制等
"""

import logging
import os
import tempfile
from typing import Tuple, List, Optional, Dict, Any
from telegram import Bot, InputMediaVideo, InputMediaPhoto
from telegram.error import TelegramError

from .manager import DouyinManager
from .formatter import DouyinFormatter


class DouyinSender:
    """抖音内容发送器"""

    def __init__(self):
        """初始化发送器"""
        self.manager = DouyinManager()
        self.formatter = DouyinFormatter()

    async def send_content(self, bot: Bot, content_info: dict, douyin_url: str, target_chat_id: str) -> None:
        """
        发送抖音内容到指定频道 - 统一使用MediaGroup形式

        Args:
            bot: Telegram Bot实例
            content_info: 内容信息
            douyin_url: 抖音用户链接
            target_chat_id: 目标频道ID
        """
        try:
            logging.info(f"开始发送抖音内容: {content_info.get('title', '无标题')} to {target_chat_id}")

            # 格式化caption
            caption = self.formatter.format_caption(content_info)
            media_type = content_info.get("media_type", "")

            # 检查是否有媒体内容
            if not media_type or media_type not in ["video", "image", "images"]:
                logging.info(f"抖音内容无媒体文件，跳过发送: {content_info.get('title', '无标题')}")
                return

            # 根据媒体类型发送
            if media_type == "video":
                await self._send_video_content(bot, content_info, caption, target_chat_id)
            elif media_type == "images":
                await self._send_images_content(bot, content_info, caption, target_chat_id)
            elif media_type == "image":
                await self._send_single_image_content(bot, content_info, caption, target_chat_id)

            logging.info(f"抖音内容发送成功: {content_info.get('title', '无标题')}")

        except Exception as e:
            logging.error(f"发送抖音内容失败: {str(e)}", exc_info=True)
            raise

    async def _send_video_content(self, bot: Bot, content_info: dict, caption: str, target_chat_id: str) -> None:
        """
        发送视频内容，支持两阶段容错机制：
        第一阶段：直接发送URL链接 (url -> download -> download2)
        第二阶段：下载文件发送 (download -> download2)

        Args:
            bot: Telegram Bot实例
            content_info: 内容信息
            caption: 媒体标题
            target_chat_id: 目标频道ID
        """
        video_info = content_info.get("video_info", {})

        # 获取所有可能的视频URL，按优先级排序
        video_urls = self._get_video_urls_by_priority(video_info)

        if not video_urls:
            logging.warning(f"视频内容无可用URL: {content_info.get('title', '无标题')}")
            return

        # 第一阶段：尝试直接发送URL链接
        logging.info(f"第一阶段：尝试直接发送URL链接，共 {len(video_urls)} 个URL")
        for url_type, video_url in video_urls:
            try:
                logging.info(f"尝试直接发送视频URL ({url_type}): {video_url[:100]}...")

                # 创建媒体组（直接使用URL）
                media_group = [
                    InputMediaVideo(
                        media=video_url,
                        caption=caption,
                        parse_mode='Markdown'
                    )
                ]

                # 发送媒体组
                await bot.send_media_group(
                    chat_id=target_chat_id,
                    media=media_group
                )

                logging.info(f"视频URL发送成功 ({url_type}): {content_info.get('title', '无标题')}")
                return  # 成功发送，退出函数

            except TelegramError as telegram_error:
                logging.warning(f"Telegram URL发送失败 ({url_type}): {str(telegram_error)}")
                continue
            except Exception as e:
                logging.warning(f"处理视频URL失败 ({url_type}): {str(e)}")
                continue

        # 第一阶段全部失败，进入第二阶段：下载文件发送
        logging.info(f"第一阶段全部失败，进入第二阶段：下载文件发送")

        # 获取下载URL列表（跳过url，只用download和download2）
        download_urls = self._get_download_urls_by_priority(video_info)

        if not download_urls:
            raise Exception(f"所有视频URL都发送失败，且无可用下载链接")

        logging.info(f"第二阶段：尝试下载文件发送，共 {len(download_urls)} 个下载URL")
        for url_type, video_url in download_urls:
            try:
                logging.info(f"尝试下载并发送视频 ({url_type}): {video_url[:100]}...")

                # 下载视频文件
                success, error_msg, local_path = self.manager.download_and_save_media(
                    content_info, video_url, "video"
                )

                if not success:
                    logging.warning(f"视频下载失败 ({url_type}): {error_msg}")
                    continue

                try:
                    # 创建媒体组（使用本地文件）
                    media_group = [
                        InputMediaVideo(
                            media=open(local_path, 'rb'),
                            caption=caption,
                            parse_mode='Markdown'
                        )
                    ]

                    # 发送媒体组
                    await bot.send_media_group(
                        chat_id=target_chat_id,
                        media=media_group
                    )

                    logging.info(f"视频文件发送成功 ({url_type}): {content_info.get('title', '无标题')}")
                    return  # 成功发送，退出函数

                except TelegramError as telegram_error:
                    logging.warning(f"Telegram文件发送失败 ({url_type}): {str(telegram_error)}")
                    continue

                finally:
                    # 清理临时文件
                    self._cleanup_temp_file(local_path)

            except Exception as e:
                logging.warning(f"处理下载URL失败 ({url_type}): {str(e)}")
                continue

        # 两个阶段都失败了
        raise Exception(f"所有发送方式都失败：URL发送尝试了 {len(video_urls)} 个链接，文件发送尝试了 {len(download_urls)} 个链接")

    async def _send_images_content(self, bot: Bot, content_info: dict, caption: str, target_chat_id: str) -> None:
        """
        发送多图内容

        Args:
            bot: Telegram Bot实例
            content_info: 内容信息
            caption: 媒体标题
            target_chat_id: 目标频道ID
        """
        images = content_info.get("images", [])

        if not images:
            logging.warning(f"多图内容无图片URL: {content_info.get('title', '无标题')}")
            return

        media_group = []
        temp_files = []

        try:
            # 下载所有图片（最多10张，Telegram限制）
            for i, image_url in enumerate(images[:10]):
                try:
                    logging.info(f"下载图片 {i+1}/{min(len(images), 10)}: {image_url[:100]}...")

                    success, error_msg, local_path = self.manager.download_and_save_media(
                        content_info, image_url, "image"
                    )

                    if success:
                        media_group.append(
                            InputMediaPhoto(
                                media=open(local_path, 'rb'),
                                caption=caption if i == 0 else None,  # 只在第一张图片添加caption
                                parse_mode='Markdown'
                            )
                        )
                        temp_files.append(local_path)
                    else:
                        logging.warning(f"图片下载失败 {i+1}: {error_msg}")

                except Exception as e:
                    logging.warning(f"处理图片失败 {i+1}: {str(e)}")
                    continue

            if not media_group:
                raise Exception("所有图片下载都失败了")

            # 发送媒体组
            await bot.send_media_group(
                chat_id=target_chat_id,
                media=media_group
            )

            logging.info(f"多图发送成功: {len(media_group)} 张图片")

        finally:
            # 清理所有临时文件
            for temp_file in temp_files:
                self._cleanup_temp_file(temp_file)

    async def _send_single_image_content(self, bot: Bot, content_info: dict, caption: str, target_chat_id: str) -> None:
        """
        发送单图内容

        Args:
            bot: Telegram Bot实例
            content_info: 内容信息
            caption: 媒体标题
            target_chat_id: 目标频道ID
        """
        image_url = content_info.get("media_url", "")

        if not image_url:
            logging.warning(f"单图内容无图片URL: {content_info.get('title', '无标题')}")
            return

        try:
            logging.info(f"下载单图: {image_url[:100]}...")

            # 下载图片文件
            success, error_msg, local_path = self.manager.download_and_save_media(
                content_info, image_url, "image"
            )

            if not success:
                raise Exception(f"图片下载失败: {error_msg}")

            try:
                # 创建媒体组（只包含一张图片）
                media_group = [
                    InputMediaPhoto(
                        media=open(local_path, 'rb'),
                        caption=caption,
                        parse_mode='Markdown'
                    )
                ]

                # 发送媒体组
                await bot.send_media_group(
                    chat_id=target_chat_id,
                    media=media_group
                )

                logging.info(f"单图发送成功: {content_info.get('title', '无标题')}")

            finally:
                # 清理临时文件
                self._cleanup_temp_file(local_path)

        except Exception as e:
            logging.error(f"发送单图失败: {str(e)}", exc_info=True)
            raise

    def _get_video_urls_by_priority(self, video_info: dict) -> List[Tuple[str, str]]:
        """
        按优先级获取视频URL列表

        Args:
            video_info: 视频信息字典

        Returns:
            List[Tuple[str, str]]: [(url_type, url), ...] 按优先级排序
        """
        urls = []

        # 优先级1: url (主要播放链接)
        if video_info.get("url"):
            urls.append(("url", video_info["url"]))

        # 优先级2: download (下载链接1)
        if video_info.get("download"):
            urls.append(("download", video_info["download"]))

        # 优先级3: download2 (下载链接2)
        if video_info.get("download2"):
            urls.append(("download2", video_info["download2"]))

        logging.info(f"找到 {len(urls)} 个视频URL: {[url_type for url_type, _ in urls]}")
        return urls

    def _get_download_urls_by_priority(self, video_info: dict) -> List[Tuple[str, str]]:
        """
        按优先级获取下载URL列表

        Args:
            video_info: 视频信息字典

        Returns:
            List[Tuple[str, str]]: [(url_type, url), ...] 按优先级排序
        """
        urls = []

        # 优先级1: download (下载链接1)
        if video_info.get("download"):
            urls.append(("download", video_info["download"]))

        # 优先级2: download2 (下载链接2)
        if video_info.get("download2"):
            urls.append(("download2", video_info["download2"]))

        logging.info(f"找到 {len(urls)} 个下载URL: {[url_type for url_type, _ in urls]}")
        return urls

    def _cleanup_temp_file(self, file_path: str) -> None:
        """
        清理临时文件

        Args:
            file_path: 文件路径
        """
        try:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
                logging.debug(f"清理临时文件: {file_path}")
        except Exception as e:
            logging.warning(f"清理临时文件失败 {file_path}: {str(e)}")


# 全局发送器实例
douyin_sender = DouyinSender()


async def send_douyin_content(bot: Bot, content_info: dict, douyin_url: str, target_chat_id: str) -> None:
    """
    发送抖音内容的统一接口

    Args:
        bot: Telegram Bot实例
        content_info: 内容信息
        douyin_url: 抖音用户链接
        target_chat_id: 目标频道ID
    """
    await douyin_sender.send_content(bot, content_info, douyin_url, target_chat_id)