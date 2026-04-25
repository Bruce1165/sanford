#!/bin/bash
#
# Manual trigger for five flags pool screening
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_PATH="/usr/bin/python3"
TASK_SCRIPT="$SCRIPT_DIR/run_five_flags_pool_screening.py"

# Parse arguments
MAX_WORKERS=4
POOL_IDS=""
AS_OF_DATE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --workers)
            MAX_WORKERS=$2
            shift 2
            ;;
        --pool-ids)
            POOL_IDS=$2
            shift 2
            ;;
        --as-of-date)
            AS_OF_DATE=$2
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --workers N       Number of parallel workers (default: 4)"
            echo "  --pool-ids IDS   Specific pool IDs to screen (comma-separated)"
            echo "  --as-of-date D   Catch-up target date (YYYY-MM-DD, resolves to recent trading day)"
            echo "  --help           Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage"
            exit 1
            ;;
    esac
done

echo "🚀 Starting five flags pool screening"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Build Python command
PYTHON_CMD="$PYTHON_PATH $TASK_SCRIPT"

if [ ! -z "$POOL_IDS" ]; then
    echo "🎯 Specific pools: $POOL_IDS"
    PYTHON_CMD="$PYTHON_CMD --pool-ids $POOL_IDS"
fi
if [ ! -z "$AS_OF_DATE" ]; then
    echo "📅 Target date: $AS_OF_DATE"
    PYTHON_CMD="$PYTHON_CMD --as-of-date $AS_OF_DATE"
fi

echo "👷 Parallel workers: $MAX_WORKERS"
echo ""

# Run screening
$PYTHON_CMD --max-workers $MAX_WORKERS

echo ""
echo "✅ Screening completed!"
echo ""
echo "📊 View results:"
echo "  sqlite3 data/stock_data.db \"SELECT screener_id, COUNT(*) FROM lao_ya_tou_five_flags GROUP BY screener_id;\""
echo ""
echo "📄 View logs:"
echo "  tail -100 logs/five_flags_screening.log"
