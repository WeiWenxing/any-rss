"""
RSS消息发送模块
负责处理所有与消息发送相关的功能
"""

import logging
import asyncio
import re
from telegram import Bot, InputMediaPhoto
from datetime import datetime
from urllib.parse import urlparse


def extract_and_clean_images(content: str) -> list[str]:
    """
    提取并清理图片URL

    Args:
        content: HTML内容

    Returns:
        list[str]: 清理后的有效图片URL列表
    """
    images = []
    if not content:
        return images

    img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
    raw_images = re.findall(img_pattern, content, re.IGNORECASE)
    logging.info(f"提取到 {len(raw_images)} 张原始图片")

    # 清理和验证图片URL
    for img_url in raw_images:
        # 清理HTML实体编码
        clean_url = img_url.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        clean_url = clean_url.replace('&quot;', '"').strip()

        # 过滤掉明显的小图标和装饰图片
        if any(keyword in clean_url.lower() for keyword in ['icon', 'logo', 'avatar', 'emoji', 'button']):
            logging.debug(f"过滤装饰图片: {clean_url}")
            continue

        # 验证URL格式
        if clean_url.startswith(('http://', 'https://')):
            images.append(clean_url)
            logging.debug(f"添加有效图片: {clean_url}")
        else:
            logging.warning(f"跳过无效图片URL: {clean_url}")

    logging.info(f"清理后有效图片数量: {len(images)}")

    # 记录前几张图片URL用于调试
    for i, img_url in enumerate(images[:3], 1):
        logging.info(f"图片{i}: {img_url}")

    return images


def calculate_balanced_batches(total_images: int, max_per_batch: int = 10) -> list[int]:
    """
    计算均衡的图片分批方案

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


async def send_image_groups_with_caption(
    bot: Bot,
    chat_id: str,
    title: str,
    author: str,
    images: list[str],
    full_caption: str = None
) -> None:
    """
    发送图片组，支持两种caption格式：
    1. 简洁格式：#作者 + title + 批次信息（用于图片为主模式）
    2. 完整格式：传入完整的caption内容（用于文字为主模式）

    Args:
        bot: Telegram Bot实例
        chat_id: 目标聊天ID
        title: 标题
        author: 作者
        images: 图片URL列表
        full_caption: 完整的caption内容（可选，如果提供则使用完整格式）
    """
    if not images:
        logging.warning("send_image_groups_with_caption: 没有图片可发送")
        return

    # 判断使用哪种caption格式
    use_full_caption = full_caption is not None

    if use_full_caption:
        logging.info(f"开始发送带完整caption的图片组: 图片数量={len(images)}, caption长度={len(full_caption)}")

        # 确保caption不超过Telegram限制（1024字符）
        max_caption_length = 1024
        if len(full_caption) > max_caption_length:
            full_caption = full_caption[:max_caption_length-3] + "..."
            logging.info(f"Caption过长已截断到 {len(full_caption)} 字符")
    else:
        logging.info(f"开始发送图片组: 标题='{title}', 作者='{author}', 图片数量={len(images)}")

        # 截断标题（Telegram caption限制1024字符）
        max_title_length = 100
        original_title = title
        if len(title) > max_title_length:
            title = title[:max_title_length] + "..."
            logging.info(f"标题过长已截断: '{original_title}' -> '{title}'")

    # 计算均衡的分批方案
    batch_sizes = calculate_balanced_batches(len(images), max_per_batch=10)
    total_batches = len(batch_sizes)

    logging.info(f"将发送 {total_batches} 个媒体组，分批方案: {batch_sizes}")

    # 按照分批方案发送图片
    image_index = 0
    for batch_num, batch_size in enumerate(batch_sizes, 1):
        # 获取当前批次的图片
        batch_images = images[image_index:image_index + batch_size]
        image_index += batch_size

        logging.info(f"准备发送第 {batch_num}/{total_batches} 批，包含 {batch_size} 张图片")

        # 构建caption
        if use_full_caption:
            # 完整caption格式
            if batch_num == 1:
                # 第一批：使用完整caption
                if total_batches > 1:
                    # 如果有多批，在第一批caption后添加批次信息（前面加空格）
                    caption = f"{full_caption}\n\n {batch_num}/{total_batches}"
                else:
                    # 只有一批，直接使用完整caption
                    caption = full_caption
            else:
                # 后续批次：只显示批次信息（前面加空格）
                caption = f" {batch_num}/{total_batches}"
        else:
            # 简洁caption格式：#作者 + title + 批次信息
            caption_parts = []

            # 添加作者（如果有）
            if author:
                caption_parts.append(f"#{author}")
                logging.debug(f"添加作者标签: #{author}")

            # 添加标题
            caption_parts.append(title)

            # 只在多批次时显示批次信息
            if total_batches > 1:
                batch_info = f"{batch_num}/{total_batches}"
                caption_parts.append(batch_info)
                logging.debug(f"添加批次信息: {batch_info}")

            caption = " ".join(caption_parts)

        logging.info(f"第 {batch_num} 批caption长度: {len(caption)}")

        # 构建媒体组
        media_list = []

        # 每个批次的第一张图片包含caption
        for j, img_url in enumerate(batch_images):
            if j == 0:  # 每批的第一张图片包含caption
                media_list.append(InputMediaPhoto(media=img_url, caption=caption))
                logging.debug(f"第 {batch_num} 批第1张图片(带caption): {img_url}")
            else:
                media_list.append(InputMediaPhoto(media=img_url))
                logging.debug(f"第 {batch_num} 批第{j+1}张图片: {img_url}")

        try:
            # 发送媒体组
            await bot.send_media_group(chat_id=chat_id, media=media_list)
            logging.info(f"✅ 成功发送第 {batch_num}/{total_batches} 批媒体组 ({batch_size}张图片)")
        except Exception as e:
            logging.error(f"❌ 发送第 {batch_num} 批媒体组失败: {str(e)}")

            # 如果是图片无法访问的错误，记录详细信息
            if "webpage_media_empty" in str(e):
                logging.error(f"图片无法访问错误，批次 {batch_num} 的图片URL:")
                for j, img_url in enumerate(batch_images):
                    logging.error(f"  图片{j+1}: {img_url}")
                # 继续处理下一批，不中断整个流程
                continue


async def send_text_message(
    bot: Bot,
    chat_id: str,
    title: str,
    link: str,
    content: str,
    published_time: str
) -> None:
    """
    发送纯文字消息（文字为主模式）
    """
    try:
        # 构建消息内容
        message_parts = []

        # 添加标题
        if title:
            message_parts.append(f"📰 {title}")

        # 添加内容（限制长度）
        if content:
            # 清理HTML标签
            clean_content = re.sub(r'<[^>]+>', '', content)
            clean_content = clean_content.replace('&nbsp;', ' ').replace('&amp;', '&')
            clean_content = clean_content.replace('&lt;', '<').replace('&gt;', '>')
            clean_content = clean_content.replace('&quot;', '"').strip()

            # 限制内容长度
            max_content_length = 500
            if len(clean_content) > max_content_length:
                clean_content = clean_content[:max_content_length] + "..."

            if clean_content:
                message_parts.append(f"\n{clean_content}")

        # 添加发布时间
        if published_time:
            message_parts.append(f"\n⏰ {published_time}")

        # 添加链接
        if link:
            message_parts.append(f"\n🔗 {link}")

        message = "".join(message_parts)

        # 发送消息
        await bot.send_message(chat_id=chat_id, text=message)
        logging.info(f"✅ 文字消息发送成功: '{title}'")

    except Exception as e:
        logging.error(f"❌ 发送文字消息失败: '{title}', 错误: {str(e)}")
        raise


async def send_update_notification(
    bot: Bot,
    url: str,
    new_entries: list[dict],
    xml_content: str | None,
    target_chat: str = None,
) -> None:
    """
    发送Feed更新通知，包括新增条目列表。
    使用智能消息发送：
    - 图片为主模式（≥2张图片）：媒体组 + 简洁caption
    - 文字为主模式（<2张图片）：完整文字内容 + 图片补充
    - 支持均衡分批，每批最多10张图片，分布更均匀
    """
    from core.config import telegram_config
    from .entry_processor import process_and_send_entry

    chat_id = target_chat or telegram_config["target_chat"]
    if not chat_id:
        logging.error("未配置发送目标，请检查TELEGRAM_TARGET_CHAT环境变量")
        return

    domain = urlparse(url).netloc

    try:
        # 只发送条目内容，不发送开始和结束通知
        if new_entries:
            logging.info(f"开始发送 {len(new_entries)} 个条目 for {domain}")

            for i, entry in enumerate(new_entries, 1):
                try:
                    # 发送条目消息（包含图片）
                    await process_and_send_entry(bot, chat_id, entry, i, len(new_entries))
                    logging.info(f"已发送条目: {entry.get('title', 'Unknown')}")

                    # 控制发送速度，避免flood exceed
                    # Telegram限制：同一聊天每秒最多1条消息，每分钟最多20条消息
                    if i % 10 == 0:  # 每10条消息暂停1分钟
                        logging.info(f"已发送10条消息，暂停60秒避免flood exceed...")
                        await asyncio.sleep(60)
                    else:
                        # 每条消息间隔8秒，确保不会触发flood control
                        logging.debug(f"等待8秒后发送下一条目...")
                        await asyncio.sleep(8)

                except Exception as e:
                    logging.error(f"发送条目失败: {entry.get('title', 'Unknown')}, 错误: {str(e)}")
                    # 出错后也要等待，避免连续错误
                    await asyncio.sleep(5)
                    continue

            logging.info(f"已发送 {len(new_entries)} 个条目 for {domain}")
        else:
            logging.info(f"{domain} 无新增内容，跳过发送")
    except Exception as e:
        logging.error(f"发送Feed更新消息失败 for {url}: {str(e)}", exc_info=True)