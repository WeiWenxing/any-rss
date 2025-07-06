"""
Douyin1命令处理器模块

该模块负责处理所有Douyin1相关的Telegram命令，继承统一命令处理器基类。
支持抖音账号订阅的添加、删除和查看功能，提供统一的用户反馈体验。

主要功能：
1. /douyin1_add - 添加抖音账号订阅（包含完整的反馈流程）
2. /douyin1_del - 删除抖音账号订阅
3. /douyin1_list - 查看订阅列表
4. 抖音URL验证和格式化
5. 统一的错误处理和用户反馈

作者: Assistant
创建时间: 2024年
"""

import logging
import asyncio
from typing import Dict, List, Tuple, Optional
from urllib.parse import urlparse
from telegram import Update, Bot
from telegram.ext import ContextTypes, CommandHandler, Application

from services.common.unified_commands import UnifiedCommandHandler


class MockDouyin1Manager:
    """
    Douyin1管理器的模拟实现
    
    暂时提供基本的接口实现，用于命令处理器的UI测试
    实际的管理器将在后续步骤中实现
    """
    
    def __init__(self, data_dir: str = "storage/douyin1"):
        """
        初始化模拟管理器
        
        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = data_dir
        self.logger = logging.getLogger("douyin1_mock_manager")
        self.logger.info(f"Douyin1模拟管理器初始化 - 数据目录: {data_dir}")
        
        # 模拟订阅数据
        self._mock_subscriptions = {}
    
    def get_subscriptions(self) -> Dict[str, List[str]]:
        """
        获取订阅列表
        
        Returns:
            Dict[str, List[str]]: 订阅数据 {url: [chat_id1, chat_id2, ...]}
        """
        self.logger.info("获取订阅列表（模拟数据）")
        return self._mock_subscriptions.copy()
    
    async def add_subscription(self, source_url: str, chat_id: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        添加订阅
        
        Args:
            source_url: 抖音链接
            chat_id: 频道ID
            
        Returns:
            Tuple[bool, str, Optional[Dict]]: (成功标志, 错误信息, 额外信息)
        """
        self.logger.info(f"添加订阅（模拟）: {source_url} -> {chat_id}")
        
        # 模拟添加逻辑
        if source_url not in self._mock_subscriptions:
            self._mock_subscriptions[source_url] = []
        
        if chat_id not in self._mock_subscriptions[source_url]:
            self._mock_subscriptions[source_url].append(chat_id)
            return True, "", {"need_alignment": len(self._mock_subscriptions[source_url]) > 1}
        
        return False, "订阅已存在", None
    
    async def remove_subscription(self, source_url: str, chat_id: str) -> bool:
        """
        删除订阅
        
        Args:
            source_url: 抖音链接
            chat_id: 频道ID
            
        Returns:
            bool: 是否删除成功
        """
        self.logger.info(f"删除订阅（模拟）: {source_url} -> {chat_id}")
        
        if source_url in self._mock_subscriptions:
            if chat_id in self._mock_subscriptions[source_url]:
                self._mock_subscriptions[source_url].remove(chat_id)
                if not self._mock_subscriptions[source_url]:
                    del self._mock_subscriptions[source_url]
                return True
        
        return False
    
    def check_updates(self, source_url: str) -> Tuple[bool, str, List]:
        """
        检查更新
        
        Args:
            source_url: 抖音链接
            
        Returns:
            Tuple[bool, str, List]: (成功标志, 错误信息, 内容列表)
        """
        self.logger.info(f"检查更新（模拟）: {source_url}")
        
        # 模拟返回一些内容
        mock_content = [
            {"id": "mock_1", "title": "模拟内容1"},
            {"id": "mock_2", "title": "模拟内容2"}
        ]
        
        return True, "", mock_content


class Douyin1CommandHandler(UnifiedCommandHandler):
    """
    Douyin1命令处理器

    继承统一命令处理器基类，提供抖音账号订阅管理功能
    """

    def __init__(self, data_dir: str = "storage/douyin1"):
        """
        初始化Douyin1命令处理器

        Args:
            data_dir: 数据存储目录
        """
        # 暂时使用模拟管理器
        mock_manager = MockDouyin1Manager(data_dir)

        # 调用父类构造函数
        super().__init__(module_name="douyin1", manager=mock_manager)

        self.logger.info("Douyin1命令处理器初始化完成")

    # ==================== 重写UnifiedCommandHandler的方法 ====================

    def get_module_display_name(self) -> str:
        """
        获取模块显示名称（用于用户反馈）

        Returns:
            str: 模块显示名称
        """
        return "抖音订阅 (Douyin1)"

    def get_source_display_name(self, source_url: str) -> str:
        """
        获取数据源的显示名称

        Args:
            source_url: 抖音链接

        Returns:
            str: 显示名称
        """
        # 暂时直接返回URL，后续可以实现解析用户名
        return source_url

    def validate_chat_id(self, chat_id: str) -> Tuple[bool, str]:
        """
        验证频道ID格式

        Args:
            chat_id: 频道ID

        Returns:
            Tuple[bool, str]: (是否有效, 错误信息)
        """
        if not chat_id:
            return False, "频道ID不能为空"

        # 抖音订阅的频道ID格式检查
        if not (chat_id.startswith('@') or chat_id.startswith('-') or chat_id.isdigit()):
            return False, "频道ID格式错误，应为 @channel_name 或数字ID"

        return True, ""

    def _validate_source_url(self, source_url: str) -> Tuple[bool, str]:
        """
        验证抖音URL格式
        
        Args:
            source_url: 抖音链接
            
        Returns:
            Tuple[bool, str]: (是否有效, 错误信息)
        """
        if not source_url:
            return False, "抖音链接不能为空"
        
        # 支持的抖音域名
        valid_domains = [
            'https://www.douyin.com/',
            'http://www.douyin.com/', 
            'https://v.douyin.com/',
            'http://v.douyin.com/',
        ]
        
        for domain in valid_domains:
            if source_url.startswith(domain):
                return True, ""
        
        return False, (
            "抖音链接格式不正确\n"
            "支持的格式：\n"
            "• https://www.douyin.com/user/xxx\n"
            "• https://v.douyin.com/xxx（短链接）"
        )

    # ==================== 重写命令处理方法以添加URL验证 ====================

    async def handle_add_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        处理添加订阅命令（增加抖音URL验证）

        Args:
            update: Telegram更新对象
            context: 命令上下文
        """
        try:
            display_name = self.get_module_display_name()

            # 记录命令开始处理
            user = update.message.from_user
            chat_id = update.message.chat_id
            self.logger.info(f"🚀 开始处理 /douyin1_add 命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

            # 1. 参数验证
            self.logger.info(f"📝 步骤1: 参数验证 - 参数数量: {len(context.args)}")
            if len(context.args) < 2:
                self.logger.warning(f"❌ 参数不足: 需要2个参数，实际收到{len(context.args)}个")
                await update.message.reply_text(
                    f"❌ 参数不足\n\n"
                    f"用法: /douyin1_add <抖音链接> <频道ID>\n\n"
                    f"示例:\n"
                    f"/douyin1_add https://www.douyin.com/user/MS4wLjABAAAA... @my_channel\n"
                    f"/douyin1_add https://v.douyin.com/iM5g7LsM/ -1001234567890"
                )
                return

            source_url = context.args[0].strip()
            target_chat_id = context.args[1].strip()
            self.logger.info(f"📋 解析参数 - 源URL: {source_url}, 目标频道: {target_chat_id}")

            # 验证抖音URL格式
            self.logger.info(f"🔍 步骤2a: 抖音URL格式验证")
            url_valid, url_error = self._validate_source_url(source_url)
            if not url_valid:
                self.logger.error(f"❌ 抖音URL验证失败: {url_error}")
                await update.message.reply_text(f"❌ {url_error}")
                return
            self.logger.info(f"✅ 抖音URL格式验证通过")

            # 验证频道ID格式
            self.logger.info(f"🔍 步骤2b: 频道ID格式验证")
            chat_valid, chat_error = self.validate_chat_id(target_chat_id)
            if not chat_valid:
                self.logger.error(f"❌ 频道ID验证失败: {chat_error}")
                await update.message.reply_text(f"❌ {chat_error}")
                return
            self.logger.info(f"✅ 频道ID格式验证通过")

            # 调用父类的处理逻辑
            await super().handle_add_command(update, context)

        except Exception as e:
            self.logger.error(f"❌ 处理douyin1_add命令时发生错误: {e}", exc_info=True)
            await update.message.reply_text(f"❌ 处理命令时发生错误: {str(e)}")


# 全局实例
_douyin1_command_handler = None


def get_douyin1_command_handler(data_dir: str = "storage/douyin1") -> Douyin1CommandHandler:
    """
    获取Douyin1命令处理器实例（单例模式）

    Args:
        data_dir: 数据存储目录

    Returns:
        Douyin1CommandHandler: 命令处理器实例
    """
    global _douyin1_command_handler
    if _douyin1_command_handler is None:
        _douyin1_command_handler = Douyin1CommandHandler(data_dir)
    return _douyin1_command_handler


# ==================== Telegram命令处理函数 ====================

async def douyin1_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /douyin1_add 命令

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    handler = get_douyin1_command_handler()
    await handler.handle_add_command(update, context)


async def douyin1_del_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /douyin1_del 命令

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    handler = get_douyin1_command_handler()
    await handler.handle_remove_command(update, context)


async def douyin1_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /douyin1_list 命令

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    handler = get_douyin1_command_handler()
    await handler.handle_list_command(update, context)


def register_douyin1_commands(application: Application) -> None:
    """
    注册Douyin1相关的命令处理器

    Args:
        application: Telegram应用实例
    """
    # 导入debug配置
    from core.config import debug_config

    # 注册基础命令
    application.add_handler(CommandHandler("douyin1_add", douyin1_add_command))
    application.add_handler(CommandHandler("douyin1_del", douyin1_del_command))
    application.add_handler(CommandHandler("douyin1_list", douyin1_list_command))

    # 根据debug模式决定是否注册调试命令
    if debug_config["enabled"]:
        # 注册调试命令
        from .debug_commands import register_douyin1_debug_commands
        register_douyin1_debug_commands(application)
        logging.info("✅ Douyin1调试命令已注册（DEBUG模式开启）")
    else:
        logging.info("ℹ️ Douyin1调试命令已跳过（DEBUG模式关闭）")

    logging.info("Douyin1命令处理器注册完成") 