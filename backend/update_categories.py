#!/usr/bin/env python3
"""
Update screener categories to match Dashboard Tag Pages
"""
import json
from pathlib import Path
import glob

# 所有现有配置文件都归类为"经典公式"
# 因为目前数据库中没有"内部公式"的筛选器
# 筛选器：上升、2.1型、20天突破、双底、高紧旗

CLASSIC_FORMULA_SCREENERS = [
    'shuang_shou_ban',
    'jin_feng_huang',
    'yin_feng_huang',
    'shi_pan_xian',
    'zhang_ting_bei_liang_yin',
    'breakout_main',
    'breakout_20day',
    'double_bottom',
    'high_tight_flag',
    'launch_31',
    'ascending_triangle',
    'coffee_cup',
    'coffee_cup_v4',
    'cup_handle',
    'flat_base',
    'daily_hot_cold',
    'ashare_21',
    'er_ban_hui_tiao',
    'lao_ya_tou_zhou_xian',
]

def main():
    config_dir = Path('/Users/mac/NeoTrade2/config/screeners')
    config_files = sorted(config_dir.glob('*.json'))

    updated_count = 0

    for config_file in config_files:
        screener_name = config_file.stem

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            old_category = config.get('category', '未分类')

            # 所有现有筛选器都归类为"经典公式"
            if old_category != '经典公式':
                config['category'] = '经典公式'

                # Update metadata
                if 'metadata' not in config:
                    config['metadata'] = {}
                config['metadata']['updated_at'] = '2026-04-17'
                config['metadata']['updated_by'] = 'category_fix'

                # Save back
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)

                print(f'Updated: {screener_name}: {old_category} → 经典公式')
                updated_count += 1

        except Exception as e:
            print(f'ERROR: Failed to update {config_file.name}: {e}')

    print(f'Updated {updated_count} screener categories to "经典公式"')


if __name__ == '__main__':
    main()
