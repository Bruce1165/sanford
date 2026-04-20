#!/usr/bin/env python3
"""
Cron task for daily five flags pool screening with pre-check

This cron task runs daily at 22:00 to check for unprocessed
pool records and execute five flags screening if any exist.

Author: Claude Code
Date: 2026-04-19
"""

import sys
import os
import logging
from datetime import datetime
from pathlib import Path

# Add scripts directory to path (cron is in scripts/cron/, so we need to go up 2 levels)
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from database package
from database.lao_ya_tou_pool import LaoYaTouPoolRepository
from database.lao_ya_tou_five_flags import LaoYaTouFiveFlagsRepository

# Import screening script from parent directory
from run_five_flags_pool_screening import FiveFlagsPoolScreening

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('logs/five_flags_cron.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def pre_check_unprocessed(db_path: str = 'data/stock_data.db') -> dict:
    """
    Pre-check: Check for unprocessed pool records.

    Args:
        db_path: Path to database file

    Returns:
        {
            'has_unprocessed': bool,
            'unprocessed_count': int,
            'check_time': str
        }
    """
    pool_repo = LaoYaTouPoolRepository(db_path)

    # Query for unprocessed pools
    unprocessed_pools = pool_repo.find_unprocessed_pools()

    return {
        'has_unprocessed': len(unprocessed_pools) > 0,
        'unprocessed_count': len(unprocessed_pools),
        'check_time': datetime.now().isoformat()
    }


def run_screening_if_needed(check_result: dict, max_workers: int = 4) -> dict:
    """
    Execute screening based on pre-check result.

    Returns:
        {
            'ran_screening': bool,
            'reason': str,
            'result': dict or None
        }
    """
    if not check_result['has_unprocessed']:
        return {
            'ran_screening': False,
            'reason': 'No unprocessed pools',
            'result': None
        }

    logger.info(f"Starting five flags pool screening with {max_workers} workers")
    logger.info(f"Found {check_result['unprocessed_count']} unprocessed pool records")

    try:
        # Create screening instance
        screening = FiveFlagsPoolScreening(
            db_path='data/stock_data.db',
            max_workers=max_workers
        )

        # Run screening
        result = screening.run_screening()

        logger.info(f"Screening completed. Total matches: {result.get('processed_stocks', 0)}")

        return {
            'ran_screening': True,
            'reason': 'Screening completed',
            'result': result
        }

    except Exception as e:
        logger.error(f"Screening failed: {e}", exc_info=True)
        return {
            'ran_screening': False,
            'reason': f"Error: {str(e)}",
            'result': None
        }


def send_notification(result: dict):
    """
    Send notification (optional).

    Args:
        result: Screening result
    """
    # TODO: Implement notification logic (can extend to email, DingTalk, etc.)
    logger.info(f"Screening completed. Total matches: {result.get('processed_stocks', 0)}")


def main():
    """Main function."""
    logger.info("Starting five flags pool cron task")

    try:
        # 1. Pre-check
        check_result = pre_check_unprocessed()

        if not check_result['has_unprocessed']:
            logger.info(f"No unprocessed pools found. Skipping.")
            return {
                'success': True,
                'ran_screening': False,
                'reason': 'No unprocessed pools',
                'check_time': check_result['check_time']
            }

        logger.info(f"Found {check_result['unprocessed_count']} unprocessed pool records")

        # 2. Run screening
        screening_result = run_screening_if_needed(check_result)

        # 3. Send notification
        if screening_result['ran_screening']:
            send_notification(screening_result['result'])

        return {
            'success': True,
            'ran_screening': screening_result['ran_screening'],
            'reason': screening_result['reason'],
            'result': screening_result['result']
        }

    except Exception as e:
        logger.error(f"Cron task failed: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


if __name__ == '__main__':
    result = main()
    sys.exit(0 if result['success'] else 1)
