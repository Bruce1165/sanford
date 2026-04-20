#!/usr/bin/env python3
"""
Test script for configuration loading functionality

Tests:
1. BaseScreener config loading
2. Parameter schema generation
3. Config application to instance variables
"""
import sys
from pathlib import Path
from typing import Dict, Optional

# Add workspace root to path (must be before any imports)
workspace_root = Path(__file__).parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

# Import BaseScreener from screeners package
# Note: This requires screeners/__init__.py to exist
from screeners.base_screener import BaseScreener


class TestScreener(BaseScreener):
    """Test screener with config parameters"""

    screener_name = "test_screener"

    # Configurable parameters
    LIMIT_DAYS: int = 14
    MIN_SCORE: float = 80.0
    ENABLE_FILTER: bool = True
    FILTER_NAME: str = "default"

    @classmethod
    def get_parameter_schema(cls):
        """Define parameter schema"""
        return {
            'LIMIT_DAYS': {
                'type': 'int',
                'default': 14,
                'min': 1,
                'max': 60,
                'display_name': '时间范围（天）',
                'description': '筛选的时间窗口长度',
                'group': '基础设置'
            },
            'MIN_SCORE': {
                'type': 'float',
                'default': 80.0,
                'min': 0,
                'max': 100,
                'step': 0.1,
                'display_name': '最小评分',
                'description': '股票必须达到的最低评分',
                'group': '评分条件'
            },
            'ENABLE_FILTER': {
                'type': 'bool',
                'default': True,
                'display_name': '启用过滤器',
                'description': '是否启用额外过滤条件',
                'group': '过滤设置'
            },
            'FILTER_NAME': {
                'type': 'string',
                'default': 'default',
                'display_name': '过滤器名称',
                'description': '使用的过滤器类型',
                'group': '过滤设置'
            }
        }

    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """Test implementation"""
        return None


def test_base_screener():
    """Test BaseScreener config loading (using TestScreener as concrete implementation)"""
    print("=" * 60)
    print("Test 1: BaseScreener Config Loading")
    print("=" * 60)

    screener = TestScreener(screener_name="base_test")

    # Test get_config
    config = screener.get_config()
    print(f"✓ Config loaded: {len(config)} fields")
    print(f"  Display name: {config.get('display_name')}")
    print(f"  Category: {config.get('category')}")
    print(f"  Parameters: {len(config.get('parameters', {}))} params")

    # Test get_parameter_schema (should have 4 parameters for TestScreener)
    schema = screener.get_parameter_schema()
    print(f"✓ TestScreener schema: {len(schema)} parameters (expected: 4)")

    print()


def test_test_screener():
    """Test TestScreener with config parameters"""
    print("=" * 60)
    print("Test 2: TestScreener with Config Parameters")
    print("=" * 60)

    screener = TestScreener()

    # Test schema
    schema = screener.get_parameter_schema()
    print(f"✓ Schema defined: {len(schema)} parameters")
    for param_name, param_config in schema.items():
        print(f"  - {param_name} ({param_config['type']}): {param_config.get('display_name')}")

    # Test default config
    config = screener.get_config()
    print(f"\n✓ Default config generated")
    print(f"  Display name: {config.get('display_name')}")
    print(f"  Parameters:")
    for param_name, param_config in config.get('parameters', {}).items():
        print(f"    - {param_name}: {param_config.get('value')}")

    # Test parameter values applied
    print(f"\n✓ Parameter values applied to instance:")
    print(f"  LIMIT_DAYS = {screener.LIMIT_DAYS} (expected: 14)")
    print(f"  MIN_SCORE = {screener.MIN_SCORE} (expected: 80.0)")
    print(f"  ENABLE_FILTER = {screener.ENABLE_FILTER} (expected: True)")
    print(f"  FILTER_NAME = {screener.FILTER_NAME} (expected: 'default')")

    # Test get_parameter_value
    print(f"\n✓ get_parameter_value method:")
    print(f"  LIMIT_DAYS = {screener.get_parameter_value('LIMIT_DAYS')}")
    print(f"  NON_EXISTENT = {screener.get_parameter_value('NON_EXISTENT', 'default')}")

    print()


def test_config_loader_integration():
    """Test integration with ConfigLoader"""
    print("=" * 60)
    print("Test 3: ConfigLoader Integration")
    print("=" * 60)

    try:
        from backend.config_loader import ConfigLoader

        # Test loading existing screener config
        config = ConfigLoader.load_config('er_ban_hui_tiao')
        if config:
            print(f"✓ Loaded config for er_ban_hui_tiao")
            print(f"  Display name: {config.get('display_name')}")
            print(f"  Description: {config.get('description', '')[:50]}...")
            print(f"  Parameters: {len(config.get('parameters', {}))} params")
        else:
            print("✓ No config found for er_ban_hui_tiao (expected if not yet created)")

        # Test parameter validation
        schema = TestScreener.get_parameter_schema()
        valid, error = ConfigLoader.validate_parameter('LIMIT_DAYS', 15, schema)
        print(f"\n✓ Parameter validation:")
        print(f"  LIMIT_DAYS=15: {valid} ({error or 'OK'})")

        valid, error = ConfigLoader.validate_parameter('LIMIT_DAYS', 999, schema)
        print(f"  LIMIT_DAYS=999: {valid} ({error or 'OK'})")

    except ImportError as e:
        print(f"✗ ConfigLoader import failed: {e}")

    print()


def test_docstring_generation():
    """Test docstring generation"""
    print("=" * 60)
    print("Test 4: Docstring Generation")
    print("=" * 60)

    try:
        from backend.docstring_updater import DocstringUpdater

        # Get test screener config and schema
        screener = TestScreener()
        config = screener.get_config()
        schema = screener.get_parameter_schema()

        # Generate docstring
        docstring = DocstringUpdater.generate_docstring('test_screener', config, schema)

        print("✓ Generated docstring:")
        print(docstring)

    except ImportError as e:
        print(f"✗ DocstringUpdater import failed: {e}")

    print()


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("Configuration Loading Test Suite")
    print("=" * 60 + "\n")

    test_base_screener()
    test_test_screener()
    test_config_loader_integration()
    test_docstring_generation()

    print("=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == '__main__':
    main()
