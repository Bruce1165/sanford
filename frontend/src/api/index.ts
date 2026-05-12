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

export interface CupHandleLabAlignmentResponse {
  meta: {
    target_date: string;
    latest_v4_date: string | null;
    latest_v42_date: string | null;
    latest_common_date: string | null;
    candidate_dates?: Array<{
      date: string;
      v4_count: number;
      v42_base_count: number;
      v42_hardened_count: number;
    }>;
  };
  counts: {
    v4_count: number;
    v42_base_count: number;
    v42_hardened_count: number;
    overlap_base_count: number;
    overlap_hardened_count: number;
  };
  ratios: {
    hardened_vs_v4: number;
    hardened_vs_base: number;
    base_vs_v4: number;
  };
  quality: {
    base_success_rate: number;
    hardened_success_rate: number;
    delta_success_rate: number;
  };
  warnings: string[];
  samples: {
    only_v4: Array<{ stock_code: string; stock_name: string }>;
    only_v42_hardened: Array<{ stock_code: string; stock_name: string }>;
    intersection_hardened: Array<{ stock_code: string; stock_name: string }>;
  };
}

export interface CupHandleLabV4PoolCompareResponse {
  meta: {
    target_date: string;
    requested_date?: string | null;
    latest_v4_run_date?: string | null;
    latest_trade_date?: string | null;
    fallback_to_effective_trade_date?: boolean;
    candidate_dates: string[];
    market_state: string;
    route_cluster_id: string;
    route_desc: string;
    lab_mode: string;
  };
  counts: {
    v4_count: number;
    v42_base_count: number;
    v42_hardened_count: number;
  };
  ratios: {
    base_vs_v4: number;
    hardened_vs_v4: number;
    hardened_vs_base: number;
  };
  quality: {
    label_spec: { strength: number; drawdown: number; up_days_min: number };
    base_ready_n: number;
    base_success_n: number;
    base_success_rate: number;
    hard_ready_n: number;
    hard_success_n: number;
    hard_success_rate: number;
    delta_success_rate: number;
  };
  process: {
    route_miss: number;
    hard_fail: number;
    base_pass: number;
    hard_pass: number;
  };
  samples: {
    kept_top: Array<{ stock_code: string; stock_name: string; segment_id: string; dynamic_score: number; gate_count: number }>;
    removed_top: Array<{ stock_code: string; stock_name: string; segment_id: string; dynamic_score: number; gate_count: number }>;
  };
  delivery_pool: {
    limit: number;
    v4_today: Array<{
      signal_date: string;
      stock_code: string;
      stock_name: string;
      segment_id: string;
      gate_count: number;
      enhancement_score: number;
      industry?: string;
      sector_lv1?: string;
      sector_lv2?: string;
      history_cup_n?: number | null;
      history_success_n?: number | null;
      history_success_rate?: number | null;
      history_has_success?: boolean | null;
    }>;
    v42_base_today: Array<{
      signal_date: string;
      stock_code: string;
      stock_name: string;
      segment_id: string;
      dynamic_score: number;
      gate_count: number;
      route: string;
      industry?: string;
      sector_lv1?: string;
      sector_lv2?: string;
      history_cup_n?: number | null;
      history_success_n?: number | null;
      history_success_rate?: number | null;
      history_has_success?: boolean | null;
    }>;
    v42_hardened_today: Array<{
      signal_date: string;
      stock_code: string;
      stock_name: string;
      segment_id: string;
      dynamic_score: number;
      gate_count: number;
      route: string;
      industry?: string;
      sector_lv1?: string;
      sector_lv2?: string;
      history_cup_n?: number | null;
      history_success_n?: number | null;
      history_success_rate?: number | null;
      history_has_success?: boolean | null;
    }>;
  };
  history_tail: Array<{
    run_date: string;
    market_state: string;
    v4_count: number;
    v42_base_count: number;
    v42_hardened_count: number;
    keep_rate_base: number;
    keep_rate_hardened: number;
    base_ready_n: number;
    base_success_n: number;
    base_success_rate: number;
    hard_ready_n: number;
    hard_success_n: number;
    hard_success_rate: number;
    delta_success_rate: number;
  }>;
  warnings: string[];
}

export interface CupHandleLabFeedbackItem {
  id: number;
  created_at: string;
  stock_code: string;
  stock_name: string;
  signal_date: string;
  main_view: string;
  delivery_view: string;
  q1_should_enter: 'should' | 'should_not' | 'unsure' | string;
  q2_reasons: string[];
  q3_primary_risk: 'shape' | 'volume' | 'market' | 'sector' | 'risk_reward' | string;
  q4_horizon: 't5' | 't8' | 't13' | string;
  q5_drawdown_tolerance: 'low' | 'mid' | 'high' | string;
}

export interface CupHandleLabFeedbackListResponse {
  items: CupHandleLabFeedbackItem[];
  limit: number;
  offset: number;
}

export interface CupHandleLabFeedbackSubmitRequest {
  stock_code: string;
  stock_name?: string;
  signal_date?: string;
  main_view?: 'delivery' | 'replay' | string;
  delivery_view?: 'hardened' | 'v4' | string;
  q1_should_enter: 'should' | 'should_not' | 'unsure';
  q2_reasons?: string[];
  q3_primary_risk?: 'shape' | 'volume' | 'market' | 'sector' | 'risk_reward';
  q4_horizon?: 't5' | 't8' | 't13';
  q5_drawdown_tolerance?: 'low' | 'mid' | 'high';
}

export interface CupHandleLabFeedbackSubmitResponse {
  ok: boolean;
  feedback_id?: number;
}

export interface CupHandleLabDailyBriefResponse {
  meta: {
    target_date: string;
    prev_date: string | null;
    available_dates: string[];
    latest_updated_at?: string | null;
  };
  daily_action: {
    observe_pool_n: number;
    new_watch_n: number;
    feedback_processed_n: number;
  };
  forward_summary: {
    t8_success_rate: number;
    t8_success_rate_prev: number;
    t8_success_trend: '升' | '降' | '震荡' | string;
    avg_return_t8: number | null;
    avg_drawdown_t1_t8: number | null;
    validated_sample_n: number;
  };
  reverse_findings: {
    top_risks: Array<{ risk: string; count: number }>;
  };
  model_iteration: {
    param_update_n: number | null;
    entry_improve_pct: number | null;
    note?: string;
  };
  strategy_audit?: {
    run_date?: string | null;
    decision: 'keep' | 'observe' | 'rollback' | string;
    decision_reason?: string;
    delta_success_rate_pp?: number | null;
    drawdown_delta_pp?: number | null;
    ready_n?: number | null;
    min_ready_n?: number;
    baseline_version?: string;
    candidate_version?: string;
    drawdown_threshold_pp?: number | null;
    drawdown_gate_status?: 'pending_data' | 'pass' | 'fail' | string;
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

export interface AssistantPoolCommonalitiesResponse {
  filters: {
    processed: string;
    start_date: string | null;
    end_date: string | null;
    top: number;
    sample: number;
  };
  pool: {
    rows: number;
    unique_stocks: number;
    processed_rows: number;
    unprocessed_rows: number;
    min_start_date: string | null;
    max_end_date: string | null;
    avg_window_days: number | null;
  };
  top_files: Array<{ file_name: string; count: number }>;
  sector_lv1_top: Array<{ sector_lv1: string; stock_count: number }>;
  price_performance: {
    sample_stocks: number;
    sample_with_prices: number;
    return_pct: {
      mean: number | null;
      p0: number | null;
      p25: number | null;
      p50: number | null;
      p75: number | null;
      p100: number | null;
    };
  };
}

export interface AssistantParamOverrideItem {
  param: string;
  default: any;
  current: any;
  display_name?: string | null;
  description?: string | null;
  group?: string | null;
  type?: string | null;
}

export interface AssistantFiveFlagsParameterOverridesResponse {
  screeners: Array<{
    screener: string;
    display_name?: string | null;
    category?: string | null;
    version?: string | null;
    updated_at?: string | null;
    schema_param_count: number;
    override_count: number;
    overrides: AssistantParamOverrideItem[];
    error?: string;
  }>;
  phase_profiles: any;
}

export interface AssistantLaoYaTouLabelSummaryResponse {
  filters: {
    start_date: string | null;
    end_date: string | null;
    top: number;
  };
  labels: {
    rows: number;
    unique_stocks: number;
    unique_label_dates: number;
    min_label_date: string | null;
    max_label_date: string | null;
  };
  by_label_date: Array<{ label_date: string; rows: number; stocks: number }>;
}

export interface AssistantLaoYaTouBaselineEvalResponse {
  filters: {
    start_date: string | null;
    end_date: string | null;
    max_dates: number;
    max_stocks_per_date: number;
  };
  params: Record<string, any>;
  baseline: {
    label_dates: string[];
    samples: number;
    stage1_hits: number;
    stage2_hits: number;
    stage1_recall: number | null;
    stage2_recall: number | null;
    data_missing: number;
    errors: number;
    by_signal: Record<string, number>;
  };
  by_label_date: Array<{
    label_date: string;
    samples: number;
    stage1_hits: number;
    stage2_hits: number;
    data_missing: number;
    errors: number;
    by_signal: Record<string, number>;
  }>;
}

export interface AssistantLaoYaTouDailyCompareResponse {
  requested_date: string;
  trade_date: string;
  non_trading_day?: boolean;
  our_screener: {
    computed: boolean;
    processed_stocks: number;
    errors: number;
    max_stocks: number;
    count: number;
    by_signal: Record<string, number>;
  };
  tdx_upload: {
    count: number;
    by_file: Array<{ file_name: string; count: number }>;
  };
  compare: {
    intersection_count: number;
    ours_only_count: number;
    tdx_only_count: number;
    precision: number | null;
    recall: number | null;
    jaccard: number | null;
  };
  codes?: {
    intersection: string[];
    ours_only: string[];
    tdx_only: string[];
  };
}

export interface AssistantRuleSourceRef {
  ref: string;
  title: string;
}

export interface AssistantRulesTraceItem {
  rule_id: string;
  rule_name: string;
  source: AssistantRuleSourceRef;
  predicate: string;
  result: boolean;
  evidence: Record<string, any>;
  conclusion: string;
}

export interface AssistantRulesWhyStep {
  source: AssistantRuleSourceRef;
  condition: string;
  result: string;
  evidence?: Record<string, any>;
}

export interface AssistantRulesModel {
  model_id: string;
  model_name: string;
  applicable: boolean;
  score: number;
  conclusion: string;
  why_steps: AssistantRulesWhyStep[];
  plan: Record<string, any>;
}

export interface AssistantRulesAnalyzeResult {
  code: string;
  name?: string | null;
  trade_date: string;
  horizon: 'short' | 'medium' | 'long';
  stock: Record<string, any>;
  facts?: Record<string, any>;
  models?: AssistantRulesModel[];
  selected_model_id?: string | null;
  explanation_text?: string;
  trace?: AssistantRulesTraceItem[];
  error?: string;
}

export interface AssistantRulesAnalyzeResponse {
  request: {
    codes: string[];
    horizon: 'short' | 'medium' | 'long';
    models?: string[];
    requested_date: string | null;
    trade_date: string;
  };
  results: AssistantRulesAnalyzeResult[];
  run_id?: string;
}

export interface AssistantFeedbackSubmitRequest {
  run_id?: string;
  code?: string;
  rating?: number;
  usefulness?: boolean;
  issue_type?: string;
  comment?: string;
  tags?: string[] | string;
  extra?: Record<string, any>;
}

export interface AssistantFeedbackSubmitResponse {
  ok: boolean;
  feedback_id?: number | null;
}

export interface AssistantFeedbackListResponse {
  items: Array<{
    id: number;
    created_at: string;
    run_id?: string | null;
    code?: string | null;
    rating?: number | null;
    usefulness?: number | null;
    issue_type?: string | null;
    comment?: string | null;
    tags?: any;
    extra_json?: any;
  }>;
  limit: number;
  offset: number;
}

export interface AssistantRulesVerifyResponse {
  run_id: string;
  created_at: string;
  trade_date: string;
  horizon: string;
  engine_version: string;
  forward_days: number;
  items: Array<{
    code: string;
    available: boolean;
    reason?: string;
    available_days?: number;
    entry_date?: string;
    entry_close?: number;
    exit_date?: string;
    exit_close?: number;
    return_pct?: number;
    max_drawdown_pct?: number;
    selected_model_id?: string | null;
  }>;
}

export type StrategyId = 'neil_turtle_short' | 'triple_screen';
export type StrategyTaskType = 'backfill' | 'daily';
export type StrategyExecuteMode = 'dry_run' | 'execute';
export type StrategyRunStatus = 'queued' | 'running' | 'success' | 'failed' | 'cancelled';

export interface StrategyRunCreateRequest {
  strategy_id: StrategyId;
  task_type: StrategyTaskType;
  execute_mode: StrategyExecuteMode;
  as_of_date?: string;
  stock_codes?: string;
  export_pdf?: boolean;
}

export interface StrategyRunRecord {
  run_id: string;
  status: StrategyRunStatus | string;
  requested_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  strategy_id: StrategyId | string;
  task_type: StrategyTaskType | string;
  execute_mode: StrategyExecuteMode | string;
  as_of_date?: string | null;
  stock_codes?: string | null;
  export_pdf?: boolean;
  command?: string[];
  command_exit_code?: number | null;
  export_command?: string[];
  export_exit_code?: number | null;
  error?: string | null;
  log_path?: string | null;
  report_path?: string | null;
  artifacts?: string[];
  summary?: Record<string, any>;
  log_tail?: string[];
}

export interface StrategyRunsListResponse {
  items: StrategyRunRecord[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  filters: {
    run_id: string | null;
    strategy_id: string | null;
    task_type: string | null;
    status: string | null;
  };
}

export interface StrategyRunLogsResponse {
  run_id: string;
  tail: number;
  log_path: string | null;
  exists: boolean;
  lines: string[];
}

export interface StrategyLabRecentSignalsSummaryResponse {
  meta: {
    strategy_id: StrategyId;
    days: number;
    per_day_limit: number;
    latest_close_date: string | null;
  };
  items: Array<{
    trade_date: string;
    count: number;
    up_n: number;
    down_n: number;
    flat_n: number;
    avg_return_pct: number | null;
    stocks: Array<{
      stock_code: string;
      stock_name: string;
      entry_trade_date: string;
      entry_close: number | null;
      latest_trade_date?: string | null;
      latest_close?: number | null;
      return_pct?: number | null;
    }>;
  }>;
}

export interface CupHandleLabSummaryResponse {
  meta: {
    latest_snapshot_detected_at: string | null;
    latest_hardened_version: string | null;
    latest_hardened_published_at: string | null;
  };
  quality: {
    hardened_success_rate: number;
    hardened_pick_n: number;
    hardened_success_n: number;
    base_success_rate: number | null;
    delta_vs_base: number | null;
  };
  states: Array<{
    state: string;
    success_rate: number;
    pick_n: number;
  }>;
  trend_4w: Array<{
    window: string;
    pick_n: number;
    success_n: number;
    success_rate: number;
  }>;
  self_explanatory: {
    goal: string;
    method: string;
    note: string;
  };
}

export interface CupHandleLabDailyItem {
  signal_date: string;
  market_state: string;
  cluster_desc: string;
  pick_n: number;
  success_n: number;
  success_rate: number;
  avg_dynamic_score: number;
  avg_end_return_t8: number;
}

export interface CupHandleLabDailyResponse {
  items: CupHandleLabDailyItem[];
  total: number;
  limit: number;
}

export interface CupHandleLabDiffItem {
  signal_date: string;
  base_n: number;
  base_success: number;
  base_rate: number;
  hard_n: number;
  hard_success: number;
  hard_rate: number;
  removed_n: number;
  added_n: number;
}

export interface CupHandleLabDiffResponse {
  items: CupHandleLabDiffItem[];
  total: number;
  limit: number;
}

export interface CupHandleLabAuditResponse {
  rules: Array<Record<string, any>>;
  removed_examples: Array<Record<string, any>>;
  alerts: Array<Record<string, any>>;
  refresh_mode: {
    default: string;
    hint: string;
  };
}

export interface CupHandleLabStockEntryItem {
  entry_id: string;
  entry_desc: string;
  market_state: string;
  segment_id: string;
  signal_date: string;
  dynamic_score: number;
  is_success_strict?: number | null;
  end_return_t8?: number | null;
  drawdown_mag_t1_t8?: number | null;
  estimated_win_rate: number;
  sample_n: number;
  reason_tags: string[];
}

export interface CupHandleLabStockItem {
  stock_code: string;
  stock_name: string;
  signal_date: string;
  estimated_win_rate: number;
  dynamic_score: number;
  sample_n: number;
  entry_count: number;
  reason_tags: string[];
  is_success_strict?: number | null;
  end_return_t8?: number | null;
  drawdown_mag_t1_t8?: number | null;
  history_cup_n?: number | null;
  history_ready_n?: number | null;
  history_success_n?: number | null;
  history_success_rate?: number | null;
  history_has_success?: boolean | null;
  industry?: string;
  sector_lv1?: string;
  sector_lv2?: string;
  matched_themes?: string[];
  theme_hit_n?: number;
  entries: CupHandleLabStockEntryItem[];
}

export interface CupHandleLabStocksResponse {
  items: CupHandleLabStockItem[];
  total: number;
  limit: number;
  meta: {
    latest_signal_date: string | null;
    sort_rule: string;
    window_mode?: string;
    window_days?: number;
    used_date_count?: number;
    requested_signal_date?: string | null;
    available_signal_dates?: string[];
    theme_mode?: string;
    preferred_themes?: string[];
    theme_catalog?: string[];
    source_mode?: string;
    excluded_not_in_v4_n?: number;
    v4_pool_total_n?: number;
    v42_candidate_rows_n?: number;
    v42_rows_in_v4_n?: number;
    v4_baseline_missing_dates?: string[];
    v4_baseline_missing_dates_n?: number;
    v4_baseline_available_dates_n?: number;
  };
  entry_windows: Array<{
    entry_id: string;
    entry_desc: string;
    pick_n: number;
    avg_dynamic_score: number;
    estimated_win_rate: number;
  }>;
}

export interface CupHandleLabWatchPoolItem {
  id: number;
  created_at: string;
  updated_at: string;
  stock_code: string;
  stock_name: string;
  signal_date: string;
  source_pool: 'v4' | 'hardened' | string;
  run_date?: string;
  market_state?: string;
  segment_id?: string;
  route_cluster?: string;
  gate_count?: number;
  dynamic_score?: number;
  status: 'in_progress' | 'ready' | 'validated' | string;
  ready_t8?: number;
  is_success_strict?: number | null;
  end_return_t8?: number | null;
  drawdown_mag_t1_t8?: number | null;
}

export interface CupHandleLabWatchPoolResponse {
  items: CupHandleLabWatchPoolItem[];
  total: number;
  limit: number;
  offset: number;
  meta: {
    latest_signal_date: string | null;
    available_signal_dates: string[];
    requested_signal_date?: string | null;
    source_pool?: string | null;
    status?: string | null;
    window_mode?: string;
  };
}

// API 配置：开发时走 Vite proxy（/api → localhost:5003），生产时走同域
// Backend API configuration
// Use proxy in development, auto-detect in production
const env = (import.meta as any).env ?? {};
const isDev = Boolean(env.DEV);
const normalizeApiBase = (raw: string): string => {
  const cleaned = raw.trim().replace(/\/+$/, '');
  if (!cleaned) return '';
  if (/^https?:\/\//i.test(cleaned) || cleaned.startsWith('/')) return cleaned;
  if (
    /^localhost(?::\d+)?(\/.*)?$/i.test(cleaned) ||
    /^\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?(\/.*)?$/.test(cleaned) ||
    /^[a-z0-9.-]+\.[a-z]{2,}(?::\d+)?(\/.*)?$/i.test(cleaned)
  ) {
    return `http://${cleaned}`;
  }
  return `/${cleaned.replace(/^\/+/, '')}`;
};
const envApiBase = typeof env.VITE_API_BASE === 'string' ? normalizeApiBase(env.VITE_API_BASE) : '';
const API_BASE = envApiBase || (
  isDev
    ? '/api'
    : (window.location.origin && window.location.origin !== 'null'
      ? `${window.location.origin}/api`
      : 'http://127.0.0.1:5003/api')
);

const AUTH_STORAGE_KEY = 'neo_basic_auth_v1';
let authPromptAttempted = false;

function readStoredAuth(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const v = window.localStorage.getItem(AUTH_STORAGE_KEY);
    return v && v.trim() ? v : null;
  } catch {
    return null;
  }
}

function storeAuth(value: string) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(AUTH_STORAGE_KEY, value);
  } catch {
    return;
  }
}

export function getAuthorizationHeaderValue(): string | null {
  return readStoredAuth();
}

export function clearAuthorization() {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
  } catch {
    return;
  }
}

function maybePromptForPassword(): string | null {
  if (typeof window === 'undefined') return null;
  if (authPromptAttempted) return null;
  authPromptAttempted = true;
  const password = window.prompt('请输入 Dashboard 密码');
  if (!password) return null;
  const auth = `Basic ${btoa(`admin:${password}`)}`;
  storeAuth(auth);
  return auth;
}

export function promptAuthorizationOnce(): string | null {
  return maybePromptForPassword();
}

/**
 * 通用请求函数（含完善的错误处理）
 */
export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const baseHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string> | undefined) || {}),
  };

  if (!('Authorization' in baseHeaders)) {
    const storedAuth = readStoredAuth();
    if (storedAuth) baseHeaders.Authorization = storedAuth;
  }

  const doFetch = async () => fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: baseHeaders,
  });

  let response = await doFetch();
  if (response.status === 401 && !baseHeaders.Authorization) {
    const promptedAuth = maybePromptForPassword();
    if (promptedAuth) {
      baseHeaders.Authorization = promptedAuth;
      response = await doFetch();
    }
  }

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

  assistantPoolCommonalities: (params?: { processed?: 'all' | '0' | '1'; start_date?: string; end_date?: string; top?: number; sample?: number }) => {
    const q = new URLSearchParams();
    if (params?.processed) q.set('processed', params.processed);
    if (params?.start_date) q.set('start_date', params.start_date);
    if (params?.end_date) q.set('end_date', params.end_date);
    if (typeof params?.top === 'number') q.set('top', String(params.top));
    if (typeof params?.sample === 'number') q.set('sample', String(params.sample));
    const qs = q.toString();
    return apiRequest<AssistantPoolCommonalitiesResponse>(`/assistant/lao-ya-tou/pool-commonalities${qs ? `?${qs}` : ''}`);
  },

  assistantFiveFlagsParameterOverrides: () =>
    apiRequest<AssistantFiveFlagsParameterOverridesResponse>('/assistant/five-flags/parameter-overrides'),

  assistantLaoYaTouLabelSummary: (params?: { start_date?: string; end_date?: string; top?: number }) => {
    const q = new URLSearchParams();
    if (params?.start_date) q.set('start_date', params.start_date);
    if (params?.end_date) q.set('end_date', params.end_date);
    if (typeof params?.top === 'number') q.set('top', String(params.top));
    const qs = q.toString();
    return apiRequest<AssistantLaoYaTouLabelSummaryResponse>(`/assistant/lao-ya-tou/label-summary${qs ? `?${qs}` : ''}`);
  },

  assistantLaoYaTouBaselineEval: (params?: { start_date?: string; end_date?: string; max_dates?: number; max_stocks_per_date?: number }) => {
    const q = new URLSearchParams();
    if (params?.start_date) q.set('start_date', params.start_date);
    if (params?.end_date) q.set('end_date', params.end_date);
    if (typeof params?.max_dates === 'number') q.set('max_dates', String(params.max_dates));
    if (typeof params?.max_stocks_per_date === 'number') q.set('max_stocks_per_date', String(params.max_stocks_per_date));
    const qs = q.toString();
    return apiRequest<AssistantLaoYaTouBaselineEvalResponse>(`/assistant/lao-ya-tou/baseline-eval${qs ? `?${qs}` : ''}`);
  },

  assistantLaoYaTouDailyCompare: (params?: { date?: string; auto_run?: boolean; include_codes?: boolean; max_codes?: number }) => {
    const q = new URLSearchParams();
    if (params?.date) q.set('date', params.date);
    if (typeof params?.auto_run === 'boolean') q.set('auto_run', params.auto_run ? '1' : '0');
    if (typeof params?.include_codes === 'boolean') q.set('include_codes', params.include_codes ? '1' : '0');
    if (typeof params?.max_codes === 'number') q.set('max_codes', String(params.max_codes));
    const qs = q.toString();
    return apiRequest<AssistantLaoYaTouDailyCompareResponse>(`/assistant/lao-ya-tou/daily-compare${qs ? `?${qs}` : ''}`);
  },

  assistantRulesAnalyze: (params: { codes: string[] | string; horizon?: 'short' | 'medium' | 'long'; date?: string; models?: string[] | string }) => {
    const q = new URLSearchParams();
    const rawCodes = Array.isArray(params.codes) ? params.codes.join(',') : params.codes;
    q.set('codes', rawCodes);
    if (params.horizon) q.set('horizon', params.horizon);
    if (params.date) q.set('date', params.date);
    if (params.models) {
      const rawModels = Array.isArray(params.models) ? params.models.join(',') : params.models;
      q.set('models', rawModels);
    }
    const qs = q.toString();
    return apiRequest<AssistantRulesAnalyzeResponse>(`/assistant/rules/analyze?${qs}`);
  },

  assistantSubmitFeedback: (payload: AssistantFeedbackSubmitRequest) =>
    apiRequest<AssistantFeedbackSubmitResponse>('/assistant/feedback', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  assistantListFeedback: (params?: { limit?: number; offset?: number; run_id?: string; code?: string }) => {
    const q = new URLSearchParams();
    if (typeof params?.limit === 'number') q.set('limit', String(params.limit));
    if (typeof params?.offset === 'number') q.set('offset', String(params.offset));
    if (params?.run_id) q.set('run_id', params.run_id);
    if (params?.code) q.set('code', params.code);
    const qs = q.toString();
    return apiRequest<AssistantFeedbackListResponse>(`/assistant/feedback${qs ? `?${qs}` : ''}`);
  },

  assistantRulesVerify: (params: { run_id: string; forward_days?: number }) => {
    const q = new URLSearchParams();
    q.set('run_id', params.run_id);
    if (typeof params.forward_days === 'number') q.set('forward_days', String(params.forward_days));
    return apiRequest<AssistantRulesVerifyResponse>(`/assistant/rules/verify?${q.toString()}`);
  },

  /** 创建策略任务（v1 同步执行） */
  createStrategyRun: (payload: StrategyRunCreateRequest) =>
    apiRequest<StrategyRunRecord>('/strategy-runs', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** 策略任务列表 */
  listStrategyRuns: (params?: {
    run_id?: string;
    strategy_id?: StrategyId;
    task_type?: StrategyTaskType;
    status?: string;
    limit?: number;
    offset?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.run_id) q.set('run_id', params.run_id);
    if (params?.strategy_id) q.set('strategy_id', params.strategy_id);
    if (params?.task_type) q.set('task_type', params.task_type);
    if (params?.status) q.set('status', params.status);
    if (typeof params?.limit === 'number') q.set('limit', String(params.limit));
    if (typeof params?.offset === 'number') q.set('offset', String(params.offset));
    const qs = q.toString();
    return apiRequest<StrategyRunsListResponse>(`/strategy-runs${qs ? `?${qs}` : ''}`);
  },

  /** 策略任务详情 */
  getStrategyRun: (runId: string, tail?: number) => {
    const q = new URLSearchParams();
    if (typeof tail === 'number') q.set('tail', String(tail));
    const qs = q.toString();
    return apiRequest<StrategyRunRecord>(`/strategy-runs/${encodeURIComponent(runId)}${qs ? `?${qs}` : ''}`);
  },

  /** 策略任务日志 */
  getStrategyRunLogs: (runId: string, tail?: number) => {
    const q = new URLSearchParams();
    if (typeof tail === 'number') q.set('tail', String(tail));
    const qs = q.toString();
    return apiRequest<StrategyRunLogsResponse>(`/strategy-runs/${encodeURIComponent(runId)}/logs${qs ? `?${qs}` : ''}`);
  },

  /** 交易策略实验室：最近N个交易日的 daily 信号汇总 + 当前涨跌幅 */
  getStrategyLabRecentSignalsSummary: (params: { strategy_id: StrategyId; days?: number; per_day_limit?: number }) => {
    const q = new URLSearchParams();
    q.set('strategy_id', params.strategy_id);
    if (typeof params.days === 'number') q.set('days', String(params.days));
    if (typeof params.per_day_limit === 'number') q.set('per_day_limit', String(params.per_day_limit));
    return apiRequest<StrategyLabRecentSignalsSummaryResponse>(`/strategy-lab/recent-signals-summary?${q.toString()}`);
  },

  getCupHandleLabSummary: () =>
    apiRequest<CupHandleLabSummaryResponse>('/cup-handle-lab/summary'),

  getCupHandleLabDaily: (limit = 60) =>
    apiRequest<CupHandleLabDailyResponse>(`/cup-handle-lab/daily?limit=${encodeURIComponent(String(limit))}`),

  getCupHandleLabDiff: (limit = 60) =>
    apiRequest<CupHandleLabDiffResponse>(`/cup-handle-lab/diff?limit=${encodeURIComponent(String(limit))}`),

  getCupHandleLabAudit: () =>
    apiRequest<CupHandleLabAuditResponse>('/cup-handle-lab/audit'),

  getCupHandleLabStocks: (params?: { limit?: number; entry?: string; state?: string; latest_only?: boolean; window_days?: number; signal_date?: string; preferred_themes?: string[]; theme_mode?: 'off'|'prefer'|'only' }) => {
    const q = new URLSearchParams();
    q.set('limit', String(params?.limit ?? 120));
    if (params?.entry) q.set('entry', params.entry);
    if (params?.state) q.set('state', params.state);
    if (params?.latest_only === true) q.set('latest_only', '1');
    else if (params?.latest_only === false) q.set('latest_only', '0');
    if (params?.signal_date) q.set('signal_date', params.signal_date);
    if (params?.window_days) q.set('window_days', String(params.window_days));
    if (params?.preferred_themes?.length) q.set('preferred_themes', params.preferred_themes.join(','));
    if (params?.theme_mode) q.set('theme_mode', params.theme_mode);
    return apiRequest<CupHandleLabStocksResponse>(`/cup-handle-lab/stocks?${q.toString()}`);
  },
  getCupHandleLabWatchPool: (params?: { limit?: number; offset?: number; signal_date?: string; source_pool?: 'v4' | 'hardened'; status?: 'in_progress' | 'ready' | 'validated' }) => {
    const q = new URLSearchParams();
    q.set('limit', String(params?.limit ?? 240));
    if (typeof params?.offset === 'number') q.set('offset', String(params.offset));
    if (params?.signal_date) q.set('signal_date', params.signal_date);
    if (params?.source_pool) q.set('source_pool', params.source_pool);
    if (params?.status) q.set('status', params.status);
    return apiRequest<CupHandleLabWatchPoolResponse>(`/cup-handle-lab/watch-pool?${q.toString()}`);
  },
  getCupHandleLabAlignment: (params?: { date?: string }) => {
    const q = new URLSearchParams();
    if (params?.date) q.set('date', params.date);
    const query = q.toString();
    return apiRequest<CupHandleLabAlignmentResponse>(`/cup-handle-lab/alignment${query ? `?${query}` : ''}`);
  },

  getCupHandleLabV4PoolCompare: (params?: { date?: string; persist?: boolean }) => {
    const q = new URLSearchParams();
    if (params?.date) q.set('date', params.date);
    if (typeof params?.persist === 'boolean') q.set('persist', params.persist ? '1' : '0');
    q.set('limit', '240');
    const query = q.toString();
    return apiRequest<CupHandleLabV4PoolCompareResponse>(`/cup-handle-lab/v4-pool-compare${query ? `?${query}` : ''}`);
  },

  getCupHandleLabDailyBrief: (params?: { date?: string }) => {
    const q = new URLSearchParams();
    if (params?.date) q.set('date', params.date);
    const query = q.toString();
    return apiRequest<CupHandleLabDailyBriefResponse>(`/cup-handle-lab/daily-brief${query ? `?${query}` : ''}`);
  },

  getCupHandleLabFeedback: (params?: { stock_code?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.stock_code) q.set('stock_code', params.stock_code);
    if (typeof params?.limit === 'number') q.set('limit', String(params.limit));
    if (typeof params?.offset === 'number') q.set('offset', String(params.offset));
    const query = q.toString();
    return apiRequest<CupHandleLabFeedbackListResponse>(`/cup-handle-lab/feedback${query ? `?${query}` : ''}`);
  },

  submitCupHandleLabFeedback: (payload: CupHandleLabFeedbackSubmitRequest) =>
    apiRequest<CupHandleLabFeedbackSubmitResponse>('/cup-handle-lab/feedback', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

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
