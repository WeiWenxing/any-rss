"""
抖音内容发送模块
专门处理抖音内容的发送逻辑，包括媒体下载、容错机制等
"""

import logging
import os
import tempfile
import asyncio
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

    async def send_content(self, bot: Bot, content_info: dict, douyin_url: str, target_chat_id: str):
        """
        发送抖音内容到指定频道 - 统一使用MediaGroup形式

        Args:
            bot: Telegram Bot实例
            content_info: 内容信息
            douyin_url: 抖音用户链接
            target_chat_id: 目标频道ID

        Returns:
            发送的消息对象或消息列表
        """
        try:
            logging.info(f"开始发送抖音内容: {content_info.get('title', '无标题')} to {target_chat_id}")

            # 格式化caption
            caption = self.formatter.format_caption(content_info)
            media_type = content_info.get("media_type", "")

            # 检查是否有媒体内容
            if not media_type or media_type not in ["video", "image", "images"]:
                logging.info(f"抖音内容无媒体文件，跳过发送: {content_info.get('title', '无标题')}")
                return None

            # 根据媒体类型发送
            if media_type == "video":
                message = await self._send_video_content(bot, content_info, caption, target_chat_id)
            elif media_type in ["image", "images"]:  # 统一处理所有图片类型
                message = await self._send_images_content(bot, content_info, caption, target_chat_id)
            else:
                return None

            logging.info(f"抖音内容发送成功: {content_info.get('title', '无标题')}")
            return message

        except Exception as e:
            logging.error(f"发送抖音内容失败: {str(e)}", exc_info=True)
            raise

    async def _send_video_content(self, bot: Bot, content_info: dict, caption: str, target_chat_id: str):
        """
        发送视频内容，支持两阶段容错机制：
        第一阶段：直接发送URL链接 (url -> download -> download2)
        第二阶段：下载文件发送 (download -> download2)

        Args:
            bot: Telegram Bot实例
            content_info: 内容信息
            caption: 媒体标题
            target_chat_id: 目标频道ID

        Returns:
            发送的消息列表
        """
        video_info = content_info.get("video_info", {})

        # 获取所有可能的视频URL，按优先级排序
        video_urls = self._get_video_urls_by_priority(video_info)

        if not video_urls:
            logging.warning(f"视频内容无可用URL: {content_info.get('title', '无标题')}")
            return None

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
                messages = await bot.send_media_group(
                    chat_id=target_chat_id,
                    media=media_group
                )

                logging.info(f"视频URL发送成功 ({url_type}): {content_info.get('title', '无标题')}")
                return messages  # 成功发送，返回消息列表

            except TelegramError as telegram_error:
                logging.warning(f"Telegram URL发送失败 ({url_type}): {str(telegram_error)}")
                continue
            except Exception as e:
                logging.warning(f"处理视频URL失败 ({url_type}): {str(e)}")
                continue

        # 第一阶段全部失败，进入第二阶段：下载文件发送
        logging.info(f"第一阶段全部失败，进入第二阶段：下载文件发送")

        # 阶段间等待，避免过快重试
        if video_urls:  # 如果第一阶段有尝试过
            logging.debug("第一阶段失败，等待2秒后进入第二阶段...")
            await asyncio.sleep(2)

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
                    messages = await bot.send_media_group(
                        chat_id=target_chat_id,
                        media=media_group
                    )

                    logging.info(f"视频文件发送成功 ({url_type}): {content_info.get('title', '无标题')}")
                    return messages  # 成功发送，返回消息列表

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

    async def _send_images_content(self, bot: Bot, content_info: dict, caption: str, target_chat_id: str):
        """
        发送多图内容 - 参考RSS策略，使用纯URL发送，支持分批处理

        Args:
            bot: Telegram Bot实例
            content_info: 内容信息
            caption: 媒体标题
            target_chat_id: 目标频道ID

        Returns:
            发送的消息列表（第一批的消息列表）
        """
        images = content_info.get("images", [])

        if not images:
            logging.warning(f"多图内容无图片URL: {content_info.get('title', '无标题')}")
            return None

        logging.info(f"开始发送多图内容: {len(images)} 张图片")

        # 计算分批方案（每批最多10张，参考RSS策略）
        batch_sizes = self._calculate_balanced_batches(len(images), max_per_batch=10)
        total_batches = len(batch_sizes)

        logging.info(f"📦 分批发送方案: {total_batches} 批，分批大小: {batch_sizes}")

        # 按批次发送
        image_index = 0
        any_batch_success = False
        first_batch_messages = None  # 保存第一批的消息列表用于返回

        for batch_num, batch_size in enumerate(batch_sizes, 1):
            # 获取当前批次的图片
            batch_images = images[image_index:image_index + batch_size]
            image_index += batch_size

            logging.info(f"📤 准备发送第 {batch_num}/{total_batches} 批，包含 {batch_size} 张图片")

            # 构建当前批次的caption
            if total_batches > 1:
                if batch_num == 1:
                    # 第一批：使用完整caption + 批次信息
                    batch_caption = f"{caption}\n\n📸 {batch_num}/{total_batches}"
                else:
                    # 后续批次：只显示批次信息
                    batch_caption = f"📸 {batch_num}/{total_batches}"
            else:
                # 只有一批，直接使用完整caption
                batch_caption = caption

            try:
                # 构建媒体组（纯URL发送，参考RSS策略）
                telegram_media = []
                for i, image_url in enumerate(batch_images):
                    media_item = InputMediaPhoto(
                        media=image_url,  # 直接使用URL，不下载
                        caption=batch_caption if i == 0 else None,  # 只在第一张图片添加caption
                        parse_mode='Markdown'
                    )
                    telegram_media.append(media_item)

                # 发送媒体组
                messages = await bot.send_media_group(
                    chat_id=target_chat_id,
                    media=telegram_media
                )

                logging.info(f"✅ 第 {batch_num}/{total_batches} 批图片发送成功 ({batch_size}张图片)")
                any_batch_success = True

                # 保存第一批的消息列表
                if batch_num == 1:
                    first_batch_messages = messages

            except Exception as e:
                logging.error(f"❌ 第 {batch_num}/{total_batches} 批图片发送失败: {str(e)}")
                continue

            # 批次间隔：避免连续发送触发flood control
            if batch_num < total_batches:  # 不是最后一批
                logging.debug(f"等待3秒后发送下一批图片...")
                await asyncio.sleep(3)  # 批次间隔3秒

        # 检查发送结果
        if not any_batch_success:
            raise Exception(f"所有 {total_batches} 批图片都发送失败")
        elif total_batches > 1:
            logging.info(f"🎉 多图发送完成: 成功发送了部分或全部批次")
        else:
            logging.info(f"🎉 图片发送成功: {len(images)} 张图片")

        return first_batch_messages  # 返回第一批的消息列表

    def _calculate_balanced_batches(self, total_images: int, max_per_batch: int = 10) -> list[int]:
        """
        计算均衡的图片分批方案（参考RSS实现）

        Args:
            total_images: 总图片数量
            max_per_batch: 每批最大图片数量

        Returns:
            list[int]: 每批的图片数量列表
        """
        if total_images <= max_per_batch:
            return [total_images]

        # 计算需要多少批
        num_batches = (total_images + max_per_batch - 1) // max_per_batch

        # 计算基础每批数量
        base_size = total_images // num_batches
        remainder = total_images % num_batches

        # 构建分批方案：前remainder批多1张，后面的批次为base_size
        batch_sizes = []
        for i in range(num_batches):
            if i < remainder:
                batch_sizes.append(base_size + 1)
            else:
                batch_sizes.append(base_size)

        logging.info(f"均衡分批方案: 总数{total_images}, 分{num_batches}批, 方案{batch_sizes}")
        return batch_sizes

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


async def send_douyin_content(bot: Bot, content_info: dict, douyin_url: str, target_chat_id: str):
    """
    发送抖音内容的统一接口

    Args:
        bot: Telegram Bot实例
        content_info: 内容信息
        douyin_url: 抖音用户链接
        target_chat_id: 目标频道ID

    Returns:
        发送的消息对象或消息列表
    """
    return await douyin_sender.send_content(bot, content_info, douyin_url, target_chat_id)