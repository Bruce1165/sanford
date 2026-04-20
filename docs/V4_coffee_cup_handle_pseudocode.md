# V4 咖啡杯柄筛选器 - 伪代码

# ========== 类定义 ==========
# 类：CoffeeCupHandleParamsV4 - 参数类
class CoffeeCupHandleParamsV4:
    # 杯沿相关参数
    RIM_INTERVAL_MIN = 45      # 杯沿间隔最小天数
    RIM_INTERVAL_MAX = 250     # 杯沿间隔最大天数
    RIM_PRICE_MATCH_PCT = 0.05   # 杯沿价格匹配度 ±5%
    RIGHT_RIM_SEARCH_DAYS = 13  # 右侧杯沿搜索天数

    # 杯体相关参数
    CUP_DEPTH_MIN = 0.05      # 杯深最小 5%
    CUP_DEPTH_MAX = 0.70      # 杯深最大 70%
    RAPID_DECLINE_MIN = 5      # 快速下调最少天数
    RAPID_DECLINE_MAX = 60     # 快速下调最多天数
    RAPID_ASCENT_MIN = 5       # 快速上涨最少天数
    RAPID_ASCENT_MAX = 25      # 快速上涨最多天数

    # 杯柄相关参数
    HANDLE_MAX_DAYS = 13         # 杯柄最大天数
    HANDLE_MAX_DROP_PCT = 2.0    # 杯柄下跌占杯深比例

    # 成交额相关参数（2026-04-14更新）
    VOLUME_COMPARISON_DAYS = 13  # 成交额对比天数
    VOLUME_RATIO_THRESHOLD = 2.0 # 成交额倍数要求

    # 趋势相关参数
    MA5_TREND_DAYS = 14          # MA5趋势判断天数
    OSCILLATION_PRICE_CEIL_PCT = 1.0 # 震荡期价格上限占左杯沿%

# ========== 主类：CoffeeCupHandleScreener = 筛选器主类
# 类：CoffeeCupHandleScreener - V4筛选器主类
# 继承：BaseScreener

class CoffeeCupHandleScreener(BaseScreener):
    # 初始化方法 __init__
    # 参数：db_path, enable_news, enable_llm, enable_progress, params
    # 功能：初始化筛选器，加载配置参数
    # 步骤：
    # 1. 调用父类 __init__ 传入基本参数
    # 2. 调用 load_screener_config() 加载配置
    # 3. 应用配置到 self.params
    # 4. 如果没有配置，使用默认参数

    # 方法：get_parameter_schema - 返回参数配置schema
    # 功能：返回用于UI显示的参数配置
    # 返回：字典（嵌套结构）

    # 方法：calculate_required_days - 计算所需历史数据天数
    # 功能：返回需要的最大天数
    # 公式：max(杯沿最大间隔 + 快速下调最多 + 快速上涨最多 + 右杯沿搜索天数) + 10

    # 方法：check_ma5_trend - 检查MA5趋势
    # 参数：df, left_rim_idx
    # 返回：(是否通过, 原因/信息)
    # 功能：检查左杯沿前21天MA5是否呈上升趋势
    # 逻辑：后半部分均值 > 前半部分均值

    # ========== 第1轮：找右侧杯沿 ==========
    # 方法：_round1_find_right_rim
    # 参数：df
    # 返回：{'right_rim_idx', 'right_rim_price', 'handle_length', 'latest_idx'} 或 None
    # 功能：在筛选日期前13天内找最高价作为右杯沿
    # 步骤：
    # 1. 获取最新索引 latest_idx = len(df) - 1
    # 2. 计算搜索范围 right_rim_search_start = max(0, latest_idx - 13)
    # 3. 提取13天数据 right_rim_period = df.iloc[right_rim_search_start:latest_idx+1]
    # 4. 找最高价索引 right_rim_price_idx = right_rim_period['high'].idxmax()
    # 5. 获取最高价 right_rim_price = right_rim_period.loc[right_rim_price_idx, 'high']
    # 6. 计算杯柄长度 handle_length = latest_idx - right_rim_price_idx
    # 7. 验证杯柄长度 handle_length <= 13 否则返回 None

    # ========== 第2轮：找左侧杯沿 ==========
    # 方法：_round2_find_left_rim
    # 参数：df, round1_result
    # 返回：添加 left_rim_idx, left_rim_price, ma5_passed, ma5_reason 的结果 或 None
    # 功能：从T-45往回追溯到T-250找左杯沿
    # 步骤：
    # 1. 计算搜索范围：search_start = right_rim_idx - 45 (T-45), search_end = right_rim_idx - 250 (T-250)
    # 2. 确保范围有效：search_start = max(0, search_start), search_end = max(0, search_end)
    # 3. 如果 start < end 则交换（往回找）
    # 4. 往回迭代：for left_rim_idx in range(search_start, search_end - 1, -1)
    # 5. 获取价格 left_rim_price = df.iloc[left_rim_idx]['high']
    # 6. 价格匹配：price_diff_pct = abs(right_rim_price - left_rim_price) / right_rim_price
    # 7. 验证：price_diff_pct <= 0.05 否继续
    # 8. 局部高点检查：local_window_start = max(0, left_rim_idx - 5), local_window_end = min(len(df) - 1, left_rim_idx + 5)
    # 9. 提取局部窗口 local_period = df.iloc[local_window_start:local_window_end + 1]
    # 10. 局部最高价 local_high = local_period['high'].max()
    # 11. 验证：left_rim_price >= local_high - 0.001 否继续
    # 12. MA5趋势检查：ma5_passed, ma5_reason = check_ma5_trend(df, left_rim_idx)
    # 13. 找到第一个符合条件的即返回

    # ========== 第3轮：验证杯深 ==========
    # 方法：_round3_validate_cup_depth
    # 参数：df, round2_result
    # 返回：添加 cup_bottom_price, cup_depth 的结果 或 None
    # 功能：验证杯深在5%-70%范围内
    # 步骤：
    # 1. 提取杯体数据 cup_body_period = df.iloc[left_rim_idx:right_rim_idx]
    # 2. 计算杯底 cup_bottom_price = cup_body_period['low'].min()
    # 3. 计算杯深 cup_depth = (left_rim_price - cup_bottom_price) / left_rim_price
    # 4. 验证范围：5% <= cup_depth <= 70% 否则返回 None

    # ========== 第4轮：验证形态（杯体、杯柄、成交额）- 固定12天窗口 ==========
    # 方法：_round4_validate_pattern
    # 参数：df, round3_result
    # 返回：添加 handle_low, handle_drop, volume_ratio 的结果 或 None
    # 功能：验证杯体结构、杯柄、成交额（使用成交额）
    #
    # 重要更新：2026-04-14
    # 1. 固定时间窗口：快速下调和快速上涨都使用固定12天，不再嵌套循环
    # 2. 成交额比较：使用 amount（成交额）字段代替 volume（成交量），避免单位不一致问题
    #
    # 左窗口：左杯沿后12天（不包括左杯沿）
    #    left_amt_end = min(len(df), left_rim_idx + 12 + 1)
    #    left_amt_start = left_rim_idx + 1
    #    left_amt_period = df.iloc[left_amt_start:left_amt_end]
    #
    # 右窗口：右杯沿前12天（不包括右杯沿）
    #    right_amt_start = max(0, right_rim_idx - 12)
    #    right_amt_end = right_rim_idx
    #    right_amt_period = df.iloc[right_amt_start:right_amt_end]
    #
    # 检查数据长度：左右窗口都不少于12天
    #    if len(left_amt_period) < 12 or len(right_amt_period) < 12:
    #        return None
    #
    # 检查成交额数据有效性
    #    if left_amt_period['amount'].isna().any() or right_amt_period['amount'].isna().any():
    #        return None
    #
    # 计算平均成交额：left_amt_avg = left_amt_period['amount'].mean()
    #    right_amt_avg = right_amt_period['amount'].mean()
    #
    # 计算成交额比例：amt_ratio = right_amt_avg / left_amt_avg
    #
    # 验证成交额比例：amt_ratio >= 2.0
    #    if amt_ratio >= 2.0:
    #        return {
    #            **round3_result,
    #            'handle_low': handle_low,
    #            'handle_drop': handle_drop,
    #            'volume_ratio': amt_ratio,
    #        }
    #
    # return None

    # ========== 第5轮：验证当前价格 ==========
    # 方法：_round5_validate_current_price
    # 参数：df, round4_result
    # 返回：添加 latest_price 的结果 或 None
    # 功能：验证当前价格不低于安全水位
    # 步骤：
    # 1. 计算安全水位 cup_bottom_plus_depth_50pct = cup_bottom_price + cup_depth * 0.5
    # 2. 获取最新价格 latest_price = df.iloc[latest_idx]['close']
    # 3. 特殊处理：handle_length == 0 时跳过验证（杯柄未形成）
    # 4. 验证：latest_price >= cup_bottom_plus_depth_50pct 否则返回 None
    #
    # return None

    # ========== 辅助函数 ==========
    # 方法：find_cup_pattern - 组合5轮方法找形态
    # 参数：df, stock_code, stock_name
    # 返回：结果字典 或 None
    # 功能：依次调用5轮方法，全部通过则返回结果

    # ========== 主函数 ==========
    # 方法：main
    # 功能：程序入口，解析命令行参数，创建筛选器实例，运行筛选，保存结果
