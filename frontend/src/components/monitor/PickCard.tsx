import React from 'react';
import 'index.css';

interface DailyCheck {
  day: number;
  date: string;
  status: string;
  close_price?: number;
  note?: string;
}

interface Pick {
  id: number;
  screener_id: string;
  stock_code: string;
  stock_name?: string;
  industry?: string;
  market_cap?: number;
  pe?: number;
  pct_change?: number;
  entry_date: string;
  entry_price: number;
  expected_exit_date: string;
  status: 'active' | 'graduated' | 'failed';
  exit_date?: string;
  exit_reason?: string;
  daily_checks: DailyCheck[];
  created_at: string;
  cup_rim_price?: number;
  cup_bottom_price?: number;
  max_price_seen?: number;
}

interface PickCardProps {
  pick: Pick;
  onClick?: (pick: Pick) => void;
}

export const PickCard: React.FC<PickCardProps> = ({ pick, onClick }) => {
  // Calculate current day
  const currentDay = pick.daily_checks?.length || 0;
  const totalDays = 25;
  
  // Get latest price and performance
  const latestCheck = pick.daily_checks?.[pick.daily_checks.length - 1];
  const currentPrice = latestCheck?.close_price || pick.entry_price;
  const performance = pick.entry_price > 0 
    ? ((currentPrice - pick.entry_price) / pick.entry_price * 100)
    : 0;
  
  // Determine status badge
  const getStatusBadge = () => {
    switch (pick.status) {
      case 'graduated':
        return { icon: '🎓', label: 'Graduated', className: 'badge-graduated' };
      case 'failed':
        return { icon: '✗', label: 'Failed', className: 'badge-failed' };
      default:
        return { icon: '✓', label: 'Active', className: 'badge-active' };
    }
  };
  
  const statusBadge = getStatusBadge();
  
  // Determine performance color
  const getPerformanceColor = () => {
    if (performance > 0) return 'positive';
    if (performance < 0) return 'negative';
    return 'neutral';
  };
  
  // Get failure line for coffee cup
  const failureLine = pick.cup_rim_price && pick.cup_bottom_price
    ? (pick.cup_rim_price + pick.cup_bottom_price) / 2
    : null;
  
  return (
    <div 
      className={`pick-card ${pick.status}`}
      onClick={() => onClick?.(pick)}
    >
      {/* Header */}
      <div className="pick-card-header">
        <div className="stock-info">
          <span className="stock-code">{pick.stock_code}</span>
          {pick.stock_name && pick.stock_name !== '-' && (
            <span className="stock-name">{pick.stock_name}</span>
          )}
          <span className={`status-badge ${statusBadge.className}`}>
            {statusBadge.icon} {statusBadge.label}
          </span>
        </div>
        <div className="day-counter">
          Day <strong>{currentDay}</strong>/{totalDays}
        </div>
      </div>
      {/* 6-field fundamentals row */}
      <div className="pick-fundamentals">
        <span className="fund-item">
          <span className="fund-lbl">行业</span>
          <span className="fund-val">{pick.industry && pick.industry !== '-' ? pick.industry.substring(0,6) : '–'}</span>
        </span>
        <span className="fund-item">
          <span className="fund-lbl">市值</span>
          <span className="fund-val">{pick.market_cap ? (pick.market_cap >= 1e8 ? (pick.market_cap/1e8).toFixed(0)+'亿' : (pick.market_cap/1e4).toFixed(0)+'万') : '–'}</span>
        </span>
        <span className="fund-item">
          <span className="fund-lbl">PE</span>
          <span className="fund-val">{pick.pe != null ? Number(pick.pe).toFixed(1) : '–'}</span>
        </span>
        <span className="fund-item">
          <span className="fund-lbl">今日</span>
          <span className="fund-val" style={{
            color: pick.pct_change == null ? 'rgba(255,255,255,0.4)'
              : pick.pct_change > 0 ? '#00e676'
              : pick.pct_change < 0 ? '#ff4757'
              : 'rgba(255,255,255,0.4)'
          }}>
            {pick.pct_change != null ? (pick.pct_change > 0 ? '+' : '') + pick.pct_change.toFixed(2) + '%' : '–'}
          </span>
        </span>
      </div>
      
      {/* Price Info */}
      <div className="pick-card-body">
        <div className="price-row">
          <div className="price-item">
            <span className="price-label">Entry</span>
            <span className="price-value">¥{pick.entry_price.toFixed(2)}</span>
          </div>
          <div className="price-item">
            <span className="price-label">Current</span>
            <span className="price-value">¥{currentPrice.toFixed(2)}</span>
          </div>
          <div className="price-item">
            <span className="price-label">Perf</span>
            <span className={`price-value performance ${getPerformanceColor()}`}>
              {performance >= 0 ? '+' : ''}{performance.toFixed(1)}%
            </span>
          </div>
        </div>
        
        {/* Progress Bar */}
        <div className="progress-container">
          <div className="progress-bar">
            <div 
              className={`progress-fill ${pick.status}`}
              style={{ width: `${(currentDay / totalDays) * 100}%` }}
            />
          </div>
          <span className="progress-text">{Math.round((currentDay / totalDays) * 100)}%</span>
        </div>
        
        {/* Coffee Cup Specific Info */}
        {pick.screener_id === 'coffee_cup_screener' && (pick.cup_rim_price || pick.cup_bottom_price) && (
          <div className="cup-pattern-info">
            <div className="cup-row">
              {pick.cup_rim_price && (
                <span className="cup-item rim">
                  <span className="cup-label">Rim</span>
                  <span className="cup-value">¥{pick.cup_rim_price.toFixed(2)}</span>
                </span>
              )}
              {pick.cup_bottom_price && (
                <span className="cup-item bottom">
                  <span className="cup-label">Bottom</span>
                  <span className="cup-value">¥{pick.cup_bottom_price.toFixed(2)}</span>
                </span>
              )}
              {failureLine && (
                <span className="cup-item failure">
                  <span className="cup-label">Fail Line</span>
                  <span className="cup-value">¥{failureLine.toFixed(2)}</span>
                </span>
              )}
            </div>
          </div>
        )}
        
        {/* Latest Note */}
        {latestCheck?.note && (
          <div className="latest-note">
            <span className="note-label">Latest:</span>
            <span className="note-text" title={latestCheck.note}>
              {latestCheck.note.length > 40 ? latestCheck.note.substring(0, 40) + '...' : latestCheck.note}
            </span>
          </div>
        )}
      </div>
      
      {/* Footer */}
      <div className="pick-card-footer">
        <span className="entry-date">Entered: {pick.entry_date}</span>
        {pick.max_price_seen && pick.max_price_seen > pick.entry_price && (
          <span className="max-price">Max: ¥{pick.max_price_seen.toFixed(2)}</span>
        )}
      </div>
    </div>
  );
};

export default PickCard;
