"""
RSSHub管理器模块

该模块负责处理RSS特定的业务逻辑，继承统一管理器基类的通用数据管理功能。
专注于RSS解析、内容转换等RSS特有的功能。

主要功能：
1. RSS内容获取和解析
2. RSS条目ID生成
3. RSS特定的内容转换

作者: Assistant
创建时间: 2024年
"""

import logging
from typing import List, Dict, Optional, Any, Tuple

from .rss_entry import RSSEntry
from .rss_parser import RSSParser, create_rss_parser
from services.common.unified_manager import UnifiedContentManager


class RSSHubManager(UnifiedContentManager):
    """
    RSSHub管理器

    继承统一管理器基类，专注于RSS特定的业务逻辑
    """

    def __init__(self, data_dir: str = "storage/rsshub"):
        """
        初始化RSSHub管理器

        Args:
            data_dir: 数据存储目录
        """
        # 调用父类构造函数，传入data_dir启用通用数据管理
        super().__init__(module_name="rsshub", data_dir=data_dir)

        # 初始化RSS特定组件
        self.rss_parser = create_rss_parser()

        # 初始化并注册RSS转换器（确保转换器可用）
        from .rss_converter import create_rss_converter
        self.rss_converter = create_rss_converter()

        self.logger.info(f"RSSHub管理器初始化完成，数据目录: {data_dir}")

    # ==================== 实现UnifiedContentManager抽象接口 ====================

    def fetch_latest_content(self, source_url: str) -> Tuple[bool, str, Optional[List[Dict]]]:
        """
        获取指定源的最新内容（RSS特定实现）

        Args:
            source_url: 数据源URL

        Returns:
            Tuple[bool, str, Optional[List[Dict]]]: (是否成功, 错误信息, 内容数据列表)
        """
        try:
            self.logger.info(f"📥 开始获取RSS内容: {source_url}")

            # 使用RSS解析器获取最新内容
            entries = self.rss_parser.parse_feed(source_url)

            if not entries:
                self.logger.warning(f"📭 RSS源无内容或解析失败: {source_url}")
                return False, "RSS源无内容或解析失败", None

            self.logger.info(f"📊 RSS解析成功: 获取到 {len(entries)} 个条目")

            # 转换为统一的内容数据格式
            content_data_list = []
            for i, entry in enumerate(entries):
                try:
                    content_data = {
                        "title": entry.title,
                        "description": entry.description,
                        "link": entry.link,
                        "published": entry.published,
                        "updated": entry.updated,
                        "author": entry.author,
                        "item_id": entry.item_id,
                        "time": entry.effective_published_time.isoformat() if entry.effective_published_time else "",
                        "enclosures": [
                            {
                                "url": enc.url,
                                "type": enc.type,
                                "length": enc.length
                            } for enc in entry.enclosures
                        ] if entry.enclosures else []
                    }
                    content_data_list.append(content_data)

                    if i < 3:  # 只记录前3个条目的详细信息
                        self.logger.debug(f"📄 条目{i+1}: {entry.title[:50]}{'...' if len(entry.title) > 50 else ''} (ID: {entry.item_id})")

                except Exception as e:
                    self.logger.warning(f"⚠️ 转换条目{i+1}失败: {str(e)}")
                    continue

            self.logger.info(f"✅ 内容转换完成: 成功转换 {len(content_data_list)}/{len(entries)} 个条目")
            return True, "", content_data_list

        except Exception as e:
            self.logger.error(f"💥 获取RSS内容失败: {source_url}, 错误: {str(e)}", exc_info=True)
            return False, f"获取RSS内容失败: {str(e)}", None

    def generate_content_id(self, content_data: Dict) -> str:
        """
        生成内容的唯一标识（RSS特定实现）

        Args:
            content_data: 内容数据

        Returns:
            str: 唯一标识
        """
        # 如果内容数据中已有item_id，直接使用
        if "item_id" in content_data and content_data["item_id"]:
            return content_data["item_id"]

        # 否则根据内容生成ID（与RSS解析器的逻辑保持一致）
        if content_data.get("link"):
            return content_data["link"]
        elif content_data.get("title") and content_data.get("published"):
            return f"{content_data['title']}_{content_data['published']}"
        else:
            return f"rss_item_{hash(str(content_data))}"

    # ==================== RSS特定的便利方法 ====================

    def get_all_rss_urls(self) -> List[str]:
        """
        获取所有RSS源URL列表（兼容性方法，调用通用实现）

        Returns:
            List[str]: RSS源URL列表
        """
        return self.get_all_source_urls()


def create_rsshub_manager(data_dir: str = "storage/rsshub") -> RSSHubManager:
    """
    创建RSSHub管理器实例

    Args:
        data_dir: 数据存储目录

    Returns:
        RSSHubManager: 管理器实例
    """
    return RSSHubManager(data_dir)


if __name__ == "__main__":
    # 模块测试代码
    def test_rsshub_manager():
        """测试RSSHub管理器功能"""
        print("🧪 RSSHub管理器模块测试")

        # 创建管理器实例
        manager = create_rsshub_manager("test_storage/rsshub")

        # 测试基本功能
        print("✅ RSSHub管理器创建成功")
        print(f"📊 当前订阅数量: {len(manager.get_subscriptions())}")

        print("🎉 RSSHub管理器模块测试完成")

    # 运行测试
    test_rsshub_manager()