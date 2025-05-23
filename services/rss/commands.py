import logging
import asyncio
from .manager import RSSManager
from pathlib import Path
from urllib.parse import urlparse
from core.config import telegram_config
from telegram import Update, Bot
from telegram.ext import ContextTypes, CommandHandler, Application

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

        await asyncio.sleep(1)
        if new_entries:
            logging.info(f"开始发送 {len(new_entries)} 个新条目 for {domain}")
            for entry in new_entries:
                # 构造条目消息
                entry_title = entry.get('title', '无标题')
                entry_link = entry.get('link', '')
                entry_summary = entry.get('summary', '')

                # 限制摘要长度
                if entry_summary and len(entry_summary) > 200:
                    entry_summary = entry_summary[:200] + "..."

                entry_message = f"📰 {entry_title}\n"
                if entry_link:
                    entry_message += f"🔗 {entry_link}\n"
                if entry_summary:
                    entry_message += f"📝 {entry_summary}\n"

                await bot.send_message(
                    chat_id=chat_id, text=entry_message, disable_web_page_preview=False
                )
                logging.info(f"已发送条目: {entry_title}")
                await asyncio.sleep(1)
            logging.info(f"已发送 {len(new_entries)} 个新条目 for {domain}")

            # 发送更新结束的消息
            await asyncio.sleep(1)
            end_message = (
                f"✨ {domain} 更新推送完成 ✨\n------------------------------------"
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
            "支持标准的RSS 2.0和Atom 1.0格式"
        )
        return

    url = context.args[0]
    logging.info(f"执行add命令，URL: {url}")

    success, error_msg, xml_content, new_entries = rss_manager.add_feed(url)

    if success:
        if "已存在的feed更新成功" in error_msg or "今天已经更新过此Feed" in error_msg:
            await update.message.reply_text(f"该Feed已在监控列表中")
        else:
            await update.message.reply_text(f"成功添加Feed监控：{url}")

        # 发送更新通知
        await send_update_notification(context.bot, url, new_entries, xml_content)
        logging.info(f"已尝试发送更新通知 for {url} after add command")

    else:
        logging.error(f"添加Feed监控失败: {url} 原因: {error_msg}")
        await update.message.reply_text(
            f"添加Feed监控失败：{url}\n原因：{error_msg}"
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


def register_commands(application: Application):
    """注册RSS相关的命令"""
    # 注册新的独立命令
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("del", del_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("news", force_summary_command_handler))


async def force_send_keywords_summary(bot: Bot, target_chat: str = None) -> None:
    """
    强制从存储的 current 和 latest Feed 文件比对生成并发送关键词汇总。
    """
    chat_id = target_chat or telegram_config["target_chat"]
    if not chat_id:
        logging.error("未配置发送目标，请检查TELEGRAM_TARGET_CHAT环境变量")
        return

    all_new_entries_for_summary = []
    feeds = rss_manager.get_feeds()

    if not feeds:
        logging.info("没有配置任何 Feed，无法生成汇总。")
        try:
            await bot.send_message(chat_id=chat_id, text="⚠️ 没有配置任何 Feed，无法生成关键词汇总。")
        except Exception as e:
            logging.error(f"发送无 feeds 通知失败: {str(e)}")
        return

    logging.info(f"开始为 {len(feeds)} 个 feeds 强制生成关键词汇总。")
    for feed_url in feeds:
        try:
            feed_dir = rss_manager._get_feed_dir(feed_url)
            current_feed_file = feed_dir / "feed-current.xml"
            latest_feed_file = feed_dir / "feed-latest.xml"

            if current_feed_file.exists() and latest_feed_file.exists():
                current_xml = current_feed_file.read_text()
                latest_xml = latest_feed_file.read_text()

                new_entries_for_feed = rss_manager.compare_feeds(current_xml, latest_xml)
                if new_entries_for_feed:
                    logging.info(f"强制汇总 - 为 {feed_url} 从 current/latest 文件比较中发现 {len(new_entries_for_feed)} 个新条目。")
                    all_new_entries_for_summary.extend(new_entries_for_feed)
                else:
                    logging.info(f"强制汇总 - 为 {feed_url} 从 current/latest 文件比较中未发现新条目。")
            else:
                logging.warning(f"强制汇总 - 对于 {feed_url}，current ({current_feed_file.exists()}) 或 latest ({latest_feed_file.exists()}) Feed 文件不存在，跳过比较。")
        except Exception as e:
            logging.error(f"强制汇总 - 处理 feed {feed_url} 时出错: {str(e)}")
            continue

    if all_new_entries_for_summary:
        logging.info(f"强制汇总 - 共收集到 {len(all_new_entries_for_summary)} 个新条目用于生成汇总。")
        await send_keywords_summary(bot, all_new_entries_for_summary, target_chat=chat_id)
    else:
        logging.info("强制汇总 - 所有 feeds 均未从 current/latest 文件比较中发现新条目，不发送汇总。")
        try:
            await bot.send_message(chat_id=chat_id, text="ℹ️ 所有监控源的 current/latest Feed 对比均无新增内容，无需发送关键词汇总。")
        except Exception as e:
            logging.error(f"发送无新增内容通知失败: {str(e)}")


async def force_summary_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /news 命令，强制发送关键词汇总"""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logging.info(f"收到 /news 命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

    try:
        await update.message.reply_text("⏳ 正在尝试从已存储的 Feed 数据生成并发送关键词汇总...")

        await force_send_keywords_summary(context.bot)

        logging.info(f"已通过 /news 命令尝试强制发送关键词汇总。")
        await update.message.reply_text("✅ 关键词汇总已尝试发送至目标频道。如果没有任何新增内容，则不会发送。")
    except Exception as e:
        logging.error(f"执行 /news 命令失败: {str(e)}", exc_info=True)
        try:
            await update.message.reply_text(f"❌ 执行 /news 命令时出错: {str(e)}")
        except Exception as e_reply:
            logging.error(f"发送 /news 错误回执失败: {str(e_reply)}")


async def send_keywords_summary(
    bot: Bot,
    all_new_entries: list[dict],
    target_chat: str = None,
) -> None:
    """
    从条目列表中提取关键词并按域名分组发送汇总消息

    Args:
        bot: Telegram Bot实例
        all_new_entries: 所有新增条目的列表
        target_chat: 发送目标ID,默认使用配置中的target_chat
    """
    chat_id = target_chat or telegram_config["target_chat"]
    if not chat_id:
        logging.error("未配置发送目标，请检查TELEGRAM_TARGET_CHAT环境变量")
        return

    if not all_new_entries:
        return

    # 创建域名-关键词映射字典
    domain_keywords = {}

    # 从条目中提取关键词
    for entry in all_new_entries:
        try:
            title = entry.get('title', '')
            link = entry.get('link', '')

            if link:
                # 解析URL获取域名
                parsed_url = urlparse(link)
                domain = parsed_url.netloc

                # 使用标题作为关键词
                if title.strip():
                    if domain not in domain_keywords:
                        domain_keywords[domain] = []
                    domain_keywords[domain].append(title.strip())
        except Exception as e:
            logging.debug(f"从条目提取关键词失败: {entry}, 错误: {str(e)}")
            continue

    # 对每个域名的关键词列表去重
    for domain in domain_keywords:
        domain_keywords[domain] = list(set(domain_keywords[domain]))

    # 如果有关键词，构建并发送消息
    if domain_keywords:
        summary_message = (
            "━━━━━━━━━━━━━━━━━━\n" "🎯 #今日新增 #关键词 #速览 🎯\n" "━━━━━━━━━━━━━━━━━━\n\n"
        )

        # 按域名分组展示关键词
        for domain, keywords in domain_keywords.items():
            if keywords:
                summary_message += f"📌 {domain}:\n"
                for i, keyword in enumerate(keywords, 1):
                    # 限制关键词长度
                    if len(keyword) > 50:
                        keyword = keyword[:50] + "..."
                    summary_message += f"  {i}. {keyword}\n"
                summary_message += "\n"

        # 发送汇总消息
        try:
            await bot.send_message(
                chat_id=chat_id, text=summary_message, disable_web_page_preview=True
            )
        except Exception as e:
            logging.error(f"发送关键词汇总消息失败 (chat_id: {chat_id}): {str(e)}")
