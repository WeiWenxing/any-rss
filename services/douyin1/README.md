# Douyin1 模块

抖音内容订阅服务模块，支持从抖音用户主页获取最新视频内容。

## 功能特性

- ✅ 支持抖音用户主页链接解析
- ✅ 自动处理短链接重定向
- ✅ 从URL中提取sec_user_id
- ✅ 调用第三方API获取视频数据
- ✅ 解析视频详细信息（标题、描述、统计数据等）
- ✅ 智能缓存机制，避免重复请求
- ✅ 完整的错误处理和日志记录

## 核心组件

### DouyinFetcher (fetcher.py)

抖音内容获取器，负责：
- URL解析和重定向处理
- API调用和数据解析
- 视频信息提取
- 缓存管理

### ContentManager (manager.py)

内容管理器，负责：
- 账号订阅管理
- 内容更新检查
- 新内容过滤
- 统一架构集成

## 使用方法

### 基本用法

```python
from services.douyin1.fetcher import DouyinFetcher

# 创建获取器实例
fetcher = DouyinFetcher()

# 从抖音URL获取用户内容
douyin_url = "https://www.douyin.com/user/MS4wLjABAAAA4dOPs2xB33L5Sc8YUO2gFq9U6x5LXFkJ8v15AqeIgc8"
success, message, video_list = fetcher.fetch_user_content(douyin_url, count=10)

if success:
    print(f"成功获取 {len(video_list)} 个视频")
    for video in video_list:
        print(f"视频ID: {video['aweme_id']}")
        print(f"描述: {video['desc']}")
        print(f"播放量: {video['statistics']['play_count']}")
else:
    print(f"获取失败: {message}")
```

### 高级用法

```python
# 分步处理
fetcher = DouyinFetcher()

# 1. 提取sec_user_id
success, message, sec_user_id = fetcher.extract_sec_user_id(douyin_url)
if success:
    print(f"用户ID: {sec_user_id}")
    
    # 2. 获取视频数据
    success, message, api_data = fetcher.fetch_user_videos(sec_user_id, count=20)
    if success:
        print(f"获取到原始API数据")

# 3. 检查缓存状态
is_cached = fetcher.is_cache_hit(douyin_url)
print(f"缓存命中: {is_cached}")

# 4. 清除特定URL的缓存
fetcher.clear_cache(douyin_url)
```

## 支持的URL格式

- `https://www.douyin.com/user/MS4wLjABAAAA...`
- `https://v.douyin.com/短链接/`
- 其他抖音域名的用户主页链接

## API接口

使用的第三方API：
- **接口地址**: `https://api.douyin.wtf/api/douyin/web/fetch_user_post_videos`
- **请求参数**: 
  - `sec_user_id`: 用户ID
  - `max_cursor`: 游标位置（分页）
  - `count`: 获取数量

## 缓存机制

**参考sitemap模块的缓存策略实现**

- **缓存类型**: 文件缓存
- **缓存时间**: 1小时（3600秒）
- **缓存键**: 基于抖音URL的MD5哈希值
- **缓存值**: 原始API数据（不进行序列化处理）
- **缓存目录**: `storage/cache/douyin1_api/`
- **缓存配置**: `use_json=False, decode_responses=False`

### 缓存策略特点

1. **基于URL的缓存键**: 使用完整的抖音URL作为缓存键基础，确保不同URL有独立的缓存
2. **原始数据存储**: 缓存存储的是API返回的原始JSON数据，不进行任何序列化处理
3. **高效访问**: 相同URL的重复请求直接从缓存获取，避免频繁API调用
4. **智能管理**: 支持单个URL缓存清除和全局缓存清除

### 缓存方法

```python
# 检查缓存命中
is_hit = fetcher.is_cache_hit(douyin_url)

# 清除特定URL缓存
fetcher.clear_cache(douyin_url)

# 清除所有缓存
fetcher.clear_cache()

# 获取缓存信息
cache_info = fetcher.get_cache_info()
```

## 数据结构

### 视频信息结构

```python
{
    "aweme_id": "7504205454530268476",           # 视频ID
    "desc": "#让我成为你心里的一根刺吧",              # 视频描述
    "caption": "#让我成为你心里的一根刺吧",           # 视频标题
    "create_time": 1747208991,                   # 创建时间（Unix时间戳）
    "duration": 11400,                           # 视频时长（毫秒）
    "aweme_type": 0,                            # 视频类型
    "is_top": 1,                                # 是否置顶
    
    "author": {                                 # 作者信息
        "uid": "92470219398",
        "nickname": "用户昵称",
        "signature": "用户签名",
        "avatar_thumb": ["头像URL列表"]
    },
    
    "statistics": {                             # 统计信息
        "play_count": 0,                        # 播放量
        "digg_count": 101264,                   # 点赞量
        "comment_count": 1207,                  # 评论量
        "share_count": 0,                       # 分享量
        "collect_count": 0                      # 收藏量
    },
    
    "video": {                                  # 视频信息
        "uri": "视频URI",
        "url_list": ["视频URL列表"],
        "width": 1080,                          # 视频宽度
        "height": 1920,                         # 视频高度
        "data_size": 4207811,                   # 文件大小
        "file_hash": "文件哈希",
        "url_key": "URL密钥"
    },
    
    "cover": {                                  # 封面信息
        "uri": "封面URI",
        "url_list": ["封面URL列表"]
    },
    
    "music": {                                  # 音乐信息
        "id": "音乐ID",
        "title": "音乐标题",
        "author": "音乐作者",
        "play_url": ["音乐播放URL列表"]
    },
    
    "share_url": "分享链接"
}
```

## 错误处理

常见错误类型：
- URL格式错误
- 网络请求失败
- API返回错误
- 数据解析失败
- 重定向处理失败

所有错误都会记录详细的日志信息，包括堆栈跟踪。

## 更新日志

### v1.0.1 (2024-07-06)
- 🔄 **缓存策略重构**: 参考sitemap模块实现
- 🔑 **缓存键优化**: 使用抖音URL作为缓存键基础
- 💾 **原始数据存储**: 缓存存储原始API数据，不进行序列化
- 🚀 **性能提升**: 优化缓存命中率和访问速度
- 🛠️ **方法增强**: 新增`is_cache_hit()`方法

### v1.0.0 (2024-07-06)
- 🎉 **初始版本**: 基础功能实现
- 🔍 **URL解析**: 支持多种抖音URL格式
- 📡 **API集成**: 集成第三方抖音API
- 🎬 **视频解析**: 完整的视频信息提取
- 💾 **缓存机制**: 基础缓存功能

## 注意事项

1. **API限制**: 第三方API可能有访问频率限制
2. **网络依赖**: 需要稳定的网络连接
3. **URL格式**: 确保提供正确的抖音用户主页链接
4. **数据时效**: 缓存数据可能不是最新的
5. **缓存管理**: 定期清理缓存以获取最新数据

## 开发者信息

- **作者**: Assistant
- **创建时间**: 2024年
- **版本**: 1.0.1
- **许可**: 项目许可证 