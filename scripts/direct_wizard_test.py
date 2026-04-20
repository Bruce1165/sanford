#!/usr/bin/env python3
"""Direct test importing from __init__"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))

try:
    # Import from __init__ explicitly
    from wizard import CoffeeCupWizard
    print("✓ Import successful (from __init__)")
    wizard = CoffeeCupWizard()
    print("✓ Wizard instantiated")
    print(f"  Config market: {wizard.config['market_context']['market']}")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("=" * 60)
print("✓ Coffee Cup Wizard class loads successfully")
print("=" * 60)
