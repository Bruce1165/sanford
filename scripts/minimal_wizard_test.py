#!/usr/bin/env python3

import sys
import os

backend_path = '/Users/mac/NeoTrade2/backend'
if backend_path not in sys.path:
    sys.path.append(backend_path)

from coffee_cup_wizard import CoffeeCupWizard
print("✓ Wizard imported successfully")
