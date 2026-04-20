#!/usr/bin/env python3
"""
Final category fix - separate 内部公式 vs 经典公式
"""
import json
from pathlib import Path

# 内部公式：老鸭头的内部逻辑
INTERNAL_FORMULA_SCREENERS = {
    'ascending_triangle',
    'ashare_21',
    'breakout_20day',
    'double_bottom',
    'high_tight_flag',
}

# 经典公式：形态识别、主力启动、市场监控、形态突破、综合选股
# 所有其他筛选器

def main():
    config_dir = Path('/Users/mac/NeoTrade2/config/screeners')
    config_files = sorted(config_dir.glob('*.json'))

    internal_count = 0
    classic_count = 0

    for config_file in config_files:
        screener_name = config_file.stem

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # Determine category
            if screener_name in INTERNAL_FORMULA_SCREENERS:
                new_category = '内部公式'
                internal_count += 1
            else:
                new_category = '经典公式'
                classic_count += 1

            # Check if update needed
            old_category = config.get('category', '')
            if old_category != new_category:
                config['category'] = new_category

                # Update metadata
                if 'metadata' not in config:
                    config['metadata'] = {}
                config['metadata']['updated_at'] = '2026-04-17'
                config['metadata']['updated_by'] = 'final_category_fix'

                # Save back
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)

                category_emoji = '🔹' if new_category == '内部公式' else '📐'
                print(f'{category_emoji} {screener_name}: {old_category} → {new_category}')

        except Exception as e:
            print(f'ERROR: Failed to update {config_file.name}: {e}')

    print(f'Updated {internal_count} internal formula screeners, {classic_count} classic formula screeners')


if __name__ == '__main__':
    main()
