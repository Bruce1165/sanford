#!/usr/bin/env python3
"""
Phase 1: Research & Analysis - Coffee Cup Formation Analysis

This script analyzes historical data to identify:
1. Stocks that successfully formed coffee cups (last 18+ months)
2. Timeline of screener triggers during cup formation
3. Correlation between screeners and cup phases
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database paths
STOCK_DATA_DB = Path(__file__).parent.parent / 'data' / 'stock_data.db'
DASHBOARD_DB = Path(__file__).parent.parent / 'data' / 'dashboard.db'

# Available screeners (excluding base and test screeners)
ALL_SCREENERS = [
    'ashare_21',
    'breakout_20day',
    'breakout_main',
    'coffee_cup',
    'cup_handle',
    'daily_hot_cold',
    'double_bottom',
    'er_ban_hui_tiao',
    'flat_base',
    'high_tight_flag',
    'jin_feng_huang',
    'shi_pan_xian',
    'shuang_shou_ban',
    'yin_feng_huang',
    'zhang_ting_bei_liang_yin',
]


class CupFormationAnalyzer:
    """Analyze coffee cup formations and correlate with other screeners"""

    def __init__(self):
        self.stock_data_conn = None
        self.dashboard_conn = None

    def get_stock_data_conn(self) -> sqlite3.Connection:
        """Get stock_data.db connection"""
        if self.stock_data_conn is None:
            self.stock_data_conn = sqlite3.connect(str(STOCK_DATA_DB), timeout=30)
            self.stock_data_conn.row_factory = sqlite3.Row
        return self.stock_data_conn

    def get_dashboard_conn(self) -> sqlite3.Connection:
        """Get dashboard.db connection"""
        if self.dashboard_conn is None:
            self.dashboard_conn = sqlite3.connect(str(DASHBOARD_DB), timeout=30)
            self.dashboard_conn.row_factory = sqlite3.Row
        return self.dashboard_conn

    def get_date_range(self) -> Tuple[str, str]:
        """Get the full date range of available data"""
        with self.get_stock_data_conn() as conn:
            row = conn.execute(
                "SELECT MIN(trade_date) as min_date, MAX(trade_date) as max_date FROM daily_prices"
            ).fetchone()
            return row['min_date'], row['max_date']

    def get_daily_prices(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Get daily price data for a stock"""
        sql = """
            SELECT trade_date, open, high, low, close, volume,
                   COALESCE(amount, 0) as amount,
                   COALESCE(pct_change, 0) as pct_change,
                   COALESCE(turnover, 0) as turnover
            FROM daily_prices
            WHERE code = ? AND trade_date BETWEEN ? AND ?
            ORDER BY trade_date ASC
        """
        with self.get_stock_data_conn() as conn:
            df = pd.read_sql_query(sql, conn, params=(code, start_date, end_date))
        if not df.empty:
            df['trade_date'] = pd.to_datetime(df['trade_date'])
        return df

    def identify_cup_formations(self) -> List[Dict]:
        """
        Identify stocks that formed coffee cups by running the coffee cup screener
        on historical dates
        """
        from coffee_cup_screener import CoffeeCupScreener

        min_date, max_date = self.get_date_range()
        logger.info(f"Data range: {min_date} to {max_date}")

        # Get all trading dates in the range (for running screener on each date)
        with self.get_stock_data_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT trade_date FROM daily_prices WHERE trade_date >= ? ORDER BY trade_date",
                (min_date,)
            ).fetchall()

        trading_dates = [r['trade_date'] for r in rows]

        # Sample dates (run screener every week instead of every day to save time)
        sample_dates = trading_dates[::7]  # Every 7th trading day
        logger.info(f"Analyzing {len(sample_dates)} sample dates from {len(trading_dates)} total trading days")

        screener = CoffeeCupScreener(db_path=str(STOCK_DATA_DB), enable_progress=False)
        all_cups = []

        for date_str in sample_dates:
            logger.info(f"Running coffee cup screener for {date_str}...")

            try:
                # Set current date
                screener.current_date = date_str

                # Get all stocks
                stocks = screener.get_all_stocks()

                # Screen each stock
                for stock in stocks:
                    try:
                        result = screener.screen_stock(stock.code, stock.name)
                        if result is not None:
                            # This stock formed a cup on this date
                            cup_info = {
                                'code': stock.code,
                                'name': stock.name,
                                'cup_date': date_str,
                                'close': result.get('close', 0),
                                'turnover': result.get('turnover', 0),
                                'pct_change': result.get('pct_change', 0),
                                'cup_depth': result.get('cup_depth', 0),
                                'handle_retrace': result.get('handle_retrace', 0),
                                'cup_high': result.get('cup_rim_price', 0),
                                'cup_low': result.get('cup_bottom_price', 0),
                                'handle_date': result.get('handle_date', ''),
                                'rs_score': result.get('rs_score', 0),
                            }
                            all_cups.append(cup_info)
                    except Exception as e:
                        logger.debug(f"Error screening {stock.code} on {date_str}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Error running screener on {date_str}: {e}")
                continue

        logger.info(f"Found {len(all_cups)} coffee cup formations")
        return all_cups

    def run_screeners_on_date(self, date_str: str) -> Dict[str, List[str]]:
        """
        Run all screeners (except coffee_cup) on a specific date
        Returns: {screener_name: [stock_code1, stock_code2, ...]}
        """
        screener_results = {}

        # Import screeners dynamically
        for screener_name in ALL_SCREENERS:
            if screener_name == 'coffee_cup' or screener_name == 'base':
                continue

            try:
                # Dynamic import of screener module
                module = __import__(f'_{screener_name}_screener', fromlist=['screeners'])

                # Get the screener class
                screener_class = getattr(module, f'{screener_name.title().replace("_", "")}Screener')

                # Create instance
                screener = screener_class(
                    db_path=str(STOCK_DATA_DB),
                    enable_progress=False,
                    enable_news=False,
                    enable_llm=False
                )

                # Set date
                screener.current_date = date_str

                # Run screening
                results, summary = screener.run()

                # Extract stock codes
                stock_codes = [r.code for r in results]
                screener_results[screener_name] = stock_codes

                logger.info(f"  {screener_name}: {len(stock_codes)} stocks")

            except Exception as e:
                logger.debug(f"Error running {screener_name} screener: {e}")
                screener_results[screener_name] = []

        return screener_results

    def build_screener_timeline(self, start_date: str, end_date: str) -> Dict[str, Dict[str, List[str]]]:
        """
        Build a timeline of screener triggers for all stocks across a date range

        Returns: {date: {screener_name: [stock_codes]}}
        """
        # Get all trading dates in range
        with self.get_stock_data_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT trade_date FROM daily_prices WHERE trade_date BETWEEN ? AND ? ORDER BY trade_date",
                (start_date, end_date)
            ).fetchall()

        trading_dates = [r['trade_date'] for r in rows]

        # Sample dates (every 5 trading days to save time)
        sample_dates = trading_dates[::5]
        logger.info(f"Building timeline from {len(sample_dates)} dates")

        timeline = {}

        for date_str in sample_dates:
            logger.info(f"Running all screeners on {date_str}...")
            screener_results = self.run_screeners_on_date(date_str)
            timeline[date_str] = screener_results

        return timeline

    def get_screener_triggers_for_stock(self, code: str, timeline: Dict[str, Dict[str, List[str]]]) -> Dict[str, List[str]]:
        """
        Extract screener trigger dates for a specific stock from the timeline

        Returns: {screener_name: [date1, date2, ...]}
        """
        screener_triggers = {}

        for date_str, screener_results in timeline.items():
            for screener_name, stock_codes in screener_results.items():
                if code in stock_codes:
                    if screener_name not in screener_triggers:
                        screener_triggers[screener_name] = []
                    screener_triggers[screener_name].append(date_str)

        # Sort dates for each screener
        for screener_name in screener_triggers:
            screener_triggers[screener_name].sort()

        return screener_triggers

    def get_screener_triggers(self, code: str, formation_date: str,
                              timeline: Dict[str, Dict[str, List[str]]],
                              lookback_days: int = 180) -> Dict[str, List[str]]:
        """
        Get which screeners triggered for a stock in the months leading up to cup formation

        Returns: {screener_name: [date1, date2, ...]}
        """
        # Calculate start date for analysis (lookback period before cup formation)
        cup_dt = datetime.strptime(formation_date, '%Y-%m-%d')
        start_dt = cup_dt - timedelta(days=lookback_days)
        start_date_str = start_dt.strftime('%Y-%m-%d')

        # Use the pre-built timeline to extract triggers
        screener_triggers = {}

        for date_str, screener_results in timeline.items():
            # Only consider dates within our analysis window
            if not (start_date_str <= date_str <= formation_date):
                continue

            for screener_name, stock_codes in screener_results.items():
                if code in stock_codes:
                    if screener_name not in screener_triggers:
                        screener_triggers[screener_name] = []
                    screener_triggers[screener_name].append(date_str)

        # Sort dates for each screener
        for screener_name in screener_triggers:
            screener_triggers[screener_name].sort()

        return screener_triggers

    def analyze_cup_formation_timeline(self, cup_info: Dict) -> Dict:
        """
        Analyze the timeline of screener triggers for a single cup formation

        Returns: Analysis including phases, screener correlations, etc.
        """
        code = cup_info['code']
        formation_date = cup_info['cup_date']

        # Get screener triggers leading up to this cup
        screener_triggers = self.get_screener_triggers(code, formation_date)

        # Get price data for the period
        min_date, max_date = self.get_date_range()
        start_dt = datetime.strptime(formation_date, '%Y-%m-%d') - timedelta(days=180)
        start_date_str = start_dt.strftime('%Y-%m-%d')
        price_data = self.get_daily_prices(code, start_date_str, formation_date)

        if price_data.empty:
            logger.warning(f"No price data for {code} from {start_date_str} to {formation_date}")
            return {}

        # Calculate cup phases based on price data
        # We'll approximate phases based on cup parameters
        cup_high = cup_info['cup_high']
        cup_low = cup_info['cup_low']
        handle_date = cup_info['handle_date']

        # Calculate approximate phase boundaries
        if handle_date:
            handle_dt = datetime.strptime(handle_date, '%Y-%m-%d')
            if handle_dt <= start_dt:
                handle_dt = datetime.strptime(formation_date, '%Y-%m-%d')

            # Estimate cup body period
            cup_body_days = (handle_dt - start_dt).days
            if cup_body_days > 0:
                cup_body_start = start_dt
                cup_body_end = handle_dt
            else:
                cup_body_start = start_dt
                cup_body_end = datetime.strptime(formation_date, '%Y-%m-%d')
        else:
            cup_body_start = start_dt
            cup_body_end = datetime.strptime(formation_date, '%Y-%m-%d')

        # Map screener triggers to phases
        phase_mapping = {
            'uptrend': [],      # Phase 1: Prior uptrend
            'consolidation': [],  # Phase 2: Rounded consolidation
            'recovery': [],       # Phase 3: Right side recovery
            'handle': [],         # Phase 4: Handle formation
        }

        for screener_name, trigger_dates in screener_triggers.items():
            for trigger_date in trigger_dates:
                trigger_dt = datetime.strptime(trigger_date, '%Y-%m-%d')

                # Map to phase based on timing relative to cup formation
                if trigger_dt < cup_body_start + timedelta(days=30):
                    # Early in formation - likely uptrend
                    phase_mapping['uptrend'].append((screener_name, trigger_date))
                elif trigger_dt < cup_body_start + timedelta(days=90):
                    # Mid-period - likely consolidation
                    phase_mapping['consolidation'].append((screener_name, trigger_date))
                elif trigger_dt < datetime.strptime(formation_date, '%Y-%m-%d') - timedelta(days=21):
                    # Late period - likely recovery
                    phase_mapping['recovery'].append((screener_name, trigger_date))
                else:
                    # Very recent - likely handle or breakout
                    phase_mapping['handle'].append((screener_name, trigger_date))

        return {
            'code': code,
            'name': cup_info['name'],
            'cup_date': formation_date,
            'cup_high': cup_high,
            'cup_low': cup_low,
            'cup_depth_pct': cup_info.get('cup_depth', 0),
            'handle_date': cup_info.get('handle_date', ''),
            'screener_triggers': screener_triggers,
            'phase_mapping': phase_mapping,
            'total_screener_triggers': sum(len(v) for v in screener_triggers.values()),
            'screeners_by_phase': {
                'uptrend': list(set([s for s, d in phase_mapping['uptrend']])),
                'consolidation': list(set([s for s, d in phase_mapping['consolidation']])),
                'recovery': list(set([s for s, d in phase_mapping['recovery']])),
                'handle': list(set([s for s, d in phase_mapping['handle']])),
            }
        }

    def analyze_all_cup_formations(self) -> List[Dict]:
        """Analyze all cup formations and their screener timelines"""
        logger.info("=" * 80)
        logger.info("Phase 1: Identifying Coffee Cup Formations")
        logger.info("=" * 80)

        # Step 1: Identify all cup formations
        cup_formations = self.identify_cup_formations()

        if not cup_formations:
            logger.warning("No cup formations found. Exiting.")
            return []

        logger.info(f"Analyzing timeline for {len(cup_formations)} cup formations...")

        # Step 2: Analyze screener triggers for each cup
        all_analyses = []
        for i, cup_info in enumerate(cup_formations):
            logger.info(f"Analyzing cup {i+1}/{len(cup_formations)}: {cup_info['code']} - {cup_info['name']}")

            analysis = self.analyze_cup_formation_timeline(cup_info)
            if analysis:
                all_analyses.append(analysis)

        return all_analyses

    def generate_summary_report(self, analyses: List[Dict]) -> Dict:
        """Generate summary statistics from all analyses"""
        if not analyses:
            return {}

        summary = {
            'total_cups': len(analyses),
            'avg_screener_triggers_per_cup': 0,
            'screener_frequency': {},
            'phase_screener_counts': {
                'uptrend': {},
                'consolidation': {},
                'recovery': {},
                'handle': {}
            },
            'most_common_sequences': []
        }

        total_triggers = 0
        screener_counts = {}

        for analysis in analyses:
            # Count triggers per cup
            triggers = analysis.get('total_screener_triggers', 0)
            total_triggers += triggers

            # Count screeners by name
            for screener_name, dates in analysis.get('screener_triggers', {}).items():
                screener_counts[screener_name] = screener_counts.get(screener_name, 0) + len(dates)

            # Count screeners by phase
            for phase, screeners in analysis.get('screeners_by_phase', {}).items():
                for screener in screeners:
                    phase_counts = summary['phase_screener_counts'][phase]
                    phase_counts[screener] = phase_counts.get(screener, 0) + 1

        # Calculate averages
        if len(analyses) > 0:
            summary['avg_screener_triggers_per_cup'] = total_triggers / len(analyses)

        summary['screener_frequency'] = dict(sorted(
            screener_counts.items(), key=lambda x: x[1], reverse=True
        ))

        return summary

    def save_results(self, analyses: List[Dict], summary: Dict):
        """Save analysis results to Excel files"""
        from config import DATA_DIR

        output_dir = Path(DATA_DIR) / 'analysis' / 'cup_formation_phase1'
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Save detailed analyses
        if analyses:
            analyses_df = pd.DataFrame(analyses)
            analyses_path = output_dir / f'cup_formations_detailed_{timestamp}.xlsx'
            analyses_df.to_excel(analyses_path, index=False, engine='xlsxwriter')
            logger.info(f"Detailed analyses saved to: {analyses_path}")

        # Save summary
        if summary:
            # Summary stats
            summary_data = [
                {'Metric': 'Total Coffee Cups', 'Value': summary.get('total_cups', 0)},
                {'Metric': 'Avg Screener Triggers per Cup', 'Value': f"{summary.get('avg_screener_triggers_per_cup', 0):.1f}"},
            ]

            # Screener frequency
            for screener, count in summary.get('screener_frequency', {}).items():
                summary_data.append({'Metric': f'{screener} Frequency', 'Value': count})

            summary_df = pd.DataFrame(summary_data)
            summary_path = output_dir / f'cup_formations_summary_{timestamp}.xlsx'
            summary_df.to_excel(summary_path, index=False, engine='xlsxwriter')
            logger.info(f"Summary saved to: {summary_path}")

        # Save phase correlations
        if summary:
            phase_data = []
            for phase, screener_counts in summary.get('phase_screener_counts', {}).items():
                for screener, count in screener_counts.items():
                    phase_data.append({
                        'Phase': phase,
                        'Screener': screener,
                        'Frequency': count
                    })

            phase_df = pd.DataFrame(phase_data)
            phase_path = output_dir / f'cup_formations_phases_{timestamp}.xlsx'
            phase_df.to_excel(phase_path, index=False, engine='xlsxwriter')
            logger.info(f"Phase correlations saved to: {phase_path}")

        return output_dir


def main():
    """Main execution function"""
    logger.info("Starting Phase 1: Coffee Cup Formation Analysis")

    analyzer = CupFormationAnalyzer()

    # Run the analysis
    analyses = analyzer.analyze_all_cup_formations()

    # Generate summary
    summary = analyzer.generate_summary_report(analyses)

    # Save results
    output_dir = analyzer.save_results(analyses, summary)

    logger.info("=" * 80)
    logger.info("Phase 1 Analysis Complete!")
    logger.info("=" * 80)
    logger.info(f"Results saved to: {output_dir}")
    logger.info(f"Total cups analyzed: {len(analyses)}")
    logger.info(f"Avg screener triggers per cup: {summary.get('avg_screener_triggers_per_cup', 0):.1f}")

    if summary.get('screener_frequency'):
        logger.info("\nTop 10 most frequent screeners during cup formation:")
        for i, (screener, count) in enumerate(list(summary['screener_frequency'].items())[:10]):
            logger.info(f"  {i+1}. {screener}: {count} times")

    logger.info("\nNext steps:")
    logger.info("1. Review the detailed Excel files to understand patterns")
    logger.info("2. Identify which screeners consistently trigger during specific phases")
    logger.info("3. Determine temporal sequences for prediction modeling")
    logger.info("4. Move to Phase 2: Prototype Implementation")


if __name__ == '__main__':
    main()
