import logging
import asyncio
import re
import time
from .manager import RSSManager
from pathlib import Path
from urllib.parse import urlparse
from core.config import telegram_config
from telegram import Update, Bot, InputMediaPhoto
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
    使用智能消息发送：
    - 图片为主模式（≥2张图片）：媒体组 + 简洁caption
    - 文字为主模式（<2张图片）：完整文字内容 + 图片补充
    - 支持均衡分批，每批最多10张图片，分布更均匀
    """
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
                    await send_entry_with_media(bot, chat_id, entry, i, len(new_entries))
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


async def send_image_groups_with_caption(
    bot: Bot,
    chat_id: str,
    title: str,
    author: str,
    images: list[str]
) -> None:
    """
    发送图片组，统一使用简洁caption格式：#作者 + title + 批次信息
    适用于所有图片发送场景（图片为主模式和文字为主模式）
    """
    if not images:
        logging.warning("send_image_groups_with_caption: 没有图片可发送")
        return

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

        # 构建简洁的caption格式：#作者 + title + 批次信息
        caption_parts = []

        # 添加作者（如果有）
        if author:
            caption_parts.append(f"#{author}")
            logging.debug(f"添加作者标签: #{author}")

        # 添加标题
        caption_parts.append(title)

        # 只在多批次时显示批次信息
        if total_batches > 1:
            batch_info = f"📊 {batch_num}/{total_batches}"
            caption_parts.append(batch_info)
            logging.debug(f"添加批次信息: {batch_info}")

        caption = " ".join(caption_parts)
        logging.info(f"第 {batch_num} 批caption: {caption}")

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

            # 如果是flood control，等待后重试
            elif "Flood control exceeded" in str(e):
                logging.info(f"遇到flood control，等待40秒后重试第 {batch_num} 批...")
                await asyncio.sleep(40)
                try:
                    await bot.send_media_group(chat_id=chat_id, media=media_list)
                    logging.info(f"✅ 重试成功发送第 {batch_num} 批媒体组")
                except Exception as retry_error:
                    logging.error(f"❌ 重试发送第 {batch_num} 批也失败: {str(retry_error)}")
                    # 继续处理下一批，不中断整个流程
                    continue
            else:
                # 继续处理下一批，不中断整个流程
                continue

        # 每批之间增加延迟，避免flood control
        if batch_num < total_batches:
            logging.debug(f"等待5秒后发送下一批...")
            await asyncio.sleep(5)

    logging.info(f"✅ 图片组发送完成: 共 {total_batches} 批，{len(images)} 张图片")


async def send_entry_with_media(
    bot: Bot,
    chat_id: str,
    entry: dict,
    current_index: int,
    total_count: int
) -> None:
    """
    发送单个条目，智能判断图片为主还是文字为主

    Args:
        bot: Telegram Bot实例
        chat_id: 目标聊天ID
        entry: RSS条目数据
        current_index: 当前条目序号（仅用于日志）
        total_count: 总条目数（仅用于日志）
    """
    try:
        # 提取基本信息
        entry_title = entry.get('title', '无标题').strip()
        entry_link = entry.get('link', '').strip()
        entry_summary = entry.get('summary', '').strip()
        entry_description = entry.get('description', '').strip()
        entry_author = entry.get('author', '').strip()

        logging.info(f"处理条目 {current_index}/{total_count}: '{entry_title}'")

        # 获取发布时间
        published_time = ""
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                pub_time = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                published_time = pub_time.strftime("%Y-%m-%d %H:%M")
            except:
                pass
        elif entry.get('published'):
            published_time = entry.get('published', '')[:16]

        # 选择描述内容（优先使用description，其次summary）
        content = entry_description if entry_description else entry_summary

        # 使用公共函数提取图片
        images = extract_and_clean_images(content)

        # 判断是图片为主还是文字为主
        is_image_focused = len(images) >= 2
        mode = "图片为主" if is_image_focused else "文字为主"

        logging.info(f"条目模式判断: {len(images)}张图片 -> {mode}模式")

        if is_image_focused:
            # 图片为主模式：只发送图片组（带简洁caption）
            await send_image_groups_with_caption(bot, chat_id, entry_title, entry_author, images)
        else:
            # 文字为主模式：先发送文字消息，再发送图片组
            await send_text_message(bot, chat_id, entry_title, entry_link, content, published_time)

            # 如果有图片，发送图片组（带简洁caption）
            if images:
                await asyncio.sleep(3)  # 延迟避免flood control
                await send_image_groups_with_caption(bot, chat_id, entry_title, entry_author, images)

        logging.info(f"✅ 条目发送完成: '{entry_title}' ({mode})")

    except Exception as e:
        logging.error(f"❌ 发送条目失败: '{entry.get('title', 'Unknown')}', 错误: {str(e)}")
        # 不再使用降级机制，避免重复消息
        raise


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
        logging.info(f"图片数量 {total_images} ≤ {max_per_batch}，使用单批方案: [1批{total_images}张]")
        return [total_images]

    # 计算最少需要多少批
    min_batches = (total_images + max_per_batch - 1) // max_per_batch

    # 计算平均每批的数量
    avg_per_batch = total_images // min_batches
    remainder = total_images % min_batches

    # 构建分批方案
    batches = []
    for i in range(min_batches):
        # 前remainder批多分配1张图片
        batch_size = avg_per_batch + (1 if i < remainder else 0)
        batches.append(batch_size)

    # 计算旧方案对比
    old_batches = [max_per_batch] * (total_images // max_per_batch)
    if total_images % max_per_batch > 0:
        old_batches.append(total_images % max_per_batch)

    old_diff = max(old_batches) - min(old_batches) if len(old_batches) > 1 else 0
    new_diff = max(batches) - min(batches) if len(batches) > 1 else 0

    logging.info(f"智能分批算法: {total_images}张图片")
    logging.info(f"  旧方案: {old_batches} (最大差异: {old_diff}张)")
    logging.info(f"  新方案: {batches} (最大差异: {new_diff}张)")
    logging.info(f"  优化效果: 差异减少 {old_diff - new_diff}张")

    return batches


async def send_text_message(
    bot: Bot,
    chat_id: str,
    title: str,
    link: str,
    content: str,
    published_time: str
) -> None:
    """
    发送纯文字消息
    """
    # 构建完整的文字消息
    text_message = f"🕒 {published_time}\n" if published_time else ""
    text_message += f"📰 {title}\n"

    if link:
        text_message += f"🔗 {link}\n"

    if content:
        # 移除HTML标签但保留文本内容
        clean_content = re.sub(r'<[^>]+>', '', content)
        clean_content = clean_content.replace('&nbsp;', ' ').replace('&amp;', '&')
        clean_content = clean_content.replace('&lt;', '<').replace('&gt;', '>')
        clean_content = clean_content.replace('&quot;', '"').strip()

        # 限制内容长度
        if len(clean_content) > 400:
            clean_content = clean_content[:400] + "..."

        if clean_content:
            text_message += f"\n📝 {clean_content}\n"

    # 发送文字消息
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text_message,
            disable_web_page_preview=False
        )
        logging.info(f"✅ 成功发送文字消息")
    except Exception as e:
        logging.error(f"❌ 发送文字消息失败: {str(e)}")
        if "Flood control exceeded" in str(e):
            logging.info(f"遇到flood control，等待40秒后重试...")
            await asyncio.sleep(40)
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text_message,
                    disable_web_page_preview=False
                )
                logging.info(f"✅ 重试成功发送文字消息")
            except Exception as retry_error:
                logging.error(f"❌ 重试发送文字消息也失败: {str(retry_error)}")
                raise
        else:
            raise


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
            logging.error(f"检查订阅源失败: {url}, 错误: {str(e)}")

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

        # 提取图片数量用于分析
        content = mock_entry.get('description', '') or mock_entry.get('summary', '')
        images = extract_and_clean_images(content)

        # 判断消息模式
        is_image_focused = len(images) >= 2
        mode = "图片为主" if is_image_focused else "文字为主"
        logging.info(f"SHOW命令消息模式判断: {len(images)}张图片 -> {mode}模式")

        # 发送分析信息
        analysis_message = (
            f"🔧 SHOW命令分析结果：\n"
            f"------------------------------------\n"
            f"📰 标题: {mock_entry['title']}\n"
            f"👤 作者: {mock_entry.get('author', '无')}\n"
            f"🖼️ 图片数量: {len(images)}\n"
            f"📊 消息模式: {mode}\n"
            f"------------------------------------\n"
            f"正在发送实际消息..."
        )
        await update.message.reply_text(analysis_message)

        # 使用新的智能消息发送逻辑
        logging.info(f"SHOW命令开始调用send_entry_with_media，模式: {mode}")
        await send_entry_with_media(context.bot, chat_id, mock_entry, 1, 1)

        logging.info(f"SHOW命令执行成功，已发送条目: {mock_entry.get('title', 'Unknown')}, 图片数量: {len(images)}, 模式: {mode}")

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
            pub_time = datetime.fromtimestamp(time.mktime(entry.published_parsed))
            published_time = pub_time.strftime("%Y-%m-%d %H:%M")
        except:
            pass
    elif entry.get('published'):
        published_time = entry.get('published', '')[:16]  # 截取前16个字符

    # 选择描述内容（优先使用description，其次summary）
    content = entry_description if entry_description else entry_summary

    # 构建消息（时间在顶部）
    entry_message = f"🕒 {published_time}\n" if published_time else ""
    entry_message += f"📰 {entry_title}\n"

    if entry_link:
        entry_message += f"🔗 {entry_link}\n"

    if content:
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
            entry_message += f"\n📝 {clean_content}\n"

        # 添加图片链接
        if images:
            entry_message += f"\n🖼️ 图片:\n"
            for img_url in images[:3]:  # 最多显示3张图片
                entry_message += f"• {img_url}\n"

    # 添加序号信息
    entry_message += f"\n📊 {current_index}/{total_count}"

    return entry_message
