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
                    entry_message += f"\n📊 {i}/{len(new_entries)}"

                    await bot.send_message(
                        chat_id=chat_id,
                        text=entry_message,
                        disable_web_page_preview=False,
                        parse_mode=None  # 不使用Markdown或HTML解析，避免格式错误
                    )
                    logging.info(f"已发送条目 {i}/{len(new_entries)}: {entry_title}")

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
        result_message += f"\n\n🎯 正在发送关键词汇总..."
        await update.message.reply_text(result_message)

        # 发送关键词汇总
        await asyncio.sleep(5)  # 等待5秒，确保所有消息都发送完成
        await send_keywords_summary(context.bot, all_new_entries)

        # 发送最终完成消息
        await asyncio.sleep(2)
        await update.message.reply_text(
            f"🎉 所有内容已推送到频道\n"
            f"📋 关键词汇总已发送"
        )
    else:
        result_message += f"\n\n💡 所有订阅源都没有新增内容"
        await update.message.reply_text(result_message)

    logging.info(f"NEWS命令执行完成，共处理 {len(feeds)} 个订阅源，发现 {len(all_new_entries)} 条新内容")


async def send_keywords_summary(bot: Bot, all_new_entries: list[dict]) -> None:
    """
    发送关键词汇总消息，基于所有新增的Feed条目。
    """
    chat_id = telegram_config["target_chat"]
    if not chat_id:
        logging.error("未配置发送目标，请检查TELEGRAM_TARGET_CHAT环境变量")
        return

    if not all_new_entries:
        logging.info("没有新增条目，跳过关键词汇总")
        return

    try:
        # 提取所有标题和描述文本
        all_text = []
        for entry in all_new_entries:
            title = entry.get('title', '').strip()
            summary = entry.get('summary', '').strip()
            description = entry.get('description', '').strip()

            if title:
                all_text.append(title)

            # 清理HTML标签
            import re
            content = description if description else summary
            if content:
                clean_content = re.sub(r'<[^>]+>', '', content)
                clean_content = clean_content.replace('&nbsp;', ' ').replace('&amp;', '&')
                clean_content = clean_content.replace('&lt;', '<').replace('&gt;', '>')
                clean_content = clean_content.replace('&quot;', '"').strip()
                if clean_content:
                    all_text.append(clean_content)

        # 合并所有文本
        combined_text = ' '.join(all_text)

        if not combined_text.strip():
            logging.info("没有有效的文本内容，跳过关键词汇总")
            return

        # 简单的关键词提取（基于词频）
        import re
        from collections import Counter

        # 移除标点符号，分割单词
        words = re.findall(r'\b\w+\b', combined_text.lower())

        # 过滤掉常见的停用词和短词
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'}
        filtered_words = [word for word in words if len(word) > 3 and word not in stop_words]

        # 统计词频
        word_counts = Counter(filtered_words)
        top_keywords = word_counts.most_common(10)

        # 构建汇总消息
        summary_message = (
            f"📊 今日Feed更新汇总\n"
            f"------------------------------------\n"
            f"📈 共收到 {len(all_new_entries)} 条新内容\n\n"
        )

        if top_keywords:
            summary_message += "🔥 热门关键词:\n"
            for word, count in top_keywords:
                summary_message += f"• {word} ({count}次)\n"
        else:
            summary_message += "🔍 未发现明显的关键词模式\n"

        summary_message += f"\n------------------------------------\n"
        summary_message += f"⏰ 汇总时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        await bot.send_message(
            chat_id=chat_id, text=summary_message, disable_web_page_preview=True
        )
        logging.info(f"已发送关键词汇总，包含 {len(all_new_entries)} 条新内容")

    except Exception as e:
        logging.error(f"发送关键词汇总失败: {str(e)}", exc_info=True)
