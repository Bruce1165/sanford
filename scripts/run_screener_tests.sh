#!/bin/bash
# Quick script to run Playwright screener tests

set -e

echo "======================================"
echo "NeoTrade2 Screener Automated Tests"
echo "======================================"
echo ""

# Check if Flask is running
if ! lsof -i :8765 > /dev/null 2>&1; then
    echo "❌ Flask dashboard is not running on port 8765"
    echo "   Starting Flask service..."
    launchctl kickstart -k gui/$(id -u)/com.neotrade2.flask
    sleep 3
fi

# Verify Flask is running
if ! lsof -i :8765 > /dev/null 2>&1; then
    echo "❌ Failed to start Flask dashboard"
    exit 1
fi

echo "✓ Flask dashboard is running"
echo ""

# Check if Playwright is installed
if ! command -v npx playwright > /dev/null 2>&1; then
    echo "❌ Playwright is not installed"
    echo "   Installing Playwright..."
    npm install -D @playwright/test
    npx playwright install chromium
fi

echo "✓ Playwright is installed"
echo ""

# Parse arguments
MODE="test"
TEST_FILE="tests/screener-test.spec.ts"

while [[ $# -gt 0 ]]; do
    case $1 in
        --ui)
            MODE="ui"
            shift
            ;;
        --debug)
            MODE="debug"
            shift
            ;;
        --file=*)
            TEST_FILE="${1#*=}"
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --ui       Run tests in UI mode (with browser preview)"
            echo "  --debug    Run tests in debug mode (step through)"
            echo "  --file=FILE  Run specific test file"
            echo "  --help     Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                # Run all tests"
            echo "  $0 --ui           # Run in UI mode"
            echo "  $0 --debug        # Run in debug mode"
            echo "  $0 --file=tests/custom-test.spec.ts  # Run specific test"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "Running tests in $MODE mode..."
echo ""

# Run tests based on mode
case $MODE in
    ui)
        npx playwright test --ui $TEST_FILE
        ;;
    debug)
        npx playwright test --debug $TEST_FILE
        ;;
    *)
        npx playwright test $TEST_FILE
        ;;
esac

# Check test results
if [ $? -eq 0 ]; then
    echo ""
    echo "✓ All tests passed!"
    echo ""
    echo "View test report:"
    echo "  npx playwright show-report"
else
    echo ""
    echo "❌ Some tests failed"
    echo ""
    echo "View test report:"
    echo "  npx playwright show-report"
    echo ""
    echo "View screenshots and videos in test-results/"
    exit 1
fi
