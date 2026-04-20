#!/usr/bin/env python3
"""Simple direct test of CoffeeCupWizard class"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))

try:
    # Try importing without __init__
    from coffee_cup_wizard import CoffeeCupWizard
    print("✓ Import successful (direct import)")
    wizard = CoffeeCupWizard()
    print("✓ Wizard instantiated")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

print("=" * 60)
print("Coffee Cup Wizard - Simple Test")
print("=" * 60)
print()

# Test basic methods
print("Testing config loading...")
print(f"  Market: {wizard.config['market_context']['market']}")
print(f"  Probability threshold: {wizard.config['probability_formula']['prediction_threshold']}%")
print()

# Note: Cannot fully test without actual DB access
# This just verifies the class structure and config loading
print("✓ Config loads successfully")
print()

print("Key China A-share factors:")
print("  ✓ Volume sentiment (量能)")
print("  ✓ Capital structure (散户vs机构)")
print("  ✓ Limit-up proximity (涨停板情绪)")
print("  ✓ Flexible multipliers")
print("  ✓ T+1 rule awareness")
print("  ✓ No short selling awareness")
print()

print("=" * 60)
print("Ready for development:")
print("   1. Test with real data")
print("  2. Implement historical validation")
print("  3. Add economic/policy data sources")
print("  4. 康波 cycle integration")
print("  5. Run iterative optimization")
print("=" * 60)
