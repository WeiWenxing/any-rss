import logging
import asyncio
from .manager import RSSManager
from pathlib import Path
from urllib.parse import urlparse
from core.config import telegram_config
from telegram import Update, Bot
from telegram.ext import ContextTypes, CommandHandler, Application
from datetime import datetime

rss_manager = RSSManager()


async def send_update_notification(
    bot: Bot,
    url: str,
    new_entries: list[dict],
    xml_content: str | None,
    target_chat: str = None,
) -> None:
    """
    发送Feed更新通知，包括新增条目列表。
    """
    chat_id = target_chat or telegram_config["target_chat"]
    if not chat_id:
        logging.error("未配置发送目标，请检查TELEGRAM_TARGET_CHAT环境变量")
        return

    domain = urlparse(url).netloc

    try:
        # 根据是否有新增条目，分别构造美化后的标题
        if new_entries:
            header_message = (
                f"✨ {domain} ✨\n"
                f"------------------------------------\n"
                f"发现新增内容！ (共 {len(new_entries)} 条)\n"
                f"来源: {url}\n"
            )
        else:
            header_message = (
                f"✅ {domain}\n"
                f"------------------------------------\n"
                f"{domain} 今日Feed无更新\n"
                f"来源: {url}\n"
                f"------------------------------------"
            )

        await bot.send_message(
            chat_id=chat_id, text=header_message, disable_web_page_preview=True
        )

        # 增加延迟避免flood exceed
        await asyncio.sleep(2)

        if new_entries:
            logging.info(f"开始发送 {len(new_entries)} 个条目 for {domain}")

            for i, entry in enumerate(new_entries, 1):
                try:
                    # 使用统一的消息格式化函数
                    entry_message = await format_entry_message(entry, i, len(new_entries))

                    await bot.send_message(
                        chat_id=chat_id,
                        text=entry_message,
                        disable_web_page_preview=False,
                        parse_mode=None  # 不使用Markdown或HTML解析，避免格式错误
                    )
                    logging.info(f"已发送条目 {i}/{len(new_entries)}: {entry.get('title', 'Unknown')}")

                    # 控制发送速度，避免flood exceed
                    # Telegram限制：同一聊天每秒最多1条消息，每分钟最多20条消息
                    if i % 20 == 0:  # 每20条消息暂停1分钟
                        logging.info(f"已发送20条消息，暂停60秒避免flood exceed...")
                        await asyncio.sleep(60)
                    else:
                        await asyncio.sleep(3)  # 每条消息间隔3秒

                except Exception as e:
                    logging.error(f"发送条目失败: {entry.get('title', 'Unknown')}, 错误: {str(e)}")
                    await asyncio.sleep(2)  # 出错后也要等待
                    continue

            logging.info(f"已发送 {len(new_entries)} 个条目 for {domain}")

            # 发送更新结束的消息
            await asyncio.sleep(2)
            end_message = (
                f"✨ {domain} 更新推送完成 ✨\n"
                f"共推送 {len(new_entries)} 条内容\n"
                f"------------------------------------"
            )
            await bot.send_message(
                chat_id=chat_id, text=end_message, disable_web_page_preview=True
            )
            logging.info(f"已发送更新结束消息 for {domain}")
    except Exception as e:
        logging.error(f"发送Feed更新消息失败 for {url}: {str(e)}", exc_info=True)


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /add 命令"""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logging.info(f"收到ADD命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

    if not context.args:
        logging.info("显示ADD命令帮助信息")
        await update.message.reply_text(
            "请提供RSS/Feed的URL\n"
            "例如：/add https://example.com/feed.xml\n"
            "支持标准的RSS 2.0和Atom 1.0格式\n\n"
            "注意：首次添加订阅源时，会展示所有现有内容"
        )
        return

    url = context.args[0]
    logging.info(f"执行add命令，URL: {url}")

    success, error_msg, xml_content, entries = rss_manager.add_feed(url)

    if success:
        if "首次添加" in error_msg:
            await update.message.reply_text(
                f"✅ 成功添加Feed监控：{url}\n"
                f"📋 这是首次添加，将展示所有现有内容（共 {len(entries)} 条）"
            )
        elif "今天已经更新过此Feed" in error_msg:
            await update.message.reply_text(f"该Feed已在监控列表中，今天已更新过")
        else:
            await update.message.reply_text(f"✅ 成功添加Feed监控：{url}")

        # 发送更新通知
        await send_update_notification(context.bot, url, entries, xml_content)
        logging.info(f"已尝试发送更新通知 for {url} after add command")

    else:
        logging.error(f"添加Feed监控失败: {url} 原因: {error_msg}")
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
        logging.error(f"删除RSS订阅失败: {url} 原因: {error_msg}")
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

    feed_list = "\n".join([f"- {feed}" for feed in feeds])
    logging.info(f"显示RSS订阅列表，共 {len(feeds)} 个")
    await update.message.reply_text(f"当前RSS订阅列表：\n{feed_list}")


def register_commands(application: Application) -> None:
    """注册RSS相关的命令处理器"""
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("del", del_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("news", news_command))
    application.add_handler(CommandHandler("show", show_command))  # 开发者调试命令


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

    for url in feeds:
        try:
            logging.info(f"强制检查订阅源: {url}")

            # 使用download_and_parse_feed方法获取差异内容
            success, error_msg, xml_content, new_entries = rss_manager.download_and_parse_feed(url)

            if success:
                success_count += 1
                if new_entries:
                    logging.info(f"订阅源 {url} 发现 {len(new_entries)} 个新条目")
                    # 发送更新通知到频道
                    await send_update_notification(context.bot, url, new_entries, xml_content)
                    all_new_entries.extend(new_entries)
                else:
                    logging.info(f"订阅源 {url} 无新增内容")
            elif "该Feed已被删除" in error_msg:
                logging.info(f"订阅源 {url} 已被标记为删除，跳过检查")
            else:
                error_count += 1
                logging.warning(f"订阅源 {url} 检查失败: {error_msg}")

        except Exception as e:
            error_count += 1
            logging.error(f"检查订阅源失败: {url}, 错误: {str(e)}")

    # 发送检查结果摘要
    result_message = (
        f"✅ 强制检查完成\n"
        f"📊 成功: {success_count} 个\n"
        f"❌ 失败: {error_count} 个\n"
        f"📈 发现新内容: {len(all_new_entries)} 条"
    )

    if all_new_entries:
        result_message += f"\n\n✅ 所有内容已推送到频道"
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
            "用法：/show <item_xml>\n\n"
            "示例：\n"
            "/show <item>\n"
            "<title>标题</title>\n"
            "<description>描述内容</description>\n"
            "<link>链接</link>\n"
            "<pubDate>发布时间</pubDate>\n"
            "</item>"
        )
        return

    # 获取完整的消息文本，去掉命令部分
    full_text = update.message.text
    if full_text.startswith('/show '):
        item_xml = full_text[6:]  # 去掉 "/show " 前缀
    else:
        await update.message.reply_text("❌ 无法解析命令参数")
        return

    try:
        # 如果没有包含<item>标签，自动添加
        if not item_xml.strip().startswith('<item'):
            item_xml = f"<item>{item_xml}</item>"

        # 添加调试日志
        logging.info(f"SHOW命令接收到的XML内容长度: {len(item_xml)} 字符")
        logging.debug(f"SHOW命令原始内容: {item_xml[:500]}...")

        # 直接使用BeautifulSoup解析，跳过XML解析
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            await update.message.reply_text(
                "❌ 系统错误：BeautifulSoup未安装\n"
                "请联系管理员安装依赖：pip install beautifulsoup4"
            )
            logging.error("BeautifulSoup未安装，无法解析RSS内容")
            return

        # 使用BeautifulSoup解析（优先xml解析器，失败则用html.parser）
        try:
            soup = BeautifulSoup(item_xml, 'xml')
            logging.info("使用XML解析器成功解析内容")
        except Exception as xml_error:
            logging.warning(f"XML解析器失败: {str(xml_error)}, 尝试HTML解析器")
            soup = BeautifulSoup(item_xml, 'html.parser')
            logging.info("使用HTML解析器成功解析内容")

        # 提取各个字段
        mock_entry = {
            'title': '无标题',
            'description': '',
            'summary': '',
            'link': '',
            'published': '',
            'author': '',
            'id': ''
        }

        # 提取标题
        if soup.title:
            mock_entry['title'] = soup.title.get_text().strip()

        # 提取描述（保留HTML格式，因为format_entry_message会处理）
        if soup.description:
            # 获取description标签的内部HTML内容
            desc_content = soup.description.decode_contents() if soup.description.contents else soup.description.get_text()
            mock_entry['description'] = desc_content.strip()
            mock_entry['summary'] = mock_entry['description']

        # 提取链接
        if soup.link:
            mock_entry['link'] = soup.link.get_text().strip()

        # 提取发布时间（支持多种格式）
        pubdate_tag = soup.find('pubDate') or soup.find('pubdate') or soup.find('published')
        if pubdate_tag:
            mock_entry['published'] = pubdate_tag.get_text().strip()

        # 提取作者
        if soup.author:
            mock_entry['author'] = soup.author.get_text().strip()

        # 提取GUID
        if soup.guid:
            mock_entry['id'] = soup.guid.get_text().strip()

        logging.info(f"BeautifulSoup解析成功，提取到标题: {mock_entry['title']}")

        # 使用现有的消息格式化逻辑
        formatted_message = await format_entry_message(mock_entry, 1, 1)

        # 发送格式化后的消息
        await update.message.reply_text(
            f"🔧 调试结果（BeautifulSoup解析）：\n"
            f"------------------------------------\n"
            f"{formatted_message}\n"
            f"------------------------------------\n"
            f"✅ 消息格式化完成"
        )

        logging.info(f"SHOW命令执行成功，已格式化条目: {mock_entry.get('title', 'Unknown')}")

    except Exception as e:
        await update.message.reply_text(f"❌ 处理失败: {str(e)}")
        logging.error(f"SHOW命令执行失败: {str(e)}", exc_info=True)


async def format_entry_message(entry: dict, current_index: int, total_count: int) -> str:
    """
    格式化单个条目消息

    Args:
        entry: 条目数据字典
        current_index: 当前条目序号
        total_count: 总条目数

    Returns:
        str: 格式化后的消息文本
    """
    # 构造详细的条目消息
    entry_title = entry.get('title', '无标题').strip()
    entry_link = entry.get('link', '').strip()
    entry_summary = entry.get('summary', '').strip()
    entry_description = entry.get('description', '').strip()

    # 获取发布时间
    published_time = ""
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        try:
            import time
            pub_time = datetime.fromtimestamp(time.mktime(entry.published_parsed))
            published_time = pub_time.strftime("%Y-%m-%d %H:%M")
        except:
            pass
    elif entry.get('published'):
        published_time = entry.get('published', '')[:16]  # 截取前16个字符

    # 选择描述内容（优先使用description，其次summary）
    content = entry_description if entry_description else entry_summary

    # 构建消息
    entry_message = f"📰 {entry_title}\n"

    if published_time:
        entry_message += f"🕒 {published_time}\n"

    if entry_link:
        entry_message += f"🔗 {entry_link}\n"

    if content:
        # 处理HTML标签和图片
        import re

        # 提取图片链接
        img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
        images = re.findall(img_pattern, content, re.IGNORECASE)

        # 移除HTML标签但保留文本内容
        clean_content = re.sub(r'<[^>]+>', '', content)
        clean_content = clean_content.replace('&nbsp;', ' ').replace('&amp;', '&')
        clean_content = clean_content.replace('&lt;', '<').replace('&gt;', '>')
        clean_content = clean_content.replace('&quot;', '"').strip()

        # 限制内容长度
        if len(clean_content) > 500:
            clean_content = clean_content[:500] + "..."

        if clean_content:
            entry_message += f"📝 {clean_content}\n"

        # 添加图片链接
        if images:
            entry_message += f"\n🖼️ 图片:\n"
            for img_url in images[:3]:  # 最多显示3张图片
                entry_message += f"• {img_url}\n"

    # 添加序号信息
    entry_message += f"\n📊 {current_index}/{total_count}"

    return entry_message
