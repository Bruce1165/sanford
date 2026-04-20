# 每日数据更新进度文件格式文档

## 文件位置
`data/daily_update_progress_v2.json`

## 版本
v2.1 - 2026-03-19 更新

## 格式规范

```json
{
  "completed": ["001201", "001202", ...],  // Array<string>: 已完成下载的股票代码（已去重排序）
  "failed": {                               // Object: 失败记录，key为股票代码，value为失败次数
    "002013": 52,
    "002505": 48,
    ...
  },
  "target_date": "2026-03-18",             // string: 当前处理的目标日期
  "status": "pending",                      // string: 当前状态
  "last_updated": "2026-03-19T09:25:00",   // string: 最后更新时间 (ISO 8601)
  "version": "2.1"                          // string: 文件格式版本
}
```

## 状态字段说明

| 状态值 | 含义 |
|--------|------|
| `idle` | 空闲状态，等待执行 |
| `running` | 正在执行下载 |
| `completed` | 当日数据全部下载完成 |
| `failed` | 执行过程中发生错误 |

## 关键改进

### v2.1 改进点
1. **completed使用Set逻辑** - 加载时自动去重，保存时排序，避免重复条目堆积
2. **failed改为Dict结构** - `{code: fail_count}` 格式，能准确追踪每只股票的失败次数
3. **添加last_updated** - 记录最后更新时间，便于判断进度文件新鲜度
4. **添加version标记** - 便于后续版本兼容性处理
5. **幂等性保障** - 多次运行不会产生重复数据

## 数据验证

```python
import json
from pathlib import Path

progress_file = Path('data/daily_update_progress_v2.json')
with open(progress_file) as f:
    data = json.load(f)

# 验证格式
assert isinstance(data['completed'], list), "completed必须是数组"
assert isinstance(data['failed'], dict), "failed必须是对象"
assert data['status'] in ['idle', 'running', 'completed', 'failed'], "status值无效"
assert 'last_updated' in data, "缺少last_updated字段"
assert 'version' in data, "缺少version字段"

# 验证去重
assert len(data['completed']) == len(set(data['completed'])), "completed包含重复项"

print("✅ 进度文件格式验证通过")
```

## 与数据库的协同

- `completed` 列表应与数据库中 `daily_prices` 表对应日期的记录保持一致
- 脚本启动时会检查数据库已有数据，自动同步到 completed 列表
- 数据库有唯一约束 `idx_daily_prices_code_date` 防止重复插入

## 清理历史数据

如需重置某日期进度：
```python
import json
from pathlib import Path
from datetime import datetime

progress_file = Path('data/daily_update_progress_v2.json')
data = {
    'completed': [],
    'failed': {},
    'target_date': '2026-03-19',
    'status': 'idle',
    'last_updated': datetime.now().isoformat(),
    'version': '2.1'
}
with open(progress_file, 'w') as f:
    json.dump(data, f, indent=2)
```
