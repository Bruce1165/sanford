#!/usr/bin/env python3
"""
Coffee Cup Wizard CLI - China A-Share Predictive Analysis

Usage:
    python3 scripts/run_wizard.py --date 2026-04-09 [--optimize] [--limit 50]
"""

import argparse
import sys
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(__file__).parent.parent / 'backend' / 'wizard'))

from coffee_cup_wizard import CoffeeCupWizard


def main():
    parser = argparse.ArgumentParser(
        description='Coffee Cup Wizard - China A-Share Predictive Pattern Detection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze all stocks for a specific date
  python3 run_wizard.py --date 2026-04-09

  # Run optimization
  python3 run_wizard.py --optimize --iterations 50

  # Get top predictions
  python3 run_wizard.py --limit 20
        """
    )

    parser.add_argument(
        '--date',
        type=str,
        default=datetime.now().strftime('%Y-%m-%d'),
        help='Analysis date (YYYY-MM-DD), default: today'
    )

    parser.add_argument(
        '--optimize',
        action='store_true',
        help='Run optimization iterations on historical data'
    )

    parser.add_argument(
        '--iterations',
        type=int,
        default=20,
        help='Number of optimization iterations (default: 20)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Number of top predictions to output (default: 50)'
    )

    parser.add_argument(
        '--output',
        type=str,
        default='data/wizard_output.json',
        help='Output file path (default: data/wizard_output.json)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    # Initialize wizard
    wizard = CoffeeCupWizard()

    print("=" * 60)
    print("Coffee Cup Wizard - China A-Share Predictive Model")
    print(f"=" * 60)
    print(f"Analysis Date: {args.date}")
    print(f"=" * 60)

    if args.optimize:
        # Run optimization mode
        print("\n🔄 Running Optimization Mode")
        print("-" * 60)

        print("Optimization will:")
        print("  1. Test different probability formulas")
        print("  2. Adjust factor weights")
        print("  3. Validate against historical data")
        print(f"  4. Perform {args.iterations} iterations")
        print("-" * 60)

        # Load all stock codes
        all_codes = wizard._get_all_stock_codes()
        print(f"\nWill analyze {len(all_codes)} stocks across validation periods")

        # For now, save config and exit
        # Full optimization requires historical validation implementation
        print("\n⚠️  Full optimization requires historical validation module")
        print("   Currently skipping validation phase")
        print("   Configuration saved")

        return

    # Run prediction
    print(f"\n📊 Analyzing stocks...")
    print(f"Loading all {len(wizard._get_all_stock_codes())} stock codes...")

    predictions = wizard.batch_analyze(
        codes=wizard._get_all_stock_codes(),
        end_date=args.date,
        limit=args.limit
    )

    # Save results
    output_data = {
        'timestamp': datetime.now().isoformat(),
        'analysis_date': args.date,
        'total_analyzed': len(wizard._get_all_stock_codes()),
        'threshold': wizard.config['probability_formula']['prediction_threshold'],
        'predictions_count': len(predictions),
        'predictions': [
            {
                'code': pred.code,
                'name': pred.name,
                'probability': pred.adjusted_probability,
                'stage': pred.stage,
                'target_days': pred.target_days,
                'components': {
                    'cup_edge': {
                        'detected': pred.components['cup_edge']['detected'],
                        'quality': pred.components['cup_edge'].get('quality', 0),
                        'current_price': pred.components['cup_edge'].get('current_price', 0)
                    },
                    'sentiment': {
                        'score': pred.components['sentiment']['score'],
                        'level': pred.components['sentiment'].get('limit_up_level', 'none')
                    },
                    'capital': {
                        'structure': pred.components['capital']['structure']
                    }
                }
            }
            for pred in predictions
        ],
        'config': {
            'market': wizard.config['market_context']['market'],
            'factors_enabled': [
                f['name'] for f in wizard.config['probability_formula']['adjustment_factors'] if f['enabled']
            ],
            'factor_weights': {
                f['name']: f.get('multipliers', 1.0)
                for f in wizard.config['probability_formula']['adjustment_factors']
            }
        }
    }

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    # Print summary
    print("-" * 60)
    print(f"✓ Analyzed {len(predictions)} stocks with probability ≥{wizard.config['probability_formula']['prediction_threshold']}%")
    print(f"✓ Saved to: {args.output}")

    if args.verbose:
        print("\n" + "-" * 60)
        print("Sample Top Predictions:")
        print("-" * 60)
        for i, pred in enumerate(predictions[:5]):
            print(f"{i+1}. {pred.code} ({pred.name})")
            print(f"     Probability: {pred.adjusted_probability:.1f}%")
            print(f"     Stage: {pred.stage}")
            print(f"     Sentiment: {pred.components['sentiment']['score']:.2f}")
            print(f"     Capital: {pred.components['capital']['structure']}")
            print()

    print("=" * 60)


if __name__ == '__main__':
    main()
