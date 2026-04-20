# 老鸭头五旗股票池筛选功能需求

## 功能概述

老鸭头五旗股票池筛选系统对老鸭头股票池中的未处理股票进行技术分析，筛选出符合特定形态的股票，并记录到老鸭头五旗股票池数据库表。

## 筛选器定义

系统包含以下5个筛选器（按技术形态分类）：

### 1. 二板回调 (er_ban_hui_tiao)
- **技术特征**: 连续两个涨停板后出现回调
- **筛选逻辑**: 识别T日涨停、T+1日涨停、T+2日或之后回调的形态
- **关键参数**: 涨停价格、回调幅度、成交量

### 2. 金凤凰 (jin_feng_huang)
- **技术特征**: 5日内形成金凤凰形态
- **筛选逻辑**: 识别T日涨停，T+5日内再次涨停的形态
- **关键参数**: 信号日日期、启动日价格

### 3. 银凤凰 (yin_feng_huang)
- **技术特征**: 4日内形成银凤凰形态
- **筛选逻辑**: 识别T日涨停，T+4日内再次涨停的形态
- **关键参数**: 信号日日期、启动日价格

### 4. 试盘线 (shi_pan_xian)
- **技术特征**: 高量试盘后涨停
- **筛选逻辑**: 识别高量试盘日、涨停日的组合形态
- **关键参数**: 高量日期、涨停日期

### 5. 涨停倍量阴 (zhang_ting_bei_liang_yin)
- **技术特征**: 涨停后倍量阴线
- **筛选逻辑**: 识别涨停日之后出现倍量阴线的形态
- **关键参数**: 涨停价格、阴线成交量倍数

## 核心业务逻辑

### 股票起止时间核查（CRITICAL）

**必须遵守的规则**：
1. 对于老鸭头股票池中的每只股票，获取其start_date和end_date
2. 查询股票在start_date到end_date之间的所有交易日（含起止日期）
3. 对于每个交易日，调用相应的筛选器进行核查
4. **不得修改此逻辑** - 每个交易日都必须核查一遍

**实现要点**：
- 使用get_trading_days方法从daily_prices表获取交易日列表
- 遍历每个交易日，调用adapter.check_stock方法
- check_stock方法设置screener.current_date后调用screener.screen_stock

### 筛选流程

```
for each pool in unprocessed_pools:
    for each screener in 5 screeners:
        trading_days = get_trading_days(pool.stock_code, pool.start_date, pool.end_date)
        for each trade_date in trading_days:
            result = adapter.check_stock(
                screener_id=screener,
                stock_code=pool.stock_code,
                stock_name=pool.stock_name,
                date=trade_date
            )
            if result and result['matched']:
                insert_to_lao_ya_tou_five_flags_table(
                    pool_id=pool.id,
                    screener_id=screener,
                    stock_code=pool.stock_code,
                    stock_name=pool.stock_name,
                    screen_date=trade_date,
                    close_price=result['price'],
                    match_reason=result['reason']
                )
                break  # 该股票该筛选器找到匹配后，继续下一个筛选器
```

### 数据写入规则

符合条件的匹配写入lao_ya_tou_five_flags表：

- pool_id: 老鸭头股票池记录ID
- screener_id: 筛选器ID (5个之一)
- stock_code: 股票代码
- stock_name: 股票名称
- screen_date: 筛选日期（交易日）
- close_price: 收盘价格
- match_reason: 匹配原因描述

## 数据库表结构

### lao_ya_tou_pool（老鸭头股票池）
- id: 主键
- stock_code: 股票代码
- stock_name: 股票名称
- start_date: 开始日期
- end_date: 结束日期
- file_name: 来源文件名
- processed: 是否已处理 (0-未处理, 1-已处理)

### lao_ya_tou_five_flags（老鸭头五旗股票池）
- id: 主键
- pool_id: 关联老鸭头股票池ID
- screener_id: 筛选器ID
- stock_code: 股票代码
- stock_name: 股票名称
- screen_date: 筛选日期
- close_price: 收盘价格
- match_reason: 匹配原因
- created_at: 创建时间

## 性能要求

- 使用ThreadPoolExecutor进行并行筛选，提升处理效率
- 批量插入数据库（BATCH_INSERT_SIZE=100），减少IO次数
- 支持进度检查点保存，支持中断后恢复
- 完整筛选完成后，标记lao_ya_tou_pool表中的processed=1

## 调度与监控

- 记录每个筛选器的调用次数、成功次数、失败次数
- 计算平均处理时间
- 记录处理进度（已处理股票数/总股票数）
- 日志记录关键事件（开始、完成、错误）

## 相关文档

- 老鸭头股票池数据库设计: `TECHNICAL_DOCS/components/screening/lao_ya_tou_db_classifier.md`
- 筛选器集成伪代码: `TECHNICAL_DOCS/components/screening/pool_screeners_integration_pseudocode.md`
- 筛选器适配器: `scripts/pool_screener_adapter.py`
- 筛选运行脚本: `scripts/run_five_flags_pool_screening.py`

## 版本历史

- 2026-04-19: 初始版本，明确5个筛选器定义和核心业务逻辑
