"""
缓存模块

提供统一的缓存接口，支持多种缓存策略：
- file: 文件缓存（默认，零依赖）
- redis: Redis缓存（生产环境推荐）
"""

from .factory import get_cache

__all__ = ['get_cache'] 