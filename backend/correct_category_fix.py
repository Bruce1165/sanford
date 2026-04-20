#!/usr/bin/env python3
"""
Correct category mapping based on user specification
经典公式：上升、2.1型、20天突破、双底、高紧旗
内部公式：其它所有
"""
import json
from pathlib import Path

def main():
    config_dir = Path('/Users/mac/NeoTrade2/config/screeners')
    config_files = sorted(config_dir.glob('*.json'))

    # User specified categories
    CLASSIC_FORMULA = {
        'ascending_triangle_screener': '经典公式',      # 上升三角形
        'ashare_21_screener': '经典公式',         # A股2.1型
        'breakout_20day_screener': '经典公式',  # 20天突破
        'high_tight_flag_screener': '经典公式',   # 高紧旗形
        'double_bottom_screener': '经典公式',      # 双底形态
    }

    INTERNAL_FORMULA = {
        'launch_31_screener': '经典公式',       # 3.1% Launch -> 老鸭头周线（经典公式）
    }

    # All others are 内部公式
    OTHERS = [
        'breakout_main_screener',       # 突破主升
        'jin_feng_huang_screener',    # 涨停金凤凰
        'shi_pan_xian_screener',       # 涨停试盘线
        'shuang_shou_ban_screener',    # 双首板
        'yin_feng_huang_screener',    # 涨停银凤凰
        'zhang_ting_bei_liang_yin_screener',  # 老鸭头投肘周线
        'lao_ya_tou_zhou_xian_screener', # 老鸭头投肘周先线
        'daily_hot_cold_screener',     # 每日热冷股
        'er_ban_hui_tiao_screener',    # 二板回调
        'coffee_cup_handle_screener_v4', # 咖啡杯柄V4
        'cup_handle_screener',           # 咖啡杯
        'flat_base_screener',           # 平底形态
        'zhang_ting_bei_liang_yin_screener',  # 老鸭头投肘周先线（旧版）
        'high_tight_flag_screener',
        'double_bottom_screener',
        'breakout_20day_screener',
        'launch_31_screener',
        'ascending_triangle_screener',
        'ashare_21_screener',
    ]

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
            else:
                new_category = '内部公式'

            # Check if update needed
            if old_category != new_category:
                config['category'] = new_category

                # Update metadata
                if 'metadata' not in config:
                    config['metadata'] = {}
                config['metadata']['updated_at'] = '2026-04-17'
                config['metadata']['updated_by'] = 'correct_mapping'

                # Fix display_name for launch_31
                if screener_name == 'launch_31_screener':
                    config['display_name'] = '老鸭头周线'

                # Save back
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)

                category_emoji = '📐' if new_category == '经典公式' else '🔹'
                print(f'{category_emoji} {screener_name}: {old_category} → {new_category}')
                updated_count += 1

        except Exception as e:
            print(f'ERROR: Failed to update {config_file.name}: {e}')

    print(f'Updated {updated_count} screener categories')


if __name__ == '__main__':
    main()
