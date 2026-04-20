#!/usr/bin/env python3
"""
Docstring Updater - 筛选器代码注释更新模块

负责:
- 根据配置生成新的docstring
- 更新筛选器Python文件的docstring
- 保持代码逻辑不变，只更新注释
"""
import re
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime

# Add backend to path
BACKEND_ROOT = Path(__file__).parent
sys.path.insert(0, str(BACKEND_ROOT))

SCREENERS_DIR = BACKEND_ROOT.parent / 'screeners'


class DocstringUpdater:
    """Docstring更新器"""

    @staticmethod
    def generate_docstring(screener_name: str, config: Dict, schema: Dict) -> str:
        """
        根据配置生成docstring

        Args:
            screener_name: 筛选器名称
            config: 配置字典
            schema: 参数Schema

        Returns:
            生成的docstring字符串
        """
        display_name = config.get('display_name', screener_name)
        description = config.get('description', '')
        category = config.get('category', '未分类')
        version = config.get('metadata', {}).get('version', 'v1.0')

        # 生成参数说明
        parameters_text = DocstringUpdater._generate_parameters_text(config.get('parameters', {}))

        docstring_parts = [
            f'"""',
            f'{display_name} - {screener_name.title().replace("_", "")} ({version})',
            '',
            f'{description}',
            '',
            f'分类: {category}',
            '',
            '配置参数:',
            f'{parameters_text}',
            '',
            f'配置文件: config/screeners/{screener_name}.json',
            f'"""'
        ]

        return '\n'.join(docstring_parts)

    @staticmethod
    def _generate_parameters_text(parameters: Dict) -> str:
        """
        生成参数说明文本

        Args:
            parameters: 参数字典

        Returns:
            参数说明文本
        """
        if not parameters:
            return "    无参数"

        # 按分组组织参数
        groups = {}
        for param_name, param_config in parameters.items():
            group = param_config.get('group', '其他')
            if group not in groups:
                groups[group] = []
            groups[group].append((param_name, param_config))

        text_lines = []
        for group_name, param_list in groups.items():
            text_lines.append(f"    [{group_name}]")
            for param_name, param_config in param_list:
                display_name = param_config.get('display_name', param_name)
                description = param_config.get('description', '')
                value = param_config.get('value')
                param_type = param_config.get('type', '')

                # 参数说明
                desc_line = f"        {display_name} ({param_type}): {value}"
                text_lines.append(desc_line)

                if description:
                    text_lines.append(f"            {description}")

                # 范围说明
                if 'min' in param_config or 'max' in param_config:
                    range_text = "            范围: "
                    parts = []
                    if 'min' in param_config:
                        parts.append(f"最小 {param_config['min']}")
                    if 'max' in param_config:
                        parts.append(f"最大 {param_config['max']}")
                    range_text += " - ".join(parts)
                    text_lines.append(range_text)

                if 'default' in param_config:
                    text_lines.append(f"            默认值: {param_config['default']}")

            text_lines.append("")  # 空行

        return "\n".join(text_lines)

    @staticmethod
    def get_screener_file_path(screener_name: str) -> Optional[Path]:
        """
        获取筛选器文件路径

        Args:
            screener_name: 筛选器名称

        Returns:
            文件路径，如果不存在返回None
        """
        file_path = SCREENERS_DIR / f'{screener_name}_screener.py'
        if file_path.exists():
            return file_path
        return None

    @staticmethod
    def update_screener_docstring(screener_name: str, config: Dict, schema: Dict) -> Tuple[bool, str]:
        """
        更新筛选器文件的docstring

        Args:
            screener_name: 筛选器名称
            config: 配置字典
            schema: 参数Schema

        Returns:
            (是否成功, 错误信息)
        """
        file_path = DocstringUpdater.get_screener_file_path(screener_name)
        if not file_path:
            return False, f"Screener file not found: {screener_name}_screener.py"

        try:
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 生成新的docstring
            new_docstring = DocstringUpdater.generate_docstring(screener_name, config, schema)

            # 替换文件中的第一个docstring
            # 匹配从文件开头到第一个class定义之间的docstring
            pattern = r'"""[\s\S]*?"""'
            matches = list(re.finditer(pattern, content))

            if not matches:
                return False, "No docstring found in file"

            first_match = matches[0]
            start, end = first_match.span()

            # 替换docstring
            new_content = content[:start] + new_docstring + content[end:]

            # 写回文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            return True, f"Docstring updated for {screener_name}"

        except IOError as e:
            return False, f"IO Error: {str(e)}"
        except Exception as e:
            return False, f"Error: {str(e)}"

    @staticmethod
    def update_all_screeners_docstrings() -> Tuple[int, int]:
        """
        更新所有筛选器的docstring

        Returns:
            (成功数量, 失败数量)
        """
        from config_loader import ConfigLoader

        # 获取所有筛选器
        screener_files = list(SCREENERS_DIR.glob('*_screener.py'))
        screener_names = [f.stem.replace('_screener', '') for f in screener_files
                         if f.stem != 'base']

        success_count = 0
        fail_count = 0

        for screener_name in screener_names:
            # 加载配置和schema
            config = ConfigLoader.load_config(screener_name)
            if not config:
                fail_count += 1
                continue

            # 获取schema（需要动态导入筛选器类）
            schema = DocstringUpdater._get_screener_schema(screener_name)
            if not schema:
                fail_count += 1
                continue

            # 更新docstring
            success, msg = DocstringUpdater.update_screener_docstring(screener_name, config, schema)
            if success:
                success_count += 1
                print(f"✓ Updated: {screener_name}")
            else:
                fail_count += 1
                print(f"✗ Failed: {screener_name} - {msg}")

        return success_count, fail_count

    @staticmethod
    def _get_screener_schema(screener_name: str) -> Optional[Dict]:
        """
        动态获取筛选器的参数schema

        Args:
            screener_name: 筛选器名称

        Returns:
            参数Schema，如果获取失败返回None
        """
        try:
            # 动态导入筛选器模块
            module = __import__(f'screeners.{screener_name}_screener')
            # 查找筛选器类
            class_name = f"{screener_name.title().replace('_', '')}Screener"
            screener_class = getattr(module, class_name, None)

            if screener_class and hasattr(screener_class, 'get_parameter_schema'):
                return screener_class.get_parameter_schema()

        except Exception as e:
            print(f"Warning: Could not get schema for {screener_name}: {e}")

        return None


# 便捷函数
def update_docstring(screener_name: str, config: Dict, schema: Dict) -> Tuple[bool, str]:
    """便捷函数：更新筛选器docstring"""
    return DocstringUpdater.update_screener_docstring(screener_name, config, schema)


if __name__ == '__main__':
    # 测试代码
    print("Testing DocstringUpdater...")

    # 测试生成docstring
    test_config = {
        'display_name': '测试筛选器',
        'description': '这是一个测试筛选器',
        'category': '测试分类',
        'metadata': {'version': 'v1.0'},
        'parameters': {
            'limit_days': {
                'type': 'int',
                'value': 14,
                'default': 14,
                'min': 1,
                'max': 60,
                'description': '时间范围',
                'display_name': '时间范围（天）',
                'group': '基础设置'
            },
            'threshold': {
                'type': 'float',
                'value': 9.9,
                'default': 9.9,
                'min': 0,
                'max': 20,
                'description': '阈值',
                'display_name': '阈值（%）',
                'group': '信号条件'
            }
        }
    }

    docstring = DocstringUpdater.generate_docstring('test_screener', test_config, test_config.get('parameters', {}))
    print("Generated docstring:")
    print(docstring)
