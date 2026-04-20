"""
Coffee Cup Wizard - China A-Share Aware Predictive Model

NOT a traditional screener. This module:
- Detects coffee cup patterns in progress
- Incorporates China A-share specific factors (volume sentiment, retail vs institutional, limit-up proximity)
- Calculates multi-factor probability with configurable weights
- Supports iterative optimization through historical validation

Version: 2.0 (China Market Aware)
Created: 2026-04-10
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CupEdgeResult:
    """Cup edge detection result"""
    detected: bool
    quality: float
    start_idx: int
    end_idx: int
    high_price: float
    current_price: float
    days_consolidating: int
    consolidation_quality: float
    volume_shrink_pct: float
    max_dip_pct: float
    target_days: int


@dataclass
class SentimentAnalysis:
    """Volume and sentiment analysis"""
    vol_trend: float
    vol_vs_avg: float
    avg_turnover: float
    volume_spikes: int
    sentiment_score: float
    limit_up_proximity: float
    limit_up_level: str


@dataclass
class CapitalStructure:
    """Retail vs institutional analysis"""
    retail_dominance: bool
    volatility: float
    vol_consistency: float
    capital_structure: str


@dataclass
class WizardPrediction:
    """Complete prediction result"""
    code: str
    name: str
    completion_pct: float
    base_probability: float
    adjusted_probability: float
    stage: str
    components: Dict[str, Any]
    factors: Dict[str, float]
    target_days: int
    prediction_date: str


class CoffeeCupWizard:
    """Main wizard class for China A-share aware coffee cup prediction"""

    def __init__(self, config_path: str = None, db_path: str = None):
        self.config = self._load_config(config_path)
        self.db_path = Path(db_path) if db_path else Path('data/stock_data.db')
        self.stock_cache = {}

    def _load_config(self, config_path: str = None) -> Dict:
        """Load wizard configuration from JSON"""
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / 'config' / 'wizard_params.json'

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)['coffee_cup_wizard']
        except FileNotFoundError:
            logger.error(f"Config not found: {config_path}")
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """Default configuration if config file missing"""
        logger.warning("Using default configuration")
        return {
            'version': 'v2.0-default',
            'last_updated': datetime.now().isoformat(),
            'market_context': {
                'market': 'china_a_share',
                'special_rules': {
                    't_plus_1': True,
                    'no_short_selling': True,
                    'limit_up_restriction': True,
                    'retail_dominant': True
                }
            },
            'component_params': {
                'cup_edge': {
                    'enabled': True,
                    'period_min': 5,
                    'period_max': 21,
                    'height_match_pct': 95,
                    'max_drop_pct': 8,
                    'min_drop_pct': 2,
                    'volume_shrink': True,
                    'max_rise_pct': 3
                }
            },
            'sentiment_params': {
                'volume_analysis': {
                    'enabled': True,
                    'window_days': 20,
                    'spike_threshold': 2.0,
                    'spike_window': 3
                },
                'turnover_analysis': {
                    'enabled': True,
                    'high_threshold': 8,
                    'medium_threshold': 4,
                    'low_threshold': 2
                },
                'limit_up_sentiment': {
                    'enabled': True,
                    'proximity_days': [5, 10, 20],
                    'high_threshold': 0.08,
                    'medium_threshold': 0.05,
                    'low_threshold': 0.02
                }
            },
            'capital_structure_params': {
                'enabled': True,
                'turnover_weight': 0.6,
                'volatility_weight': 0.3,
                'volume_consistency_weight': 0.1,
                'retail_threshold': 0.5,
                'institution_threshold': -0.5
            },
            'probability_formula': {
                'base_components': ['cup_edge'],
                'adjustment_factors': [
                    {
                        'name': 'volume_sentiment',
                        'enabled': True,
                        'weight': 0.25,
                        'type': 'multiplier',
                        'min_value': 0.5,
                        'max_value': 1.5,
                        'description': 'Volume and sentiment multiplier (量能)'
                    },
                    {
                        'name': 'capital_structure',
                        'enabled': True,
                        'weight': 0.20,
                        'type': 'multiplier',
                        'min_value': 0.7,
                        'max_value': 1.4,
                        'description': 'Retail vs institutional dynamics (散户vs机构)'
                    },
                    {
                        'name': 'limit_up_proximity',
                        'enabled': True,
                        'weight': 0.15,
                        'type': 'multiplier',
                        'min_value': 0.9,
                        'max_value': 1.3,
                        'description': 'T+1 limit-up anticipation (涨停板情绪)'
                    },
                    {
                        'name': 'trend_alignment',
                        'enabled': True,
                        'weight': 0.10,
                        'type': 'multiplier',
                        'min_value': 0.8,
                        'max_value': 1.2,
                        'description': 'Price trend and MA alignment'
                    },
                    {
                        'name': 'rs_strength',
                        'enabled': True,
                        'weight': 0.15,
                        'type': 'multiplier',
                        'min_value': 0.8,
                        'max_value': 1.3,
                        'description': 'Relative strength vs market (RS)'
                    }
                ],
                'prediction_threshold': 50
            },
            'validation': {
                'test_periods': [
                    {
                        'start_date': '2025-06-01',
                        'end_date': '2025-06-30',
                        'min_samples': 50
                    },
                    {
                        'start_date': '2025-07-01',
                        'end_date': '2025-07-31',
                        'min_samples': 50
                    },
                    {
                        'start_date': '2025-08-01',
                        'end_date': '2025-08-31',
                        'min_samples': 50
                    },
                    {
                        'start_date': '2025-09-01',
                        'end_date': '2025-09-30',
                        'min_samples': 50
                    }
                ],
                'overall_accuracy_target': 0.65
            },
            'optimization': {
                'auto_optimize': True,
                'optimization_window': 'latest_30_days',
                'min_iterations': 10,
                'max_iterations': 100,
                'convergence_threshold': 0.01,
                'optimization_log_path': 'data/wizard_optimization_log.json'
            }
        }

    def _get_stock_data(self, code: str, end_date: str = None) -> pd.DataFrame:
        """Load stock price data from database"""
        conn = sqlite3.connect(self.db_path)
        query = """
            SELECT code, name, trade_date, open, high, low, close, preclose, volume, amount, turnover, pct_change
            FROM daily_prices dp
            JOIN stocks s ON dp.code = s.code
            WHERE dp.code = ?
            ORDER BY trade_date
        """

        df = pd.read_sql_query(query, conn, params=(code,))
        conn.close()

        if end_date:
            df = df[df['trade_date'] <= end_date]

        return df

    def _get_stock_metadata(self, code: str) -> Dict:
        """Get stock metadata (industry, sector, market cap)"""
        if code in self.stock_cache:
            return self.stock_cache[code]

        conn = sqlite3.connect(self.db_path)
        query = """
            SELECT code, name, industry, sector_lv1, sector_lv2, list_date,
                   total_market_cap, circulating_market_cap, pe_ratio, pb_ratio
            FROM stocks
            WHERE code = ?
        """

        cursor = conn.cursor()
        cursor.execute(query, (code,))
        result = cursor.fetchone()
        conn.close()

        if result:
            metadata = {
                'code': result[0],
                'name': result[1],
                'industry': result[2],
                'sector_lv1': result[3],
                'sector_lv2': result[4],
                'list_date': result[5],
                'total_market_cap': result[6] if result[6] else 0,
                'circulating_market_cap': result[7] if result[7] else 0,
                'pe_ratio': result[8] if result[8] else None,
                'pb_ratio': result[9] if result[9] else None
            }
            self.stock_cache[code] = metadata
            return metadata

        return {'code': code, 'name': 'Unknown', 'industry': 'Unknown'}

    def analyze_volume_sentiment(self, df: pd.DataFrame, params: Dict) -> SentimentAnalysis:
        """Analyze volume and sentiment (量能分析)"""
        if not params['enabled']:
            return SentimentAnalysis(0, 0, 0, 0, 0, 0)

        # Get analysis window
        window = params['window_days']
        recent_df = df.tail(window)

        # 1. Volume trend (量能趋势)
        vol_trend = recent_df['volume'].pct_change().mean()

        # 2. Volume vs 60-day average (相对量能)
        if len(df) >= 60:
            vol_avg_60d = df['volume'].rolling(60).mean().iloc[-1]
            vol_vs_avg = recent_df['volume'].mean() / vol_avg_60d
        else:
            vol_vs_avg = 1.0

        # 3. Turnover rate analysis (换手率 - 散户活跃度)
        avg_turnover = recent_df['turnover'].mean()

        # 4. Detect volume spikes (异常放量 - 可能是游资或机构建仓)
        spike_threshold = params.get('spike_threshold', 2.0)
        spike_window = params.get('spike_window', 3)
        volume_spikes = self._detect_volume_spikes(recent_df, spike_threshold, spike_window)

        # 5. Limit-up proximity (涨停板情绪)
        limit_up_proximity = self._analyze_limit_up_proximity(df, recent_df, params)

        # Calculate overall sentiment score (0-100)
        sentiment_components = []

        # Volume trend contribution
        if vol_trend > 0.1:
            sentiment_components.append(20)  # 放量
        elif vol_trend > 0:
            sentiment_components.append(10)  # 缩量
        else:
            sentiment_components.append(5)  # 量平

        # Relative volume contribution
        if vol_vs_avg > 1.3:
            sentiment_components.append(15)  # 放量
        elif vol_vs_avg > 1.0:
            sentiment_components.append(10)  # 量平
        elif vol_vs_avg > 0.7:
            sentiment_components.append(5)  # 缩量
        else:
            sentiment_components.append(0)  # 量萎缩

        # Turnover contribution (散户活跃度)
        if avg_turnover > params['turnover_analysis']['high_threshold']:
            sentiment_components.append(20)  # 高换手 = 散户活跃
        elif avg_turnover > params['turnover_analysis']['medium_threshold']:
            sentiment_components.append(10)
        elif avg_turnover > params['turnover_analysis']['low_threshold']:
            sentiment_components.append(5)
        else:
            sentiment_components.append(0)

        # Volume spikes contribution (机构建仓信号)
        if volume_spikes > 0:
            sentiment_components.append(min(10, volume_spikes * 2))

        # Limit-up proximity contribution
        sentiment_components.append(limit_up_proximity * 10)

        sentiment_score = min(100, sum(sentiment_components))

        return SentimentAnalysis(
            vol_trend=vol_trend,
            vol_vs_avg=vol_vs_avg,
            avg_turnover=avg_turnover,
            volume_spikes=volume_spikes,
            sentiment_score=sentiment_score / 100,
            limit_up_proximity=limit_up_proximity,
            limit_up_level=self._get_limit_up_level(limit_up_proximity)
        )

    def _detect_volume_spikes(self, df: pd.DataFrame, threshold: float, window: int) -> int:
        """Count significant volume spikes"""
        spikes = 0
        vol_mean = df['volume'].mean()

        for i in range(window, len(df)):
            if df.iloc[i]['volume'] > vol_mean * (1 + threshold):
                spikes += 1

        return spikes

    def _analyze_limit_up_proximity(self, df: pd.DataFrame, recent_df: pd.DataFrame, params: Dict) -> float:
        """Analyze limit-up proximity (涨停板情绪)"""
        # Find recent limit-ups
        recent_df['pct_change'] = recent_df['pct_change'].fillna(0)
        limit_ups = recent_df[recent_df['pct_change'] >= 9.9]

        if len(limit_ups) == 0:
            return 0

        # Check proximity to recent limit-ups
        current_date = df.iloc[-1]['trade_date']
        proximity_days = params.get('proximity_days', [5, 10, 20])

        for days in proximity_days:
            cutoff_date = current_date - timedelta(days=days)
            if len(limit_ups[limit_ups['trade_date'] >= cutoff_date]) > 0:
                return params.get('high_threshold', 0.08)  # High

        return params.get('low_threshold', 0.02)

    def _get_limit_up_level(self, proximity: float) -> str:
        """Convert proximity to level"""
        if proximity >= 0.08:
            return 'high'
        elif proximity >= 0.05:
            return 'medium'
        elif proximity >= 0.02:
            return 'low'
        else:
            return 'none'

    def analyze_capital_structure(self, df: pd.DataFrame, params: Dict) -> CapitalStructure:
        """Analyze retail vs institutional (散户vs机构)"""
        if not params['enabled']:
            return CapitalStructure(False, 0, 0, 'unknown')

        # Calculate indicators over last 30 days
        recent_df = df.tail(30)

        # 1. Turnover rate (高换手率 = 散户活跃)
        avg_turnover = recent_df['turnover'].mean()
        retail_indicators = avg_turnover > params.get('retail_threshold', 0.5)

        # 2. Price volatility (散户特征: 剧烈波动)
        volatility = recent_df['pct_change'].std()

        # 3. Volume consistency (机构特征: 稳健持续)
        vol_mean = recent_df['volume'].mean()
        vol_std = recent_df['volume'].std()
        vol_consistency = vol_std / vol_mean if vol_mean > 0 else 0

        # Determine capital structure
        if retail_indicators and volatility > 0.05:
            # High turnover + high volatility = retail-heavy (散户主导)
            capital_structure = 'retail_heavy'
        elif vol_consistency > 0.3:
            # Stable volume = institutional (机构主导)
            capital_structure = 'institution_heavy'
        elif retail_indicators:
            # Moderate turnover = mix
            capital_structure = 'mixed'
        else:
            capital_structure = 'unknown'

        return CapitalStructure(
            retail_dominance=retail_indicators,
            volatility=volatility,
            vol_consistency=vol_consistency,
            capital_structure=capital_structure
        )

    def detect_cup_edge(self, df: pd.DataFrame, params: Dict, handle_info: Dict = None) -> CupEdgeResult:
        """
        Detect cup edge formation (杯沿震荡期)
        China A-share specific: Right wall should be formed first (detected by existing screener)
        """
        if len(df) < 30:
            return CupEdgeResult(detected=False, quality=0, start_idx=0, end_idx=0, high_price=0, current_price=0,
                           days_consolidating=0, consolidation_quality=0, volume_shrink_pct=0, max_dip_pct=0, target_days=0)

        # Handle info from existing screener or detect
        if handle_info:
            handle_high_price = handle_info.get('high_price', df['high'].max())
        else:
            # Try to detect from df
            handle_high_price = df['high'].tail(120).max()

        if not handle_high_price or handle_high_price <= 0:
            return CupEdgeResult(detected=False, quality=0, start_idx=0, end_idx=0, high_price=0, current_price=0,
                           days_consolidating=0, consolidation_quality=0, volume_shrink_pct=0, max_dip_pct=0, target_days=0)

        # Parameters
        period_min = params.get('period_min', 5)
        period_max = params.get('period_max', 21)
        height_match_pct = params.get('height_match_pct', 95)
        max_drop_pct = params.get('max_drop_pct', 8)
        min_drop_pct = params.get('min_drop_pct', 2)
        max_rise_pct = params.get('max_rise_pct', 3)

        # Find price level to analyze (right side after handle)
        handle_level = handle_high_price
        match_range_low = handle_level * params.get('height_match_pct', 100)
        match_range_high = handle_level / params.get('height_match_pct', 100)

        # Find matching periods in the last period_max days
        for idx in range(max(0, len(df) - period_max), len(df)):
            window_data = df.iloc[idx:idx + period_max]

            # Find high in this window
            window_high = window_data['high'].max()
            if abs(window_high - handle_level) / handle_level > 0.05:
                continue  # Not close to handle level

            # Check if we reached handle level
            if window_high >= match_range_low and window_high <= match_range_high:
                handle_idx = idx + window_data['high'].idxmax()
                break

        if handle_idx is None or handle_idx < period_min:
            return CupEdgeResult(detected=False, quality=0, start_idx=0, end_idx=0, high_price=0, current_price=0,
                           days_consolidating=0, consolidation_quality=0, volume_shrink_pct=0, max_dip_pct=0, target_days=0)

        # Now check for edge consolidation AFTER handle
        edge_start = handle_idx
        edge_end = min(len(df) - 1, edge_start + period_max)

        edge_data = df.iloc[edge_start:edge_end]

        # Find consolidation candidates
        # Look for periods where high is close to handle_level, price consolidates, and volume shrinks
        candidates = []

        for i in range(5, len(edge_data) - 5):
            window = edge_data.iloc[i-5:i + 10]
            window_high = window['high'].max()
            window_low = window['low'].min()
            window_close = window['close'].iloc[-1]

            # Check if high is near handle level
            price_range = (window_high - window_low) / window_low
            if price_range > 0.15:
                continue  # Too much variation

            # Check if close is near handle level
            handle_distance = abs(window_close - handle_level) / handle_level
            if handle_distance > 0.05:
                continue  # Too far from handle level

            # Check consolidation (flat movement)
            close_prices = window['close']
            price_std = close_prices.std()
            price_mean = close_prices.mean()

            # Consolidation quality: lower std = better
            consolidation_quality = max(0, 1 - (price_std / price_mean))

            # Check volume shrinkage
            if params.get('volume_shrink', False):
                vol_shrink_pct = 1.0
            else:
                # Compare volume in edge window vs right wall
                vol_edge = window['volume'].mean()
                vol_prev = df.iloc[max(0, edge_start - 10):edge_start]['volume'].mean()
                if vol_prev > 0:
                    vol_shrink_pct = min(1.0, vol_edge / vol_prev)
                else:
                    vol_shrink_pct = 1.0

            # Check for dip before consolidation
            window_before = edge_data.iloc[i-5:i]
            window_before_close = window_before['close'].iloc[-1]
            window_low = window['low'].min()
            max_dip_pct = (window_before_close - window_low) / window_before_close

            # Check for max rise during consolidation (should be minimal)
            window_max_rise_pct = (window['high'].max() - window['low'].min()) / window['low'].min()

            # All criteria met?
            if (max_dip_pct <= max_drop_pct and
                max_dip_pct >= min_drop_pct and
                window_max_rise_pct <= max_rise_pct):

                candidates.append({
                    'idx': i + 10,
                    'consolidation_quality': consolidation_quality,
                    'vol_shrink_pct': vol_shrink_pct,
                    'max_dip_pct': max_dip_pct,
                    'window_high': window_high,
                    'window_close': window_close,
                    'days_consolidating': 10
                })

        if len(candidates) == 0:
            return CupEdgeResult(detected=False, quality=0, start_idx=0, end_idx=0, high_price=0, current_price=0,
                           days_consolidating=0, consolidation_quality=0, volume_shrink_pct=0, max_dip_pct=0, target_days=0)

        # Select best candidate
        best = max(candidates, key=lambda x: (
            x['consolidation_quality'] * 0.4 +
            (1 - x['vol_shrink_pct']) * 0.3 +
            (1 - x['max_dip_pct']) * 0.3
        ))

        current_price = df.iloc[-1]['close']
        current_high = df.iloc[-1]['high']
        price_closeness = abs(current_price - handle_level) / handle_level

        # Calculate quality score
        quality = (
            best['consolidation_quality'] * 0.5 +
            (1 - best['vol_shrink_pct']) * 0.3 +
            (1 - best['max_dip_pct']) * 0.2 +
            (1 - min(price_closeness, 0.3)) * 0.2  # Small bonus for being close to handle level
        )

        # Estimate days to complete
        # Base on typical 60-80 day formation, edge is 20-30%
        remaining_pct = 0.3  # Estimated remaining (consolidation + break out)
        target_days = int(60 * remaining_pct)

        return CupEdgeResult(
            detected=True,
            quality=quality,
            start_idx=best['idx'] - 10,
            end_idx=best['idx'],
            high_price=handle_level,
            current_price=current_price,
            days_consolidating=10,
            consolidation_quality=best['consolidation_quality'],
            volume_shrink_pct=best['vol_shrink_pct'],
            max_dip_pct=best['max_dip_pct'],
            target_days=target_days
        )

    def calculate_china_aware_probability(
        self,
        code: str,
        cup_edge: CupEdgeResult,
        sentiment: SentimentAnalysis,
        capital: CapitalStructure
        end_date: str = None
    ) -> Dict:
        """
        Calculate China A-share aware probability

        Formula:
        Probability = Base % × Π(Adjustment Factor Multiplier)

        Base = 50% (cup_edge detected and consolidating)
        Factors:
        1. Volume sentiment (0.25x) - 量能
        2. Capital structure (0.20x) - 散户vs机构
        3. Limit-up proximity (0.15x) - 涨停板情绪
        4. Trend alignment (0.10x) - 趋势
        5. RS strength (0.15x) - 相对强度
        """
        formula_params = self.config['probability_formula']

        # Base probability
        if cup_edge.detected and cup_edge.quality > 0.5:
            base_prob = 50 + (cup_edge.quality - 0.5) * 30  # 50-80%
        elif cup_edge.detected:
            base_prob = 30 + cup_edge.quality * 20  # 30-50%
        else:
            base_prob = 0

        # Initialize multipliers
        multipliers = {}

        # Apply enabled factors
        for factor in formula_params['adjustment_factors']:
            if not factor['enabled']:
                continue

            factor_name = factor['name']
            multiplier = 1.0

            if factor_name == 'volume_sentiment':
                if sentiment.sentiment_score > 0.7:
                    multiplier = factor['max_value']
                elif sentiment.sentiment_score > 0.5:
                    multiplier = factor['min_value'] + (factor['max_value'] - factor['min_value']) * 0.6
                elif sentiment.sentiment_score > 0.3:
                    multiplier = 1.0
                else:
                    multiplier = factor['min_value']

            elif factor_name == 'capital_structure':
                if capital.capital_structure == 'retail_heavy' and sentiment.avg_turnover > 5:
                    multiplier = factor['max_value']  # 1.4x for high-activity retail
                elif capital.capital_structure == 'retail_heavy':
                    multiplier = factor['min_value'] + (factor['max_value'] - factor['min_value']) * 0.5  # 1.1x
                elif capital.capital_structure == 'institution_heavy':
                    multiplier = factor['min_value']  # 0.7x
                elif capital.capital_structure == 'mixed':
                    multiplier = 1.0

            elif factor_name == 'limit_up_proximity':
                if sentiment.limit_up_level == 'high':
                    multiplier = factor['max_value']  # 1.3x
                elif sentiment.limit_up_level == 'medium':
                    multiplier = factor['min_value'] + (factor['max_value'] - factor['min_value']) * 0.6  # 1.1x
                else:
                    multiplier = factor['min_value']  # 0.9x

            elif factor_name == 'trend_alignment':
                # Need to calculate MA alignment
                df = self._get_stock_data(code, end_date)
                if len(df) >= 200:
                    ma50 = df['close'].rolling(50).mean().iloc[-1]
                    ma150 = df['close'].rolling(150).mean().iloc[-1]
                    ma200 = df['close'].rolling(200).mean().iloc[-1]
                    ma_trend = (ma50 > ma150 > ma200)
                    if ma_trend:
                        multiplier = factor['max_value']  # 1.2x
                    else:
                        multiplier = factor['min_value']  # 0.8x
                else:
                    multiplier = 1.0

            elif factor_name == 'rs_strength':
                # Simplified RS calculation
                # If strong relative performance, use higher multiplier
                if sentiment.sentiment_score > 0.6 and sentiment.vol_vs_avg > 1.0:
                    multiplier = factor['max_value']  # 1.3x
                elif sentiment.sentiment_score > 0.4:
                    multiplier = factor['min_value'] + (factor['max_value'] - factor['min_value'])  # 1.05x
                else:
                    multiplier = 1.0

            elif factor_name in ['cycle_stage', 'sector_policy', 'geopolitics']:
                # Disabled for now (no data)
                continue

            multipliers[factor_name] = multiplier

        # Calculate final probability
        probability = base_prob
        for factor_name, factor_config in formula_params['adjustment_factors']:
            if factor_name in multipliers:
                probability = probability * multipliers[factor_name]

        # Clamp to 0-100
        probability = max(0, min(100, probability))

        return {
            'base_prob': base_prob,
            'multipliers': multipliers,
            'probability': probability,
            'meets_threshold': probability >= formula_params['prediction_threshold']
        }

    def analyze_stock(self, code: str, end_date: str = None) -> WizardPrediction:
        """
        Analyze a single stock for coffee cup formation progress

        Returns: WizardPrediction object with all factors
        """
        # Load data
        df = self._get_stock_data(code, end_date)
        metadata = self._get_stock_metadata(code)

        if len(df) < 30:
            return WizardPrediction(
                code=code,
                name=metadata['name'],
                completion_pct=0,
                base_probability=0,
                adjusted_probability=0,
                stage='insufficient_data',
                components={},
                factors={},
                target_days=0,
                prediction_date=end_date or datetime.now().strftime('%Y-%m-%d')
            )

        # Analyze components
        sentiment = self.analyze_volume_sentiment(df, self.config['sentiment_params'])
        capital = self.analyze_capital_structure(df, self.config['capital_structure_params'])

        # Detect cup edge
        cup_edge = self.detect_cup_edge(df, self.config['component_params']['cup_edge'], handle_info=None)

        # Calculate probability
        prob_result = self.calculate_china_aware_probability(
            code=code,
            cup_edge=cup_edge,
            sentiment=sentiment,
            capital=capital,
            stock_metadata=metadata,
            end_date=end_date
        )

        # Determine stage
        if not cup_edge.detected:
            stage = 'no_cup_edge'
        elif cup_edge.days_consolidating >= 7:
            stage = 'cup_edge_consolidating'
        elif sentiment.sentiment_score > 0.7:
            stage = 'edge_ready_high_sentiment'
        elif sentiment.vol_vs_avg > 1.2:
            stage = 'edge_ready_high_volume'
        elif capital.capital_structure == 'retail_heavy':
            stage = 'edge_ready_retail_active'
        else:
            stage = 'edge_forming'

        # Build components dict
        components = {
            'cup_edge': {
                'detected': cup_edge.detected,
                'quality': cup_edge.quality,
                'current_price': cup_edge.current_price,
                'handle_level': cup_edge.high_price
                'days_consolidating': cup_edge.days_consolidating
            },
            'sentiment': {
                'score': sentiment.sentiment_score,
                'vol_trend': sentiment.vol_trend,
                'vol_vs_avg': sentiment.vol_vs_avg,
                'avg_turnover': sentiment.avg_turnover,
                'volume_spikes': sentiment.volume_spikes,
                'limit_up_level': sentiment.limit_up_level,
                'limit_up_proximity': sentiment.limit_up_proximity
            },
            'capital': {
                'structure': capital.capital_structure,
                'retail_dominance': capital.retail_dominance,
                'volatility': capital.volatility,
                'vol_consistency': capital.vol_consistency
            }
        }

        # Calculate target days
        if cup_edge.detected and cup_edge.quality > 0.6:
            target_days = cup_edge.target_days
        elif cup_edge.detected:
            target_days = int(cup_edge.target_days * 1.5)  # Lower quality takes longer
        else:
            target_days = 90  # Default if no edge detected

        return WizardPrediction(
            code=code,
            name=metadata['name'],
            completion_pct=prob_result['probability'],
            base_probability=prob_result['base_prob'],
            adjusted_probability=prob_result['probability'],
            stage=stage,
            components=components,
            factors=prob_result['multipliers'],
            target_days=target_days,
            prediction_date=end_date or datetime.now().strftime('%Y-%m-%d')
        )

    def batch_analyze(self, codes: List[str], end_date: str = None, limit: int = 100) -> List[WizardPrediction]:
        """Analyze multiple stocks in batch"""
        predictions = []
        processed = 0

        for code in codes:
            try:
                pred = self.analyze_stock(code, end_date)
                if pred.adjusted_probability >= self.config['probability_formula']['prediction_threshold']:
                    predictions.append(pred)

                processed += 1

                if processed % 10 == 0:
                    logger.info(f"Processed {processed}/{len(codes)} stocks")

            except Exception as e:
                logger.warning(f"Error analyzing {code}: {e}")

        # Sort by adjusted probability (descending)
        predictions.sort(key=lambda x: x.adjusted_probability, reverse=True)

        return predictions[:limit]

    def get_top_predictions(self, limit: int = 50) -> List[Dict]:
        """Get top N predictions in dict format for API"""
        predictions = self.batch_analyze(self._get_all_stock_codes(), limit=limit)
        return [
            {
                'code': pred.code,
                'name': pred.name,
                'probability': pred.adjusted_probability,
                'stage': pred.stage,
                'components': {
                    'cup_edge': pred.components['cup_edge'],
                    'sentiment': pred.components['sentiment'],
                    'capital': pred.components['capital']
                },
                'target_days': pred.target_days
            }
            for pred in predictions
        ]

    def _get_all_stock_codes(self) -> List[str]:
        """Get all stock codes from database"""
        conn = sqlite3.connect(self.db_path)
        query = "SELECT code FROM stocks ORDER BY code"
        codes = pd.read_sql_query(query, conn)['code'].tolist()
        conn.close()
        return codes


if __name__ == '__main__':
    # Test with a single stock
    wizard = CoffeeCupWizard()

    # Example: Analyze a stock
    predictions = wizard.batch_analyze(['600519'], limit=10)

    print("Coffee Cup Wizard - China A-Share Predictive Model")
    print(f"=" * 50)
    for pred in predictions:
        print(f"{pred.code} ({pred.name}): {pred.adjusted_probability:.1f}%")
        print(f"  Stage: {pred.stage}")
        print(f"  Sentiment: {pred.components['sentiment']['score']:.2f}")
        print(f"  Capital: {pred.components['capital']['structure']}")
        print(f"  Target: {pred.target_days} days")
        print("-" * 50)
