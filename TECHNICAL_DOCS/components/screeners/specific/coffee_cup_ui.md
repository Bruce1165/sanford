# Coffee Cup Wizard - Implementation Plan

**Project**: Coffee Cup Pattern Formation Prediction
**Type**: Predictive Model / Algorithm (Not Traditional Screener)
**Created**: 2026-04-09
**Status**: Planning Phase

---

## 🎯 Mission Objective

Build a **predictive algorithm** that:
1. Detects stocks in the process of forming coffee cup patterns
2. Outputs probability score (≥50% = predicted to complete)
3. Works across all 14 screeners with configurable parameters
4. Uses historical data for iterative optimization
5. Provides research-grade insights for high-probability stocks

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                  Coffee Cup Wizard                      │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Component Detection Engine                    │ │
│  │  ┌─────┐  ┌─────┐  ┌─────┐     │ │
│  │  │ Handle│→│Left  │→│Bottom│→...  │ │
│  │  │ Detect│  │ Wall  │  │Detect│     │ │
│  │  └─────┘  └─────┘  └─────┘     │ │
│  └────────────────────────────────────────────────────┘ │
│                        ↓                              │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Completion & Probability Calculator          │ │
│  │  - % formed (0-100%)                    │ │
│  │  - Confidence score                      │ │
│  │  - Target completion timeframe              │ │
│  └────────────────────────────────────────────────────┘ │
│                        ↓                              │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Historical Validator                      │ │
│  │  - Backtest accuracy                        │ │
│  │  - Optimize probability formula               │ │
│  │  - Iterative improvement                    │ │
│  └────────────────────────────────────────────────────┘ │
│                        ↓                              │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Output Generator                           │ │
│  │  - Ranked stock list (descending prob)       │ │
│  │  - JSON export                             │ │
│  │  - Dashboard integration                    │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 Phase 1: Infrastructure Setup (1-2 days)

### Task 1.1: Create Configuration System
**File**: `config/wizard_params.json`

```json
{
  "coffee_cup_wizard": {
    "version": "v1.0",
    "last_updated": "2026-04-09T00:00:00",
    "component_params": {
      "handle": {
        "period_min": 5,
        "period_max": 21,
        "shape_requirement": "upward",
        "min_height_pct": 5
      },
      "left_wall": {
        "period_min": 14,
        "period_max": 60,
        "decline_pct_min": 10,
        "decline_pct_max": 40
      },
      "bottom": {
        "period_min": 10,
        "period_max": 45,
        "flatness_threshold": 0.15,
        "max_decline_pct": 3,
        "min_consolidation_days": 5
      },
      "right_wall": {
        "period_min": 14,
        "period_max": 60,
        "ascent_pct_min": 20,
        "ascent_pct_max": 80,
        "volume_pattern": "gradual_increase"
      },
      "cup_edge": {
        "period_min": 5,
        "period_max": 21,
        "height_match_pct": 95,
        "max_drop_pct": 8,
        "min_drop_pct": 2,
        "volume_shrink": true
      }
    },
    "probability_params": {
      "base_formula": "linear",
      "adjustment_factors": [
        {
          "name": "handle_quality",
          "enabled": true,
          "weight": 0.1,
          "criteria": "sharp_vs_rounded"
        },
        {
          "name": "bottom_depth",
          "enabled": true,
          "weight": 0.15,
          "criteria": "ideal_depth_12_35_pct"
        },
        {
          "name": "trend_alignment",
          "enabled": true,
          "weight": 0.1,
          "criteria": "ma_alignment"
        },
        {
          "name": "volume_pattern",
          "enabled": true,
          "weight": 0.1,
          "criteria": "right_wall_volume_increase"
        },
        {
          "name": "rs_strength",
          "enabled": true,
          "weight": 0.1,
          "criteria": "rs_ge_85"
        }
      ],
      "prediction_threshold": 50
    },
    "validation": {
      "historical_test_start_date": "2024-09-01",
      "historical_test_end_date": "2026-03-31",
      "accuracy_target": 0.65,
      "min_validation_samples": 100
    }
  }
}
```

### Task 1.2: Create Wizard Core Module
**File**: `backend/coffee_cup_wizard.py`

```python
"""
Coffee Cup Wizard - Predictive Model for Coffee Cup Formation Detection

NOT a traditional screener. This module:
- Detects in-progress coffee cup patterns
- Calculates formation probability
- Provides research-grade predictions
- Supports iterative optimization via historical validation
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
from typing import Dict, List, Tuple, Optional

class CoffeeCupWizard:
    """Main wizard class for coffee cup prediction"""

    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.db_path = Path('data/stock_data.db')

    def _load_config(self, config_path: str = None) -> Dict:
        """Load wizard configuration from JSON"""
        if config_path is None:
            config_path = Path(__file__).parent.parent / 'config' / 'wizard_params.json'
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)['coffee_cup_wizard']

    def analyze_stock(self, code: str, end_date: str = None) -> Dict:
        """
        Analyze a single stock for coffee cup formation progress

        Returns:
        {
            'code': '600XXX',
            'name': '股票名称',
            'completion_pct': 65,
            'components': {
                'handle': {'detected': True, 'quality': 0.8},
                'left_wall': {'detected': True, 'quality': 0.9},
                'bottom': {'detected': True, 'quality': 0.7},
                'right_wall': {'detected': False, 'quality': 0},
                'cup_edge': {'detected': False, 'quality': 0}
            },
            'stage': 'right_wall_forming',
            'probability': 68,
            'target_days': 10,
            'signals': [...]
        }
        """
        pass

    def batch_analyze(self, codes: List[str], end_date: str = None) -> List[Dict]:
        """Analyze multiple stocks in batch"""
        pass

    def get_top_predictions(self, limit: int = 50) -> List[Dict]:
        """Get top N predictions sorted by probability"""
        pass
```

### Task 1.3: Create Component Detection Classes

```python
# backend/wizard/components/handle_detector.py
class HandleDetector:
    """Detect cup handle formation"""

    def detect(self, df: pd.DataFrame, params: Dict) -> Dict:
        """
        Returns:
        {
            'detected': bool,
            'quality': float (0-1),
            'start_idx': int,
            'end_idx': int,
            'high_price': float,
            'low_price': float,
            'period_days': int
        }
        """
        pass

# backend/wizard/components/left_wall_detector.py
class LeftWallDetector:
    """Detect left wall (high to low decline)"""

    def detect(self, df: pd.DataFrame, params: Dict) -> Dict:
        pass

# backend/wizard/components/bottom_detector.py
class BottomDetector:
    """Detect cup bottom (consolidation)"""

    def detect(self, df: pd.DataFrame, params: Dict) -> Dict:
        pass

# backend/wizard/components/right_wall_detector.py
class RightWallDetector:
    """Detect right wall (low to high ascent)"""

    def detect(self, df: pd.DataFrame, params: Dict) -> Dict:
        pass

# backend/wizard/components/cup_edge_detector.py
class CupEdgeDetector:
    """Detect cup edge formation"""

    def detect(self, df: pd.DataFrame, handle_info: Dict, params: Dict) -> Dict:
        pass
```

### Task 1.4: Create Probability Calculator

```python
# backend/wizard/probability_calculator.py

class ProbabilityCalculator:
    """Calculate formation probability and confidence"""

    def calculate_completion_pct(self, components: Dict) -> float:
        """
        Calculate 0-100% completion based on detected components

        Formula: (components_detected / total_components) * 100
        """
        pass

    def calculate_probability(self, completion_pct: float, factors: Dict) -> float:
        """
        Apply adjustment factors to base completion %

        Formula:
        Probability = Completion % × Π(1 + adjustment_factor × weight)

        Factors include:
        - Handle quality
        - Bottom depth (ideal 12-35%)
        - Trend alignment (MA positions)
        - Volume pattern
        - RS strength
        """
        pass

    def estimate_target_days(self, completion_pct: float) -> int:
        """Estimate days to complete based on current progress"""
        pass
```

### Task 1.5: Create Historical Validator

```python
# backend/wizard/historical_validator.py

class HistoricalValidator:
    """Validate predictions against historical outcomes"""

    def validate(self, predictions: List[Dict], actual_outcomes: Dict) -> Dict:
        """
        Compare predictions vs actual outcomes

        Returns:
        {
            'accuracy': float,
            'precision': float,
            'recall': float,
            'false_positive_rate': float,
            'false_negative_rate': float,
            'by_probability_threshold': {
                '60': {'accuracy': ..., 'precision': ...},
                '50': {'accuracy': ..., 'precision': ...},
                ...
            }
        }
        """
        pass

    def optimize_formula(self, validation_results: Dict) -> Dict:
        """
        Iterate to find optimal probability formula

        Test variations:
        - Linear vs logarithmic vs exponential
        - Different factor weights
        - Different factor combinations

        Returns: best parameters
        """
        pass
```

**Verification Standard**:
- [ ] Config file created with all parameters
- [ ] Core wizard module skeleton created
- [ ] All 5 component detector classes created
- [ ] Probability calculator created
- [ ] Historical validator created
- [ ] All modules can be imported without errors

---

## 📊 Phase 2: Component Detection Implementation (3-4 days)

### Task 2.1: Handle Detection Logic

**Algorithm**:
```python
def detect_handle(df: pd.DataFrame, period_range: Tuple[int, int]) -> Dict:
    """
    Detect handle: Low → High over X days, upward shape
    """
    # 1. Find all local low points
    local_lows = df[df['low'] == df['low'].rolling(window=5, center=True).min()]

    # 2. For each low, check if high point follows within period_range
    for low_idx in local_lows.index:
        # Check next period_range days for a high
        high_candidate = df.loc[low_idx:low_idx + period_range[1], 'high'].max()

        # Check if high > low by min_height_pct
        if high_candidate / df.loc[low_idx, 'low'] - 1 >= params['min_height_pct']:
            # Validate shape: gradual upward (not V-sharp)
            price_curve = df.loc[low_idx:low_idx + period_range[1], 'close']

            # Check slope consistency (should be mostly positive)
            slopes = price_curve.diff()
            positive_slope_pct = (slopes > 0).mean()

            if positive_slope_pct >= 0.7:  # 70% of moves are upward
                return {
                    'detected': True,
                    'start_idx': low_idx,
                    'end_idx': high_idx,
                    'period_days': (high_idx - low_idx),
                    'quality': positive_slope_pct  # 0-1, higher = better handle
                }

    return {'detected': False, 'quality': 0}
```

### Task 2.2: Left Wall Detection Logic

```python
def detect_left_wall(df: pd.DataFrame, handle_end_idx: int, period_range: Tuple[int, int], decline_range: Tuple[float, float]) -> Dict:
    """
    Detect left wall: High → Low decline over X days
    Starting from handle end (high point)
    """
    # 1. Check period_range days BEFORE handle
    wall_start = max(0, handle_end_idx - period_range[1])
    wall_end = handle_end_idx

    wall_data = df.loc[wall_start:wall_end]

    # 2. Find high and low in this period
    wall_high = wall_data['high'].max()
    wall_low = wall_data['low'].min()

    # 3. Calculate decline %
    decline_pct = (wall_high - wall_low) / wall_high

    # 4. Check if in acceptable range
    if decline_range[0] <= decline_pct <= decline_range[1]:
        # 5. Check shape: Should be downward (not flat, not erratic)
        close_prices = wall_data['close']
        trend_slope = np.polyfit(range(len(close_prices)), close_prices, 1)[0]

        if trend_slope < 0:  # Negative slope = downward
            return {
                'detected': True,
                'start_idx': wall_start,
                'end_idx': wall_end,
                'period_days': (wall_end - wall_start),
                'decline_pct': decline_pct,
                'quality': min(1.0, abs(trend_slope) / abs(wall_high - wall_low))  # Steeper = better
            }

    return {'detected': False, 'quality': 0}
```

### Task 2.3: Bottom Detection Logic

```python
def detect_bottom(df: pd.DataFrame, left_wall_end_idx: int, period_range: Tuple[int, int], flatness_threshold: float) -> Dict:
    """
    Detect bottom: Low consolidation with minimal movement
    Starting from left wall end (low point)
    """
    # 1. Check period_range days AFTER left wall
    bottom_start = left_wall_end_idx
    bottom_end = min(len(df) - 1, bottom_start + period_range[1])

    bottom_data = df.loc[bottom_start:bottom_end]

    # 2. Check for consolidation (flat prices)
    # Calculate price range
    price_range = (bottom_data['high'].max() - bottom_data['low'].min()) / bottom_data['low'].min()

    # 3. Check if flatness threshold met
    if price_range <= flatness_threshold:
        # 4. Check for min consolidation days
        if (bottom_end - bottom_start) >= params['min_consolidation_days']:

            # 5. Check bottom depth relative to cup handle high
            handle_high = df.loc[max(0, bottom_start - 50):bottom_start, 'high'].max()
            bottom_low = bottom_data['low'].min()
            depth_pct = (handle_high - bottom_low) / handle_high

            return {
                'detected': True,
                'start_idx': bottom_start,
                'end_idx': bottom_end,
                'period_days': (bottom_end - bottom_start),
                'depth_pct': depth_pct,
                'flatness': (1 - price_range / flatness_threshold),  # 0-1, flatter = better
                'quality': (1 - price_range / flatness_threshold) * 0.5 + self._check_ideal_depth(depth_pct) * 0.5
            }

    return {'detected': False, 'quality': 0}

def _check_ideal_depth(depth_pct: float) -> float:
    """Check if depth is in ideal 12-35% range"""
    if 0.12 <= depth_pct <= 0.35:
        return 1.0
    elif depth_pct < 0.12:
        return depth_pct / 0.12  # Below ideal, proportional penalty
    else:  # depth_pct > 0.35
        return max(0, 1 - (depth_pct - 0.35) / 0.35)  # Above ideal, proportional penalty
```

### Task 2.4: Right Wall Detection Logic

```python
def detect_right_wall(df: pd.DataFrame, bottom_end_idx: int, period_range: Tuple[int, int], ascent_range: Tuple[float, float]) -> Dict:
    """
    Detect right wall: Low → High ascent over X days
    Starting from bottom end (low point or near low)
    """
    # 1. Check period_range days AFTER bottom
    wall_start = bottom_end_idx
    wall_end = min(len(df) - 1, wall_start + period_range[1])

    wall_data = df.loc[wall_start:wall_end]

    # 2. Find low and high in this period
    wall_low = wall_data['low'].min()
    wall_high = wall_data['high'].max()

    # 3. Calculate ascent %
    ascent_pct = (wall_high - wall_low) / wall_low

    # 4. Check if in acceptable range
    if ascent_range[0] <= ascent_pct <= ascent_range[1]:
        # 5. Check shape: Should be upward (gradual)
        close_prices = wall_data['close']
        trend_slope = np.polyfit(range(len(close_prices)), close_prices, 1)[0]

        if trend_slope > 0:  # Positive slope = upward
            # 6. Check volume pattern (gradual increase)
            volume_trend = wall_data['volume'].pct_change().mean()

            return {
                'detected': True,
                'start_idx': wall_start,
                'end_idx': wall_end,
                'period_days': (wall_end - wall_start),
                'ascent_pct': ascent_pct,
                'volume_trend': volume_trend,
                'quality': min(1.0, trend_slope / abs(ascent_pct)) * 0.7 + min(1.0, volume_trend / 0.01) * 0.3
            }

    return {'detected': False, 'quality': 0}
```

### Task 2.5: Cup Edge Detection Logic

```python
def detect_cup_edge(df: pd.DataFrame, right_wall_end_idx: int, handle_info: Dict, params: Dict) -> Dict:
    """
    Detect cup edge: Same high as handle, slight dip, then rise to same level
    Starting from right wall end (high point)
    """
    # 1. Get handle high price
    handle_high_price = handle_info['high_price']

    # 2. Check next period_range days for edge formation
    edge_start = right_wall_end_idx
    edge_end = min(len(df) - 1, edge_start + params['period_max'])

    edge_data = df.loc[edge_start:edge_end]

    # 3. Find a point close to handle_high_price (within match_pct)
    match_range_low = handle_high_price * params['height_match_pct']
    match_range_high = handle_high_price / params['height_match_pct']

    candidates = edge_data[
        (edge_data['high'] >= match_range_low) &
        (edge_data['high'] <= match_range_high)
    ]

    if len(candidates) > 0:
        # Take the first candidate
        edge_high_idx = candidates.index[0]

        # 4. Check if there was a dip before reaching this level
        dip_data = df.loc[edge_start:edge_high_idx]
        if len(dip_data) > params['period_min']:
            max_dip_pct = (edge_data.loc[edge_start, 'high'] - dip_data['low'].min()) / edge_data.loc[edge_start, 'high']

            # Check if dip is in acceptable range
            if params['min_drop_pct'] <= max_dip_pct <= params['max_drop_pct']:
                # 5. Check volume (should shrink compared to right wall)
                right_wall_vol = df.loc[edge_start-5:right_wall_end_idx, 'volume'].mean()
                edge_vol = df.loc[edge_start:edge_high_idx, 'volume'].mean()

                vol_shrink = edge_vol / right_wall_vol if right_wall_vol > 0 else 1.0

                # 6. Consolidate edge area
                edge_consolidation_start = edge_high_idx
                edge_consolidation_end = min(len(df) - 1, edge_consolidation_start + 10)
                edge_consolidation = df.loc[edge_consolidation_start:edge_consolidation_end]

                # Check consolidation range (only down movement)
                max_rise_in_consolidation = edge_consolidation['high'].max() - edge_consolidation['close'].iloc[0]
                max_drop_in_consolidation = edge_consolidation['close'].iloc[0] - edge_consolidation['low'].min()

                if max_rise_in_consolidation <= params['max_rise_pct'] * edge_consolidation['close'].iloc[0]:
                    return {
                        'detected': True,
                        'start_idx': edge_start,
                        'end_idx': edge_consolidation_end,
                        'period_days': (edge_consolidation_end - edge_start),
                        'max_dip_pct': max_dip_pct,
                        'vol_shrink_pct': vol_shrink,
                        'quality': (vol_shrink if vol_shrink < 1 else 0) * 0.5 + (1 - max_dip_pct / params['max_drop_pct']) * 0.5
                    }

    return {'detected': False, 'quality': 0}
```

**Verification Standard**:
- [ ] Handle detection identifies valid handles
- [ ] Left wall detection shows downward decline
- [ ] Bottom detection shows consolidation
- [ ] Right wall detection shows upward ascent
- [ ] Cup edge detection shows dip and return
- [ ] All quality scores calculated correctly
- [ ] Edge cases handled (insufficient data, invalid patterns)

---

## 🎲 Phase 3: Probability & Validation Implementation (2-3 days)

### Task 3.1: Base Probability Formula

```python
def calculate_base_probability(completion_pct: float) -> float:
    """
    Initial probability based solely on component completion

    Options (iteratively tested):
    1. Linear: Probability = Completion %
    2. Logarithmic: Probability = 100 × log(1 + Completion %) / log(101)
    3. Exponential: Probability = 100 × (1 - e^(-Completion % / 30))
    """
    # Start with linear (Option 1)
    return completion_pct
```

### Task 3.2: Adjustment Factor Application

```python
def apply_adjustment_factors(base_prob: float, components: Dict, params: Dict) -> float:
    """
    Apply quality adjustments to base probability

    Formula:
    Adjusted_Probability = Base_Probability × Π(1 + Factor × Weight)

    Where each Factor is in range [-0.1, 0.1] for quality adjustments
    """
    adjusted_prob = base_prob

    for factor_config in params['probability_params']['adjustment_factors']:
        if not factor_config['enabled']:
            continue

        factor_name = factor_config['name']
        weight = factor_config['weight']

        # Calculate factor value based on component quality
        factor_value = 0  # Will calculate from components

        if factor_name == 'handle_quality':
            factor_value = components['handle']['quality'] - 0.5  # Center around 0
        elif factor_name == 'bottom_depth':
            factor_value = components['bottom']['quality'] - 0.5
        elif factor_name == 'trend_alignment':
            # Calculate MA alignment
            factor_value = 0  # Need to implement MA check
        elif factor_name == 'volume_pattern':
            factor_value = components['right_wall']['quality'] - 0.5
        elif factor_name == 'rs_strength':
            factor_value = 0  # Need to calculate RS score

        # Apply adjustment
        adjusted_prob = adjusted_prob * (1 + factor_value * weight)

    # Clamp to 0-100
    return max(0, min(100, adjusted_prob))
```

### Task 3.3: Target Days Estimation

```python
def estimate_target_days(completion_pct: float, params: Dict) -> int:
    """
    Estimate days to complete formation based on current progress

    Simple heuristic:
    - Handle + Left Wall + Bottom + Right Wall = ~80% of total time
    - Cup Edge = ~20% of total time
    """
    if completion_pct >= 100:
        return 0

    # Average total formation time from historical data or parameter
    avg_total_days = params.get('avg_formation_days', 60)

    remaining_pct = (100 - completion_pct) / 100

    # Estimate days to complete
    if completion_pct < 80:  # Before cup edge
        # Cup edge takes longer proportionally
        target_days = int(avg_total_days * remaining_pct * 1.5)
    else:  # Cup edge stage (faster)
        target_days = int(avg_total_days * remaining_pct * 0.5)

    return target_days
```

### Task 3.4: Historical Validation Implementation

```python
def validate_predictions_historically(wizard: CoffeeCupWizard, test_dates: List[str]) -> Dict:
    """
    Run wizard on historical dates where we know outcomes

    For each test date:
    1. Run wizard with data BEFORE test date
    2. Get top N predictions
    3. Check if stocks ACTUALLY formed coffee cup within target days
    4. Calculate accuracy metrics

    Returns comprehensive validation report
    """
    results = {
        'date': [],
        'predictions_made': [],
        'correct': [],
        'incorrect': [],
        'by_probability_threshold': {}
    }

    for test_date in test_dates:
        # Get data before test date (no cheating!)
        cutoff_date = datetime.strptime(test_date, '%Y-%m-%d')

        # Run wizard
        predictions = wizard.batch_analyze(all_stock_codes, end_date=test_date)
        top_predictions = [p for p in predictions if p['probability'] >= 50][:20]

        # Check outcomes
        correct_count = 0
        for pred in top_predictions:
            code = pred['code']
            # Check if this stock formed coffee cup within target_days
            actual_outcome = check_actual_outcome(code, test_date, pred['target_days'])
            results['correct'].append(actual_outcome)
            if actual_outcome:
                correct_count += 1

        accuracy = correct_count / len(top_predictions)
        results['date'].append(test_date)
        results['predictions_made'].append(len(top_predictions))
        results['accuracy'].append(accuracy)

    # Calculate overall metrics
    overall_accuracy = sum(results['accuracy']) / len(results['accuracy'])

    return {
        'overall_accuracy': overall_accuracy,
        'date_breakdown': results,
        'meets_target': overall_accuracy >= params['validation']['accuracy_target']
    }
```

**Verification Standard**:
- [ ] Base probability calculates correctly (0-100%)
- [ ] Adjustment factors modify probability reasonably
- [ ] Target days estimation is plausible
- [ ] Historical validation runs without data leakage
- [ ] Accuracy metrics calculated correctly
- [ ] Results can be saved for iterative optimization

---

## 🔄 Phase 4: Iterative Optimization (ongoing)

### Task 4.1: Formula Iteration Strategy

**Week 1**: Test all 3 base formulas (linear, log, exp)
**Week 2**: Adjust factor weights systematically
**Week 3**: Test factor combinations (enable/disable)
**Week 4**: Fine-tune component detection thresholds
**Week 5**: Evaluate and select best configuration

### Task 4.2: Optimization Automation

```python
# backend/wizard/optimizer.py

class FormulaOptimizer:
    """Automatically optimize probability formula"""

    def __init__(self, validator: HistoricalValidator):
        self.validator = validator
        self.best_config = None
        self.best_accuracy = 0

    def run_optimization(self, iterations: int = 100) -> Dict:
        """
        Systematically test different configurations

        Returns best configuration found
        """
        pass

    def optimize_base_formula(self):
        """Test linear vs logarithmic vs exponential"""
        pass

    def optimize_factor_weights(self):
        """Test different weight combinations for adjustment factors"""
        pass

    def optimize_component_thresholds(self):
        """Test different detection thresholds for each component"""
        pass
```

### Task 4.3: Results Tracking

Create `data/wizard_optimization_log.json`:

```json
{
  "runs": [
    {
      "date": "2026-04-09",
      "config": {...},
      "accuracy": 0.72,
      "precision": 0.68,
      "recall": 0.75,
      "top_predictions": {
        "pct_70": 0.85,
        "pct_60": 0.78,
        "pct_50": 0.72,
        "pct_40": 0.65
      }
    }
  ],
  "best_config": {...},
  "best_accuracy": 0.72
}
```

**Verification Standard**:
- [ ] Optimization runs generate actionable insights
- [ ] Configuration improvements are tracked
- [ ] Best configuration is automatically selected
- [ ] Results can be visualized for manual review

---

## 📤 Phase 5: Output & Integration (1-2 days)

### Task 5.1: Create CLI Interface

```python
# scripts/run_coffee_cup_wizard.py

import argparse
from backend.coffee_cup_wizard import CoffeeCupWizard

def main():
    parser = argparse.ArgumentParser(description='Coffee Cup Wizard - Predictive Pattern Detection')
    parser.add_argument('--date', type=str, help='Analysis date (YYYY-MM-DD)')
    parser.add_argument('--validate', action='store_true', help='Run historical validation')
    parser.add_argument('--optimize', action='store_true', help='Run optimization iterations')
    parser.add_argument('--output', type=str, default='data/wizard_output.json', help='Output file path')
    parser.add_argument('--limit', type=int, default=50, help='Number of top predictions')
    args = parser.parse_args()

    wizard = CoffeeCupWizard()

    if args.validate:
        # Run historical validation
        from backend.wizard.historical_validator import HistoricalValidator
        validator = HistoricalValidator()
        results = validator.validate_historical(wizard)
        print(f"Validation Accuracy: {results['overall_accuracy']:.2%}")
    elif args.optimize:
        # Run optimization
        from backend.wizard.optimizer import FormulaOptimizer
        optimizer = FormulaOptimizer(validator)
        best_config = optimizer.run_optimization(iterations=50)
        print(f"Best Accuracy: {best_config['accuracy']:.2%}")
    else:
        # Run prediction
        predictions = wizard.batch_analyze(all_stock_codes, args.date)
        top_predictions = [p for p in predictions if p['probability'] >= 50][:args.limit]

        # Save to JSON
        import json
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'analysis_date': args.date,
                'total_analyzed': len(all_stock_codes),
                'predictions': top_predictions,
                'count': len(top_predictions)
            }, f, ensure_ascii=False, indent=2)

        print(f"Generated {len(top_predictions)} predictions")
        print(f"Saved to {args.output}")

if __name__ == '__main__':
    main()
```

### Task 5.2: Dashboard Integration

**Add to `backend/app.py`**:

```python
# Coffee Cup Wizard endpoints

@app.route('/api/wizard/analyze', methods=['POST'])
@auth_required
def wizard_analyze():
    """
    Run Coffee Cup Wizard analysis on all stocks
    """
    from backend.coffee_cup_wizard import CoffeeCupWizard

    wizard = CoffeeCupWizard()
    predictions = wizard.batch_analyze(all_stock_codes)

    top_predictions = [p for p in predictions if p['probability'] >= 50][:100]

    return jsonify({
        'success': True,
        'predictions': top_predictions,
        'count': len(top_predictions)
    })

@app.route('/api/wizard/validate', methods=['GET'])
@auth_required
def wizard_validate():
    """
    Get historical validation results
    """
    # Read validation log
    validation_log = read_validation_log()

    return jsonify({
        'success': True,
        'validation_log': validation_log
    })

@app.route('/api/wizard/optimize', methods=['POST'])
@auth_required
def wizard_optimize():
    """
    Trigger optimization run
    """
    # Trigger async optimization
    run_optimization_async()

    return jsonify({
        'success': True,
        'message': 'Optimization started'
    })
```

### Task 5.3: Frontend Wizard Page

**Create `frontend/src/pages/CoffeeCupWizard.tsx`**:

```typescript
// Coffee Cup Wizard page component
import React, { useState, useEffect } from 'react';
import { Table, Button, Card, Statistic, Progress, Tag } from 'antd';
import axios from 'axios';

interface WizardPrediction {
    code: string;
    name: string;
    completion_pct: number;
    components: any;
    stage: string;
    probability: number;
    target_days: number;
}

export const CoffeeCupWizard: React.FC = () => {
    const [predictions, setPredictions] = useState<WizardPrediction[]>([]);
    const [loading, setLoading] = useState(false);
    const [validationResults, setValidationResults] = useState<any>(null);

    const runWizard = async () => {
        setLoading(true);
        const response = await axios.post('/api/wizard/analyze');
        setPredictions(response.data.predictions);
        setLoading(false);
    };

    return (
        <div className="wizard-page">
            <h1>Coffee Cup Wizard - Predictive Pattern Detection</h1>

            <Card>
                <Statistic
                    title="High Probability Stocks (≥50%)"
                    value={predictions.length}
                />
                <Button
                    type="primary"
                    onClick={runWizard}
                    loading={loading}
                >
                    Run Wizard Analysis
                </Button>
            </Card>

            <Table
                dataSource={predictions}
                columns={[
                    {
                        title: 'Code',
                        dataIndex: 'code',
                        key: 'code',
                        sorter: (a, b) => b.probability - a.probability,
                        defaultSortOrder: 'descend'
                    },
                    {
                        title: 'Probability',
                        dataIndex: 'probability',
                        key: 'probability',
                        render: (prob: number) => (
                            <Progress
                                percent={prob}
                                status="active"
                                size="small"
                            />
                        )
                    },
                    {
                        title: 'Stage',
                        dataIndex: 'stage',
                        key: 'stage',
                        render: (stage: string) => (
                            <Tag color={getStageColor(stage)}>{stage}</Tag>
                        )
                    },
                    {
                        title: 'Components',
                        key: 'components',
                        render: (record: WizardPrediction) => (
                            <div>
                                {Object.entries(record.components).map(([key, value]: [string, any]) => (
                                    <Tag color={value.detected ? 'green' : 'default'}>
                                        {key}: {value.detected ? '✓' : '✗'}
                                    </Tag>
                                ))}
                            </div>
                        )
                    },
                    {
                        title: 'Target Days',
                        dataIndex: 'target_days',
                        key: 'target_days'
                    }
                ]}
                pagination={{ pageSize: 20 }}
            />
        </div>
    );
};
```

**Verification Standard**:
- [ ] CLI interface works with all options
- [ ] Wizard can analyze all 4,663 stocks in reasonable time
- [ ] API endpoints integrated into Flask
- [ ] Frontend page displays predictions clearly
- [ ] Components are visually indicated
- [ ] Sorting by probability works correctly

---

## ⚠️ Risk Mitigation

### 1. False Positives

**Risk**: Predicting stocks that don't actually form the pattern

**Mitigation**:
- Conservative probability calculation
- Minimum 3 components required before ≥50% prediction
- Historical validation to calibrate thresholds
- Confidence score separate from probability

### 2. Data Limitations

**Risk**: Insufficient history for some stocks

**Mitigation**:
- Skip stocks with < 120 days of data
- Flag in output: "insufficient_data": true
- Allow configurable minimum history parameter

### 3. Parameter Overfitting

**Risk**: Optimization overfits to specific time period

**Mitigation**:
- Use time-series cross-validation
- Test on multiple historical periods
- Regularization in formula
- Periodic re-validation

### 4. Computational Performance

**Risk**: Analyzing 4,663 stocks is slow

**Mitigation**:
- Batch processing with pandas vectorization
- Early termination for obvious non-candidates
- Cache component detection results
- Parallel processing where possible

---

## 📊 Success Metrics

- [ ] All 5 component detectors implemented and tested
- [ ] Probability calculator with adjustment factors
- [ ] Historical validation system working
- [ ] Optimization framework implemented
- [ ] CLI interface functional
- [ ] Dashboard integration complete
- [ ] Can analyze all 4,663 stocks in < 30 minutes
- [ ] Initial validation accuracy ≥ 60%
- [ ] Top 50 predictions provide actionable research value

---

## 🗓 Timeline

| Phase | Duration | Dependencies |
|--------|-----------|--------------|
| Phase 1: Infrastructure | 1-2 days | None |
| Phase 2: Component Detection | 3-4 days | Phase 1 |
| Phase 3: Probability & Validation | 2-3 days | Phase 2 |
| Phase 4: Iterative Optimization | Ongoing (5 weeks) | Phase 3 |
| Phase 5: Output & Integration | 1-2 days | Phase 3 |

**Total Initial Implementation**: 7-11 days
**Ongoing Optimization**: 5+ weeks

---

## 📝 Next Steps After This Plan

1. User reviews and approves plan
2. Begin Phase 1 implementation
3. Create detailed task breakdown for each phase
4. Start with Handle Detection (most critical component)
5. Iterate through all components with testing at each step

---

**Document Version**: 1.0
**Last Updated**: 2026-04-09
**Status**: Ready for Implementation
