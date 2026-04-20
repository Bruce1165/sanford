# Flask App Corruption Prevention

## RULE: After ANY edit to app.py, ALWAYS validate

```bash
cd /Users/mac/NeoTrade2/backend
./validate_syntax.sh
```

This script checks:
1. Python syntax is valid
2. app.py can be imported without errors
3. Flask app initializes correctly

## If validation fails:
- Do NOT commit/restart Flask
- Fix the errors
- Run validation again

## Common Issues to Avoid:
1. **Missing imports** - Always check imports after adding new code
2. **Indentation errors** - Use consistent 4-space indentation
3. **Module-level code** - Don't run initialization at import time
4. **Broken logic** - Test API endpoints manually

## Flask Service Restart
After successful validation:
```bash
launchctl restart com.neotrade2.flask
```

Verify it's running:
```bash
lsof -i :8765
curl http://localhost:8765/api/health
```

## Last Backup
Broken version saved as: `app.py.broken_YYYYMMDD_HHMMSS`
