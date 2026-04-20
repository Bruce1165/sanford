#!/usr/bin/env python3
"""
Screener Pick Monitor — Core monitoring logic

Tracks screener picks through 10-day monitoring pipeline:
- Auto-creates pick entries when screeners run
- Manages trading day calculations
- Records daily pass/fail status
- Handles graduation (Day 10) and failure tracking

Usage:
    from screener_monitor import ScreenerMonitor
    
    monitor = ScreenerMonitor()
    
    # Create pick from screener result
    monitor.create_pick('coffee_cup_screener', '600519', '2026-03-21', 168.50)
    
    # Get active picks for review
    picks = monitor.get_active_picks('coffee_cup_screener')
    
    # Mark daily status
    monitor.mark_daily_status(pick_id, day=3, status='fail', note='Broke cup rim')
    
    # Get pipeline view
    pipeline = monitor.get_pipeline_view('coffee_cup_screener', days=10)
"""

import os
import sys
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum

# Setup paths
WORKSPACE = Path(os.environ.get('WORKSPACE_ROOT', str(Path(__file__).parent.parent)))
DATA_DIR = WORKSPACE / 'data'
SCRIPTS_DIR = WORKSPACE / 'scripts'
DB_PATH = DATA_DIR / 'stock_data.db'

sys.path.insert(0, str(SCRIPTS_DIR))


class PickStatus(Enum):
    ACTIVE = 'active'
    GRADUATED = 'graduated'
    FAILED = 'failed'


class DailyStatus(Enum):
    PASS = 'pass'
    FAIL = 'fail'
    PENDING = 'pending'


@dataclass
class ScreenerPick:
    """Represents a screener pick being monitored"""
    id: int
    screener_id: str
    stock_code: str
    entry_date: str
    entry_price: float
    expected_exit_date: str
    status: str
    exit_date: Optional[str]
    exit_reason: Optional[str]
    daily_checks: List[Dict]
    created_at: str
    cup_rim_price: Optional[float] = None
    cup_bottom_price: Optional[float] = None
    max_price_seen: Optional[float] = None
    
    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'ScreenerPick':
        daily_checks = json.loads(row['daily_checks']) if row['daily_checks'] else []
        # Handle optional columns that may not exist in older rows
        keys = row.keys()
        return cls(
            id=row['id'],
            screener_id=row['screener_id'],
            stock_code=row['stock_code'],
            entry_date=row['entry_date'],
            entry_price=row['entry_price'],
            expected_exit_date=row['expected_exit_date'],
            status=row['status'],
            exit_date=row['exit_date'],
            exit_reason=row['exit_reason'],
            daily_checks=daily_checks,
            created_at=row['created_at'],
            cup_rim_price=row['cup_rim_price'] if 'cup_rim_price' in keys else None,
            cup_bottom_price=row['cup_bottom_price'] if 'cup_bottom_price' in keys else None,
            max_price_seen=row['max_price_seen'] if 'max_price_seen' in keys else None
        )
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def get_current_day(self) -> int:
        """Calculate current monitoring day (1-10) based on daily_checks"""
        return len(self.daily_checks)
    
    def get_latest_price(self) -> Optional[float]:
        """Get most recent close price from daily checks"""
        if self.daily_checks:
            return self.daily_checks[-1].get('close_price')
        return None
    
    def get_performance_pct(self) -> Optional[float]:
        """Calculate performance % from entry to latest"""
        latest = self.get_latest_price()
        if latest and self.entry_price:
            return round((latest - self.entry_price) / self.entry_price * 100, 2)
        return None


class TradingCalendar:
    """Simple trading calendar (extendable with holiday support)"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
    
    def is_trading_day(self, date: datetime) -> bool:
        """Check if date is a trading day (Mon-Fri, no holidays yet)"""
        return date.weekday() < 5  # 0=Monday, 4=Friday
    
    def get_next_trading_day(self, date: datetime) -> datetime:
        """Get next trading day"""
        next_day = date + timedelta(days=1)
        while not self.is_trading_day(next_day):
            next_day += timedelta(days=1)
        return next_day
    
    def add_trading_days(self, date: datetime, days: int) -> datetime:
        """Add N trading days to date"""
        result = date
        for _ in range(days):
            result = self.get_next_trading_day(result)
        return result


class ScreenerMonitor:
    """Manages screener pick monitoring pipeline"""
    
    # Screener-specific monitoring periods (trading days)
    DEFAULT_MONITORING_DAYS = 10
    SCREENER_PERIODS = {
        'coffee_cup_screener': 25,  # Long-term pattern tracking
        # Add other screeners as needed
        # 'er_ban_hui_tiao_screener': 10,
        # 'zhang_ting_bei_liang_yin_screener': 5,
    }
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self.calendar = TradingCalendar(self.db_path)
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_monitoring_days(self, screener_id: str) -> int:
        """Get monitoring period for a specific screener"""
        return self.SCREENER_PERIODS.get(screener_id, self.DEFAULT_MONITORING_DAYS)
    
    def create_pick(self, screener_id: str, stock_code: str, 
                    entry_date: str, entry_price: float,
                    cup_rim_price: float = None,
                    cup_bottom_price: float = None) -> Optional[ScreenerPick]:
        """
        Create a new pick from screener result.
        
        For Coffee Cup screener, provide cup_rim_price and cup_bottom_price
        for dynamic exit calculations.
        
        Duplicate handling: If (screener_id, stock_code) already has an active pick,
        returns the existing pick instead of creating a new one.
        """
        conn = self._get_conn()
        
        try:
            # Check for existing active pick for this screener+stock
            cursor = conn.execute(
                """SELECT * FROM screener_picks 
                   WHERE screener_id = ? AND stock_code = ? AND status = 'active'""",
                (screener_id, stock_code)
            )
            existing = cursor.fetchone()
            
            if existing:
                print(f"⚠️ Pick already exists for {screener_id}/{stock_code}, continuing existing track")
                return ScreenerPick.from_row(existing)
            
            # Calculate expected exit date (N trading days from entry, screener-specific)
            monitoring_days = self.get_monitoring_days(screener_id)
            entry_dt = datetime.strptime(entry_date, '%Y-%m-%d')
            exit_dt = self.calendar.add_trading_days(entry_dt, monitoring_days)
            expected_exit_date = exit_dt.strftime('%Y-%m-%d')
            
            # Build insert query based on whether cup pattern fields are provided
            if screener_id == 'coffee_cup_screener' and cup_rim_price and cup_bottom_price:
                cursor = conn.execute(
                    """INSERT INTO screener_picks 
                       (screener_id, stock_code, entry_date, entry_price, expected_exit_date, 
                        status, cup_rim_price, cup_bottom_price, max_price_seen)
                       VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
                    (screener_id, stock_code, entry_date, entry_price, expected_exit_date,
                     cup_rim_price, cup_bottom_price, entry_price)  # max starts at entry
                )
            else:
                cursor = conn.execute(
                    """INSERT INTO screener_picks 
                       (screener_id, stock_code, entry_date, entry_price, expected_exit_date, status)
                       VALUES (?, ?, ?, ?, ?, 'active')""",
                    (screener_id, stock_code, entry_date, entry_price, expected_exit_date)
                )
            
            pick_id = cursor.lastrowid
            conn.commit()
            
            print(f"✅ Created pick #{pick_id}: {screener_id}/{stock_code} @ ¥{entry_price} ({monitoring_days} days, Exit: {expected_exit_date})")
            
            # Return the created pick
            cursor = conn.execute("SELECT * FROM screener_picks WHERE id = ?", (pick_id,))
            return ScreenerPick.from_row(cursor.fetchone())
            
        except Exception as e:
            print(f"❌ Failed to create pick: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def get_active_picks(self, screener_id: str = None) -> List[ScreenerPick]:
        """Get all active picks, optionally filtered by screener"""
        conn = self._get_conn()
        
        try:
            if screener_id:
                cursor = conn.execute(
                    """SELECT * FROM screener_picks 
                       WHERE screener_id = ? AND status = 'active'
                       ORDER BY entry_date DESC, stock_code""",
                    (screener_id,)
                )
            else:
                cursor = conn.execute(
                    """SELECT * FROM screener_picks 
                       WHERE status = 'active'
                       ORDER BY screener_id, entry_date DESC, stock_code"""
                )
            
            return [ScreenerPick.from_row(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_picks_by_screener(self, screener_id: str, 
                              status: str = None,
                              limit: int = 100) -> List[ScreenerPick]:
        """Get picks for a specific screener"""
        conn = self._get_conn()
        
        try:
            if status:
                cursor = conn.execute(
                    """SELECT * FROM screener_picks 
                       WHERE screener_id = ? AND status = ?
                       ORDER BY entry_date DESC
                       LIMIT ?""",
                    (screener_id, status, limit)
                )
            else:
                cursor = conn.execute(
                    """SELECT * FROM screener_picks 
                       WHERE screener_id = ?
                       ORDER BY entry_date DESC
                       LIMIT ?""",
                    (screener_id, limit)
                )
            
            return [ScreenerPick.from_row(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_pick(self, pick_id: int) -> Optional[ScreenerPick]:
        """Get a specific pick by ID"""
        conn = self._get_conn()
        
        try:
            cursor = conn.execute(
                "SELECT * FROM screener_picks WHERE id = ?",
                (pick_id,)
            )
            row = cursor.fetchone()
            return ScreenerPick.from_row(row) if row else None
        finally:
            conn.close()
    
    def mark_daily_status(self, pick_id: int, day: int, status: str,
                          close_price: float = None, note: str = '') -> bool:
        """
        Mark the daily status for a pick.
        
        Args:
            pick_id: Pick ID
            day: Day number (1-10)
            status: 'pass', 'fail', or 'pending'
            close_price: Closing price for the day
            note: Optional note about the check
        """
        conn = self._get_conn()
        
        try:
            # Get current daily_checks
            cursor = conn.execute(
                "SELECT daily_checks FROM screener_picks WHERE id = ?",
                (pick_id,)
            )
            row = cursor.fetchone()
            if not row:
                print(f"❌ Pick #{pick_id} not found")
                return False
            
            daily_checks = json.loads(row['daily_checks']) if row['daily_checks'] else []
            
            # Find or create entry for this day
            check_entry = {
                'day': day,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'status': status,
                'close_price': close_price,
                'note': note
            }
            
            # Replace existing entry for this day or append
            existing_idx = next((i for i, c in enumerate(daily_checks) if c.get('day') == day), None)
            if existing_idx is not None:
                daily_checks[existing_idx] = check_entry
            else:
                daily_checks.append(check_entry)
            
            # Sort by day
            daily_checks.sort(key=lambda x: x['day'])
            
            # Update database
            conn.execute(
                "UPDATE screener_picks SET daily_checks = ? WHERE id = ?",
                (json.dumps(daily_checks), pick_id)
            )
            conn.commit()
            
            # If failed, update status (but keep tracking)
            if status == 'fail':
                self._mark_failed(pick_id, day, note)
            
            print(f"✅ Marked Day {day} for pick #{pick_id}: {status}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to mark daily status: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def _mark_failed(self, pick_id: int, failed_day: int, reason: str = ''):
        """Mark pick as failed (but continue tracking)"""
        conn = self._get_conn()
        
        try:
            exit_reason = f"failed_day_{failed_day}"
            if reason:
                exit_reason += f"_{reason}"
            
            conn.execute(
                """UPDATE screener_picks 
                   SET status = 'failed', exit_date = ?, exit_reason = ?
                   WHERE id = ? AND status = 'active'""",
                (datetime.now().strftime('%Y-%m-%d'), exit_reason, pick_id)
            )
            conn.commit()
            print(f"⚠️ Pick #{pick_id} marked as failed (Day {failed_day})")
        except Exception as e:
            print(f"❌ Failed to mark as failed: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def mark_graduated(self, pick_id: int, screener_id: str = None) -> bool:
        """Mark pick as graduated (completed monitoring period)"""
        conn = self._get_conn()
        
        try:
            conn.execute(
                """UPDATE screener_picks 
                   SET status = 'graduated', exit_date = ?, exit_reason = 'completed_10_days'
                   WHERE id = ? AND status = 'active'""",
                (datetime.now().strftime('%Y-%m-%d'), pick_id)
            )
            conn.commit()
            days = self.get_monitoring_days(screener_id) if screener_id else self.DEFAULT_MONITORING_DAYS
            print(f"🎓 Pick #{pick_id} graduated (completed {days} days)")
            return True
        except Exception as e:
            print(f"❌ Failed to mark graduated: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def get_pipeline_view(self, screener_id: str, days: int = 10) -> Dict:
        """
        Get pipeline view for a screener.
        
        Returns dict with:
        - screener_id
        - picks_by_day: {day_number: [picks]}
        - stats: {active, graduated, failed, win_rate}
        """
        picks = self.get_picks_by_screener(screener_id, limit=500)
        
        # Organize by current day
        picks_by_day = {i: [] for i in range(days + 1)}  # 0-10
        
        stats = {
            'total': len(picks),
            'active': 0,
            'graduated': 0,
            'failed': 0
        }
        
        for pick in picks:
            current_day = pick.get_current_day()
            picks_by_day[min(current_day, days)].append(pick.to_dict())
            
            if pick.status == 'active':
                stats['active'] += 1
            elif pick.status == 'graduated':
                stats['graduated'] += 1
            elif pick.status == 'failed':
                stats['failed'] += 1
        
        # Calculate win rate
        completed = stats['graduated'] + stats['failed']
        stats['win_rate'] = round(stats['graduated'] / completed * 100, 1) if completed > 0 else 0
        
        return {
            'screener_id': screener_id,
            'days': days,
            'picks_by_day': picks_by_day,
            'stats': stats
        }
    
    def get_picks_for_review(self, screener_id: str = None, 
                            review_date: str = None) -> List[Dict]:
        """
        Get picks that need review for a specific date.
        
        Returns picks where:
        - Status is 'active'
        - Expected exit date >= review_date
        - The next day check hasn't been recorded yet
        """
        review_date = review_date or datetime.now().strftime('%Y-%m-%d')
        
        conn = self._get_conn()
        
        try:
            if screener_id:
                cursor = conn.execute(
                    """SELECT * FROM screener_picks 
                       WHERE screener_id = ? AND status = 'active' 
                       AND expected_exit_date >= ?
                       ORDER BY entry_date DESC""",
                    (screener_id, review_date)
                )
            else:
                cursor = conn.execute(
                    """SELECT * FROM screener_picks 
                       WHERE status = 'active' AND expected_exit_date >= ?
                       ORDER BY screener_id, entry_date DESC""",
                    (review_date,)
                )
            
            picks = [ScreenerPick.from_row(row) for row in cursor.fetchall()]
            
            # Filter out picks that already have check for today
            result = []
            for pick in picks:
                today_check = next((c for c in pick.daily_checks if c.get('date') == review_date), None)
                if not today_check:
                    result.append({
                        'pick': pick.to_dict(),
                        'current_day': pick.get_current_day() + 1,  # Next day to check
                        'entry_price': pick.entry_price,
                        'latest_price': pick.get_latest_price(),
                        'performance_pct': pick.get_performance_pct()
                    })
            
            return result
            
        finally:
            conn.close()
    
    def auto_check_graduations(self, check_date: str = None) -> List[int]:
        """
        Auto-graduate picks that have reached their monitoring period.
        Returns list of graduated pick IDs.
        """
        check_date = check_date or datetime.now().strftime('%Y-%m-%d')
        
        conn = self._get_conn()
        graduated = []
        
        try:
            cursor = conn.execute(
                """SELECT id, screener_id, daily_checks FROM screener_picks 
                   WHERE status = 'active' AND expected_exit_date <= ?""",
                (check_date,)
            )
            
            for row in cursor.fetchall():
                daily_checks = json.loads(row['daily_checks']) if row['daily_checks'] else []
                monitoring_days = self.get_monitoring_days(row['screener_id'])
                
                # Check if required days of checks recorded
                if len(daily_checks) >= monitoring_days:
                    if self.mark_graduated(row['id'], row['screener_id']):
                        graduated.append(row['id'])
            
            return graduated
            
        finally:
            conn.close()
    
    # ==================== Coffee Cup Specific Evaluation ====================
    
    def evaluate_coffee_cup(self, pick: ScreenerPick, close_price: float, 
                           day_number: int) -> Dict:
        """
        Evaluate Coffee Cup pick status based on dynamic conditions.
        
        Success: Price reaches 1.5x cup rim within 10 trading days
        Failure: Price drops below halfway line (rim + bottom)/2 within 25 days
        Continue: No condition met, keep tracking
        
        Args:
            pick: The pick being evaluated
            close_price: Today's closing price
            day_number: Current trading day number (1-25)
            
        Returns:
            {
                'action': 'continue' | 'graduate_early' | 'fail',
                'reason': str,
                'note': str
            }
        """
        if not pick.cup_rim_price or not pick.cup_bottom_price:
            return {
                'action': 'continue',
                'reason': 'no_cup_data',
                'note': 'Cup pattern data not available'
            }
        
        rim = pick.cup_rim_price
        bottom = pick.cup_bottom_price
        
        # Calculate failure line (halfway between rim and bottom)
        failure_line = (rim + bottom) / 2
        
        # Check for early success (within 10 days)
        if day_number <= 10:
            success_target = rim * 1.5
            if close_price >= success_target:
                return {
                    'action': 'graduate_early',
                    'reason': 'early_success',
                    'note': f'Price reached 1.5x rim ({success_target:.2f}) on day {day_number}'
                }
        
        # Check for failure (within 25 days, using closing price)
        if day_number <= 25:
            if close_price < failure_line:
                return {
                    'action': 'fail',
                    'reason': 'broke_halfway_line',
                    'note': f'Price {close_price:.2f} below failure line {failure_line:.2f} (day {day_number})'
                }
        
        return {
            'action': 'continue',
            'reason': 'conditions_normal',
            'note': f'Tracking... Price: {close_price:.2f}, Failure line: {failure_line:.2f}'
        }
    
    def process_daily_check(self, pick_id: int, check_date: str, 
                           close_price: float, screener_id: str = None) -> Dict:
        """
        Process daily check for a pick with automatic evaluation.
        
        Returns the result of the daily check.
        """
        pick = self.get_pick(pick_id)
        if not pick:
            return {'error': 'Pick not found'}
        
        if pick.status != 'active':
            return {'error': f'Pick not active (status: {pick.status})'}
        
        # Calculate day number
        day_number = len(pick.daily_checks) + 1
        
        # Evaluate based on screener type
        if pick.screener_id == 'coffee_cup_screener':
            evaluation = self.evaluate_coffee_cup(pick, close_price, day_number)
        else:
            # Default: just track price
            evaluation = {
                'action': 'continue',
                'reason': 'manual_review',
                'note': 'Awaiting manual review'
            }
        
        # Update max price seen
        if pick.max_price_seen is None or close_price > pick.max_price_seen:
            self._update_max_price(pick_id, close_price)
        
        # Apply action
        if evaluation['action'] == 'graduate_early':
            self.mark_graduated(pick_id, pick.screener_id)
            status = 'graduated'
        elif evaluation['action'] == 'fail':
            self._mark_failed(pick_id, day_number, evaluation['note'])
            status = 'failed'
        else:
            status = 'pass'  # Continue tracking
        
        # Record daily check
        self.mark_daily_status(pick_id, day_number, status, close_price, evaluation['note'])
        
        return {
            'pick_id': pick_id,
            'day': day_number,
            'action': evaluation['action'],
            'status': status,
            'close_price': close_price,
            'note': evaluation['note']
        }
    
    def _update_max_price(self, pick_id: int, max_price: float):
        """Update the max price seen for a pick"""
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE screener_picks SET max_price_seen = ? WHERE id = ?",
                (max_price, pick_id)
            )
            conn.commit()
        finally:
            conn.close()


def main():
    """CLI for testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Screener Pick Monitor')
    parser.add_argument('--create', action='store_true', help='Create test pick')
    parser.add_argument('--list', action='store_true', help='List active picks')
    parser.add_argument('--pipeline', metavar='SCREENER', help='Show pipeline view')
    parser.add_argument('--review', metavar='SCREENER', nargs='?', const='all', 
                       help='Show picks needing review')
    parser.add_argument('--screener', default='coffee_cup_screener', help='Screener ID')
    parser.add_argument('--code', default='600519', help='Stock code')
    parser.add_argument('--date', help='Entry date (YYYY-MM-DD)')
    parser.add_argument('--price', type=float, default=168.50, help='Entry price')
    
    args = parser.parse_args()
    
    monitor = ScreenerMonitor()
    
    if args.create:
        date = args.date or datetime.now().strftime('%Y-%m-%d')
        pick = monitor.create_pick(args.screener, args.code, date, args.price)
        if pick:
            print(f"\nCreated: {pick}")
    
    elif args.list:
        picks = monitor.get_active_picks(args.screener if args.screener != 'coffee_cup_screener' else None)
        print(f"\nActive picks: {len(picks)}")
        for p in picks[:10]:
            perf = p.get_performance_pct()
            perf_str = f"{perf:+.1f}%" if perf else "N/A"
            print(f"  #{p.id}: {p.screener_id}/{p.stock_code} Day {p.get_current_day()}/10 | {p.status} | {perf_str}")
    
    elif args.pipeline:
        view = monitor.get_pipeline_view(args.pipeline)
        print(f"\nPipeline: {view['screener_id']}")
        print(f"Stats: {view['stats']}")
        for day, picks in view['picks_by_day'].items():
            if picks:
                print(f"  Day {day}: {len(picks)} picks")
    
    elif args.review:
        screener = None if args.review == 'all' else args.review
        picks = monitor.get_picks_for_review(screener)
        print(f"\nPicks needing review: {len(picks)}")
        for item in picks:
            p = item['pick']
            print(f"  #{p['id']}: {p['screener_id']}/{p['stock_code']} | "
                  f"Day {item['current_day']}/10 | "
                  f"Entry: ¥{item['entry_price']} | "
                  f"Current: ¥{item['latest_price'] or 'N/A'} | "
                  f"Perf: {item['performance_pct'] or 0:+.1f}%")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
