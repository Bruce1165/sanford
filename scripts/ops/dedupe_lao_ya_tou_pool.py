#!/usr/bin/env python3

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def _backup_db(db_path: Path) -> Path:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = db_path.parent / f'{db_path.name}.bak_{ts}'
    shutil.copy2(db_path, backup_path)
    return backup_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default='data/stock_data.db')
    ap.add_argument('--no-backup', action='store_true')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        raise SystemExit(f'db not found: {db_path}')

    conn = _connect(db_path)
    cur = conn.cursor()

    cur.execute('SELECT COUNT(*) AS n FROM lao_ya_tou_pool')
    before_rows = int(cur.fetchone()['n'])
    cur.execute('SELECT COUNT(DISTINCT stock_code) AS n FROM lao_ya_tou_pool')
    before_distinct = int(cur.fetchone()['n'])

    if before_rows == before_distinct:
        print(f'pool already deduped: rows={before_rows} stocks={before_distinct}')
        return 0

    cur.execute(
        '''
        SELECT stock_code, COUNT(*) AS n
        FROM lao_ya_tou_pool
        GROUP BY stock_code
        HAVING COUNT(*) > 1
        ORDER BY n DESC, stock_code ASC
        '''
    )
    dup_groups = cur.fetchall()
    dup_group_count = len(dup_groups)
    dup_rows = sum(int(r['n']) for r in dup_groups)
    to_remove = before_rows - before_distinct
    print(f'pool rows={before_rows} distinct_stocks={before_distinct} dup_groups={dup_group_count} dup_rows={dup_rows} remove_rows={to_remove}')

    if not args.apply:
        print('dry-run: pass --apply to execute')
        return 0

    backup_path = None
    if not args.no_backup:
        backup_path = _backup_db(db_path)
        print(f'backup: {backup_path}')

    conn.execute('BEGIN')
    try:
        cur.execute(
            '''
            SELECT stock_code, MAX(id) AS keep_id
            FROM lao_ya_tou_pool
            GROUP BY stock_code
            '''
        )
        keep_by_code = {str(r['stock_code']).strip(): int(r['keep_id']) for r in cur.fetchall()}

        cur.execute(
            '''
            SELECT stock_code,
                   MIN(start_date) AS min_start_date,
                   MAX(end_date) AS max_end_date,
                   MAX(COALESCE(last_screened_date, '')) AS max_last_screened_date
            FROM lao_ya_tou_pool
            GROUP BY stock_code
            '''
        )
        merged = {
            str(r['stock_code']).strip(): {
                'min_start_date': str(r['min_start_date']),
                'max_end_date': str(r['max_end_date']),
                'max_last_screened_date': str(r['max_last_screened_date'] or '').strip(),
            }
            for r in cur.fetchall()
        }

        for code, keep_id in keep_by_code.items():
            m = merged.get(code) or {}
            last_screened = m.get('max_last_screened_date') or None
            processed = 1 if last_screened else 0
            cur.execute(
                '''
                UPDATE lao_ya_tou_pool
                SET start_date = ?,
                    end_date = ?,
                    last_screened_date = ?,
                    processed = ?
                WHERE id = ?
                ''',
                (m.get('min_start_date'), m.get('max_end_date'), last_screened, processed, keep_id),
            )

        cur.execute('SELECT id, stock_code FROM lao_ya_tou_pool')
        rows = cur.fetchall()
        id_to_keep = {int(r['id']): keep_by_code.get(str(r['stock_code']).strip()) for r in rows}
        id_to_keep = {k: v for k, v in id_to_keep.items() if v is not None}

        updated_flags = 0
        for old_id, keep_id in id_to_keep.items():
            if old_id == keep_id:
                continue
            cur.execute('UPDATE lao_ya_tou_five_flags SET pool_id = ? WHERE pool_id = ?', (keep_id, old_id))
            updated_flags += cur.rowcount if cur.rowcount != -1 else 0

        keep_ids = sorted(set(keep_by_code.values()))
        placeholders = ','.join(['?'] * len(keep_ids))
        cur.execute(f'DELETE FROM lao_ya_tou_pool WHERE id NOT IN ({placeholders})', keep_ids)
        deleted_pool_rows = cur.rowcount if cur.rowcount != -1 else 0

        cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_pool_stock_code_unique ON lao_ya_tou_pool(stock_code)')

        cur.execute('PRAGMA foreign_key_check')
        fk_issues = cur.fetchall()
        if fk_issues:
            raise RuntimeError(f'foreign key check failed: {len(fk_issues)} issues, first={dict(fk_issues[0])}')

        conn.commit()
        print(f'updated_five_flags_pool_id_rows={updated_flags} deleted_pool_rows={deleted_pool_rows}')
    except Exception:
        conn.rollback()
        if backup_path is not None:
            print(f'rollback complete; db backup at {backup_path}')
        raise
    finally:
        conn.close()

    conn2 = _connect(db_path)
    cur2 = conn2.cursor()
    cur2.execute('SELECT COUNT(*) AS n FROM lao_ya_tou_pool')
    after_rows = int(cur2.fetchone()['n'])
    cur2.execute('SELECT COUNT(DISTINCT stock_code) AS n FROM lao_ya_tou_pool')
    after_distinct = int(cur2.fetchone()['n'])
    conn2.close()
    print(f'after pool rows={after_rows} distinct_stocks={after_distinct}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

