#!/usr/bin/env python3
"""
Strategy Factory - 战法工厂

负责战法的发现、加载和实例化
"""
import importlib
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
from .base_strategy import BaseStrategy


class StrategyFactory:
    """战法工厂 - 负责战法的发现、加载和实例化"""

    @staticmethod
    def discover_strategies(workspace_root: str) -> List[Dict]:
        """
        发现所有战法文件

        Args:
            workspace_root: 工作空间根目录

        Returns:
            战法元数据列表
        """
        strategies = []
        strategy_dir = os.path.join(workspace_root, 'backend', 'strategies')

        if not os.path.exists(strategy_dir):
            print(f"Warning: Strategy directory not found: {strategy_dir}")
            return strategies

        # 确保策略目录在 Python 路径中
        if str(Path(workspace_root)) not in sys.path:
            sys.path.insert(0, str(Path(workspace_root)))

        for filename in os.listdir(strategy_dir):
            # 过滤条件：
            # 1. 必须以 _strategy.py 结尾
            # 2. 不能是 base_ 开头（基类）
            # 3. 不能是 __ 开头（Python内部文件）
            if (filename.endswith('_strategy.py') and
                not filename.startswith('base_') and
                not filename.startswith('__')):

                module_name = f"backend.strategies.{filename[:-3]}"
                file_path = os.path.join(strategy_dir, filename)

                try:
                    # 动态导入模块
                    module = importlib.import_module(module_name)

                    # 提取战法元数据
                    strategy_info = {
                        'name': module.__dict__.get('STRATEGY_NAME', filename[:-12]),
                        'display_name': module.__dict__.get('STRATEGY_DISPLAY_NAME', filename[:-12]),
                        'description': module.__dict__.get('STRATEGY_DESCRIPTION', ''),
                        'category': module.__dict__.get('STRATEGY_CATEGORY', '通用'),
                        'version': module.__dict__.get('STRATEGY_VERSION', 'v1.0.0'),
                        'file_path': file_path
                    }

                    strategies.append(strategy_info)
                    print(f"Discovered strategy: {strategy_info['display_name']} ({strategy_info['name']})")

                except Exception as e:
                    print(f"Error loading strategy {filename}: {e}")
                    import traceback
                    traceback.print_exc()

        return strategies

    @staticmethod
    def create_strategy(strategy_name: str, config: Dict) -> Optional[BaseStrategy]:
        """
        创建战法实例

        Args:
            strategy_name: 战法名称（与文件名对应，不含_strategy.py）
            config: 战法配置

        Returns:
            战法实例，如果创建失败返回None
        """
        try:
            # 尝试导入对应的战法模块
            module_name = f"backend.strategies.{strategy_name}_strategy"
            module = importlib.import_module(module_name)

            # 查找战法类（应该继承自 BaseStrategy）
            strategy_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    issubclass(attr, BaseStrategy) and
                    attr is not BaseStrategy):
                    strategy_class = attr
                    break

            if not strategy_class:
                print(f"Error: No valid strategy class found in {module_name}")
                return None

            # 创建实例
            strategy_instance = strategy_class(strategy_name, config)
            print(f"Created strategy instance: {strategy_instance}")
            return strategy_instance

        except ImportError as e:
            print(f"Error: Cannot import strategy module {module_name}: {e}")
            return None
        except Exception as e:
            print(f"Error creating strategy {strategy_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    def sync_strategies_with_db(workspace_root: str, db_module):
        """
        同步战法到数据库

        Args:
            workspace_root: 工作空间根目录
            db_module: 数据库模块（用于访问数据库函数）
        """
        # 发现所有战法
        strategies = StrategyFactory.discover_strategies(workspace_root)

        # 同步到数据库
        for strategy_info in strategies:
            try:
                # 注册或更新战法
                db_module.register_strategy(
                    name=strategy_info['name'],
                    display_name=strategy_info['display_name'],
                    description=strategy_info['description'],
                    category=strategy_info['category'],
                    file_path=strategy_info['file_path'],
                    version=strategy_info['version']
                )
                print(f"Synced strategy to DB: {strategy_info['display_name']}")
            except Exception as e:
                print(f"Error syncing strategy {strategy_info['name']} to DB: {e}")

        # 删除数据库中已不存在的战法（可选，谨慎使用）
        # db_strategies = db_module.get_all_strategies()
        # db_strategy_names = {s['name'] for s in db_strategies}
        # discovered_names = {s['name'] for s in strategies}
        # for name in db_strategy_names - discovered_names:
        #     print(f"Deleting obsolete strategy from DB: {name}")
        #     db_module.delete_strategy(name)

        print(f"Synced {len(strategies)} strategies to database")

    @staticmethod
    def get_strategy_config(workspace_root: str, strategy_name: str) -> Optional[Dict]:
        """
        获取战法的默认配置

        Args:
            workspace_root: 工作空间根目录
            strategy_name: 战法名称

        Returns:
            配置字典，如果失败返回None
        """
        try:
            # 尝试导入对应的战法模块
            module_name = f"backend.strategies.{strategy_name}_strategy"
            module = importlib.import_module(module_name)

            # 获取默认配置
            default_config = module.__dict__.get('STRATEGY_DEFAULT_CONFIG', {})

            # 添加元数据
            default_config.update({
                'display_name': module.__dict__.get('STRATEGY_DISPLAY_NAME', strategy_name),
                'description': module.__dict__.get('STRATEGY_DESCRIPTION', ''),
                'category': module.__dict__.get('STRATEGY_CATEGORY', '通用'),
                'version': module.__dict__.get('STRATEGY_VERSION', 'v1.0.0')
            })

            return default_config

        except Exception as e:
            print(f"Error getting config for strategy {strategy_name}: {e}")
            return None


if __name__ == '__main__':
    # 测试代码
    workspace = Path(__file__).parent.parent.parent

    print("=== Discovering Strategies ===")
    strategies = StrategyFactory.discover_strategies(str(workspace))
    print(f"\nFound {len(strategies)} strategies:")
    for s in strategies:
        print(f"  - {s['display_name']} ({s['name']}) - {s['category']}")
