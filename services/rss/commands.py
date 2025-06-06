import logging
import asyncio
import re
import time
from .manager import RSSManager
from .entry_processor import extract_entry_info, send_entry_unified
from .message_sender import send_update_notification
from pathlib import Path
from urllib.parse import urlparse
from core.config import telegram_config
from telegram import Update, Bot, InputMediaPhoto
from telegram.ext import ContextTypes, CommandHandler, Application
from datetime import datetime
from bs4 import BeautifulSoup
from .parser_utils import get_unified_parser

rss_manager = RSSManager()

# 导出函数供其他模块使用
__all__ = ['send_update_notification', 'register_commands']


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /add 命令"""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logging.info(f"收到ADD命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

    if not context.args:
        logging.info("显示ADD命令帮助信息")
        await update.message.reply_text(
            "请提供RSS/Feed的URL和目标频道ID\n"
            "格式：/add <RSS_URL> <CHAT_ID>\n\n"
            "例如：\n"
            "/add https://example.com/feed.xml @my_channel\n"
            "/add https://example.com/feed.xml -1001234567890\n\n"
            "支持标准的RSS 2.0和Atom 1.0格式\n"
            "注意：首次添加订阅源时，会展示所有现有内容"
        )
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ 参数不足\n"
            "请提供RSS URL和目标频道ID\n"
            "格式：/add <RSS_URL> <CHAT_ID>\n\n"
            "例如：/add https://example.com/feed.xml @my_channel"
        )
        return

    url = context.args[0]
    target_chat_id = context.args[1]

    logging.info(f"执行add命令，URL: {url}, 目标频道: {target_chat_id}")

    # 验证频道ID格式
    if not (target_chat_id.startswith('@') or target_chat_id.startswith('-') or target_chat_id.isdigit()):
        await update.message.reply_text(
            "❌ 无效的频道ID格式\n"
            "支持的格式：\n"
            "- @channel_name (频道用户名)\n"
            "- -1001234567890 (频道数字ID)\n"
            "- 1234567890 (用户数字ID)"
        )
        return

    success, error_msg, xml_content, entries = rss_manager.add_feed(url, target_chat_id)

    if success:
        if "首次添加" in error_msg:
            await update.message.reply_text(
                f"✅ 成功添加Feed监控：{url}\n"
                f"📺 目标频道：{target_chat_id}\n"
                f"📋 这是首次添加，将展示所有现有内容（共 {len(entries)} 条）"
            )
        elif "今天已经更新过此Feed" in error_msg:
            await update.message.reply_text(f"该Feed已在监控列表中，今天已更新过")
        else:
            await update.message.reply_text(
                f"✅ 成功添加Feed监控：{url}\n"
                f"📺 目标频道：{target_chat_id}"
            )

        # 发送更新通知到指定频道
        await send_update_notification(context.bot, url, entries, xml_content, target_chat_id)
        logging.info(f"已尝试发送更新通知 for {url} to {target_chat_id} after add command")

    else:
        logging.error(f"添加Feed监控失败: {url} 原因: {error_msg}", exc_info=True)
        await update.message.reply_text(
            f"❌ 添加Feed监控失败：{url}\n原因：{error_msg}"
        )


async def del_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /del 命令"""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logging.info(f"收到DEL命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

    if not context.args:
        logging.warning("del命令缺少URL参数")
        await update.message.reply_text(
            "请提供要删除的RSS/Feed链接\n例如：/del https://example.com/feed.xml"
        )
        return

    url = context.args[0]
    logging.info(f"执行del命令，URL: {url}")
    success, error_msg = rss_manager.remove_feed(url)
    if success:
        logging.info(f"成功删除RSS订阅: {url}")
        await update.message.reply_text(f"成功删除RSS订阅：{url}")
    else:
        logging.error(f"删除RSS订阅失败: {url} 原因: {error_msg}", exc_info=True)
        await update.message.reply_text(
            f"删除RSS订阅失败：{url}\n原因：{error_msg}"
        )


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /list 命令"""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logging.info(f"收到LIST命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

    feeds = rss_manager.get_feeds()
    if not feeds:
        logging.info("RSS订阅列表为空")
        await update.message.reply_text("当前没有RSS订阅")
        return

    # 构建订阅列表，显示URL和对应的频道ID
    feed_list = []
    for url, target_chat_id in feeds.items():
        if target_chat_id:
            feed_list.append(f"- {url} → {target_chat_id}")
        else:
            feed_list.append(f"- {url} → (未设置频道)")

    feed_list_text = "\n".join(feed_list)
    logging.info(f"显示RSS订阅列表，共 {len(feeds)} 个")
    await update.message.reply_text(f"当前RSS订阅列表：\n{feed_list_text}")


def register_commands(application: Application) -> None:
    """注册RSS相关的命令处理器"""
    # 导入debug配置
    from core.config import debug_config

    # 注册基础命令
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("del", del_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("news", news_command))

    # 根据debug模式决定是否注册调试命令
    if debug_config["enabled"]:
        application.add_handler(CommandHandler("show", show_command))  # 开发者调试命令

        # 注册调试命令
        from .debug_commands import register_debug_commands
        register_debug_commands(application)

        logging.info("✅ RSS调试命令已注册（DEBUG模式开启）")
    else:
        logging.info("ℹ️ RSS调试命令已跳过（DEBUG模式关闭）")


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /news 命令 - 强制检查所有订阅源并发送差异内容"""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logging.info(f"收到NEWS命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

    feeds = rss_manager.get_feeds()
    if not feeds:
        await update.message.reply_text("❌ 当前没有监控任何Feed订阅源")
        return

    await update.message.reply_text(
        f"🔄 开始强制检查 {len(feeds)} 个订阅源的更新...\n"
        f"这可能需要一些时间，请稍候。"
    )

    # 用于存储所有新增的条目
    all_new_entries = []
    success_count = 0
    error_count = 0

    for url, target_chat_id in feeds.items():
        try:
            logging.info(f"强制检查订阅源: {url} -> 频道: {target_chat_id}")

            # 使用download_and_parse_feed方法获取差异内容
            success, error_msg, xml_content, new_entries = rss_manager.download_and_parse_feed(url)

            if success:
                success_count += 1
                if new_entries:
                    logging.info(f"订阅源 {url} 发现 {len(new_entries)} 个新条目")
                    # 发送更新通知到绑定的频道
                    await send_update_notification(context.bot, url, new_entries, xml_content, target_chat_id)
                    all_new_entries.extend(new_entries)
                else:
                    logging.info(f"订阅源 {url} 无新增内容")
            else:
                error_count += 1
                logging.warning(f"订阅源 {url} 检查失败: {error_msg}")

        except Exception as e:
            error_count += 1
            logging.error(f"检查订阅源失败: {url}, 错误: {str(e)}", exc_info=True)

    # 发送检查结果摘要
    result_message = (
        f"✅ 强制检查完成\n"
        f"📊 成功: {success_count} 个\n"
        f"❌ 失败: {error_count} 个\n"
        f"📈 发现新内容: {len(all_new_entries)} 条"
    )

    if all_new_entries:
        result_message += f"\n\n✅ 所有内容已推送到对应频道"
        await update.message.reply_text(result_message)
    else:
        result_message += f"\n\n💡 所有订阅源都没有新增内容"
        await update.message.reply_text(result_message)

    logging.info(f"NEWS命令执行完成，共处理 {len(feeds)} 个订阅源，发现 {len(all_new_entries)} 条新内容")


async def show_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /show 命令 - 开发者专用，用于测试单个RSS条目的消息格式"""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logging.info(f"收到SHOW命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

    if not context.args:
        await update.message.reply_text(
            "🔧 开发者调试命令\n\n"
            "用法：/show [type] <item_xml>\n\n"
            "参数说明：\n"
            "• type: 消息类型 (可选)\n"
            "  - auto: 自动判断 (默认)\n"
            "  - text: 强制文字为主模式\n"
            "  - media: 强制图片为主模式\n\n"
            "支持格式：\n"
            "• RSS 2.0: <item>...</item>\n"
            "• Atom 1.0: <entry>...</entry>\n\n"
            "示例：\n"
            "RSS格式：\n"
            "/show <item><title>标题</title><description>描述</description></item>\n\n"
            "Atom格式：\n"
            "/show <entry><title>标题</title><content>内容</content></entry>\n\n"
            "强制模式：\n"
            "/show text <entry><title>标题</title></entry>\n"
            "/show media <item><title>标题</title></item>"
        )
        return

    # 解析参数：检查第一个参数是否是type
    message_type = "auto"  # 默认值
    xml_start_index = 0

    # 检查第一个参数是否是有效的type
    if len(context.args) > 0 and context.args[0].lower() in ['auto', 'text', 'media']:
        message_type = context.args[0].lower()
        xml_start_index = 1
        logging.info(f"SHOW命令指定消息类型: {message_type}")
    else:
        logging.info(f"SHOW命令使用默认消息类型: {message_type}")

    # 获取完整的消息文本，去掉命令部分
    full_text = update.message.text
    if full_text.startswith('/show '):
        remaining_text = full_text[6:]  # 去掉 "/show " 前缀

        # 如果指定了type，需要去掉type参数
        if xml_start_index == 1:
            # 找到第一个空格后的内容作为XML
            parts = remaining_text.split(' ', 1)
            if len(parts) > 1:
                item_xml = parts[1]
            else:
                await update.message.reply_text(
                    f"❌ 指定了消息类型 '{message_type}' 但缺少XML内容\n"
                    f"用法：/show {message_type} <item_xml>"
                )
                return
        else:
            item_xml = remaining_text
    else:
        await update.message.reply_text("❌ 无法解析命令参数")
        return

    # 验证XML内容不为空
    if not item_xml.strip():
        await update.message.reply_text(
            "❌ XML内容为空\n"
            "请提供有效的RSS条目XML内容"
        )
        return

    try:
        # 添加调试日志
        logging.info(f"SHOW命令接收到的XML内容长度: {len(item_xml)} 字符")
        logging.debug(f"SHOW命令原始内容: {item_xml[:500]}...")

        # 使用统一解析器解析XML片段
        parser = get_unified_parser()
        entry_data = parser.extract_entry_data_from_xml(item_xml)

        if not entry_data:
            await update.message.reply_text(
                "❌ 解析失败\n"
                "无法解析提供的XML内容，请检查格式是否正确"
            )
            return

        logging.info(f"统一解析器解析成功，提取到标题: {entry_data['title']}")

        # 将解析结果转换为entry_processor期望的格式
        mock_entry = {
            'title': entry_data['title'],
            'description': entry_data['description'],
            'summary': entry_data['summary'],
            'link': entry_data['link'],
            'published': entry_data['published'],
            'author': entry_data['author'],
            'id': entry_data['id'],
            'content': entry_data['description']  # 将description复制到content字段
        }

        # 使用统一的条目信息提取函数（手动解析模式）
        entry_info = extract_entry_info(mock_entry, is_feedparser_entry=False)

        # 添加格式类型到entry_info中
        entry_info['format_type'] = entry_data['format_type']

        # 使用统一的发送函数，并显示分析信息
        await send_entry_unified(
            context.bot,
            chat_id,
            entry_info,
            message_type=message_type,
            show_analysis=True
        )

        logging.info(f"SHOW命令执行成功，已发送条目: {entry_info.get('title', 'Unknown')}, 模式: {message_type}")

    except Exception as e:
        await update.message.reply_text(f"❌ 处理失败: {str(e)}")
        logging.error(f"SHOW命令执行失败: {str(e)}", exc_info=True)
