#!/usr/bin/env python3
"""Analyze LYT classification results."""

import json

with open('/Users/mac/NeoTrade2/data/lao_ya_tou_enhanced_2026-04-16.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('=' * 80)
print('LAO YA TOU ENHANCED CLASSIFICATION SUMMARY')
print('=' * 80)
print(f'Screening Date: 2026-04-16')
print(f'Screening Mode: {data["screening_mode"].upper()}')
print(f'Total Stocks Screened: {data["total_screened"]}')
print(f'')
print(f'Signal 1 (Duck Nostril - Aggressive): {len(data["signal_1"])} stocks')
print(f'Signal 2 (Duck Mouth - Stable): {len(data["signal_2"])} stocks')
print(f'Signal 3 (Volume Breakout - Chase): {len(data["signal_3"])} stocks')
print(f'')
print(f'Total LYT Pattern Stocks: {len(data["signal_1"]) + len(data["signal_2"]) + len(data["signal_3"])}')
print('=' * 80)

# Top 10 by confidence for each signal
for signal_type, signal_name in [
    ('signal_1', 'SIGNAL 1 (Duck Nostril)'),
    ('signal_2', 'SIGNAL 2 (Duck Mouth)'),
    ('signal_3', 'SIGNAL 3 (Volume Breakout)')
]:
    if data[signal_type]:
        sorted_stocks = sorted(data[signal_type], key=lambda x: x['confidence'], reverse=True)[:10]
        print(f'\n{signal_name} - Top 10 by Confidence:')
        print('-' * 80)
        print(f'{"Code":<8} {"Name":<16} {"Date":<12} {"Price":<8} {"Gap":<8} {"VolRatio":<8} {"Conf":<6}')
        print('-' * 80)
        for stock in sorted_stocks:
            print(f'{stock["code"]:<8} {stock["name"]:<16} {stock["signal_date"]:<12} '
                  f'{stock["signal_price"]:<8.2f} {stock["gap"]:<8.2f} '
                  f'{stock["volume_ratio"]:<8.2f} {stock["confidence"]:<6.2f}')
