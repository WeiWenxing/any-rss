"""
统一间隔管理器模块

该模块完全复用douyin模块的成熟间隔管理逻辑，为所有模块提供统一的发送间隔控制。
实现配置化的分层时间间隔控制，避免Telegram Flood Control限制。

主要功能：
1. 完全复用douyin模块的间隔管理逻辑
2. 支持多种应用场景的配置化间隔控制
3. 动态间隔调整和错误率监控
4. 批量发送的智能间隔管理
5. 跨模块的统一间隔接口

支持的场景：
- batch_send: 批量内容发送（8秒基础间隔）
- forward: 多频道转发（2秒基础间隔）
- alignment: 历史内容对齐（1秒基础间隔）
- rsshub_send: RSSHub内容发送（5秒基础间隔）
- default: 默认场景（5秒基础间隔）

作者: Assistant
创建时间: 2024年
"""

import asyncio
import logging
import time
from typing import Optional


class UnifiedIntervalConfig:
    """统一间隔配置类（完全复用douyin模块逻辑）"""

    def __init__(self, scenario: str = "default"):
        """
        初始化间隔配置

        Args:
            scenario: 应用场景 ("batch_send", "forward", "alignment", "rsshub_send", "default")
        """
        self.scenario = scenario
        self.configs = {
            # 批量内容发送场景（douyin模块原配置）
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

            # 多频道转发场景（douyin模块原配置）
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

            # 历史内容对齐场景（douyin模块原配置）
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

            # RSSHub内容发送场景（新增，基于RSS特点优化）
            "rsshub_send": {
                "base_interval": 5.0,           # RSS发送间隔：5秒（中等频率）
                "batch_interval": 60.0,         # 批量间隔：每10条暂停60秒
                "batch_threshold": 10,          # 批量阈值：每10条
                "error_recovery_interval": 4.0, # 错误恢复间隔：4秒
                "flood_control_interval": 60.0, # Flood Control惩罚间隔：60秒
                "max_interval": 25.0,           # 最大间隔：25秒
                "min_interval": 2.0,            # 最小间隔：2秒
                "error_threshold": 0.12,        # 错误率阈值：12%
                "enable_dynamic_adjustment": True, # 启用动态调整
            },

            # 默认场景（douyin模块原配置）
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


class UnifiedIntervalManager:
    """
    统一间隔管理器（完全复用douyin模块逻辑）

    为所有模块提供统一的发送间隔控制，避免Telegram Flood Control限制。
    """

    def __init__(self, scenario: str = "default"):
        """
        初始化统一间隔管理器

        Args:
            scenario: 应用场景 ("batch_send", "forward", "alignment", "rsshub_send", "default")
        """
        self.config = UnifiedIntervalConfig(scenario)
        self.scenario = scenario

        # 从配置加载参数（完全复用douyin模块的配置结构）
        self.base_interval = self.config.get_config("base_interval")
        self.batch_interval = self.config.get_config("batch_interval")
        self.batch_threshold = self.config.get_config("batch_threshold")
        self.error_recovery_interval = self.config.get_config("error_recovery_interval")
        self.flood_control_interval = self.config.get_config("flood_control_interval")
        self.max_interval = self.config.get_config("max_interval")
        self.min_interval = self.config.get_config("min_interval")
        self.error_threshold = self.config.get_config("error_threshold")
        self.enable_dynamic_adjustment = self.config.get_config("enable_dynamic_adjustment")

        # 统计信息（完全复用douyin模块的统计逻辑）
        self.sent_count = 0
        self.error_count = 0
        self.last_reset_time = time.time()

        self.logger = logging.getLogger(__name__)
        self.logger.info(f"📊 统一间隔管理器初始化完成 - 场景:{self.scenario}, 基础间隔:{self.base_interval}s, 批量间隔:{self.batch_interval}s, 批量阈值:{self.batch_threshold}")

    async def wait_before_send(self, content_index: int, total_content: int,
                              recent_error_rate: float = 0.0) -> None:
        """
        发送前等待策略（完全复用douyin模块逻辑）

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
            self.logger.info(f"📦 已发送{content_index}个内容，执行批量间隔暂停{self.batch_interval}秒...")
            await self._sleep_with_progress(self.batch_interval, "批量间隔")
            return

        # 常规间隔
        self.logger.debug(f"⏱️ 等待{interval:.1f}秒后发送第{content_index + 1}/{total_content}个内容...")
        await asyncio.sleep(interval)

    async def wait_after_error(self, error_type: str, retry_count: int = 0) -> None:
        """
        错误后等待策略（完全复用douyin模块逻辑）

        Args:
            error_type: 错误类型
            retry_count: 重试次数
        """
        if error_type == "flood_control":
            # Flood Control错误，等待更长时间
            wait_time = self.flood_control_interval + (retry_count * 30)
            self.logger.warning(f"🚫 遇到Flood Control限制，等待{wait_time}秒后重试...")
            await self._sleep_with_progress(wait_time, "Flood Control恢复")
        elif error_type == "rate_limit":
            # 一般限流错误
            wait_time = self.error_recovery_interval * (2 ** retry_count)  # 指数退避
            self.logger.warning(f"⚠️ 遇到限流错误，等待{wait_time}秒后重试...")
            await self._sleep_with_progress(wait_time, "限流恢复")
        else:
            # 其他错误
            self.logger.warning(f"❌ 发送错误，等待{self.error_recovery_interval}秒后继续...")
            await asyncio.sleep(self.error_recovery_interval)

    def _calculate_dynamic_interval(self, recent_error_rate: float) -> float:
        """
        计算动态发送间隔（完全复用douyin模块逻辑）

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
            self.logger.debug(f"🔧 [{self.scenario}] 根据错误率{recent_error_rate:.2%}调整间隔为{interval:.1f}秒")

        # 限制在合理范围内
        interval = max(self.min_interval, min(interval, self.max_interval))

        return interval

    def update_statistics(self, success: bool) -> None:
        """
        更新发送统计信息（完全复用douyin模块逻辑）

        Args:
            success: 是否发送成功
        """
        self.sent_count += 1
        if not success:
            self.error_count += 1

    def get_recent_error_rate(self) -> float:
        """
        获取最近的错误率（完全复用douyin模块逻辑）

        Returns:
            float: 错误率（0.0-1.0）
        """
        if self.sent_count == 0:
            return 0.0

        return self.error_count / self.sent_count

    async def _sleep_with_progress(self, total_seconds: float, reason: str) -> None:
        """
        带进度显示的等待（完全复用douyin模块逻辑）

        Args:
            total_seconds: 总等待时间
            reason: 等待原因
        """
        if total_seconds <= 10:
            # 短时间等待，直接sleep
            await asyncio.sleep(total_seconds)
            return

        # 长时间等待，分段显示进度
        interval = 10  # 每10秒显示一次进度
        elapsed = 0

        while elapsed < total_seconds:
            remaining = total_seconds - elapsed
            wait_time = min(interval, remaining)

            await asyncio.sleep(wait_time)
            elapsed += wait_time

            if elapsed < total_seconds:
                remaining_time = total_seconds - elapsed
                self.logger.info(f"⏳ {reason}中... 剩余{remaining_time:.0f}秒")

    def get_statistics_summary(self) -> str:
        """
        获取统计信息摘要（完全复用douyin模块逻辑）

        Returns:
            str: 统计信息摘要
        """
        error_rate = self.get_recent_error_rate()
        runtime = time.time() - self.last_reset_time

        return (f"统计摘要[{self.scenario}]: 发送{self.sent_count}条, "
                f"错误{self.error_count}条, 错误率{error_rate:.1%}, "
                f"运行时间{runtime/60:.1f}分钟")

    def get_config_summary(self) -> str:
        """
        获取配置信息摘要（完全复用douyin模块逻辑）

        Returns:
            str: 配置信息摘要
        """
        return (f"配置摘要[{self.scenario}]: 基础间隔{self.base_interval}s, "
                f"批量间隔{self.batch_interval}s, 批量阈值{self.batch_threshold}, "
                f"错误阈值{self.error_threshold:.1%}, "
                f"动态调整{'开启' if self.enable_dynamic_adjustment else '关闭'}")

    def reset_statistics(self) -> None:
        """
        重置统计信息

        用于长时间运行的场景，定期重置统计避免累积偏差。
        """
        self.sent_count = 0
        self.error_count = 0
        self.last_reset_time = time.time()
        self.logger.info(f"📊 [{self.scenario}] 统计信息已重置")


# 便捷函数：创建统一间隔管理器实例
def create_unified_interval_manager(scenario: str = "default") -> UnifiedIntervalManager:
    """
    创建统一间隔管理器实例

    Args:
        scenario: 应用场景

    Returns:
        UnifiedIntervalManager: 间隔管理器实例
    """
    return UnifiedIntervalManager(scenario)


# 便捷函数：获取场景配置信息
def get_scenario_config(scenario: str) -> dict:
    """
    获取指定场景的配置信息

    Args:
        scenario: 应用场景

    Returns:
        dict: 场景配置信息
    """
    config = UnifiedIntervalConfig(scenario)
    return config.get_all_config()


# 便捷函数：列出所有支持的场景
def list_supported_scenarios() -> list:
    """
    列出所有支持的应用场景

    Returns:
        list: 支持的场景列表
    """
    config = UnifiedIntervalConfig()
    return list(config.configs.keys())


if __name__ == "__main__":
    # 模块测试代码
    import asyncio

    async def test_unified_interval_manager():
        """测试统一间隔管理器功能"""
        print("🧪 统一间隔管理器模块测试")

        # 测试不同场景的间隔管理器
        scenarios = ["batch_send", "forward", "alignment", "rsshub_send", "default"]

        for scenario in scenarios:
            print(f"\n📋 测试场景: {scenario}")

            # 创建间隔管理器
            manager = create_unified_interval_manager(scenario)
            print(f"✅ 创建间隔管理器: {scenario}")

            # 显示配置信息
            print(f"📊 {manager.get_config_summary()}")

            # 模拟发送过程
            for i in range(3):
                await manager.wait_before_send(i, 3, 0.05)  # 5%错误率
                manager.update_statistics(success=(i != 1))  # 第2个失败
                print(f"✅ 模拟发送第{i+1}条消息")

            # 显示统计信息
            print(f"📈 {manager.get_statistics_summary()}")

        # 测试便捷函数
        print(f"\n🔧 支持的场景: {list_supported_scenarios()}")

        rsshub_config = get_scenario_config("rsshub_send")
        print(f"📋 RSSHub场景配置: 基础间隔={rsshub_config['base_interval']}s")

        print("\n🎉 统一间隔管理器模块测试完成")

    # 运行测试
    asyncio.run(test_unified_interval_manager())