"""
Douyin1调试命令处理器

提供Douyin1模块的调试功能，包括账号状态检查、手动内容获取、统计信息查看等。
这些命令仅在DEBUG模式下可用，用于开发和故障排除。

主要功能：
1. /douyin1_debug_check - 检查抖音账号状态
2. /douyin1_debug_fetch - 手动获取最新内容
3. /douyin1_debug_stats - 查看模块统计信息
4. /douyin1_debug_test - 测试模块功能

作者: Assistant
创建时间: 2024年
"""

import logging
from typing import Dict, List, Optional
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, Application

from .commands import get_douyin1_command_handler


async def douyin1_debug_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /douyin1_debug_check 命令 - 检查抖音账号状态

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    try:
        user = update.message.from_user
        logging.info(f"🔍 收到douyin1_debug_check命令 - 用户: {user.username}(ID:{user.id})")

        # 参数验证
        if not context.args:
            await update.message.reply_text(
                "🔍 抖音账号状态检查\n\n"
                "用法: /douyin1_debug_check <抖音链接>\n\n"
                "示例:\n"
                "/douyin1_debug_check https://www.douyin.com/user/MS4wLjABAAAA...\n"
                "/douyin1_debug_check https://v.douyin.com/iM5g7LsM/"
            )
            return

        douyin_url = context.args[0].strip()
        logging.info(f"🔍 检查抖音账号状态: {douyin_url}")

        # 发送处理中消息
        processing_message = await update.message.reply_text(
            f"🔍 正在检查抖音账号状态...\n"
            f"🔗 链接: {douyin_url}\n"
            f"⏳ 请稍候..."
        )

        # 模拟检查过程
        try:
            # 获取命令处理器
            handler = get_douyin1_command_handler()
            
            # 模拟状态检查
            await processing_message.edit_text(
                f"✅ 抖音账号状态检查完成\n"
                f"🔗 链接: {douyin_url}\n"
                f"📊 状态: 正常（模拟结果）\n"
                f"📝 备注: 当前为模拟实现，实际功能待开发"
            )
            
        except Exception as e:
            logging.error(f"❌ 检查抖音账号状态失败: {e}", exc_info=True)
            await processing_message.edit_text(
                f"❌ 检查抖音账号状态失败\n"
                f"🔗 链接: {douyin_url}\n"
                f"❌ 错误: {str(e)}"
            )

    except Exception as e:
        logging.error(f"❌ 处理douyin1_debug_check命令时发生错误: {e}", exc_info=True)
        await update.message.reply_text(f"❌ 处理命令时发生错误: {str(e)}")


async def douyin1_debug_fetch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /douyin1_debug_fetch 命令 - 手动获取最新内容

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    try:
        user = update.message.from_user
        logging.info(f"📥 收到douyin1_debug_fetch命令 - 用户: {user.username}(ID:{user.id})")

        # 参数验证
        if not context.args:
            await update.message.reply_text(
                "📥 手动获取抖音最新内容\n\n"
                "用法: /douyin1_debug_fetch <抖音链接>\n\n"
                "示例:\n"
                "/douyin1_debug_fetch https://www.douyin.com/user/MS4wLjABAAAA...\n"
                "/douyin1_debug_fetch https://v.douyin.com/iM5g7LsM/"
            )
            return

        douyin_url = context.args[0].strip()
        logging.info(f"📥 手动获取内容: {douyin_url}")

        # 发送处理中消息
        processing_message = await update.message.reply_text(
            f"📥 正在获取最新内容...\n"
            f"🔗 链接: {douyin_url}\n"
            f"⏳ 请稍候..."
        )

        # 模拟获取过程
        try:
            # 获取命令处理器
            handler = get_douyin1_command_handler()
            
            # 模拟内容获取
            await processing_message.edit_text(
                f"✅ 最新内容获取完成\n"
                f"🔗 链接: {douyin_url}\n"
                f"📊 获取数量: 5 个（模拟结果）\n"
                f"📝 备注: 当前为模拟实现，实际功能待开发"
            )
            
        except Exception as e:
            logging.error(f"❌ 获取最新内容失败: {e}", exc_info=True)
            await processing_message.edit_text(
                f"❌ 获取最新内容失败\n"
                f"🔗 链接: {douyin_url}\n"
                f"❌ 错误: {str(e)}"
            )

    except Exception as e:
        logging.error(f"❌ 处理douyin1_debug_fetch命令时发生错误: {e}", exc_info=True)
        await update.message.reply_text(f"❌ 处理命令时发生错误: {str(e)}")


async def douyin1_debug_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /douyin1_debug_stats 命令 - 查看模块统计信息

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    try:
        user = update.message.from_user
        logging.info(f"📊 收到douyin1_debug_stats命令 - 用户: {user.username}(ID:{user.id})")

        # 获取命令处理器
        handler = get_douyin1_command_handler()
        
        # 获取统计信息
        subscriptions = handler.manager.get_subscriptions()
        
        # 计算统计数据
        total_sources = len(subscriptions)
        total_channels = sum(len(channels) for channels in subscriptions.values())
        
        # 构建统计信息
        stats_text = (
            f"📊 Douyin1模块统计信息\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 订阅统计:\n"
            f"  • 抖音账号数: {total_sources}\n"
            f"  • 订阅频道数: {total_channels}\n"
            f"  • 平均每账号订阅数: {total_channels / total_sources if total_sources > 0 else 0:.1f}\n\n"
            f"🔧 模块状态:\n"
            f"  • 模块名称: douyin1\n"
            f"  • 命令处理器: 已初始化\n"
            f"  • 管理器类型: MockDouyin1Manager（模拟）\n"
            f"  • 数据目录: {handler.manager.data_dir}\n\n"
            f"📝 备注: 当前使用模拟管理器，实际功能待开发"
        )
        
        await update.message.reply_text(stats_text)

    except Exception as e:
        logging.error(f"❌ 处理douyin1_debug_stats命令时发生错误: {e}", exc_info=True)
        await update.message.reply_text(f"❌ 处理命令时发生错误: {str(e)}")


async def douyin1_debug_test_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /douyin1_debug_test 命令 - 测试模块功能

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    try:
        user = update.message.from_user
        logging.info(f"🧪 收到douyin1_debug_test命令 - 用户: {user.username}(ID:{user.id})")

        # 发送测试开始消息
        test_message = await update.message.reply_text(
            f"🧪 开始测试Douyin1模块功能...\n"
            f"⏳ 请稍候..."
        )

        # 执行测试
        try:
            # 获取命令处理器
            handler = get_douyin1_command_handler()
            
            # 测试项目
            test_results = []
            
            # 测试1: 命令处理器初始化
            test_results.append("✅ 命令处理器初始化: 正常")
            
            # 测试2: 管理器功能
            test_results.append("✅ 管理器功能: 正常（模拟）")
            
            # 测试3: URL验证
            test_url = "https://www.douyin.com/user/test"
            url_valid, _ = handler._validate_source_url(test_url)
            test_results.append(f"✅ URL验证: {'正常' if url_valid else '异常'}")
            
            # 测试4: 频道ID验证
            chat_valid, _ = handler.validate_chat_id("@test_channel")
            test_results.append(f"✅ 频道ID验证: {'正常' if chat_valid else '异常'}")
            
            # 构建测试结果
            results_text = (
                f"🧪 Douyin1模块功能测试完成\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📋 测试结果:\n"
                + "\n".join(f"  {result}" for result in test_results) +
                f"\n\n📝 备注: 当前为基础功能测试，实际业务逻辑待开发"
            )
            
            await test_message.edit_text(results_text)
            
        except Exception as e:
            logging.error(f"❌ 模块功能测试失败: {e}", exc_info=True)
            await test_message.edit_text(
                f"❌ 模块功能测试失败\n"
                f"❌ 错误: {str(e)}"
            )

    except Exception as e:
        logging.error(f"❌ 处理douyin1_debug_test命令时发生错误: {e}", exc_info=True)
        await update.message.reply_text(f"❌ 处理命令时发生错误: {str(e)}")


def register_douyin1_debug_commands(application: Application) -> None:
    """
    注册Douyin1调试命令处理器

    Args:
        application: Telegram应用实例
    """
    # 注册调试命令
    application.add_handler(CommandHandler("douyin1_debug_check", douyin1_debug_check_command))
    application.add_handler(CommandHandler("douyin1_debug_fetch", douyin1_debug_fetch_command))
    application.add_handler(CommandHandler("douyin1_debug_stats", douyin1_debug_stats_command))
    application.add_handler(CommandHandler("douyin1_debug_test", douyin1_debug_test_command))

    logging.info("Douyin1调试命令处理器注册完成") 