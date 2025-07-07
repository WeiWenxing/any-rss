# 🔄 Douyin到Douyin1数据迁移指南

## 📋 概述

本指南用于将douyin模块的数据迁移到douyin1模块，确保订阅关系、已知内容和消息映射的完整性。

## 🛠️ 准备工作

### 1. 环境要求
- Python 3.7+
- 项目根目录执行权限
- 足够的磁盘空间（备份需要）

### 2. 文件准备
确保以下文件存在：
- `migrate_douyin_to_douyin1.py` - 迁移脚本
- `storage/douyin/` - 源数据目录

## 🚀 使用方法

### 基本用法

```bash
# 1. 试运行模式（推荐先执行）
python migrate_douyin_to_douyin1.py --dry-run

# 2. 实际执行迁移
python migrate_douyin_to_douyin1.py

# 3. 详细输出模式
python migrate_douyin_to_douyin1.py --verbose

# 4. 不创建备份（不推荐）
python migrate_douyin_to_douyin1.py --no-backup
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--dry-run` | 试运行模式，不实际修改文件 | False |
| `--no-backup` | 不创建备份 | False |
| `--verbose` | 详细输出 | False |

## 📊 迁移内容

### 1. 订阅数据
- **源文件**: `storage/douyin/config/subscriptions.json`
- **目标文件**: `storage/douyin1/config/subscriptions.json`
- **格式**: `{URL: [频道ID列表]}`

### 2. 已知内容ID
- **源文件**: `storage/douyin/data/{hash}/known_item_ids.json`
- **目标文件**: `storage/douyin1/data/{safe_name}/known_item_ids.json`
- **格式**: `[内容ID列表]`

### 3. 消息映射
- **源文件**: `storage/douyin/config/message_mappings.json`
- **目标文件**: `storage/douyin1/config/message_mappings.json`
- **格式**: `{URL: {item_id: {chat_id: message_id}}}`

## 🔍 目录映射规则

### Douyin模块（源）
```
storage/douyin/data/{SHA256_HASH}/
└── known_item_ids.json
```

### Douyin1模块（目标）
```
storage/douyin1/data/{SAFE_FILENAME}/
└── known_item_ids.json
```

### 映射算法
- **Douyin**: `SHA256(URL)[:16]`
- **Douyin1**: `safe_filename(URL)` - 替换特殊字符，限制长度

## 📝 执行步骤

### 第一步：试运行
```bash
python migrate_douyin_to_douyin1.py --dry-run --verbose
```

**检查输出**：
- 是否发现所有订阅数据
- URL映射是否正确
- 是否有错误信息

### 第二步：实际执行
```bash
python migrate_douyin_to_douyin1.py --verbose
```

**自动执行**：
1. 创建数据备份
2. 构建URL映射关系
3. 迁移订阅数据
4. 迁移已知内容
5. 迁移消息映射
6. 验证迁移结果

### 第三步：验证结果
检查以下文件是否正确生成：
- `storage/douyin1/config/subscriptions.json`
- `storage/douyin1/config/message_mappings.json`
- `storage/douyin1/data/{safe_name}/known_item_ids.json`

## 🔧 故障排除

### 常见问题

#### 1. 权限错误
```bash
# 解决方案：确保有写入权限
chmod +w storage/
```

#### 2. 源目录不存在
```
错误：源数据目录不存在: storage/douyin
```
**解决方案**：确认douyin模块已正确配置并有数据

#### 3. JSON格式错误
```
错误：JSON解析失败
```
**解决方案**：检查源文件是否为有效JSON格式

#### 4. 磁盘空间不足
```
错误：创建备份失败
```
**解决方案**：清理磁盘空间或使用 `--no-backup` 参数

### 日志文件
每次执行都会生成日志文件：
- 文件名：`migration_log_YYYYMMDD_HHMMSS.log`
- 包含详细的执行过程和错误信息

## ⚠️ 注意事项

### 数据安全
1. **必须备份**：脚本会自动创建备份，除非使用 `--no-backup`
2. **试运行**：先使用 `--dry-run` 验证迁移计划
3. **验证结果**：迁移后会自动验证数据完整性

### 性能考虑
1. **大数据量**：如果数据量很大，迁移可能需要较长时间
2. **并发访问**：迁移期间避免同时访问相关数据
3. **磁盘IO**：备份和迁移会产生大量磁盘IO

### 兼容性
1. **数据格式**：两个模块的数据格式基本兼容
2. **目录结构**：目录命名规则不同，脚本会自动处理
3. **缓存系统**：两个模块使用不同的缓存，需要分别管理

## 📈 迁移后操作

### 1. 测试验证
```bash
# 测试douyin1模块功能
python -c "from services.douyin1.manager import ContentManager; cm = ContentManager(); print(cm.get_subscriptions())"
```

### 2. 清理旧数据（可选）
```bash
# 确认迁移成功后，可以移除douyin目录
# 谨慎操作！建议保留一段时间
# rm -rf storage/douyin/
```

### 3. 更新配置
- 更新bot配置，启用douyin1模块
- 停用douyin模块
- 更新相关脚本和定时任务

## 📞 技术支持

如果遇到问题：
1. 检查日志文件中的详细错误信息
2. 确认源数据的完整性
3. 验证文件权限和磁盘空间
4. 使用 `--verbose` 参数获取更多信息

## 🎯 最佳实践

1. **分阶段执行**：先试运行，再实际执行
2. **数据备份**：始终保留原始数据备份
3. **逐步验证**：每个步骤都要验证结果
4. **监控日志**：密切关注迁移过程中的日志输出
5. **测试功能**：迁移后充分测试douyin1模块功能

---

**祝您迁移顺利！** 🎉 