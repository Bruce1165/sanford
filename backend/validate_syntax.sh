#!/bin/bash
# Pre-commit hook to validate Python syntax before Flask app.py edits
# Run this after ANY edit to app.py

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_FILE="$SCRIPT_DIR/app.py"

echo "🔍 Validating Python syntax for app.py..."

# Check syntax
python3 -m py_compile "$APP_FILE"

# Test import
cd "$SCRIPT_DIR"
python3 -c "import app; print('✅ app.py is valid')"

echo "✅ Validation passed"
