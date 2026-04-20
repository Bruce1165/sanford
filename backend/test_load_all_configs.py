#!/usr/bin/env python3
"""
Test loading all screener configs from files
"""
import sys
from pathlib import Path

workspace_root = Path(__file__).parent.parent
sys.path.insert(0, str(workspace_root))

from backend.config_loader import ConfigLoader

# Get all config files
config_dir = workspace_root / 'config' / 'screeners'
config_files = sorted(config_dir.glob('*.json'))

print("=" * 60)
print("Testing Config Loading for All Screeners")
print("=" * 60)

success_count = 0
fail_count = 0

for config_file in config_files:
    screener_name = config_file.stem
    print(f"\n[{screener_name}]")

    # Load from file
    config = ConfigLoader.load_from_file(screener_name)
    if config:
        print(f"  ✓ Loaded from file")
        print(f"    Display name: {config.get('display_name')}")
        print(f"    Category: {config.get('category')}")
        params = config.get('parameters', {})
        print(f"    Parameters: {len(params)}")
        for param_name, param_config in params.items():
            print(f"      - {param_name}: {param_config.get('value')}")
        success_count += 1
    else:
        print(f"  ✗ Failed to load from file")
        fail_count += 1

print("\n" + "=" * 60)
print(f"Summary: {success_count} success, {fail_count} failed")
print("=" * 60)
