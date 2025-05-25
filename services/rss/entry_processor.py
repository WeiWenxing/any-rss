"""
RSS条目处理模块
负责条目信息提取、格式化和发送逻辑
"""

import logging
import re
from datetime import datetime
from telegram import Bot
from .message_sender import (
    extract_and_clean_images,
    send_image_groups_with_caption,
    send_text_message
)


def extract_entry_info(entry_data, is_feedparser_entry=True):
    """
    统一的条目信息提取函数

    Args:
        entry_data: 条目数据（可以是feedparser的entry对象或字典）
        is_feedparser_entry: 是否为feedparser解析的entry对象

    Returns:
        dict: 标准化的条目信息
    """
    try:
        if is_feedparser_entry:
            # feedparser解析的entry对象
            entry_info = {
                'title': entry_data.get('title', '无标题').strip(),
                'link': entry_data.get('link', '').strip(),
                'summary': entry_data.get('summary', '').strip(),
                'description': entry_data.get('description', '').strip(),
                'author': entry_data.get('author', '').strip(),
                'id': entry_data.get('id', '').strip(),
                'published': '',
                'content': ''
            }

            # 获取发布时间
            if hasattr(entry_data, 'published_parsed') and entry_data.published_parsed:
                try:
                    published_dt = datetime(*entry_data.published_parsed[:6])
                    entry_info['published'] = published_dt.strftime('%Y-%m-%d %H:%M')
                except Exception as e:
                    logging.warning(f"解析发布时间失败: {e}")
                    entry_info['published'] = entry_data.get('published', '')
            else:
                entry_info['published'] = entry_data.get('published', '')

            # 获取内容（优先使用content，然后是summary，最后是description）
            if hasattr(entry_data, 'content') and entry_data.content:
                # feedparser的content是一个列表
                entry_info['content'] = entry_data.content[0].value if entry_data.content else ''
            else:
                entry_info['content'] = entry_info['summary'] or entry_info['description']

        else:
            # 手动解析的字典格式（来自BeautifulSoup等）
            entry_info = {
                'title': entry_data.get('title', '无标题').strip(),
                'link': entry_data.get('link', '').strip(),
                'summary': entry_data.get('summary', '').strip(),
                'description': entry_data.get('description', '').strip(),
                'author': entry_data.get('author', '').strip(),
                'id': entry_data.get('id', '').strip(),
                'published': entry_data.get('published', ''),
                'content': entry_data.get('content', '')
            }

            # 对于手动解析的数据，content优先级：content > description > summary
            if not entry_info['content']:
                entry_info['content'] = entry_info['description'] or entry_info['summary']

        # 统一处理：如果没有content，使用summary或description
        if not entry_info['content']:
            entry_info['content'] = entry_info['summary'] or entry_info['description']

        logging.debug(f"条目信息提取完成: 标题='{entry_info['title']}', 作者='{entry_info['author']}', 内容长度={len(entry_info['content'])}")
        return entry_info

    except Exception as e:
        logging.error(f"提取条目信息失败: {str(e)}")
        # 返回基本信息，避免完全失败
        return {
            'title': '信息提取失败',
            'link': '',
            'summary': '',
            'description': '',
            'author': '',
            'id': '',
            'published': '',
            'content': str(entry_data) if entry_data else ''
        }


async def send_entry_unified(
    bot: Bot,
    chat_id: str,
    entry_info: dict,
    message_type: str = "auto",
    show_analysis: bool = False
) -> None:
    """
    统一的条目发送函数，支持自动判断和强制模式

    Args:
        bot: Telegram Bot实例
        chat_id: 目标聊天ID
        entry_info: 标准化的条目信息
        message_type: 消息类型 ("auto", "text", "media")
        show_analysis: 是否显示分析信息（用于调试）
    """
    try:
        title = entry_info.get('title', '无标题')
        link = entry_info.get('link', '')
        content = entry_info.get('content', '')
        author = entry_info.get('author', '')
        published_time = entry_info.get('published', '')

        # 提取图片
        images = extract_and_clean_images(content)

        # 根据消息类型决定发送模式
        if message_type == "auto":
            # 自动判断：≥2张图片为图片为主，<2张图片为文字为主
            mode = "图片为主" if len(images) >= 2 else "文字为主"
        elif message_type == "media":
            mode = "图片为主"
        else:  # message_type == "text"
            mode = "文字为主"

        logging.info(f"条目发送模式: {mode} (图片数量: {len(images)}, 类型: {message_type})")

        # 发送分析信息（仅在调试模式下）
        if show_analysis:
            format_type = entry_info.get('format_type', '未知')
            analysis_info = (
                f"🔧 SHOW命令分析结果：\n"
                f"------------------------------------\n"
                f"📋 格式类型: {format_type}\n"
                f"📰 标题: {title}\n"
                f"👤 作者: {author or '无'}\n"
                f"🔗 链接: {link[:50]}{'...' if len(link) > 50 else ''}\n"
                f"🕒 时间: {published_time or '无'}\n"
                f"🖼️ 图片数量: {len(images)}\n"
                f"⚙️ 指定类型: {message_type}\n"
                f"📊 实际模式: {mode}\n"
                f"📝 内容长度: {len(content)} 字符\n"
                f"------------------------------------\n"
                f"正在发送实际消息..."
            )
            await bot.send_message(chat_id=chat_id, text=analysis_info)

        # 根据模式发送消息
        if mode == "图片为主" and images:
            # 图片为主模式：发送媒体组
            await send_image_groups_with_caption(bot, chat_id, title, author, images)
        else:
            # 文字为主模式：发送文字消息
            await send_text_message(bot, chat_id, title, link, content, published_time)

            # 如果有图片，作为补充发送
            if images:
                logging.info(f"文字为主模式，补充发送 {len(images)} 张图片")
                await send_image_groups_with_caption(bot, chat_id, f"📷 {title} - 补充图片", author, images)

        logging.info(f"✅ 条目发送完成: '{title}' ({mode})")

    except Exception as e:
        logging.error(f"❌ 发送条目失败: '{entry_info.get('title', 'Unknown')}', 错误: {str(e)}")
        raise


async def process_and_send_entry(
    bot: Bot,
    chat_id: str,
    entry: dict,
    current_index: int,
    total_count: int
) -> None:
    """
    处理并发送单个条目（用于RSS推送）

    Args:
        bot: Telegram Bot实例
        chat_id: 目标聊天ID
        entry: feedparser解析的条目对象
        current_index: 当前条目索引
        total_count: 总条目数量
    """
    try:
        # 提取条目信息
        entry_info = extract_entry_info(entry, is_feedparser_entry=True)

        # 添加进度信息到标题
        original_title = entry_info['title']
        entry_info['title'] = f"[{current_index}/{total_count}] {original_title}"

        # 使用统一发送函数
        await send_entry_unified(bot, chat_id, entry_info, message_type="auto")

        logging.info(f"✅ 条目处理完成: {current_index}/{total_count} - '{original_title}'")

    except Exception as e:
        logging.error(f"❌ 处理条目失败: {current_index}/{total_count} - {str(e)}")
        raise