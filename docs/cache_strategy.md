# Redis缓存策略使用指南

## 概述

本项目实现了统一的缓存接口，支持两种缓存策略：
- **文件缓存**：零依赖，适合开发和小规模部署
- **Redis缓存**：高性能，适合生产环境和分布式部署

## 架构设计

```
services/common/cache/
├── base.py          # 缓存接口抽象基类
├── file_cache.py    # 文件缓存实现
├── redis_cache.py   # Redis缓存实现
├── factory.py       # 缓存工厂（自动选择策略）
├── management.py    # 缓存管理工具
└── __init__.py      # 模块导出
```

## 快速开始

### 1. 基本使用

```python
from services.common.cache import get_cache

# 自动选择缓存类型（根据环境配置）
cache = get_cache("my_cache", ttl=3600)

# 设置缓存
cache.set("key", "value")

# 获取缓存
value = cache.get("key")

# 检查存在
if cache.exists("key"):
    print("缓存存在")

# 删除缓存
cache.delete("key")
```

### 2. 指定缓存类型

```python
# 强制使用文件缓存
file_cache = get_cache("file_cache", cache_type="file")

# 强制使用Redis缓存（需要安装redis库）
redis_cache = get_cache("redis_cache", cache_type="redis")
```

## 配置说明

### 环境变量配置

在 `.env` 文件中添加以下配置：

```bash
# 缓存类型选择
CACHE_TYPE=file          # 或 redis

# 文件缓存配置
CACHE_DIR=storage/cache

# Redis缓存配置（方式1：URL）
REDIS_URL=redis://localhost:6379/0
# 带密码的Redis URL
REDIS_URL=redis://:password@localhost:6379/0

# Redis缓存配置（方式2：分别配置）
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_password
```

### 自动选择策略

缓存类型选择优先级：
1. 环境变量 `CACHE_TYPE`
2. Redis可用且有配置 → 自动选择Redis
3. 默认 → 文件缓存

### 代码中配置

```python
# 文件缓存配置
file_cache = get_cache(
    "my_cache",
    cache_type="file",
    cache_dir="custom/cache/dir"
)

# Redis缓存配置
redis_cache = get_cache(
    "my_cache",
    cache_type="redis",
    host="localhost",
    port=6379,
    db=0,
    password="your_password"
)
```

## 安装依赖

### 文件缓存
无需额外依赖，使用Python标准库。

### Redis缓存
```bash
pip install redis>=4.0.0
```

## 高级功能

### 1. 缓存管理

```python
from services.common.cache.management import get_cache_manager

manager = get_cache_manager()

# 获取所有缓存信息
info = manager.get_all_cache_info()

# 清空指定缓存
manager.clear_cache("cache_name")

# 清空所有缓存
manager.clear_all_caches()

# 清理过期缓存
manager.cleanup_expired_caches()

# 健康检查
health = manager.health_check()

# 性能测试
perf = manager.test_cache_performance("cache_name", operations=1000)
```

### 2. 缓存迁移

```python
# 从文件缓存迁移到Redis缓存
manager.migrate_cache(
    source_name="old_cache",
    target_name="new_cache", 
    source_type="file",
    target_type="redis"
)
```

### 3. 共享缓存实例

```python
from services.common.cache.factory import get_shared_cache

# 获取共享缓存实例（单例模式）
cache1 = get_shared_cache("shared_cache")
cache2 = get_shared_cache("shared_cache")  # 同一个实例
```

## 性能对比

| 特性 | 文件缓存 | Redis缓存 |
|------|----------|-----------|
| 依赖 | 无 | redis库 |
| 性能 | 中等 | 高 |
| 分布式 | 不支持 | 支持 |
| 持久化 | 文件 | 内存+可选持久化 |
| 内存使用 | 低 | 中等 |
| 适用场景 | 开发/小规模 | 生产/大规模 |

## 最佳实践

### 1. 开发环境
```bash
# .env
CACHE_TYPE=file
CACHE_DIR=storage/cache
```

### 2. 生产环境
```bash
# .env
CACHE_TYPE=redis
REDIS_URL=redis://:password@redis-server:6379/0
```

### 3. 容错处理
```python
# 启用降级策略（Redis失败时自动降级到文件缓存）
cache = get_cache(
    "my_cache",
    cache_type="redis",
    allow_fallback=True  # 默认为True
)
```

### 4. TTL设置
```python
# 不同类型数据使用不同TTL
user_cache = get_cache("users", ttl=3600)      # 1小时
session_cache = get_cache("sessions", ttl=1800) # 30分钟
temp_cache = get_cache("temp", ttl=300)        # 5分钟
```

### 5. 键命名规范
```python
# 使用有意义的键名
cache.set("user:123:profile", user_data)
cache.set("rss:feed:456:latest", feed_data)
cache.set("douyin:user:789:videos", video_list)
```

## 监控和调试

### 1. 日志配置
```python
import logging
logging.getLogger("cache").setLevel(logging.DEBUG)
```

### 2. 缓存信息查看
```python
from services.common.cache.factory import get_cache_info

cache = get_cache("my_cache")
info = get_cache_info(cache)
print(f"缓存信息: {info}")
```

### 3. 健康检查
```python
health = manager.health_check()
if health["overall_status"] != "healthy":
    print(f"缓存状态异常: {health}")
```

## 故障排除

### 1. Redis连接失败
- 检查Redis服务是否运行
- 验证连接配置（host、port、password）
- 检查网络连接和防火墙设置

### 2. 文件缓存权限问题
- 确保缓存目录有写入权限
- 检查磁盘空间是否充足

### 3. 性能问题
- 使用性能测试工具分析瓶颈
- 考虑调整TTL设置
- 评估是否需要升级到Redis缓存

## 测试

运行缓存系统测试：
```bash
python test_cache.py
```

测试包含：
- 基本CRUD操作
- TTL过期测试
- 缓存工厂测试
- 环境变量配置测试
- 性能基准测试 