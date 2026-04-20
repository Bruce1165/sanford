/**
 * Robust Date Utilities - Bulletproof date handling
 * All dates are handled as YYYY-MM-DD internally
 */

/**
 * Get today's date in YYYY-MM-DD format
 */
export function getToday(): string {
  return new Date().toISOString().split('T')[0];
}

/**
 * Get yesterday's date in YYYY-MM-DD format
 */
export function getYesterday(): string {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d.toISOString().split('T')[0];
}

/**
 * Format screener name to Chinese display name
 */
export function formatScreenerName(screenerName: string): string {
  const displayNameMap: Record<string, string> = {
    'lao_ya_tou_zhou_xian_v2_fixed': '老鸭头周线筛选器',
    'lao_ya_tou_zhou_xian_simple': '老鸭头周线筛选器（简化版）',
    'lao_ya_tou_zhou_xian': '老鸭头周线筛选器',
    'coffee_cup_handle_screener_v4': 'V4 咖啡杯柄筛选器',
    'er_ban_hui_tiao': '测试筛选器',
    'breakout_20day': '20日突破筛选器',
    'daily_hot_cold': '每日冷热筛选器'
  };

  return displayNameMap[screenerName] || screenerName;
}

/**
 * Ensure a date string is in YYYY-MM-DD format
 * Handles: Date objects, YYYY-MM-DD, YYYY/MM/DD, YYYYMMDD, timestamps
 */
export function toISODate(date: string | Date | number): string {
  if (!date) return '';
  
  // Already in YYYY-MM-DD format
  if (typeof date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return date;
  }
  
  // YYYY/MM/DD format - convert to YYYY-MM-DD
  if (typeof date === 'string' && /^\d{4}\/\d{2}\/\d{2}$/.test(date)) {
    return date.replace(/\//g, '-');
  }
  
  // YYYYMMDD format
  if (typeof date === 'string' && /^\d{8}$/.test(date)) {
    return `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`;
  }
  
  // Date object - use LOCAL date methods (not UTC!)
  const d = date instanceof Date ? date : new Date(date);
  if (!isNaN(d.getTime())) {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }
  
  console.warn('Invalid date:', date);
  return '';
}

/**
 * Format a date for display (localized)
 */
export function formatDisplayDate(date: string | Date): string {
  const isoDate = toISODate(date);
  if (!isoDate) return '';
  
  const [year, month, day] = isoDate.split('-');
  // Return in local format: YYYY/MM/DD for CN, MM/DD/YYYY for US, etc.
  const locale = navigator.language || 'zh-CN';
  if (locale.startsWith('zh')) {
    return `${year}/${month}/${day}`;
  }
  return `${month}/${day}/${year}`;
}

/**
 * Validate if string is a valid date (YYYY-MM-DD format)
 */
export function isValidDate(date: string): boolean {
  if (!date || typeof date !== 'string') return false;
  
  // Check format
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return false;
  
  // Check if valid date
  const d = new Date(date);
  return !isNaN(d.getTime());
}

/**
 * Format date for API calls - always returns YYYY-MM-DD
 * This is the SINGLE function used before all API calls
 */
export function formatDate(date: string | Date): string {
  return toISODate(date);
}

/**
 * Get the most recent trading day
 * Skips weekends (Saturday=6, Sunday=0)
 * Returns YYYY-MM-DD format
 */
export function getLastTradingDay(): string {
  const d = new Date();
  const dayOfWeek = d.getDay();
  
  // If Sunday (0), go back 2 days to Friday
  if (dayOfWeek === 0) {
    d.setDate(d.getDate() - 2);
  }
  // If Saturday (6), go back 1 day to Friday
  else if (dayOfWeek === 6) {
    d.setDate(d.getDate() - 1);
  }
  // Otherwise, use yesterday (standard behavior)
  else {
    d.setDate(d.getDate() - 1);
  }
  
  // Use local date methods to avoid UTC issues
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Ensure a date is a valid trading day (not weekend)
 * If the date falls on a weekend, returns the previous Friday
 */
export function ensureTradingDay(date: string): string {
  const isoDate = toISODate(date);
  if (!isoDate) return getLastTradingDay();
  
  const d = new Date(isoDate);
  const dayOfWeek = d.getDay();
  
  // If Sunday (0), go back 2 days to Friday
  if (dayOfWeek === 0) {
    d.setDate(d.getDate() - 2);
  }
  // If Saturday (6), go back 1 day to Friday
  else if (dayOfWeek === 6) {
    d.setDate(d.getDate() - 1);
  }
  
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Get default date (last trading day) for screener runs
 */
export function getDefaultDate(): string {
  return getLastTradingDay();
}

/**
 * Format stock code - remove .SH/.SZ suffix, ensure 6 digits
 */
export function formatStockCode(code: string): string {
  if (!code) return '';
  
  const str = String(code).trim();
  const clean = str.replace(/\.(SH|SZ)$/i, '');

  if (/^\d{6}$/.test(clean)) {
    return clean;
  }
  
  console.warn('Invalid stock code:', code);
  return clean;
}

/**
 * Validate stock code format (6 digits)
 */
export function isValidStockCode(code: string): boolean {
  return /^\d{6}$/.test(formatStockCode(code));
}

/**
 * Convert to iFind format (adds .SH or .SZ)
 */
export function toIfindCode(code: string): string {
  const clean = formatStockCode(code);
  if (!clean) return '';
  return clean.startsWith('6') ? `${clean}.SH` : `${clean}.SZ`;
}

/**
 * Parse date from input value
 * Handles browser inconsistencies with date inputs
 */
export function parseDateInput(value: string): string {
  // HTML5 date input should return YYYY-MM-DD
  // But some browsers might return localized format
  return toISODate(value);
}

/**
 * Get max date for date input (today)
 */
export function getMaxDate(): string {
  return getToday();
}

/**
 * Get min date for date input
 */
export function getMinDate(): string {
  return '2024-01-01';
}
