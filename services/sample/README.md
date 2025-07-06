# Sample模块 - 参数化命令系统

这是一个示例模块，展示了如何使用参数化的命令前缀系统。新模块只需要修改几个配置常量，就能自动生成所有相关的命令。

## 🎯 核心特性

- **零配置拷贝**: 只需修改4个配置常量即可创建新模块
- **动态命令生成**: 命令前缀自动基于模块名生成
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
```

**参数化方式**（只需修改配置）：
```python
# __init__.py
MODULE_NAME = "新模块名"  # 只需修改这一个地方！

# 其他文件自动使用动态生成的命令名称
command_names = get_command_names()
CommandHandler(command_names["add"], handle_add_command)
```

### 3. 动态帮助信息
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

## 💡 最佳实践

1. **模块名称**: 使用小写字母和下划线，如 `twitter`, `youtube_shorts`
2. **显示名称**: 包含中文和英文，如 `Twitter订阅 (Twitter)`
3. **描述**: 简洁明了，描述模块主要功能
4. **目录前缀**: 与模块名称保持一致，如 `storage/twitter`

这个参数化系统大大简化了新模块的创建过程，提高了开发效率和代码一致性。 