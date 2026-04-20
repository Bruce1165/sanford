#!/usr/bin/env python3
"""Test config API to debug the issue."""
import sys
import sqlite3
import json
import requests
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "dashboard.db"

def main():
    print("Testing config API directly...")

    # Check what's in database
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM screener_configs
        WHERE screener_name = ?
    ''', ('lao_ya_tou_zhou_xian_screener',))
    row = cursor.fetchone()

    if row:
        print(f"Raw config_json: {row['config_json']}")
        print(f"Raw config_schema: {row['config_schema']}")
    else:
        print("No config found")
        conn.close()
        sys.exit(1)

    # Try to parse the JSON
    try:
        config_json = json.loads(row['config_json'])
        print(f"Parsed config_json: {config_json}")
    except Exception as e:
        print(f"Failed to parse config_json: {e}")
        conn.close()
        sys.exit(1)

    # Test API endpoint
    try:
        response = requests.get('http://localhost:8765/api/screeners/lao_ya_tou_zhou_xian_screener/config', timeout=5)
        print(f"API Response Status: {response.status_code}")
        print(f"API Response: {response.text}")
        print(f"API Response JSON: {response.json()}")
    except Exception as e:
        print(f"API Request Failed: {e}")

    conn.close()

if __name__ == '__main__':
    main()
