#!/usr/bin/env python3
"""
Screener Config Loader - 筛选器配置加载模块

负责:
- 从JSON文件加载筛选器配置
- 从数据库加载筛选器配置
- 参数验证
- 配置文件和数据库同步
"""
import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
from datetime import datetime

# Add backend to path
BACKEND_ROOT = Path(__file__).parent
sys.path.insert(0, str(BACKEND_ROOT))

try:
    from models import get_screener_config, save_screener_config, get_all_screener_configs
except ImportError:
    print("Warning: Could not import models. Database operations will be disabled.")

CONFIG_DIR = BACKEND_ROOT.parent / 'config' / 'screeners'


class ConfigLoader:
    """筛选器配置加载器"""

    @staticmethod
    def get_config_path(screener_name: str) -> Path:
        """获取筛选器配置文件路径"""
        return CONFIG_DIR / f'{screener_name}.json'

    @staticmethod
    def load_from_file(screener_name: str) -> Optional[Dict]:
        """
        从JSON文件加载配置

        Args:
            screener_name: 筛选器名称

        Returns:
            配置字典，如果文件不存在返回None
        """
        config_path = ConfigLoader.get_config_path(screener_name)

        if not config_path.exists():
            return None

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading config from {config_path}: {e}")
            return None

    @staticmethod
    def load_from_database(screener_name: str) -> Optional[Dict]:
        """
        从数据库加载配置

        Args:
            screener_name: 筛选名称

        Returns:
            配置字典，如果不存在返回None
        """
        try:
            config_data = get_screener_config(screener_name)
            print(f"[DEBUG ConfigLoader] get_screener_config returned: {config_data}")
            print(f"[DEBUG ConfigLoader] config_data type: {type(config_data)}")
            if config_data:
                # Parse config_json (may already be a dict or JSON string)
                config_json_raw = config_data['config_json']
                if isinstance(config_json_raw, dict):
                    config_json = config_json_raw
                else:
                    config_json = json.loads(config_json_raw)
                print(f"[DEBUG ConfigLoader] Parsed config_json: {config_json}")

                # Get schema (may already be a dict or JSON string)
                schema_json_raw = config_data['config_schema']
                if isinstance(schema_json_raw, dict):
                    schema_json = schema_json_raw
                else:
                    schema_json = json.loads(schema_json_raw)
                print(f"[DEBUG ConfigLoader] Parsed schema_json: {schema_json}")

                # Extract schema parameters for parameter mapping
                schema_parameters = schema_json.get('parameters', {})
                print(f"[DEBUG ConfigLoader] Schema parameters: {list(schema_parameters.keys())}")

                # Build parameters dict with schema metadata
                parameters_with_schema = {}
                for param_name, param_value in config_json.items():
                    if param_name in schema_parameters:
                        param_schema = schema_parameters[param_name]
                        parameters_with_schema[param_name] = {
                            'value': param_value,
                            'display_name': param_schema.get('display_name', param_name),
                            'description': param_schema.get('description', ''),
                            'group': param_schema.get('group', '其他'),
                            'type': param_schema.get('type', 'string')
                        }
                print(f"[DEBUG ConfigLoader] Built parameters with {len(parameters_with_schema)} items")

                # 提取配置JSON和Schema
                return {
                    'metadata': {
                        'version': config_data['current_version'],
                        'last_updated': config_data['updated_at']
                    },
                    'display_name': config_data['display_name'],
                    'description': config_data['description'],
                    'category': config_data['category'],
                    'parameters': parameters_with_schema
                }
            else:
                print(f"[DEBUG ConfigLoader] config_data is None, returning None")
        except Exception as e:
            print(f"Error loading config from database: {e}")

        return None

    @staticmethod
    def load_config(screener_name: str, prefer_database: bool = True) -> Optional[Dict]:
        """
        加载筛选器配置（优先从数据库，回退到文件）

        Args:
            screener_name: 筛选器名称
            prefer_database: 是否优先从数据库加载

        Returns:
            配置字典，如果都不存在返回None
        """
        if prefer_database:
            # 优先从数据库加载
            config = ConfigLoader.load_from_database(screener_name)
            if config:
                return config

        # 回退到文件
        return ConfigLoader.load_from_file(screener_name)

    @staticmethod
    def save_to_file(screener_name: str, config: Dict) -> bool:
        """
        保存配置到JSON文件

        Args:
            screener_name: 筛选器名称
            config: 配置字典

        Returns:
            是否成功
        """
        config_path = ConfigLoader.get_config_path(screener_name)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # 添加元数据
        if 'metadata' not in config:
            config['metadata'] = {}
        config['metadata']['last_updated'] = datetime.now().isoformat()

        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except (IOError, TypeError) as e:
            print(f"Error saving config to {config_path}: {e}")
            return False

    @staticmethod
    def save_config(screener_name: str, config: Dict, schema: Dict,
                   change_summary: str = '', changed_by: str = 'system') -> Tuple[bool, str]:
        """
        保存配置到数据库和文件

        Args:
            screener_name: 筛选器名称
            config: 配置字典
            schema: 参数Schema
            change_summary: 变更摘要
            changed_by: 修改人

        Returns:
            (是否成功, 新版本号)
        """
        print(f"[DEBUG] ConfigLoader.save_config called for: {screener_name}")
        print(f"[DEBUG] config keys: {list(config.keys())}")
        print(f"[DEBUG] schema keys: {list(schema.keys())}")

        # 保存到数据库
        try:
            print(f"[DEBUG] Saving to database...")
            new_version = save_screener_config(screener_name, config, schema, change_summary, changed_by)
            print(f"[DEBUG] Database save successful, version: {new_version}")
        except Exception as e:
            print(f"[ERROR] Error saving config to database: {e}")
            import traceback
            traceback.print_exc()
            return False, ''

        # 保存到文件
        print(f"[DEBUG] Saving to file...")
        file_save_success = ConfigLoader.save_to_file(screener_name, config)
        print(f"[DEBUG] File save result: {file_save_success}")
        if not file_save_success:
            print(f"Warning: Failed to save config to file, but database save succeeded")

        return True, new_version

    @staticmethod
    def validate_parameter(param_name: str, param_value: Any, schema: Dict) -> Tuple[bool, Optional[str]]:
        """
        验证单个参数

        Args:
            param_name: 参数名称
            param_value: 参数值
            schema: 参数Schema

        Returns:
            (是否有效, 错误信息)
        """
        if param_name not in schema:
            return False, f"未知参数: {param_name}"

        param_schema = schema[param_name]
        param_type = param_schema['type']

        # 类型验证
        try:
            if param_type == 'int':
                if not isinstance(param_value, (int, float)):
                    param_value = int(param_value)
                if not isinstance(param_value, int):
                    return False, f"{param_schema.get('display_name', param_name)} 必须是整数"
            elif param_type == 'float':
                if not isinstance(param_value, (int, float)):
                    param_value = float(param_value)
            elif param_type == 'bool':
                if not isinstance(param_value, bool):
                    if isinstance(param_value, str):
                        param_value = param_value.lower() in ('true', '1', 'yes')
                    else:
                        return False, f"{param_schema.get('display_name', param_name)} 必须是布尔值"
            elif param_type == 'string':
                if not isinstance(param_value, str):
                    param_value = str(param_value)
        except (ValueError, TypeError) as e:
            return False, f"{param_schema.get('display_name', param_name)} 类型错误: {str(e)}"

        # 范围验证
        if 'min' in param_schema and param_value < param_schema['min']:
            return False, f"{param_schema.get('display_name', param_name)} 必须 >= {param_schema['min']}"

        if 'max' in param_schema and param_value > param_schema['max']:
            return False, f"{param_schema.get('display_name', param_name)} 必须 <= {param_schema['max']}"

        # 步进验证
        if 'step' in param_schema and param_type in ('int', 'float'):
            step = param_schema['step']
            if param_type == 'int':
                step = int(step)
            default = param_schema['default']
            if ((param_value - default) / step) % 1 != 0:
                return False, f"{param_schema.get('display_name', param_name)} 必须是 {step} 的倍数"

        return True, None

    @staticmethod
    def validate_parameters(parameters: Dict, schema: Dict) -> Tuple[bool, Dict[str, str]]:
        """
        验证所有参数

        Args:
            parameters: 参数字典
            schema: 参数Schema

        Returns:
            (是否全部有效, 错误字典)
        """
        errors = {}
        all_valid = True

        for param_name, param_value in parameters.items():
            valid, error_msg = ConfigLoader.validate_parameter(param_name, param_value, schema)
            if not valid:
                all_valid = False
                errors[param_name] = error_msg

        return all_valid, errors

    @staticmethod
    def get_all_screener_configs() -> Dict[str, Dict]:
        """获取所有筛选器配置（从数据库）"""
        try:
            configs = get_all_screener_configs()
            return {c['screener_name']: c for c in configs}
        except Exception as e:
            print(f"Error getting all configs: {e}")
            return {}

    @staticmethod
    def sync_config_to_database(screener_name: str, schema: Dict) -> bool:
        """
        同步文件配置到数据库

        Args:
            screener_name: 筛选器名称
            schema: 参数Schema

        Returns:
            是否成功
        """
        config = ConfigLoader.load_from_file(screener_name)
        if not config:
            return False

        success, _ = ConfigLoader.save_config(
            screener_name,
            config,
            schema,
            change_summary='从文件同步',
            changed_by='system'
        )

        return success


# 便捷函数
def load_screener_config(screener_name: str) -> Optional[Dict]:
    """便捷函数：加载筛选器配置"""
    return ConfigLoader.load_config(screener_name)


if __name__ == '__main__':
    # 测试代码
    print("Testing ConfigLoader...")

    # 测试加载配置
    config = load_screener_config('er_ban_hui_tiao')
    if config:
        print(f"✓ Loaded config: {config['display_name']}")
    else:
        print("✗ Config not found (this is expected if not yet created)")

    # 测试参数验证
    test_schema = {
        'limit_days': {
            'type': 'int',
            'default': 14,
            'min': 1,
            'max': 60
        }
    }

    valid, error = ConfigLoader.validate_parameter('limit_days', 15, test_schema)
    print(f"Validation test (15): {valid}, {error}")

    valid, error = ConfigLoader.validate_parameter('limit_days', 999, test_schema)
    print(f"Validation test (999): {valid}, {error}")
