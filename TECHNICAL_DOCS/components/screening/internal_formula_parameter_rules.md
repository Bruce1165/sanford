# 内部公式筛选器参数与规则（用户可读版）

## 说明
- 本文仅描述可量化参数。
- 每条规则使用“参数名（当前值）=> 自然语言条件”的形式展示。
- 参数来源：`config/screeners/*.json`。

## coffee_cup_v4（咖啡杯柄V4）
- `RIM_INTERVAL_MIN(45)` + `RIM_INTERVAL_MAX(250)` => 左右杯沿间隔必须在 45~250 个交易日。
- `RIM_PRICE_MATCH_PCT(0.05)` => 右杯沿价格与左杯沿价格偏差不超过 5%。
- `RIGHT_RIM_SEARCH_DAYS(13)` => 右杯沿局部高点在最近 13 天窗口内搜索。
- `CUP_DEPTH_MIN(0.05)` + `CUP_DEPTH_MAX(0.7)` => 杯深比例必须在 5%~70%。
- `RAPID_DECLINE_DAYS(12)` => 快速下跌阶段窗口固定按 12 个交易日执行（可配置）。
- `RAPID_ASCENT_DAYS(12)` => 快速上涨阶段窗口固定按 12 个交易日执行（可配置）。
- `HANDLE_PERIOD_MIN(5)` + `HANDLE_PERIOD_MAX(20)` => 杯柄长度必须在该区间。
- `MA5_TREND_DAYS(14)` + `MA_TREND_WINDOW(5)` + `MA_TREND_MIN_VALID_POINTS(10)` => MA 趋势判断窗口与最少有效点按参数执行。
- `DECLINE_AMOUNT_MAX_RATIO(0.5)` => 快速下跌总成交额必须小于快速上涨总成交额 * 0.5。
- `SAFETY_LEVEL_DEPTH_RATIO(0.5)` => 安全水位 = 杯底 + 杯深 * 0.5。
- `RECENT_LOW_LOOKBACK_DAYS(18)` => “创近期新低”判定窗口为最近 18 天。
- `HISTORY_BUFFER_DAYS(50)` => 历史数据加载天数额外增加 50 天缓冲。

## daily_hot_cold（每日冷热股）
- `LIMIT_UP_MAIN(9.9)` + `LIMIT_UP_GEM_STAR(19.9)` => 主板/创业科创板涨停阈值按参数判定。
- `LIMIT_DOWN_MAIN(-9.9)` + `LIMIT_DOWN_GEM_STAR(-19.9)` => 主板/创业科创板跌停阈值按参数判定。
- `NEW_STOCK_DAYS(60)` => 上市不足 60 天股票过滤。
- `MIN_AMOUNT(10.0)` => 成交额至少 10 亿（配置单位：亿元）。
- `HOT_PCT_THRESHOLD(5.0)` => 涨幅 >= 5% 判定热股。
- `COLD_PCT_THRESHOLD(-5.0)` => 跌幅 <= -5% 判定冷股。
- `LIMIT_STATS_DAYS(20)` => 涨跌停统计窗口为近 20 日。
- `HIGH_TURNOVER_THRESHOLD(15.0)` + `VOLUME_SURGE_TURNOVER(5.0)` => 高换手/放量阈值按参数执行。
- `BREAKOUT_THRESHOLD(0.99)` + `BREAKDOWN_THRESHOLD(1.01)` => 突破/跌破判定系数按参数执行。
- `MIN_HISTORY_DAYS(5)` => 计算涨跌停统计与收益率前，至少需要 5 天历史数据。

## er_ban_hui_tiao（二板回调）
- `LIMIT_DAYS(14)` => 信号必须出现在最近 14 个交易日内。
- `LIMIT_UP_THRESHOLD(9.9)` => 涨停判定阈值为 9.9%。
- `FIRST_BOARD_VOLUME_RATIO(2.0)` => 首板成交额 >= 前一日成交额 * 2.0。
- `MIN_SIGNAL_ONE_DAYS(3)` => 计算信号一前，至少要求 3 天有效历史数据。
- `MIN_HISTORY_DAYS(10)` + `HISTORY_BUFFER_DAYS(10)` => 数据加载与最小样本天数按参数执行。

## jin_feng_huang（涨停金凤凰）
- `LIMIT_DAYS(14)` => 信号必须出现在最近 14 个交易日内。
- `LIMIT_UP_THRESHOLD(9.9)` => 涨停判定阈值为 9.9%。
- `SIGNAL_ONE_VOLUME_RATIO(2.0)` => 信号一成交额 >= 前一日 * 2.0。
- `SIGNAL_TWO_VOLUME_RATIO(2.0)` => 信号二成交额 >= 前一日 * 2.0。
- `SIGNAL_FOUR_VOLUME_RATIO(0.5)` => 信号四（地量）成交额 < 前一日 * 0.5。
- `SIGNAL_FIVE_VOLUME_RATIO(2.0)` => 信号五（启动）成交额 >= 前一日 * 2.0。
- `MIN_HISTORY_DAYS(10)` + `HISTORY_BUFFER_DAYS(10)` => 数据加载与最小样本天数按参数执行。

## shi_pan_xian（涨停试盘线）
- `CONSOLIDATION_DAYS(20)` => 高量阳线前需至少 20 天低位横盘。
- `HIGH_VOLUME_LOOKBACK(30)` => 在最近 30 天内识别阶段高量阳线。
- `MAX_CONSOLIDATION_GAIN(0.1)` => 横盘区间首尾涨跌幅绝对值 <= 10%。
- `HIGH_VOLUME_PEAK_TOLERANCE(0.95)` => 候选高量阳线成交量 >= 回看窗口最大量 * 0.95。
- `LIMIT_UP_SEARCH_DAYS(5)` => 高量阳线后最多 5 天内需出现低量涨停。
- `VOLUME_SHRINK_THRESHOLD(0.25)` => 缩量判定：成交量 < 高量阳线成交量 * 0.25。
- `CALLBACK_MAX_DAYS(10)` => 回调观察窗口最多 10 天。
- `BREAKOUT_VOLUME_RATIO(1.5)` => 再放量日成交量 > 缩量区间均量 * 1.5。
- `MIN_HISTORY_DAYS(50)` => 单股至少需要 50 天历史数据。
- `MIN_DAYS_AFTER_HIGH_VOLUME(3)` => 高量阳线后至少保留 3 天观察窗口。
- `MAIN_BOARD_LIMIT_UP_PCT(9.5)` + `GEM_STAR_LIMIT_UP_PCT(19.5)` + `BSE_LIMIT_UP_PCT(29.5)` + `ST_LIMIT_UP_PCT(4.5)` => 分板块涨停阈值按参数执行。

## yin_feng_huang（涨停银凤凰）
- `LIMIT_DAYS(14)` => 信号必须出现在最近 14 个交易日内。
- `LIMIT_UP_THRESHOLD(9.9)` => 涨停判定阈值为 9.9%。
- `SIGNAL_ONE_VOLUME_RATIO(2.0)` => 信号一成交额 >= 前一日 * 2.0。
- `SIGNAL_THREE_SHRINK_RATIO(1.0)` => 信号三成交额 < 前一日 * 1.0（即严格小于前一日）。
- `SIGNAL_FOUR_VOLUME_RATIO(2.0)` => 信号四成交额 >= 前一日 * 2.0。
- `MIN_HISTORY_DAYS(10)` + `HISTORY_BUFFER_DAYS(10)` => 数据加载与最小样本天数按参数执行。

## zhang_ting_bei_liang_yin（涨停倍量阴）
- `LIMIT_DAYS(14)` => 信号必须出现在最近 14 个交易日内。
- `LIMIT_UP_THRESHOLD(9.9)` => 涨停判定阈值为 9.9%。
- `SIGNAL_ONE_BODY_RATIO(3.0)` => 信号一实体长度 >= 下引线长度 * 3.0。
- `SIGNAL_TWO_BODY_RATIO(2.0)` => 信号二阴线实体长度 >=（上影+下影）* 2.0。
- `SIGNAL_THREE_VOLUME_RATIO(2.0)` => 信号二成交额 > 信号一成交额 * 2.0。
- `SIGNAL_FOUR_VOLUME_RATIO(0.5)` => 地量日成交额 < 信号二成交额 * 0.5。
- `SIGNAL_FIVE_VOLUME_RATIO(2.0)` => 启动日成交额 > 前一日成交额 * 2.0。
- `MIN_HISTORY_DAYS(10)` + `HISTORY_BUFFER_DAYS(10)` => 数据加载与最小样本天数按参数执行。
