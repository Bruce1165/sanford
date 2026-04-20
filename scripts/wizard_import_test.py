#!/usr/bin/env python3
"""Simplified wizard test - direct import"""

import sys
import os

# Add backend to path
backend_path = '/Users/mac/NeoTrade2/backend'
if backend_path not in sys.path:
    sys.path.append(backend_path)

from coffee_cup_wizard import CoffeeCupWizard

print("=" * 60)
print("✓ Wizard class loads successfully")
print(f"Config market: {wizard.config['market_context']['market']}")
print("=" * 60)
