/**
 * API Client — 统一类型化 API 层
 *
 * 修复记录：
 * - fix(C2): 密码从 neo123 统一为 NeoTrade123（与 App.tsx/MonitorV2.tsx 一致，原来 401 必现）
 * - fix(C3): getResults 端点从不存在的 /screeners/{name}/results 改为正确的 /results?screener=...&date=...
 * - fix: 错误信息更具体，包含 HTTP 状态码和响应片段
 */

export interface Screener {
  id: number;
  name: string;
  display_name: string;
  description: string;
  category: string;
  file_path: string;
  schedule: string;
  created_at: string;
  updated_at: string;
}

export interface Modules {
  screeners: {
    items: string[];
    displayNames: Record<string, string>;
    title: string;
  };
  cron: {
    items: string[];
    displayNames: Record<string, string>;
    schedules: Record<string, string>;
    title: string;
  };
}

export interface CheckResult {
  match: boolean;
  code: string;
  name: string;
  date: string;
  reasons: string[];
  details?: Record<string, any>;
  risk_management?: Record<string, string>;
}

// API 配置：开发时走 Vite proxy（/api → localhost:5003），生产时走同域
// Backend API configuration
// Use proxy in development, auto-detect in production
const isDev = (import.meta as any).env?.DEV === 'true';
const API_BASE = isDev ? '/api' : `${window.location.origin}/api`;

/**
 * 通用请求函数（含完善的错误处理）
 */
export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Basic ' + btoa('admin:NeoTrade123'),
      ...(options.headers as Record<string, string> || {}),
    },
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => '');
    throw new Error(`API ${response.status}: ${errorText.substring(0, 120) || response.statusText}`);
  }

  return response.json();
}

/** API 函数集合 */
export const api = {
  /** 获取所有筛选器列表 */
  getScreeners: () =>
    apiRequest<{ screeners: Screener[]; modules: Modules }>('/screeners'),

  /** 触发运行某筛选器 */
  runScreener: (name: string, date?: string) =>
    apiRequest<{ success: boolean; run_id: number; stocks_found: number; message: string }>(
      `/screeners/${name}/run`,
      { method: 'POST', body: JSON.stringify({ date }) }
    ),

  /** 检查单个股票是否命中某筛选器 */
  checkStock: (screener: string, code: string, date?: string) =>
    apiRequest<CheckResult>('/check-stock', {
      method: 'POST',
      body: JSON.stringify({ screener, code, date }),
    }),

  /**
   * 获取筛选结果
   * fix(C3): 原来调用 /screeners/{name}/results，该路由后端根本不存在（404）
   * 正确端点是 /results?screener=...&date=...
   */
  getResults: (name: string, date: string) =>
    apiRequest<{ results: any[]; count: number; screener: string; date: string }>(
      `/results?screener=${encodeURIComponent(name)}&date=${encodeURIComponent(date)}`
    ),

  /** 获取策略回测列表 */
  getBacktests: () =>
    apiRequest<{ backtests: any[]; count: number }>('/strategy/backtests'),

  /** 获取指定回测的交易明细 */
  getBacktestTrades: (id: number) =>
    apiRequest<{ trades: any[]; summary: any }>(`/strategy/trades/${id}`),

  /** 获取日历数据 */
  getCalendar: () =>
    apiRequest<{ calendar: any[] }>('/calendar'),

  /** 获取访问统计 */
  getAccessStats: () =>
    apiRequest<{ success: boolean; data: { today: { date: string; unique_visitors: number }; this_month: { start_date: string; end_date: string; unique_visitors: number } } }>('/stats/access'),

  /**
   * 健康检查（无需 Auth，后端有豁免）
   * 注意：不走 apiRequest，因为 /api/health 不要求认证头
   */
  health: () =>
    fetch(`${API_BASE}/health`).then(r => {
      if (!r.ok) throw new Error(`Health check failed: ${r.status}`);
      return r.json() as Promise<{ status: string; timestamp: string }>;
    }),
};
