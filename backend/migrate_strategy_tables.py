#!/usr/bin/env python3
"""
Database Migration Script - Create Strategy Tables

运行此脚本来创建战法相关的数据库表和索引
"""
import sys
from pathlib import Path

# Add workspace to path
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "backend"))

try:
    from models import init_db, get_db_connection
except ImportError:
    from backend.models import init_db, get_db_connection


def verify_tables_created():
    """验证表是否创建成功"""
    print("\n=== 验证表创建 ===")

    conn = get_db_connection()
    cursor = conn.cursor()

    # 检查战法相关表
    strategy_tables = [
        'strategies',
        'strategy_runs',
        'strategy_signals',
        'strategy_performance'
    ]

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    existing_tables = [row['name'] for row in cursor.fetchall()]

    print(f"\n数据库中的表总数: {len(existing_tables)}")

    all_created = True
    for table in strategy_tables:
        if table in existing_tables:
            print(f"  ✓ {table} - 已创建")
        else:
            print(f"  ✗ {table} - 未找到")
            all_created = False

    # 检查索引
    print("\n=== 验证索引创建 ===")
    strategy_indexes = [
        'idx_strategy_runs_lookup',
        'idx_strategy_signals_run',
        'idx_strategy_signals_code',
        'idx_strategy_signals_type',
        'idx_strategy_performance_strategy'
    ]

    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name")
    existing_indexes = [row['name'] for row in cursor.fetchall()]

    all_indexes_created = True
    for index in strategy_indexes:
        if index in existing_indexes:
            print(f"  ✓ {index} - 已创建")
        else:
            print(f"  ✗ {index} - 未找到")
            all_indexes_created = False

    conn.close()

    if all_created and all_indexes_created:
        print("\n✅ 所有表和索引创建成功！")
        return True
    else:
        print("\n❌ 部分表或索引创建失败！")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("战法数据库表迁移脚本")
    print("=" * 60)

    print("\n开始创建数据库表...")
    try:
        init_db()
        print("\n✓ 数据库初始化完成")
    except Exception as e:
        print(f"\n✗ 数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 验证表创建
    success = verify_tables_created()

    if success:
        print("\n" + "=" * 60)
        print("迁移完成！")
        print("=" * 60)
        print("\n下一步:")
        print("1. 在 backend/app.py 中注册战法蓝图")
        print("2. 重启 Flask 服务器")
        print("3. 测试 API 端点")
    else:
        print("\n" + "=" * 60)
        print("迁移未完全成功，请检查错误信息")
        print("=" * 60)

    return success


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
