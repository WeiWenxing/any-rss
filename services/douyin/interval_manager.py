"""
抖音模块消息发送时间间隔管理器
实现配置化的分层时间间隔控制，避免Telegram Flood Control限制
"""

import asyncio
import logging
import time
from typing import Optional


class IntervalConfig:
    """间隔配置类"""
    
    def __init__(self, scenario: str = "default"):
        """
        初始化间隔配置
        
        Args:
            scenario: 应用场景 ("batch_send", "forward", "alignment", "default")
        """
        self.scenario = scenario
        self.configs = {
            # 批量内容发送场景
            "batch_send": {
                "base_interval": 8.0,           # 基础发送间隔：8秒
                "batch_interval": 60.0,         # 批量间隔：每10条消息暂停60秒
                "batch_threshold": 10,          # 批量阈值：每10条
                "error_recovery_interval": 5.0, # 错误恢复间隔：5秒
                "flood_control_interval": 60.0, # Flood Control惩罚间隔：60秒
                "max_interval": 30.0,           # 最大间隔：30秒
                "min_interval": 3.0,            # 最小间隔：3秒
                "error_threshold": 0.1,         # 错误率阈值：10%
                "enable_dynamic_adjustment": True, # 启用动态调整
            },
            
            # 多频道转发场景
            "forward": {
                "base_interval": 2.0,           # 转发间隔：2秒（比发送短）
                "batch_interval": 60.0,         # 批量间隔：每10条暂停60秒
                "batch_threshold": 10,          # 批量阈值：每10条
                "error_recovery_interval": 5.0, # 错误恢复间隔：5秒
                "flood_control_interval": 60.0, # Flood Control惩罚间隔：60秒
                "max_interval": 15.0,           # 最大间隔：15秒
                "min_interval": 1.0,            # 最小间隔：1秒
                "error_threshold": 0.15,        # 错误率阈值：15%（转发容错性更高）
                "enable_dynamic_adjustment": True,
            },
            
            # 历史内容对齐场景
            "alignment": {
                "base_interval": 1.0,           # 对齐间隔：1秒（转发操作轻量）
                "batch_interval": 60.0,         # 批量间隔：每10条暂停60秒
                "batch_threshold": 10,          # 批量阈值：每10条
                "error_recovery_interval": 3.0, # 错误恢复间隔：3秒
                "flood_control_interval": 60.0, # Flood Control惩罚间隔：60秒
                "max_interval": 10.0,           # 最大间隔：10秒
                "min_interval": 0.5,            # 最小间隔：0.5秒
                "error_threshold": 0.2,         # 错误率阈值：20%（历史对齐容错性最高）
                "enable_dynamic_adjustment": False, # 历史对齐不需要动态调整
            },
            
            # 默认场景
            "default": {
                "base_interval": 5.0,
                "batch_interval": 60.0,
                "batch_threshold": 10,
                "error_recovery_interval": 5.0,
                "flood_control_interval": 60.0,
                "max_interval": 20.0,
                "min_interval": 2.0,
                "error_threshold": 0.1,
                "enable_dynamic_adjustment": True,
            }
        }
    
    def get_config(self, key: str):
        """获取配置值"""
        return self.configs[self.scenario].get(key, self.configs["default"][key])
    
    def get_all_config(self) -> dict:
        """获取当前场景的完整配置"""
        return self.configs[self.scenario].copy()


class MessageSendingIntervalManager:
    """消息发送时间间隔管理器"""

    def __init__(self, scenario: str = "default"):
        """
        初始化间隔管理器
        
        Args:
            scenario: 应用场景 ("batch_send", "forward", "alignment", "default")
        """
        self.config = IntervalConfig(scenario)
        self.scenario = scenario
        
        # 从配置加载参数
        self.base_interval = self.config.get_config("base_interval")
        self.batch_interval = self.config.get_config("batch_interval")
        self.batch_threshold = self.config.get_config("batch_threshold")
        self.error_recovery_interval = self.config.get_config("error_recovery_interval")
        self.flood_control_interval = self.config.get_config("flood_control_interval")
        self.max_interval = self.config.get_config("max_interval")
        self.min_interval = self.config.get_config("min_interval")
        self.error_threshold = self.config.get_config("error_threshold")
        self.enable_dynamic_adjustment = self.config.get_config("enable_dynamic_adjustment")

        # 统计信息
        self.sent_count = 0
        self.error_count = 0
        self.last_reset_time = time.time()
        
        logging.info(f"📊 消息间隔管理器初始化完成 - 场景:{self.scenario}, 基础间隔:{self.base_interval}s, 批量间隔:{self.batch_interval}s, 批量阈值:{self.batch_threshold}")

    async def wait_before_send(self, content_index: int, total_content: int,
                              recent_error_rate: float = 0.0) -> None:
        """
        发送前等待策略

        Args:
            content_index: 当前内容索引（从0开始）
            total_content: 总内容数量
            recent_error_rate: 最近错误率
        """
        # 第一个内容不需要等待
        if content_index == 0:
            return

        # 计算动态间隔
        interval = self._calculate_dynamic_interval(recent_error_rate)

        # 批量间隔检查（使用配置的批量阈值）
        if content_index > 0 and content_index % self.batch_threshold == 0:
            logging.info(f"📦 已发送{content_index}个内容，执行批量间隔暂停{self.batch_interval}秒...")
            await self._sleep_with_progress(self.batch_interval, "批量间隔")
            return

        # 常规间隔
        logging.debug(f"⏱️ 等待{interval:.1f}秒后发送第{content_index + 1}/{total_content}个内容...")
        await asyncio.sleep(interval)

    async def wait_after_error(self, error_type: str, retry_count: int = 0) -> None:
        """
        错误后等待策略

        Args:
            error_type: 错误类型
            retry_count: 重试次数
        """
        if error_type == "flood_control":
            # Flood Control错误，等待更长时间
            wait_time = self.flood_control_interval + (retry_count * 30)
            logging.warning(f"🚫 遇到Flood Control限制，等待{wait_time}秒后重试...")
            await self._sleep_with_progress(wait_time, "Flood Control恢复")
        elif error_type == "rate_limit":
            # 一般限流错误
            wait_time = self.error_recovery_interval * (2 ** retry_count)  # 指数退避
            logging.warning(f"⚠️ 遇到限流错误，等待{wait_time}秒后重试...")
            await self._sleep_with_progress(wait_time, "限流恢复")
        else:
            # 其他错误
            logging.warning(f"❌ 发送错误，等待{self.error_recovery_interval}秒后继续...")
            await asyncio.sleep(self.error_recovery_interval)

    def _calculate_dynamic_interval(self, recent_error_rate: float) -> float:
        """
        计算动态发送间隔

        Args:
            recent_error_rate: 最近错误率

        Returns:
            float: 计算后的间隔时间
        """
        interval = self.base_interval

        # 根据配置决定是否启用动态调整
        if self.enable_dynamic_adjustment and recent_error_rate > self.error_threshold:
            # 错误率高时增加间隔
            error_multiplier = 1 + (recent_error_rate * 3)
            interval *= error_multiplier
            logging.debug(f"🔧 [{self.scenario}] 根据错误率{recent_error_rate:.2%}调整间隔为{interval:.1f}秒")

        # 限制在合理范围内
        interval = max(self.min_interval, min(interval, self.max_interval))

        return interval

    def update_statistics(self, success: bool) -> None:
        """
        更新发送统计信息

        Args:
            success: 是否发送成功
        """
        self.sent_count += 1
        if not success:
            self.error_count += 1

        # 每小时重置统计
        if time.time() - self.last_reset_time > 3600:
            old_error_rate = self.get_recent_error_rate()
            logging.info(f"📊 [{self.scenario}] 统计重置 - 过去1小时: 发送{self.sent_count}次, 错误率{old_error_rate:.2%}")
            self.sent_count = 0
            self.error_count = 0
            self.last_reset_time = time.time()

    def get_recent_error_rate(self) -> float:
        """
        获取最近错误率

        Returns:
            float: 错误率（0.0-1.0）
        """
        if self.sent_count == 0:
            return 0.0
        return self.error_count / self.sent_count

    async def _sleep_with_progress(self, total_seconds: float, reason: str) -> None:
        """
        带进度显示的等待

        Args:
            total_seconds: 总等待时间
            reason: 等待原因
        """
        if total_seconds <= 10:
            # 短时间等待，直接sleep
            await asyncio.sleep(total_seconds)
            return

        # 长时间等待，显示进度
        interval = 10  # 每10秒显示一次进度
        elapsed = 0

        while elapsed < total_seconds:
            remaining = total_seconds - elapsed
            if remaining <= interval:
                # 最后一段时间
                await asyncio.sleep(remaining)
                break
            else:
                # 等待一个间隔
                await asyncio.sleep(interval)
                elapsed += interval
                logging.info(f"⏳ [{self.scenario}] {reason}等待中... 剩余{remaining - interval:.0f}秒")

        logging.info(f"✅ [{self.scenario}] {reason}等待完成")

    def get_statistics_summary(self) -> str:
        """
        获取统计信息摘要

        Returns:
            str: 统计信息字符串
        """
        error_rate = self.get_recent_error_rate()
        elapsed_time = time.time() - self.last_reset_time
        return (f"📊 [{self.scenario}] 发送统计: {self.sent_count}次发送, "
                f"错误率{error_rate:.2%}, "
                f"运行时间{elapsed_time/60:.1f}分钟")

    def get_config_summary(self) -> str:
        """
        获取配置信息摘要

        Returns:
            str: 配置信息字符串
        """
        return (f"⚙️ [{self.scenario}] 配置: 基础间隔{self.base_interval}s, "
                f"批量阈值{self.batch_threshold}, "
                f"动态调整{'开启' if self.enable_dynamic_adjustment else '关闭'}") 