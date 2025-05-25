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
import requests


def extract_and_clean_media(content: str) -> list[dict]:
    """
    提取并清理媒体URL（包括图片和视频），返回包含类型信息的媒体列表

    Args:
        content: HTML内容

    Returns:
        list[dict]: 媒体信息列表，每个元素包含 {'url': str, 'type': str}
                   type 可能是 'image' 或 'video'
    """
    media_list = []
    if not content:
        return media_list

    # 提取图片URL
    img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
    raw_images = re.findall(img_pattern, content, re.IGNORECASE)
    logging.info(f"提取到 {len(raw_images)} 张原始图片")

    # 提取视频URL
    video_pattern = r'<video[^>]+src=["\']([^"\']+)["\'][^>]*>'
    raw_videos = re.findall(video_pattern, content, re.IGNORECASE)
    logging.info(f"提取到 {len(raw_videos)} 个原始视频")

    # 处理图片
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
            media_list.append({'url': clean_url, 'type': 'image'})
            logging.debug(f"添加有效图片: {clean_url}")
        else:
            logging.warning(f"跳过无效图片URL: {clean_url}")

    # 处理视频
    for video_url in raw_videos:
        # 清理HTML实体编码
        clean_url = video_url.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        clean_url = clean_url.replace('&quot;', '"').strip()

        # 验证URL格式
        if clean_url.startswith(('http://', 'https://')):
            media_list.append({'url': clean_url, 'type': 'video'})
            logging.debug(f"添加有效视频: {clean_url}")
        else:
            logging.warning(f"跳过无效视频URL: {clean_url}")

    logging.info(f"清理后有效媒体数量: {len(media_list)} (图片: {len(raw_images)}, 视频: {len(raw_videos)})")

    # 记录前几个媒体URL用于调试
    for i, media_info in enumerate(media_list[:3], 1):
        media_type = "图片" if media_info['type'] == 'image' else "视频"
        logging.info(f"媒体{i}({media_type}): {media_info['url']}")

    return media_list


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


async def send_media_groups_with_caption(
    bot: Bot,
    chat_id: str,
    title: str,
    author: str,
    media_list: list[dict],
    full_caption: str = None
) -> None:
    """
    发送媒体组（图片和视频），支持两种caption格式：
    1. 简洁格式：#作者 + title + 批次信息（用于媒体为主模式）
    2. 完整格式：传入完整的caption内容（用于文字为主模式）

    Args:
        bot: Telegram Bot实例
        chat_id: 目标聊天ID
        title: 标题
        author: 作者
        media_list: 媒体信息列表，每个元素包含 {'url': str, 'type': str}
        full_caption: 完整的caption内容（可选，如果提供则使用完整格式）

    Raises:
        MediaAccessError: 当媒体无法访问时抛出，调用方可以降级到文字模式
    """
    if not media_list:
        logging.warning("send_media_groups_with_caption: 没有媒体可发送")
        return

    # 🔍 分析媒体文件大小信息（不过滤，只记录）
    media_analysis = analyze_media_files_info(media_list)

    # 🔍 详细打印每个媒体文件的大小信息
    logging.info(f"📊 媒体文件详细信息:")
    for detail in media_analysis['details']:
        media_type_name = detail['type_name']
        index = detail['index']
        accessible = detail['accessible']
        size_mb = detail['size_mb']
        url = detail['url']

        if accessible:
            if size_mb > 0:
                # 判断是否可能导致发送失败
                risk_level = ""
                if size_mb > 50:
                    risk_level = " 🚨 高风险：超过50MB Bot API限制"
                elif size_mb > 20:
                    risk_level = " ⚠️ 中风险：较大文件"
                elif size_mb > 10:
                    risk_level = " ⚡ 低风险：中等大小"

                logging.info(f"   {media_type_name}{index}: {size_mb:.2f}MB{risk_level}")
            else:
                logging.info(f"   {media_type_name}{index}: 大小未知 ❓")
        else:
            logging.info(f"   {media_type_name}{index}: 无法访问 ❌ - {detail['error_msg']}")

        logging.info(f"   URL: {url}")

    # 判断使用哪种caption格式
    use_full_caption = full_caption is not None

    if use_full_caption:
        logging.info(f"开始发送带完整caption的媒体组: 媒体数量={len(media_list)}, caption长度={len(full_caption)}")

        # 确保caption不超过Telegram限制（1024字符）
        max_caption_length = 1024
        if len(full_caption) > max_caption_length:
            full_caption = full_caption[:max_caption_length-3] + "..."
            logging.info(f"Caption过长已截断到 {len(full_caption)} 字符")
    else:
        logging.info(f"开始发送媒体组: 标题='{title}', 作者='{author}', 媒体数量={len(media_list)}")

        # 截断标题（Telegram caption限制1024字符）
        max_title_length = 100
        original_title = title
        if len(title) > max_title_length:
            title = title[:max_title_length] + "..."
            logging.info(f"标题过长已截断: '{original_title}' -> '{title}'")

    # 计算均衡的分批方案
    batch_sizes = calculate_balanced_batches(len(media_list), max_per_batch=10)
    total_batches = len(batch_sizes)

    logging.info(f"将发送 {total_batches} 个媒体组，分批方案: {batch_sizes}")

    # 记录是否有任何批次发送成功
    any_batch_success = False
    media_access_errors = []

    # 按照分批方案发送媒体
    media_index = 0
    for batch_num, batch_size in enumerate(batch_sizes, 1):
        # 获取当前批次的媒体
        batch_media = media_list[media_index:media_index + batch_size]
        media_index += batch_size

        logging.info(f"准备发送第 {batch_num}/{total_batches} 批，包含 {batch_size} 个媒体")

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
        telegram_media_list = []

        # 每个批次的第一个媒体包含caption
        for j, media_info in enumerate(batch_media):
            media_url = media_info['url']
            media_type = media_info['type']

            # 根据媒体类型构建对应的InputMedia对象
            if media_type == 'video':
                # 视频文件
                if j == 0:  # 每批的第一个媒体包含caption
                    from telegram import InputMediaVideo
                    telegram_media_list.append(InputMediaVideo(media=media_url, caption=caption))
                    logging.debug(f"第 {batch_num} 批第1个媒体(视频,带caption): {media_url}")
                else:
                    from telegram import InputMediaVideo
                    telegram_media_list.append(InputMediaVideo(media=media_url))
                    logging.debug(f"第 {batch_num} 批第{j+1}个媒体(视频): {media_url}")
            else:  # media_type == 'image'
                # 图片文件
                if j == 0:  # 每批的第一个媒体包含caption
                    telegram_media_list.append(InputMediaPhoto(media=media_url, caption=caption))
                    logging.debug(f"第 {batch_num} 批第1个媒体(图片,带caption): {media_url}")
                else:
                    telegram_media_list.append(InputMediaPhoto(media=media_url))
                    logging.debug(f"第 {batch_num} 批第{j+1}个媒体(图片): {media_url}")

        try:
            # 发送媒体组
            await bot.send_media_group(chat_id=chat_id, media=telegram_media_list)
            logging.info(f"✅ 成功发送第 {batch_num}/{total_batches} 批媒体组 ({batch_size}个媒体)")
            any_batch_success = True
        except Exception as e:
            logging.error(f"❌ 发送第 {batch_num} 批媒体组失败: {str(e)}", exc_info=True)

            # 如果是媒体无法访问的错误，记录详细信息
            if "webpage_media_empty" in str(e):
                logging.error(f"媒体无法访问错误，批次 {batch_num} 的媒体URL:")
                for j, media_info in enumerate(batch_media):
                    media_type = "图片" if media_info['type'] == 'image' else "视频"
                    logging.error(f"  媒体{j+1}({media_type}): {media_info['url']}")
                media_access_errors.append(f"批次{batch_num}: {str(e)}")
                # 继续处理下一批
                continue

            # 如果发送失败，尝试逐个发送（降级处理）
            logging.info(f"尝试逐个发送第 {batch_num} 批的媒体...")
            batch_success = False
            for j, media_info in enumerate(batch_media):
                media_url = media_info['url']
                media_type = media_info['type']

                try:
                    if media_type == 'video':
                        # 发送视频
                        if j == 0:
                            await bot.send_video(chat_id=chat_id, video=media_url, caption=caption)
                        else:
                            await bot.send_video(chat_id=chat_id, video=media_url)
                        logging.info(f"✅ 逐个发送视频成功: {media_url}")
                        batch_success = True
                    else:  # media_type == 'image'
                        # 发送图片
                        if j == 0:
                            await bot.send_photo(chat_id=chat_id, photo=media_url, caption=caption)
                        else:
                            await bot.send_photo(chat_id=chat_id, photo=media_url)
                        logging.info(f"✅ 逐个发送图片成功: {media_url}")
                        batch_success = True
                except Exception as single_error:
                    media_type_name = "视频" if media_type == 'video' else "图片"
                    logging.error(f"❌ 逐个发送{media_type_name}失败: {media_url}, 错误: {str(single_error)}", exc_info=True)

            if batch_success:
                any_batch_success = True

    # 如果所有批次都因为媒体无法访问而失败，抛出特殊异常
    if not any_batch_success and media_access_errors:
        error_msg = f"所有媒体都无法访问: {'; '.join(media_access_errors)}"
        logging.error(f"媒体组发送完全失败: {error_msg}", exc_info=True)
        # 定义一个自定义异常类
        class MediaAccessError(Exception):
            pass
        raise MediaAccessError(error_msg)


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
        logging.error(f"❌ 发送文字消息失败: '{title}', 错误: {str(e)}", exc_info=True)
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
                    logging.error(f"发送条目失败: {entry.get('title', 'Unknown')}, 错误: {str(e)}", exc_info=True)
                    # 出错后也要等待，避免连续错误
                    await asyncio.sleep(5)
                    continue

            logging.info(f"已发送 {len(new_entries)} 个条目 for {domain}")
        else:
            logging.info(f"{domain} 无新增内容，跳过发送")
    except Exception as e:
        logging.error(f"发送Feed更新消息失败 for {url}: {str(e)}", exc_info=True)


def check_media_accessibility(media_url: str, max_size_mb: int = 45) -> tuple[bool, str, int]:
    """
    检查媒体文件的可访问性和大小

    Args:
        media_url: 媒体URL
        max_size_mb: 最大允许大小（MB）

    Returns:
        tuple[bool, str, int]: (是否可访问, 错误信息, 文件大小MB)
    """
    try:
        # 发送HEAD请求检查文件信息
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        response = requests.head(media_url, headers=headers, timeout=10, allow_redirects=True)

        if response.status_code != 200:
            return False, f"HTTP {response.status_code}", 0

        # 检查文件大小
        content_length = response.headers.get('content-length')
        if content_length:
            size_bytes = int(content_length)
            size_mb = size_bytes / (1024 * 1024)

            if size_mb > max_size_mb:
                return False, f"文件过大 ({size_mb:.1f}MB > {max_size_mb}MB)", int(size_mb)

            return True, "", int(size_mb)
        else:
            # 无法获取文件大小，假设可以尝试
            return True, "无法获取文件大小", 0

    except requests.exceptions.RequestException as e:
        return False, f"网络错误: {str(e)}", 0
    except Exception as e:
        return False, f"检查失败: {str(e)}", 0


def analyze_media_files_info(media_list: list[dict]) -> dict:
    """
    分析媒体文件列表的大小信息，只检查不过滤

    Args:
        media_list: 媒体信息列表，每个元素包含 {'url': str, 'type': str}

    Returns:
        dict: 包含分析结果的字典
    """
    if not media_list:
        return {
            'total_count': 0,
            'total_size_mb': 0,
            'large_files_count': 0,
            'accessible_count': 0,
            'details': []
        }

    logging.info(f"🔍 开始分析 {len(media_list)} 个媒体文件的大小信息...")

    total_size_mb = 0
    large_files_count = 0
    accessible_count = 0
    details = []

    for i, media_info in enumerate(media_list, 1):
        media_url = media_info['url']
        media_type = media_info['type']
        media_type_name = "视频" if media_type == 'video' else "图片"

        # 检查文件大小（设置很大的限制，不过滤任何文件）
        accessible, error_msg, size_mb = check_media_accessibility(media_url, max_size_mb=999999)

        file_info = {
            'index': i,
            'url': media_url,
            'type': media_type,
            'type_name': media_type_name,
            'accessible': accessible,
            'size_mb': size_mb,
            'error_msg': error_msg
        }

        if accessible:
            accessible_count += 1
            if size_mb > 0:
                total_size_mb += size_mb
                size_status = ""

                # 标记大文件
                if media_type == 'video' and size_mb > 50:
                    large_files_count += 1
                    size_status = " ⚠️ 超过Bot API 50MB限制"
                elif media_type == 'image' and size_mb > 10:
                    large_files_count += 1
                    size_status = " ⚠️ 较大图片文件"

                logging.info(f"📁 {media_type_name}{i}: {size_mb:.1f}MB{size_status}")
                file_info['size_status'] = size_status
            else:
                logging.info(f"📁 {media_type_name}{i}: 大小未知")
                file_info['size_status'] = " ℹ️ 大小未知"

            logging.info(f"🔗 URL: {media_url}")
        else:
            logging.warning(f"❌ {media_type_name}{i}: 无法访问 - {error_msg}")
            logging.warning(f"🔗 URL: {media_url}")
            file_info['size_status'] = f" ❌ 无法访问: {error_msg}"

        details.append(file_info)

    # 打印汇总信息
    analysis_result = {
        'total_count': len(media_list),
        'accessible_count': accessible_count,
        'total_size_mb': total_size_mb,
        'large_files_count': large_files_count,
        'details': details
    }

    logging.info(f"📊 媒体文件分析汇总:")
    logging.info(f"   总文件数: {analysis_result['total_count']}")
    logging.info(f"   可访问文件: {analysis_result['accessible_count']}")
    if total_size_mb > 0:
        logging.info(f"   总大小: {total_size_mb:.1f}MB")
    logging.info(f"   大文件数量: {large_files_count}")

    return analysis_result