#!/usr/bin/env python3
"""
Fix classification: 类型只有三个 - 内部公式、经典公式、其它
经典公式：上升、2.1型、20天突破、双底、高紧旗
内部公式：形态识别、主力启动、突破信号、市场监控、综合选股
其它：其他所有
"""
import json
from pathlib import Path

def main():
    config_dir = Path('/Users/mac/NeoTrade2/config/screeners')
    config_files = sorted(config_dir.glob('*.json'))

    # 正确的三个类型分类
    CLASSIC_FORMULA = {
        'ascending_triangle_screener': '经典公式',
        'ashare_21_screener': '经典公式',
        'breakout_20day_screener': '经典公式',
        'high_tight_flag_screener': '经典公式',
        'double_bottom_screener': '经典公式',
        'launch_31_screener': '经典公式',
    }

    INTERNAL_FORMULA = {
        'breakout_main_screener': '内部公式',
        'jin_feng_huang_screener': '内部公式',
        'shi_pan_xian_screener': '内部公式',
        'shuang_shou_ban_screener': '内部公式',
        'yin_feng_huang_screener': '内部公式',
        'zhang_ting_bei_liang_yin_screener': '内部公式',
        'zhang_ting_bei_liang_yin_screener': '内部公式',
        'lao_ya_tou_zhou_xian_screener': '内部公式',
        'daily_hot_cold_screener': '内部公式',
        'er_ban_hui_tiao_screener': '内部公式',
        'coffee_cup_handle_screener_v4': '内部公式',
        'cup_handle_screener': '内部公式',
        'flat_base_screener': '内部公式',
        'high_tight_flag_screener': '内部公式',
    }

    # 形态识别、突破信号、市场监控、综合选股
    PATTERN_RECOGNITION = {
        'breakout_main_screener': '内部公式',
        'jin_feng_huang_screener': '内部公式',
        'shi_pan_xian_screener': '内部公式',
        'shuang_shou_ban_screener': '内部公式',
        'yin_feng_huang_screener': '内部公式',
    'daily_hot_cold_screener': '内部公式',
        'er_ban_hui_tiao_screener': '内部公式',
        'coffee_cup_handle_screener_v4': '内部公式',
        'cup_handle_screener': '内部公式',
        'flat_base_screener': '内部公式',
        'high_tight_flag_screener': '内部公式',
        'launch_31_screener': '内部公式',
    }

    # 其他所有
    OTHERS = {
        'coffee_cup': '其它',
        'coffee_cup_v4': '其它',
    }

    updated_count = 0

    for config_file in config_files:
        screener_name = config_file.stem

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            old_category = config.get('category', '')

            # Determine new category
            if screener_name in CLASSIC_FORMULA:
                new_category = '经典公式'
            elif screener_name in INTERNAL_FORMULA:
                new_category = '内部公式'
            elif screener_name in PATTERN_RECOGNITION:
                new_category = '内部公式'
            elif screener_name in OTHERS:
                new_category = '其它'
            else:
                new_category = '其它'

            # Check if update needed
            if old_category != new_category:
                config['category'] = new_category

                # Update metadata
                if 'metadata' not in config:
                    config['metadata'] = {}
                config['metadata']['updated_at'] = '2026-04-17'
                config['metadata']['updated_by'] = 'fix_3types'

                # Save back
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)

                category_emoji = '📐' if new_category == '经典公式' else '🔹' if new_category == '内部公式' else '📦'
                print(f'{category_emoji} {screener_name}: {old_category} → {new_category}')
                updated_count += 1

        except Exception as e:
            print(f'ERROR: Failed to update {config_file.name}: {e}')

    print(f'Updated {updated_count} screener categories')
    print('')
    print('三大类型分类：')
    print('📐 经典公式：上升、2.1型、20天突破、双底、高紧旗')
    print('🔹 内部公式：形态识别、主力启动、突破信号、市场监控、综合选股')
    print('📦 其它：咖啡杯、cup_handle等')


if __name__ == '__main__':
    main()
