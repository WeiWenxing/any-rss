"""
RSS模块配置管理
统一管理RSS相关的配置参数
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class RSSConfig:
    """RSS模块配置类"""

    # 网络请求配置
    request_timeout: int = 30
    request_retries: int = 3
    request_backoff_factor: float = 1.5
    max_concurrent_feeds: int = 5

    # 媒体处理配置
    max_media_per_batch: int = 10
    media_check_timeout: int = 10
    large_file_threshold_official: int = 20  # MB
    large_file_threshold_local: int = 50     # MB

    # 文件管理配置
    pending_file_keep_days: int = 7
    feed_cache_keep_days: int = 30

    # 消息格式配置
    max_title_length: int = 100
    max_caption_length: int = 1024

    # 请求头配置
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

    def get_request_headers(self) -> Dict[str, str]:
        """获取标准请求头"""
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache"
        }


# 全局配置实例
rss_config = RSSConfig()


def update_config(**kwargs) -> None:
    """
    更新配置参数

    Args:
        **kwargs: 要更新的配置项
    """
    global rss_config
    for key, value in kwargs.items():
        if hasattr(rss_config, key):
            setattr(rss_config, key, value)
            logging.info(f"RSS配置更新: {key} = {value}")
        else:
            logging.warning(f"未知的RSS配置项: {key}")


def get_config() -> RSSConfig:
    """获取当前配置"""
    return rss_config


class ParserConfig:
    """解析器配置类"""

    # BeautifulSoup解析器优先级
    # 对于RSS/Atom XML片段，优先使用xml解析器
    XML_PARSERS = ['xml', 'html.parser']

    # 对于HTML内容，只使用html.parser
    HTML_PARSER = 'html.parser'

    # feedparser已经处理RSS/Atom，避免重复解析
    USE_FEEDPARSER_ONLY_FOR_RSS = True


def get_parser_config() -> ParserConfig:
    """获取解析器配置"""
    return ParserConfig()