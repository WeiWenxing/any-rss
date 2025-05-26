"""
抖音调试命令模块
专门用于各种抖音相关的测试和调试功能
"""

import logging
import json
import asyncio
import tempfile
import os
import time
from telegram import Update, Bot
from telegram.ext import ContextTypes, CommandHandler, Application, MessageHandler, filters

from .formatter import DouyinFormatter
from .sender import send_douyin_content


# 全局实例
douyin_formatter = DouyinFormatter()

# 用户状态管理
user_upload_states = {}
STATE_TIMEOUT = 300  # 5分钟超时


async def douyin_debug_show_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    调试版本的抖音内容展示命令，用于测试单个抖音数据的格式化和发送
    用法1: /douyin_debug_show (无参数，提示上传文件)
    用法2: /douyin_debug_show <JSON数据> (传统方式，适用于短JSON)
    """
    try:
        user = update.message.from_user
        chat_id = update.message.chat_id
        logging.info(f"收到DOUYIN_DEBUG_SHOW命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

        if not context.args:
            # 无参数模式：提示用户上传文件
            user_upload_states[user.id] = {
                'command': 'debug_show',
                'timestamp': time.time(),
                'chat_id': chat_id
            }

            help_text = (
                f"📁 **抖音内容调试 - 文件上传模式**\n\n"
                f"请上传包含抖音内容数据的JSON文件进行调试。\n\n"
                f"📋 **文件要求：**\n"
                f"• 文件格式：.json\n"
                f"• 文件大小：< 10MB\n"
                f"• 必要字段：aweme\\_id, title, type\n\n"
                f"🔧 **获取样例文件：**\n"
                f"• `/douyin_debug_file simple` - 基础样例\n"
                f"• `/douyin_debug_file full` - 完整样例\n\n"
                f"⏰ **注意：**\n"
                f"• 请在5分钟内上传文件\n"
                f"• 上传文件后会自动执行完整调试\n"
                f"• 包含格式化预览和实际媒体发送\n\n"
                f"💡 **其他调试方式：**\n"
                f"• `/douyin_debug_url` <链接> - 通过抖音链接调试\n"
                f"• `/douyin_debug_format` - 只测试格式化\n"
                f"• 直接上传JSON文件 - 无需命令"
            )

            await update.message.reply_text(help_text, parse_mode='Markdown')
            logging.info(f"用户 {user.id} 进入文件上传等待状态")
            return

        # 有参数模式：传统JSON参数处理（保持向后兼容）
        # 合并所有参数作为JSON字符串
        json_str = " ".join(context.args)
        logging.info(f"DOUYIN_DEBUG_SHOW命令接收到的JSON长度: {len(json_str)} 字符")

        # 解析JSON数据
        try:
            content_info = json.loads(json_str)
            logging.info(f"成功解析JSON数据，包含字段: {list(content_info.keys())}")
        except json.JSONDecodeError as e:
            logging.error(f"JSON解析失败: {str(e)}")
            await update.message.reply_text(
                f"❌ JSON格式错误: {str(e)}\n\n"
                "💡 **建议使用文件上传模式：**\n"
                "1. 发送 `/douyin_debug_show` (无参数)\n"
                "2. 按提示上传JSON文件\n\n"
                "这样可以避免长JSON的问题！"
            )
            return

        # 验证必要字段
        required_fields = ["aweme_id", "title", "type"]
        missing_fields = [field for field in required_fields if field not in content_info]

        if missing_fields:
            await update.message.reply_text(
                f"❌ 缺少必要字段: {', '.join(missing_fields)}\n\n"
                f"必要字段: {', '.join(required_fields)}"
            )
            return

        # 执行调试处理
        await _process_debug_show(update, context, content_info, "参数传入")

    except Exception as e:
        logging.error(f"DOUYIN_DEBUG_SHOW命令执行失败: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 命令执行失败: {str(e)}")


async def _process_debug_show(update: Update, context: ContextTypes.DEFAULT_TYPE, content_info: dict, source: str) -> None:
    """
    处理抖音调试展示的核心逻辑

    Args:
        update: Telegram更新对象
        context: 上下文对象
        content_info: 抖音内容信息
        source: 数据来源描述
    """
    try:
        # 导入fetcher来处理内容信息
        from .fetcher import DouyinFetcher
        fetcher = DouyinFetcher()

        # 使用extract_content_info处理原始JSON数据，确保media_type等字段被正确设置
        processed_content_info = fetcher.extract_content_info(content_info)
        if not processed_content_info:
            await update.message.reply_text("❌ 处理内容信息失败")
            return

        # 使用处理后的数据
        content_info = processed_content_info

        title = content_info.get('title', 'Unknown')
        aweme_id = content_info.get('aweme_id', 'Unknown')
        content_type = content_info.get('type', 'Unknown')
        media_type = content_info.get('media_type', 'Unknown')
        chat_id = update.message.chat_id

        logging.info(f"解析到内容: ID={aweme_id}, 标题={title}, 类型={content_type}, 媒体类型={media_type}, 来源={source}")

        # 发送状态消息
        status_msg = await update.message.reply_text(
            f"🔄 开始调试抖音内容...\n"
            f"📋 ID: {aweme_id}\n"
            f"📝 标题: {title}\n"
            f"📱 类型: {content_type}\n"
            f"🎬 媒体类型: {media_type}\n"
            f"📥 数据来源: {source}"
        )

        # 格式化消息预览
        try:
            message_text = douyin_formatter.format_content_message(content_info)
            caption = douyin_formatter.format_caption(content_info)

            preview_text = (
                f"📊 格式化结果预览:\n\n"
                f"🔹 消息文本 (前200字符):\n"
                f"{message_text[:200]}{'...' if len(message_text) > 200 else ''}\n\n"
                f"🔹 媒体标题 (前100字符):\n"
                f"{caption[:100]}{'...' if len(caption) > 100 else ''}\n\n"
                f"📏 消息长度: {len(message_text)} 字符\n"
                f"📏 标题长度: {len(caption)} 字符"
            )

            await status_msg.edit_text(preview_text)

            # 等待一下再发送实际内容
            await asyncio.sleep(2)

        except Exception as format_error:
            logging.error(f"格式化预览失败: {str(format_error)}", exc_info=True)
            await status_msg.edit_text(f"❌ 格式化预览失败: {str(format_error)}")
            return

        # 发送实际内容
        try:
            await update.message.reply_text("🚀 开始发送实际内容...")

            # 使用抖音内容发送函数
            await send_douyin_content(
                bot=context.bot,
                content_info=content_info,
                douyin_url=f"debug://{source}",  # 调试用的虚拟URL
                target_chat_id=str(chat_id)
            )

            await update.message.reply_text(f"✅ 抖音内容调试发送成功！\n📥 数据来源: {source}")
            logging.info(f"DOUYIN_DEBUG_SHOW命令执行成功: {aweme_id}, 来源: {source}")

        except Exception as send_error:
            logging.error(f"发送抖音内容失败: {str(send_error)}", exc_info=True)
            await update.message.reply_text(f"❌ 发送失败: {str(send_error)}")

    except Exception as e:
        logging.error(f"处理调试展示失败: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 处理失败: {str(e)}")


async def douyin_debug_format_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    调试抖音内容格式化命令，只显示格式化结果不发送媒体
    用法: /douyin_debug_format <JSON数据>
    """
    try:
        user = update.message.from_user
        chat_id = update.message.chat_id
        logging.info(f"收到DOUYIN_DEBUG_FORMAT命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

        if not context.args:
            await update.message.reply_text(
                "❌ 请提供抖音内容JSON数据\n\n"
                "用法: /douyin_debug_format <JSON数据>\n\n"
                "💡 此命令只显示格式化结果，不发送媒体文件"
            )
            return

        # 合并所有参数作为JSON字符串
        json_str = " ".join(context.args)
        logging.info(f"DOUYIN_DEBUG_FORMAT命令接收到的JSON长度: {len(json_str)} 字符")

        # 解析JSON数据
        try:
            content_info = json.loads(json_str)
            logging.info(f"成功解析JSON数据，包含字段: {list(content_info.keys())}")
        except json.JSONDecodeError as e:
            logging.error(f"JSON解析失败: {str(e)}")
            await update.message.reply_text(f"❌ JSON格式错误: {str(e)}")
            return

        # 格式化内容
        try:
            message_text = douyin_formatter.format_content_message(content_info)
            caption = douyin_formatter.format_caption(content_info)

            # 构建详细的格式化结果
            result_text = (
                f"📊 抖音内容格式化结果\n\n"
                f"🔹 完整消息文本:\n"
                f"{'='*30}\n"
                f"{message_text}\n"
                f"{'='*30}\n\n"
                f"🔹 媒体标题:\n"
                f"{'='*20}\n"
                f"{caption}\n"
                f"{'='*20}\n\n"
                f"📊 统计信息:\n"
                f"• 消息长度: {len(message_text)} 字符\n"
                f"• 标题长度: {len(caption)} 字符\n"
                f"• 媒体类型: {content_info.get('type', 'Unknown')}\n"
                f"• 作者: {content_info.get('nickname', 'Unknown')}\n"
                f"• 发布时间: {content_info.get('time', 'Unknown')}"
            )

            # 如果消息太长，分段发送
            if len(result_text) > 4000:
                # 分段发送
                await update.message.reply_text(
                    f"📊 抖音内容格式化结果\n\n"
                    f"🔹 完整消息文本:\n"
                    f"{'='*30}"
                )
                await update.message.reply_text(message_text)
                await update.message.reply_text(
                    f"{'='*30}\n\n"
                    f"🔹 媒体标题:\n"
                    f"{'='*20}"
                )
                await update.message.reply_text(caption)
                await update.message.reply_text(
                    f"{'='*20}\n\n"
                    f"📊 统计信息:\n"
                    f"• 消息长度: {len(message_text)} 字符\n"
                    f"• 标题长度: {len(caption)} 字符\n"
                    f"• 媒体类型: {content_info.get('type', 'Unknown')}\n"
                    f"• 作者: {content_info.get('nickname', 'Unknown')}\n"
                    f"• 发布时间: {content_info.get('time', 'Unknown')}"
                )
            else:
                await update.message.reply_text(result_text)

            logging.info(f"DOUYIN_DEBUG_FORMAT命令执行成功")

        except Exception as format_error:
            logging.error(f"格式化失败: {str(format_error)}", exc_info=True)
            await update.message.reply_text(f"❌ 格式化失败: {str(format_error)}")

    except Exception as e:
        logging.error(f"DOUYIN_DEBUG_FORMAT命令执行失败: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 命令执行失败: {str(e)}")


async def douyin_debug_sample_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    提供抖音调试数据样例
    用法: /douyin_debug_sample [type]
    type: simple(默认) | full
    """
    try:
        user = update.message.from_user
        chat_id = update.message.chat_id
        logging.info(f"收到DOUYIN_DEBUG_SAMPLE命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

        # 检查参数，决定返回简单样例还是完整样例
        sample_type = "simple"
        if context.args and len(context.args) > 0:
            sample_type = context.args[0].lower()

        if sample_type == "full":
            # 提供完整的示例数据（包含视频信息）
            sample_data = {
                "aweme_id": "7478284850366090536",
                "nickname": "小神仙",
                "avatar": "https://p3-pc.douyinpic.com/aweme/100x100/aweme-avatar/tos-cn-avt-0015_0c674ba9c10210a155778a3b29f2987e.jpeg?from=327834062",
                "share_url": "https://www.iesdouyin.com/share/video/7478284850366090536/?region=CN&mid=7456268046764739366&u_code=154976742&did=MS4wLjABAAAAaQQlJ5k7rEi3LJKVPpMRgdlMiKvnRcdfjHHxdel0lXeTIITq7Jd5YHddBbu5_TU9&iid=MS4wLjABAAAANwkJuWIRFOzg5uCpDRpMj4OX-QryoDgn-yYlXQnRwQQ&with_sec_did=1&video_share_track_ver=&titleType=title&share_sign=.0pxqWyhpVdxMZjSwJAfbPMwX7SESw6nuq19wVph1mc-&share_version=290100&ts=1748223024&from_aid=6383&from_ssr=1",
                "author": "小神仙",
                "title": "人在知足时最幸福",
                "comment": 663,
                "play": 0,
                "like": 40477,
                "pic": "https://p3-pc-sign.douyinpic.com/tos-cn-p-0015/oUp8Bi9xQINZvgsBHI3nAs2yNyiAAIIIQzgPI~tplv-dy-360p.jpeg?lk3s=138a59ce&x-expires=1749430800&x-signature=7epG7y8Qsr%2Ff0f7rcKwuDxRQnD8%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=false&sc=origin_cover&biz_tag=pcweb_cover&l=202505260930231DBC771B80C9F87B513B",
                "pic_list": [
                    "https://p3-pc-sign.douyinpic.com/tos-cn-p-0015/oUp8Bi9xQINZvgsBHI3nAs2yNyiAAIIIQzgPI~tplv-dy-360p.jpeg?lk3s=138a59ce&x-expires=1749430800&x-signature=7epG7y8Qsr%2Ff0f7rcKwuDxRQnD8%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=false&sc=origin_cover&biz_tag=pcweb_cover&l=202505260930231DBC771B80C9F87B513B",
                    "https://p9-pc-sign.douyinpic.com/tos-cn-p-0015/oUp8Bi9xQINZvgsBHI3nAs2yNyiAAIIIQzgPI~tplv-dy-360p.jpeg?lk3s=138a59ce&x-expires=1749430800&x-signature=NN2ia%2Ff%2FpKEAyHXfIUJnfwUwjtA%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=false&sc=origin_cover&biz_tag=pcweb_cover&l=202505260930231DBC771B80C9F87B513B"
                ],
                "type": "视频",
                "video_info": {
                    "id": "v0200fg10000cv435mnog65j826sr7og",
                    "pic": "https://p3-pc-sign.douyinpic.com/tos-cn-p-0015/oUp8Bi9xQINZvgsBHI3nAs2yNyiAAIIIQzgPI~tplv-dy-360p.jpeg?lk3s=138a59ce&x-expires=1749430800&x-signature=7epG7y8Qsr%2Ff0f7rcKwuDxRQnD8%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=false&sc=origin_cover&biz_tag=pcweb_cover&l=202505260930231DBC771B80C9F87B513B",
                    "pic_list": [
                        "https://p3-pc-sign.douyinpic.com/tos-cn-p-0015/oUp8Bi9xQINZvgsBHI3nAs2yNyiAAIIIQzgPI~tplv-dy-360p.jpeg?lk3s=138a59ce&x-expires=1749430800&x-signature=7epG7y8Qsr%2Ff0f7rcKwuDxRQnD8%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=false&sc=origin_cover&biz_tag=pcweb_cover&l=202505260930231DBC771B80C9F87B513B",
                        "https://p9-pc-sign.douyinpic.com/tos-cn-p-0015/oUp8Bi9xQINZvgsBHI3nAs2yNyiAAIIIQzgPI~tplv-dy-360p.jpeg?lk3s=138a59ce&x-expires=1749430800&x-signature=NN2ia%2Ff%2FpKEAyHXfIUJnfwUwjtA%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=false&sc=origin_cover&biz_tag=pcweb_cover&l=202505260930231DBC771B80C9F87B513B"
                    ],
                    "height": 635,
                    "width": 360,
                    "size": "1.4 MB",
                    "url": "https://v3-web.douyinvod.com/022c59e81ce506a211255f7363581edc/6833ee6c/video/tos/cn/tos-cn-ve-15/oUDBCbaffIWnFAAmQLWi9PPDgEEACIgRguy6Iy/?a=6383&ch=10010&cr=3&dr=0&lr=all&cd=0%7C0%7C0%7C3&cv=1&br=890&bt=890&cs=0&ds=4&ft=LjhJEL998xsRu.0mD0P5XEhX.xiXO~QjRVJE2wpHpCPD-Ipz&mime_type=video_mp4&qs=0&rc=MzY5Ojs3ZWQ7Zzk2aWU1ZEBpajp2NW05cnA2eTMzNGkzM0A0LzViMDYvNWIxXy4zMy4zYSNsbzM1MmRrMjFgLS1kLS9zcw%3D%3D&btag=80000e00008000&cquery=100x_100z_100o_101r_100B&dy_q=1748223024&feature_id=46a7bb47b4fd1280f3d3825bf2b29388&l=202505260930231DBC771B80C9F87B513B",
                    "download": "https://www.douyin.com/aweme/v1/play/?video_id=v0200fg10000cv435mnog65j826sr7og&line=0&file_id=6a126b6f13b64de88a2b9438e7862370&sign=5d1445fffb4589320262cdc5ac73b32b&is_play_url=1&source=PackSourceEnum_PUBLISH",
                    "download2": "https://www.douyin.com/aweme/v1/play/?video_id=v0200fg10000cv435mnog65j826sr7og&ratio=1080p&line=0"
                },
                "music_info": {
                    "id": 7456268046764739366,
                    "title": "@何存真创作的原声",
                    "author": "何存真",
                    "pic": "https://p3-pc.douyinpic.com/aweme/1080x1080/aweme-avatar/tos-cn-avt-0015_f33e41e1b7ce95a229bdf0d697889fc1.jpeg?from=327834062",
                    "pic_list": [
                        "https://p3-pc.douyinpic.com/aweme/1080x1080/aweme-avatar/tos-cn-avt-0015_f33e41e1b7ce95a229bdf0d697889fc1.jpeg?from=327834062"
                    ],
                    "url": "https://sf5-hl-cdn-tos.douyinstatic.com/obj/ies-music/7456268160275073830.mp3",
                    "url_list": [
                        "https://sf5-hl-cdn-tos.douyinstatic.com/obj/ies-music/7456268160275073830.mp3",
                        "https://sf5-hl-ali-cdn-tos.douyinstatic.com/obj/ies-music/7456268160275073830.mp3"
                    ],
                    "duration": "0分14秒",
                    "height": 720,
                    "width": 720,
                    "owner_nickname": "何存真"
                },
                "images_info": {
                    "images": [
                        "不是图文没有信息"
                    ],
                    "height": "不是图文没有信息",
                    "width": "不是图文没有信息"
                },
                "hot_words": {
                    "text_extra": [],
                    "hashtag_id": None,
                    "start": None
                },
                "time": "2025-03-05"
            }

            sample_description = "完整视频数据样例（包含视频下载链接、音乐信息等）"
        else:
            # 提供简单的示例数据
            sample_data = {
                "aweme_id": "7478284850366090536",
                "nickname": "小神仙",
                "avatar": "https://p3-pc.douyinpic.com/aweme/100x100/aweme-avatar/tos-cn-avt-0015_0c674ba9c10210a155778a3b29f2987e.jpeg?from=327834062",
                "share_url": "https://www.iesdouyin.com/share/video/7478284850366090536/",
                "author": "小神仙",
                "title": "人在知足时最幸福",
                "comment": 663,
                "play": 0,
                "like": 40477,
                "type": "视频",
                "time": "2025-03-05"
            }

            sample_description = "简单数据样例（基础字段）"

        # 格式化JSON字符串
        json_str = json.dumps(sample_data, ensure_ascii=False, indent=2)

        # 计算各部分长度
        header_base = f"📋 抖音调试数据样例 - {sample_description}\n\n🔹 使用方法:\n1. 复制下面的JSON数据\n2. 使用 `/douyin_debug_show` 或 `/douyin_debug_format` 命令\n3. 将JSON数据作为参数传入\n\n🔹 示例JSON数据:\n"
        footer_base = f"\n💡 提示:\n• `/douyin_debug_show` - 完整测试（包含媒体发送）\n• `/douyin_debug_format` - 只测试格式化\n• `/douyin_debug_sample` - 显示简单样例数据\n• `/douyin_debug_sample full` - 显示完整样例数据"
        json_with_markdown = f"```json\n{json_str}\n```"

        # 检查JSON是否太长需要分割
        if len(json_with_markdown) > 3500:  # 留出一些余量
            # JSON太长，需要分割发送
            await update.message.reply_text(header_base)

            # 分割JSON字符串
            json_lines = json_str.split('\n')
            current_chunk = "```json\n"

            for line in json_lines:
                # 检查添加这一行是否会超过限制
                test_chunk = current_chunk + line + '\n'
                if len(test_chunk + "```") > 3800:  # 留出余量给结束标记
                    # 发送当前块
                    current_chunk += "```"
                    await update.message.reply_text(current_chunk, parse_mode='Markdown')
                    # 开始新块
                    current_chunk = "```json\n" + line + '\n'
                else:
                    current_chunk += line + '\n'

            # 发送最后一块
            if current_chunk.strip() != "```json":
                current_chunk += "```"
                await update.message.reply_text(current_chunk, parse_mode='Markdown')

            # 发送提示信息
            await update.message.reply_text(footer_base)

        elif len(header_base + json_with_markdown + footer_base) > 4000:
            # 整体太长但JSON不太长，分段发送
            header_text = (
                f"📋 抖音调试数据样例 - {sample_description}\n\n"
                f"🔹 使用方法:\n"
                f"1. 复制下面的JSON数据\n"
                f"2. 使用 `/douyin_debug_show` 或 `/douyin_debug_format` 命令\n"
                f"3. 将JSON数据作为参数传入\n\n"
                f"🔹 示例JSON数据:"
            )

            footer_text = (
                f"💡 提示:\n"
                f"• `/douyin_debug_show` - 完整测试（包含媒体发送）\n"
                f"• `/douyin_debug_format` - 只测试格式化\n"
                f"• `/douyin_debug_sample` - 显示简单样例数据\n"
                f"• `/douyin_debug_sample full` - 显示完整样例数据"
            )

            await update.message.reply_text(header_text)
            await update.message.reply_text(json_with_markdown, parse_mode='Markdown')
            await update.message.reply_text(footer_text)
        else:
            # 整体长度合适，一次发送
            help_text = header_base + json_with_markdown + footer_base
            await update.message.reply_text(help_text, parse_mode='Markdown')

        logging.info(f"DOUYIN_DEBUG_SAMPLE命令执行成功，类型: {sample_type}")

    except Exception as e:
        logging.error(f"DOUYIN_DEBUG_SAMPLE命令执行失败: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 命令执行失败: {str(e)}")


async def douyin_debug_file_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    提供抖音调试数据文件下载
    用法: /douyin_debug_file [type]
    type: simple(默认) | full
    """
    try:
        user = update.message.from_user
        chat_id = update.message.chat_id
        logging.info(f"收到DOUYIN_DEBUG_FILE命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

        # 检查参数，决定返回简单样例还是完整样例
        sample_type = "simple"
        if context.args and len(context.args) > 0:
            sample_type = context.args[0].lower()

        if sample_type == "full":
            # 提供完整的示例数据（包含视频信息）
            sample_data = {
                "aweme_id": "7478284850366090536",
                "nickname": "小神仙",
                "avatar": "https://p3-pc.douyinpic.com/aweme/100x100/aweme-avatar/tos-cn-avt-0015_0c674ba9c10210a155778a3b29f2987e.jpeg?from=327834062",
                "share_url": "https://www.iesdouyin.com/share/video/7478284850366090536/?region=CN&mid=7456268046764739366&u_code=154976742&did=MS4wLjABAAAAaQQlJ5k7rEi3LJKVPpMRgdlMiKvnRcdfjHHxdel0lXeTIITq7Jd5YHddBbu5_TU9&iid=MS4wLjABAAAANwkJuWIRFOzg5uCpDRpMj4OX-QryoDgn-yYlXQnRwQQ&with_sec_did=1&video_share_track_ver=&titleType=title&share_sign=.0pxqWyhpVdxMZjSwJAfbPMwX7SESw6nuq19wVph1mc-&share_version=290100&ts=1748223024&from_aid=6383&from_ssr=1",
                "author": "小神仙",
                "title": "人在知足时最幸福",
                "comment": 663,
                "play": 0,
                "like": 40477,
                "pic": "https://p3-pc-sign.douyinpic.com/tos-cn-p-0015/oUp8Bi9xQINZvgsBHI3nAs2yNyiAAIIIQzgPI~tplv-dy-360p.jpeg?lk3s=138a59ce&x-expires=1749430800&x-signature=7epG7y8Qsr%2Ff0f7rcKwuDxRQnD8%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=false&sc=origin_cover&biz_tag=pcweb_cover&l=202505260930231DBC771B80C9F87B513B",
                "pic_list": [
                    "https://p3-pc-sign.douyinpic.com/tos-cn-p-0015/oUp8Bi9xQINZvgsBHI3nAs2yNyiAAIIIQzgPI~tplv-dy-360p.jpeg?lk3s=138a59ce&x-expires=1749430800&x-signature=7epG7y8Qsr%2Ff0f7rcKwuDxRQnD8%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=false&sc=origin_cover&biz_tag=pcweb_cover&l=202505260930231DBC771B80C9F87B513B",
                    "https://p9-pc-sign.douyinpic.com/tos-cn-p-0015/oUp8Bi9xQINZvgsBHI3nAs2yNyiAAIIIQzgPI~tplv-dy-360p.jpeg?lk3s=138a59ce&x-expires=1749430800&x-signature=NN2ia%2Ff%2FpKEAyHXfIUJnfwUwjtA%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=false&sc=origin_cover&biz_tag=pcweb_cover&l=202505260930231DBC771B80C9F87B513B"
                ],
                "type": "视频",
                "video_info": {
                    "id": "v0200fg10000cv435mnog65j826sr7og",
                    "pic": "https://p3-pc-sign.douyinpic.com/tos-cn-p-0015/oUp8Bi9xQINZvgsBHI3nAs2yNyiAAIIIQzgPI~tplv-dy-360p.jpeg?lk3s=138a59ce&x-expires=1749430800&x-signature=7epG7y8Qsr%2Ff0f7rcKwuDxRQnD8%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=false&sc=origin_cover&biz_tag=pcweb_cover&l=202505260930231DBC771B80C9F87B513B",
                    "pic_list": [
                        "https://p3-pc-sign.douyinpic.com/tos-cn-p-0015/oUp8Bi9xQINZvgsBHI3nAs2yNyiAAIIIQzgPI~tplv-dy-360p.jpeg?lk3s=138a59ce&x-expires=1749430800&x-signature=7epG7y8Qsr%2Ff0f7rcKwuDxRQnD8%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=false&sc=origin_cover&biz_tag=pcweb_cover&l=202505260930231DBC771B80C9F87B513B",
                        "https://p9-pc-sign.douyinpic.com/tos-cn-p-0015/oUp8Bi9xQINZvgsBHI3nAs2yNyiAAIIIQzgPI~tplv-dy-360p.jpeg?lk3s=138a59ce&x-expires=1749430800&x-signature=NN2ia%2Ff%2FpKEAyHXfIUJnfwUwjtA%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=false&sc=origin_cover&biz_tag=pcweb_cover&l=202505260930231DBC771B80C9F87B513B"
                    ],
                    "height": 635,
                    "width": 360,
                    "size": "1.4 MB",
                    "url": "https://v3-web.douyinvod.com/022c59e81ce506a211255f7363581edc/6833ee6c/video/tos/cn/tos-cn-ve-15/oUDBCbaffIWnFAAmQLWi9PPDgEEACIgRguy6Iy/?a=6383&ch=10010&cr=3&dr=0&lr=all&cd=0%7C0%7C0%7C3&cv=1&br=890&bt=890&cs=0&ds=4&ft=LjhJEL998xsRu.0mD0P5XEhX.xiXO~QjRVJE2wpHpCPD-Ipz&mime_type=video_mp4&qs=0&rc=MzY5Ojs3ZWQ7Zzk2aWU1ZEBpajp2NW05cnA2eTMzNGkzM0A0LzViMDYvNWIxXy4zMy4zYSNsbzM1MmRrMjFgLS1kLS9zcw%3D%3D&btag=80000e00008000&cquery=100x_100z_100o_101r_100B&dy_q=1748223024&feature_id=46a7bb47b4fd1280f3d3825bf2b29388&l=202505260930231DBC771B80C9F87B513B",
                    "download": "https://www.douyin.com/aweme/v1/play/?video_id=v0200fg10000cv435mnog65j826sr7og&line=0&file_id=6a126b6f13b64de88a2b9438e7862370&sign=5d1445fffb4589320262cdc5ac73b32b&is_play_url=1&source=PackSourceEnum_PUBLISH",
                    "download2": "https://www.douyin.com/aweme/v1/play/?video_id=v0200fg10000cv435mnog65j826sr7og&ratio=1080p&line=0"
                },
                "music_info": {
                    "id": 7456268046764739366,
                    "title": "@何存真创作的原声",
                    "author": "何存真",
                    "pic": "https://p3-pc.douyinpic.com/aweme/1080x1080/aweme-avatar/tos-cn-avt-0015_f33e41e1b7ce95a229bdf0d697889fc1.jpeg?from=327834062",
                    "pic_list": [
                        "https://p3-pc.douyinpic.com/aweme/1080x1080/aweme-avatar/tos-cn-avt-0015_f33e41e1b7ce95a229bdf0d697889fc1.jpeg?from=327834062"
                    ],
                    "url": "https://sf5-hl-cdn-tos.douyinstatic.com/obj/ies-music/7456268160275073830.mp3",
                    "url_list": [
                        "https://sf5-hl-cdn-tos.douyinstatic.com/obj/ies-music/7456268160275073830.mp3",
                        "https://sf5-hl-ali-cdn-tos.douyinstatic.com/obj/ies-music/7456268160275073830.mp3"
                    ],
                    "duration": "0分14秒",
                    "height": 720,
                    "width": 720,
                    "owner_nickname": "何存真"
                },
                "images_info": {
                    "images": [
                        "不是图文没有信息"
                    ],
                    "height": "不是图文没有信息",
                    "width": "不是图文没有信息"
                },
                "hot_words": {
                    "text_extra": [],
                    "hashtag_id": None,
                    "start": None
                },
                "time": "2025-03-05"
            }

            filename = "douyin_debug_sample_full.json"
            description = "完整视频数据样例（包含视频下载链接、音乐信息等）"
        else:
            # 提供简单的示例数据
            sample_data = {
                "aweme_id": "7478284850366090536",
                "nickname": "小神仙",
                "avatar": "https://p3-pc.douyinpic.com/aweme/100x100/aweme-avatar/tos-cn-avt-0015_0c674ba9c10210a155778a3b29f2987e.jpeg?from=327834062",
                "share_url": "https://www.iesdouyin.com/share/video/7478284850366090536/",
                "author": "小神仙",
                "title": "人在知足时最幸福",
                "comment": 663,
                "play": 0,
                "like": 40477,
                "type": "视频",
                "time": "2025-03-05"
            }

            filename = "douyin_debug_sample_simple.json"
            description = "简单数据样例（基础字段）"

        # 格式化JSON字符串
        json_str = json.dumps(sample_data, ensure_ascii=False, indent=2)

        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as temp_file:
            temp_file.write(json_str)
            temp_file_path = temp_file.name

        try:
            # 发送文件
            with open(temp_file_path, 'rb') as file:
                await update.message.reply_document(
                    document=file,
                    filename=filename,
                    caption=(
                        f"📋 抖音调试数据文件 - {description}\n\n"
                        f"💡 使用方法:\n"
                        f"1. 下载此JSON文件\n"
                        f"2. 复制文件内容\n"
                        f"3. 使用 `/douyin_debug_show` 或 `/douyin_debug_format` 命令\n"
                        f"4. 将JSON数据作为参数传入\n\n"
                        f"🔧 其他命令:\n"
                        f"• `/douyin_debug_sample` - 显示简单样例（消息形式）\n"
                        f"• `/douyin_debug_sample full` - 显示完整样例（消息形式）\n"
                        f"• `/douyin_debug_file` - 下载简单样例文件\n"
                        f"• `/douyin_debug_file full` - 下载完整样例文件"
                    ),
                    parse_mode='Markdown'
                )

            logging.info(f"DOUYIN_DEBUG_FILE命令执行成功，类型: {sample_type}")

        finally:
            # 清理临时文件
            try:
                os.unlink(temp_file_path)
            except Exception as cleanup_error:
                logging.warning(f"清理临时文件失败: {str(cleanup_error)}")

    except Exception as e:
        logging.error(f"DOUYIN_DEBUG_FILE命令执行失败: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 命令执行失败: {str(e)}")


async def douyin_debug_upload_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理用户上传的JSON文件进行抖音调试
    支持.json文件上传，根据用户状态决定处理方式
    """
    try:
        user = update.message.from_user
        chat_id = update.message.chat_id

        # 检查是否有文件
        if not update.message.document:
            return

        document = update.message.document

        # 检查文件类型
        if not (document.file_name.endswith('.json') or document.mime_type == 'application/json'):
            return

        logging.info(f"收到JSON文件上传 - 用户: {user.username}(ID:{user.id}) 文件: {document.file_name}")

        # 清理超时的用户状态
        _cleanup_expired_states()

        # 检查用户状态
        user_state = user_upload_states.get(user.id)
        if user_state:
            # 用户在等待文件上传状态
            command_type = user_state.get('command')
            logging.info(f"用户 {user.id} 处于 {command_type} 等待状态，处理文件上传")

            # 清除用户状态
            del user_upload_states[user.id]

            # 根据命令类型处理
            if command_type == 'debug_show':
                await _handle_debug_show_upload(update, context, document)
            else:
                await update.message.reply_text(f"❌ 未知的命令类型: {command_type}")
        else:
            # 用户没有等待状态，使用通用处理
            logging.info(f"用户 {user.id} 无等待状态，使用通用文件处理")
            await _handle_general_upload(update, context, document)

    except Exception as e:
        logging.error(f"处理JSON文件上传失败: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 处理文件失败: {str(e)}")


async def _handle_debug_show_upload(update: Update, context: ContextTypes.DEFAULT_TYPE, document) -> None:
    """
    处理debug_show命令的文件上传
    """
    try:
        # 检查文件大小（限制10MB）
        if document.file_size > 10 * 1024 * 1024:
            await update.message.reply_text("❌ 文件太大，请上传小于10MB的JSON文件")
            return

        # 发送处理状态
        status_msg = await update.message.reply_text(
            f"🔄 正在处理JSON文件: {document.file_name}\n"
            f"📏 文件大小: {document.file_size} 字节\n"
            f"🎯 调试模式: 完整展示（格式化+发送）"
        )

        # 下载并解析文件
        content_info = await _download_and_parse_json(context, document, status_msg)
        if not content_info:
            return

        # 验证必要字段
        required_fields = ["aweme_id", "title", "type"]
        missing_fields = [field for field in required_fields if field not in content_info]

        if missing_fields:
            await status_msg.edit_text(
                f"❌ 缺少必要字段: {', '.join(missing_fields)}\n\n"
                f"必要字段: {', '.join(required_fields)}"
            )
            return

        # 更新状态
        title = content_info.get('title', 'Unknown')
        aweme_id = content_info.get('aweme_id', 'Unknown')
        content_type = content_info.get('type', 'Unknown')
        media_type = content_info.get('media_type', 'Unknown')

        await status_msg.edit_text(
            f"✅ JSON文件解析成功！\n"
            f"📋 ID: {aweme_id}\n"
            f"📝 标题: {title}\n"
            f"📱 类型: {content_type}\n"
            f"🎬 媒体类型: {media_type}\n"
            f"📁 文件: {document.file_name}\n\n"
            f"🔄 开始完整调试处理..."
        )

        # 执行调试处理
        await _process_debug_show(update, context, content_info, f"文件上传({document.file_name})")

    except Exception as e:
        logging.error(f"处理debug_show文件上传失败: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 处理失败: {str(e)}")


async def _handle_general_upload(update: Update, context: ContextTypes.DEFAULT_TYPE, document) -> None:
    """
    处理通用的JSON文件上传（原有逻辑）
    """
    try:
        # 检查文件大小（限制10MB）
        if document.file_size > 10 * 1024 * 1024:
            await update.message.reply_text("❌ 文件太大，请上传小于10MB的JSON文件")
            return

        # 发送处理状态
        status_msg = await update.message.reply_text(
            f"🔄 正在处理JSON文件: {document.file_name}\n"
            f"📏 文件大小: {document.file_size} 字节\n"
            f"🎯 调试模式: 通用处理"
        )

        # 下载并解析文件
        content_info = await _download_and_parse_json(context, document, status_msg)
        if not content_info:
            return

        # 验证必要字段
        required_fields = ["aweme_id", "title", "type"]
        missing_fields = [field for field in required_fields if field not in content_info]

        if missing_fields:
            await status_msg.edit_text(
                f"❌ 缺少必要字段: {', '.join(missing_fields)}\n\n"
                f"必要字段: {', '.join(required_fields)}"
            )
            return

        # 更新状态
        title = content_info.get('title', 'Unknown')
        aweme_id = content_info.get('aweme_id', 'Unknown')
        content_type = content_info.get('type', 'Unknown')
        media_type = content_info.get('media_type', 'Unknown')

        await status_msg.edit_text(
            f"✅ JSON文件解析成功！\n"
            f"📋 ID: {aweme_id}\n"
            f"📝 标题: {title}\n"
            f"📱 类型: {content_type}\n"
            f"🎬 媒体类型: {media_type}\n"
            f"📁 文件: {document.file_name}\n\n"
            f"🔄 开始调试处理..."
        )

        # 执行调试处理
        await _process_debug_show(update, context, content_info, f"通用上传({document.file_name})")

    except Exception as e:
        logging.error(f"处理通用文件上传失败: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 处理失败: {str(e)}")


async def _download_and_parse_json(context: ContextTypes.DEFAULT_TYPE, document, status_msg) -> dict:
    """
    下载并解析JSON文件

    Returns:
        dict: 解析后的JSON数据，失败时返回None
    """
    try:
        # 下载文件
        file = await context.bot.get_file(document.file_id)

        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w+b', suffix='.json', delete=False) as temp_file:
            temp_file_path = temp_file.name

        try:
            # 下载到临时文件
            await file.download_to_drive(temp_file_path)

            # 读取并解析JSON
            with open(temp_file_path, 'r', encoding='utf-8') as f:
                json_content = f.read()

            # 解析JSON
            try:
                content_info = json.loads(json_content)
                logging.info(f"成功解析JSON文件，包含字段: {list(content_info.keys())}")
                return content_info
            except json.JSONDecodeError as e:
                await status_msg.edit_text(f"❌ JSON格式错误: {str(e)}")
                return None

        finally:
            # 清理临时文件
            try:
                os.unlink(temp_file_path)
            except Exception as cleanup_error:
                logging.warning(f"清理临时文件失败: {str(cleanup_error)}")

    except Exception as e:
        logging.error(f"下载解析JSON文件失败: {str(e)}", exc_info=True)
        await status_msg.edit_text(f"❌ 下载文件失败: {str(e)}")
        return None


def _cleanup_expired_states():
    """清理超时的用户状态"""
    current_time = time.time()
    expired_users = []

    for user_id, state in user_upload_states.items():
        if current_time - state['timestamp'] > STATE_TIMEOUT:
            expired_users.append(user_id)

    for user_id in expired_users:
        del user_upload_states[user_id]
        logging.info(f"清理用户 {user_id} 的超时状态")

    if expired_users:
        logging.info(f"清理了 {len(expired_users)} 个超时的用户状态")


async def douyin_debug_url_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    通过URL获取JSON数据进行调试
    用法: /douyin_debug_url <抖音链接>
    """
    try:
        user = update.message.from_user
        chat_id = update.message.chat_id
        logging.info(f"收到DOUYIN_DEBUG_URL命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

        if not context.args:
            await update.message.reply_text(
                "❌ 请提供抖音链接\n\n"
                "用法: /douyin_debug_url <抖音链接>\n\n"
                "示例:\n"
                "• /douyin_debug_url https://v.douyin.com/iM5g7LsM/\n"
                "• /douyin_debug_url https://www.douyin.com/video/7478284850366090536\n\n"
                "💡 此命令会自动获取抖音内容并进行调试"
            )
            return

        douyin_url = context.args[0]
        logging.info(f"DOUYIN_DEBUG_URL命令接收到的链接: {douyin_url}")

        # 发送状态消息
        status_msg = await update.message.reply_text(
            f"🔄 正在获取抖音内容...\n"
            f"🔗 链接: {douyin_url}"
        )

        # 导入抖音获取器
        try:
            from .fetcher import DouyinFetcher
            fetcher = DouyinFetcher()

            # 获取抖音内容
            content_info = await fetcher.fetch_content(douyin_url)

            if not content_info:
                await status_msg.edit_text("❌ 无法获取抖音内容，请检查链接是否有效")
                return

            title = content_info.get('title', 'Unknown')
            aweme_id = content_info.get('aweme_id', 'Unknown')
            content_type = content_info.get('type', 'Unknown')
            media_type = content_info.get('media_type', 'Unknown')

            await status_msg.edit_text(
                f"✅ 抖音内容获取成功！\n"
                f"📋 ID: {aweme_id}\n"
                f"📝 标题: {title}\n"
                f"📱 类型: {content_type}\n"
                f"🎬 媒体类型: {media_type}\n\n"
                f"🔄 开始调试处理..."
            )

        except Exception as fetch_error:
            logging.error(f"获取抖音内容失败: {str(fetch_error)}", exc_info=True)
            await status_msg.edit_text(f"❌ 获取抖音内容失败: {str(fetch_error)}")
            return

        # 格式化预览
        try:
            message_text = douyin_formatter.format_content_message(content_info)
            caption = douyin_formatter.format_caption(content_info)

            preview_text = (
                f"📊 格式化结果预览:\n\n"
                f"🔹 消息文本 (前200字符):\n"
                f"{message_text[:200]}{'...' if len(message_text) > 200 else ''}\n\n"
                f"🔹 媒体标题 (前100字符):\n"
                f"{caption[:100]}{'...' if len(caption) > 100 else ''}\n\n"
                f"📏 消息长度: {len(message_text)} 字符\n"
                f"📏 标题长度: {len(caption)} 字符"
            )

            await update.message.reply_text(preview_text)

            # 等待一下再发送实际内容
            await asyncio.sleep(2)

        except Exception as format_error:
            logging.error(f"格式化预览失败: {str(format_error)}", exc_info=True)
            await update.message.reply_text(f"❌ 格式化预览失败: {str(format_error)}")
            return

        # 发送实际内容
        try:
            await update.message.reply_text("🚀 开始发送实际内容...")

            # 使用抖音内容发送函数
            await send_douyin_content(
                bot=context.bot,
                content_info=content_info,
                douyin_url=douyin_url,
                target_chat_id=str(chat_id)
            )

            await update.message.reply_text("✅ 抖音内容调试发送成功！")
            logging.info(f"DOUYIN_DEBUG_URL命令执行成功: {douyin_url} -> {aweme_id}")

        except Exception as send_error:
            logging.error(f"发送抖音内容失败: {str(send_error)}", exc_info=True)
            await update.message.reply_text(f"❌ 发送失败: {str(send_error)}")

    except Exception as e:
        logging.error(f"DOUYIN_DEBUG_URL命令执行失败: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 命令执行失败: {str(e)}")


def register_douyin_debug_commands(application: Application) -> None:
    """注册抖音调试命令"""
    application.add_handler(CommandHandler("douyin_debug_show", douyin_debug_show_command))
    application.add_handler(CommandHandler("douyin_debug_format", douyin_debug_format_command))
    application.add_handler(CommandHandler("douyin_debug_sample", douyin_debug_sample_command))
    application.add_handler(CommandHandler("douyin_debug_file", douyin_debug_file_command))
    application.add_handler(CommandHandler("douyin_debug_url", douyin_debug_url_command))

    # 添加文件上传处理器（只处理JSON文件）
    json_file_filter = filters.Document.FileExtension("json") | filters.Document.MimeType("application/json")
    application.add_handler(MessageHandler(json_file_filter, douyin_debug_upload_handler))

    logging.info("✅ 抖音调试命令注册完成")

