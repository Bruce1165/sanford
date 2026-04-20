#!/usr/bin/env python3
"""
Fix #5 ascending_triangle to 内部公式
"""
import json
from pathlib import Path

def main():
    config_file = Path('/Users/mac/NeoTrade2/config/screeners/ascending_triangle_screener.json')

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Change to 内部公式
        config['category'] = '内部公式'

        # Update metadata
        if 'metadata' not in config:
            config['metadata'] = {}
        config['metadata']['updated_at'] = '2026-04-17'
        config['metadata']['updated_by'] = 'fix_5th_internal'

        # Save back
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        print(f'✅ ascending_triangle_screener: 经典公式 → 内部公式')

    except Exception as e:
        print(f'ERROR: {e}')


if __name__ == '__main__':
    main()
