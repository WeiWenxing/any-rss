# Sample模块 - 参数化命令系统

这是一个示例模块，展示了如何使用参数化的命令前缀系统。新模块只需要修改几个配置常量，就能自动生成所有相关的命令。

## 🎯 核心特性

- **零配置拷贝**: 只需修改4个配置常量即可创建新模块
- **动态命令生成**: 命令前缀自动基于模块名生成
- **通用类名和方法名**: 所有类名、方法名都不包含具体模块名，避免歧义
- **统一架构**: 继承统一的命令处理器和管理器
- **完整功能**: 包含基础命令、调试命令、帮助系统

## 📋 配置常量

在 `__init__.py` 文件中，只需修改以下4个常量：

```python
# ==================== 模块配置（新模块只需修改这里）====================
# 模块名称（用于命令前缀，如 sample_add, sample_del 等）
MODULE_NAME = "sample"
# 模块显示名称（用于用户界面显示）
MODULE_DISPLAY_NAME = "样本订阅 (Sample)"
# 模块描述
MODULE_DESCRIPTION = "样本内容订阅服务"
# 数据存储目录前缀
DATA_DIR_PREFIX = "storage/sample"
```

## 🔧 创建新模块步骤

1. **拷贝模块目录**
   ```bash
   cp -r services/sample services/新模块名
   ```

2. **修改配置常量**
   编辑 `services/新模块名/__init__.py`，修改上述4个常量：
   ```python
   MODULE_NAME = "新模块名"
   MODULE_DISPLAY_NAME = "新模块显示名"
   MODULE_DESCRIPTION = "新模块描述"
   DATA_DIR_PREFIX = "storage/新模块名"
   ```

3. **完成！**
   所有命令前缀自动更新：
   - `/新模块名_add`
   - `/新模块名_del`
   - `/新模块名_list`
   - `/新模块名_debug_show`

## 📚 动态生成的命令

基于 `MODULE_NAME = "sample"`，自动生成：

| 命令类型 | 命令名称 | 功能描述 |
|---------|---------|---------|
| 基础命令 | `/sample_add` | 添加订阅 |
| 基础命令 | `/sample_del` | 删除订阅 |
| 基础命令 | `/sample_list` | 查看订阅列表 |
| 调试命令 | `/sample_debug_show` | 显示内容详情 |

## 🏗️ 架构优势

### 传统方式 vs 参数化方式

**传统方式**（需要修改多个文件）：
```python
# commands.py
async def sample_add_command(...)  # 需要修改函数名
CommandHandler("sample_add", sample_add_command)  # 需要修改命令名

# debug_commands.py
async def sample_debug_show_command(...)  # 需要修改函数名
CommandHandler("sample_debug_show", sample_debug_show_command)  # 需要修改命令名

# help_provider.py
return "• /sample_add <链接> <频道ID> - 添加订阅"  # 需要修改帮助文本

# manager.py
class SampleManager(...)  # 需要修改类名
def create_sample_manager(...)  # 需要修改函数名
```

**参数化方式**（只需修改配置）：
```python
# __init__.py
MODULE_NAME = "新模块名"  # 只需修改这一个地方！

# 其他文件使用通用命名，无需修改
class ContentManager(...)  # 通用类名
class ModuleCommandHandler(...)  # 通用类名
def create_content_manager(...)  # 通用函数名
command_names = get_command_names()  # 动态获取命令名
```

## 🔍 技术实现

### 1. 通用类名和方法名
```python
# manager.py - 使用通用命名
class ContentManager(UnifiedContentManager):  # 不包含具体模块名
class MockContentFetcher:  # 通用的获取器名称
class MockMessageConverter:  # 通用的转换器名称
def create_content_manager():  # 通用的创建函数

# commands.py - 使用通用命名
class ModuleCommandHandler(UnifiedCommandHandler):  # 通用的命令处理器名称
def get_command_handler():  # 通用的获取函数
async def handle_add_command():  # 通用的处理函数

# help_provider.py - 使用通用命名
class ModuleHelpProvider(ModuleHelpProvider):  # 通用的帮助提供者名称
```

### 2. 命令名称动态生成
```python
def get_command_names() -> Dict[str, str]:
    return {
        "add": f"{MODULE_NAME}_add",
        "del": f"{MODULE_NAME}_del",
        "list": f"{MODULE_NAME}_list",
        "debug_show": f"{MODULE_NAME}_debug_show"
    }
```

### 3. 统一命令注册
```python
def register_commands(application: Application) -> None:
    command_names = get_command_names()
    application.add_handler(CommandHandler(command_names["add"], handle_add_command))
    application.add_handler(CommandHandler(command_names["del"], handle_del_command))
    application.add_handler(CommandHandler(command_names["list"], handle_list_command))
```

### 4. 动态帮助信息
```python
def get_basic_commands(self) -> str:
    command_names = get_command_names()
    return (
        f"• /{command_names['add']} <链接> <频道ID> - 添加订阅\n"
        f"• /{command_names['del']} <链接> <频道ID> - 删除订阅\n"
        f"• /{command_names['list']} [频道ID] - 查看订阅列表"
    )
```

## 🚀 使用示例

假设创建一个名为 `twitter` 的新模块：

1. 拷贝模块：`cp -r services/sample services/twitter`
2. 修改配置：
   ```python
   MODULE_NAME = "twitter"
   MODULE_DISPLAY_NAME = "Twitter订阅 (Twitter)"
   MODULE_DESCRIPTION = "Twitter内容订阅服务"
   DATA_DIR_PREFIX = "storage/twitter"
   ```
3. 自动生成的命令：
   - `/twitter_add`
   - `/twitter_del`
   - `/twitter_list`
   - `/twitter_debug_show`
4. **所有类名和方法名保持通用**：
   - `ContentManager` (不是 `TwitterManager`)
   - `ModuleCommandHandler` (不是 `TwitterCommandHandler`)
   - `create_content_manager()` (不是 `create_twitter_manager()`)

## 💡 最佳实践

1. **模块名称**: 使用小写字母和下划线，如 `twitter`, `youtube_shorts`
2. **显示名称**: 包含中文和英文，如 `Twitter订阅 (Twitter)`
3. **描述**: 简洁明了，描述模块主要功能
4. **目录前缀**: 与模块名称保持一致，如 `storage/twitter`
5. **类名通用**: 所有类名都使用通用命名，避免包含具体模块名
6. **方法名通用**: 所有方法名都使用通用命名，避免歧义

## ✨ 通用化改进

### 修改前（包含具体模块名）:
```python
class SampleManager(...)           # ❌ 包含模块名
class SampleCommandHandler(...)    # ❌ 包含模块名
def create_sample_manager(...)     # ❌ 包含模块名
def sample_add_command(...)        # ❌ 包含模块名
```

### 修改后（通用命名）:
```python
class ContentManager(...)          # ✅ 通用命名
class ModuleCommandHandler(...)    # ✅ 通用命名
def create_content_manager(...)    # ✅ 通用命名
def handle_add_command(...)        # ✅ 通用命名
```

这个参数化系统大大简化了新模块的创建过程，提高了开发效率和代码一致性，同时避免了类名和方法名的歧义问题。