#!/usr/bin/env python3
"""
Final category fix - correct mapping
经典公式：1、2、3、4、5、6（上升、2.1型、20天突破、双底、高紧旗）
内部公式：7、9、12、13、14、15、其他所有
"""
import json
from pathlib import Path

def main():
    config_dir = Path('/Users/mac/NeoTrade2/config/screeners')
    config_files = sorted(config_dir.glob('*.json'))

    # Correct category mapping
    CLASSIC_FORMULA = {
        'ascending_triangle_screener': '经典公式',
        'ashare_21_screener': '经典公式',
        'breakout_20day_screener': '经典公式',
        'high_tight_flag_screener': '经典公式',
        'double_bottom_screener': '经典公式',
        'launch_31_screener': '经典公式',  # 老鸭头周线
    }

    INTERNAL_FORMULA = {
        'zhang_ting_bei_liang_yin_screener': '经典公式',  # 老鸭头投肘周线（新版）
        'lao_ya_tou_zhou_xian_screener': '经典公式',
        'yin_feng_huang_screener': '经典公式',
        'shi_pan_xian_screener': '经典公式',
        'shuang_shou_ban_screener': '经典公式',
        'jin_feng_huang_screener': '经典公式',
        'daily_hot_cold_screener': '经典公式',
        'er_ban_hui_tiao_screener': '经典公式',
        'coffee_cup_handle_screener_v4': '经典公式',
        'cup_handle_screener': '经典公式',
        'flat_base_screener': '经典公式',
        'zhang_ting_bei_liang_yin_screener': '内部公式',  # 老鸭头投肘周先线（旧版）
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
            elif screener_name == 'zhang_ting_bei_liang_yin_screener':
                new_category = '内部公式'  # 旧版本，不使用
            else:
                new_category = '经典公式'

            # Check if update needed
            if old_category != new_category:
                config['category'] = new_category

                # Update metadata
                if 'metadata' not in config:
                    config['metadata'] = {}
                config['metadata']['updated_at'] = '2026-04-17'
                config['metadata']['updated_by'] = 'final_fix_v2'

                # Fix display_name for launch_31
                if screener_name == 'launch_31_screener':
                    config['display_name'] = '老鸭头周线'

                # Mark old zhang version
                if screener_name == 'zhang_ting_bei_liang_yin_screener':
                    config['display_name'] = '老鸭头投肘周先线（旧版）'

                # Save back
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)

                category_emoji = '📐' if new_category == '经典公式' else '🔹'
                print(f'{category_emoji} {screener_name}: {old_category} → {new_category}')
                updated_count += 1

        except Exception as e:
            print(f'ERROR: Failed to update {config_file.name}: {e}')

    # Delete old version config
    old_config = config_dir / 'zhang_ting_bei_liang_yin_screener.json'
    if old_config.exists():
        import os
        try:
            os.remove(old_config)
            print(f'Deleted old version config: zhang_ting_bei_liang_yin_screener.json')
        except Exception as e:
            print(f'WARNING: Failed to delete old config: {e}')

    print(f'Updated {updated_count} screener categories')


if __name__ == '__main__':
    main()
