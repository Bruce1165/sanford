import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

interface FiveFlagsHealth {
  status: string;
  timestamp: string;
  pool_total_count: number;
  pool_unprocessed_count: number;
  result_total_count: number;
  latest_result_date: string | null;
}

interface PoolStockItem {
  stock_code: string;
  stock_name: string;
  sector_compound?: string;
  start_date: string;
  end_date: string;
  unprocessed_count: number;
  has_hits: number;
}

interface PoolStockCompatItem extends Partial<PoolStockItem> {
  id?: number;
  processed?: number;
  file_name?: string;
}

interface FailedCheck {
  key: string;
  label: string;
  passed: boolean;
  message: string;
}

interface RunItem {
  run_id: string;
  status: string;
  requested_at?: string;
  started_at?: string;
  last_update?: string;
  completed_at?: string | null;
  total_stocks?: number;
  processed_stocks?: number;
  failed_stocks?: number;
  total_matches?: number;
  progress?: {
    percent?: number;
    processed_stocks?: number;
    total_stocks?: number;
  };
}

interface FiveFlagsResult {
  id: number;
  pool_id: number;
  screener_id: string;
  stock_code: string;
  stock_name: string;
  screen_date: string;
  close_price: number;
  match_reason: string;
  created_at: string;
}

interface TimelineDetail {
  screener_id: string;
  match_reason: string;
  reason_hit?: string;
  reason_miss?: string;
  failed_checks?: FailedCheck[];
  first_failed_check?: FailedCheck | null;
  diagnostic_hints?: string[];
  close_price: number;
  pool_id: number | null;
  created_at: string | null;
}

interface TimelineCell {
  screener_id: string;
  label: string;
  hit: boolean;
  reason_hit: string;
  reason_miss: string;
  failed_checks?: FailedCheck[];
  first_failed_check?: FailedCheck | null;
  diagnostic_hints?: string[];
}

interface TimelineEntry {
  date: string;
  hits: string[];
  details: TimelineDetail[];
  items?: TimelineCell[];
}

interface TimelineResponse {
  stock_code: string;
  stock_name?: string;
  diag_meta?: {
    include_miss_details: boolean;
    max_diag_cells: number;
    diagnostics_applied: boolean;
  };
  screeners?: { screener_id: string; label: string }[];
  timeline: TimelineEntry[];
  daily_quotes?: Array<{
    trade_date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    pct_change: number;
    volume: number;
    amount: number;
    turnover: number;
  }>;
}

interface CellDiagnosisResponse {
  stock_code: string;
  stock_name?: string;
  date: string;
  screener_id: string;
  matched: boolean;
  reason_hit?: string;
  reason_miss?: string;
  failed_checks?: FailedCheck[];
  first_failed_check?: FailedCheck | null;
  diagnostic_hints?: string[];
  daily_quote?: {
    trade_date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    pct_change: number;
    volume: number;
    amount: number;
    turnover: number;
  } | null;
  price?: number;
}

interface RunDetailResponse {
  run: RunItem;
  progress?: {
    percent?: number;
    processed_stocks?: number;
    total_stocks?: number;
  };
}

interface PoolUploadResponse {
  success: boolean;
  upload?: {
    status?: string;
    message?: string;
    uploaded?: number;
  };
  queue?: {
    job_id?: string;
    status?: string;
    run_id?: string | null;
  };
  error?: string;
  errors?: string[];
}

interface ManualRunResponse {
  job_id?: string;
  status?: string;
  queue_status?: string;
  run_id?: string | null;
  accepted?: boolean;
  reason?: string;
  error?: string;
}

interface QueueJob {
  job_id: string;
  status: 'queued' | 'started' | 'completed' | 'failed' | string;
  run_id?: string | null;
  error?: string | null;
}

interface QueueDetailResponse {
  job: QueueJob;
}

interface RunFeedbackDialog {
  visible: boolean;
  tone: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
}

interface CronLogBlock {
  path: string;
  exists: boolean;
  updated_at: string | null;
  lines: string[];
}

interface CronLogsResponse {
  tail: number;
  stdout: CronLogBlock;
  stderr: CronLogBlock;
}

interface PoolListResponse {
  items: Array<{ id?: number }>;
  total: number;
}

function extractCellDiagnosisFromTimeline(
  resp: TimelineResponse,
  targetDate: string,
  screenerKey: string
): CellDiagnosisResponse | null {
  const day = (resp.timeline || []).find((x) => x.date === targetDate);
  if (!day) return null;
  const cell = (day.items || []).find((x) => resolveScreenerKey(x.screener_id) === screenerKey);
  if (!cell) return null;
  const quote = (resp.daily_quotes || []).find((q) => q.trade_date === targetDate) || null;
  return {
    stock_code: resp.stock_code,
    stock_name: resp.stock_name,
    date: targetDate,
    screener_id: cell.screener_id,
    matched: !!cell.hit,
    reason_hit: cell.reason_hit || '',
    reason_miss: cell.reason_miss || '',
    failed_checks: cell.failed_checks || [],
    first_failed_check: cell.first_failed_check || null,
    diagnostic_hints: cell.diagnostic_hints || [],
    daily_quote: quote,
    price: quote?.close,
  };
}

function formatDateOnly(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function shiftDate(dateStr: string, days: number): string {
  const d = new Date(`${dateStr}T00:00:00`);
  if (Number.isNaN(d.getTime())) return dateStr;
  d.setDate(d.getDate() + days);
  return formatDateOnly(d);
}

function buildDateRange(start: string, end: string): string[] {
  if (!start || !end || start > end) return [];
  const range: string[] = [];
  let cursor = start;
  let guard = 0;
  while (cursor <= end && guard < 400) {
    range.push(cursor);
    cursor = shiftDate(cursor, 1);
    guard += 1;
  }
  return range;
}

const MAX_WINDOW_DAYS = 15;

const FIXED_SCREENERS = [
  { key: 'shi_pan_xian', label: '试盘线', color: '#2563eb', aliases: ['试盘线', '涨停试盘线', 'shi_pan_xian', 'shipanxian', 'test_line'] },
  { key: 'jin_feng_huang', label: '金凤凰', color: '#f59e0b', aliases: ['金凤凰', '涨停金凤凰', 'jin_feng_huang', 'jinfenghuang', 'golden_phoenix'] },
  { key: 'yin_feng_huang', label: '银凤凰', color: '#64748b', aliases: ['银凤凰', '涨停银凤凰', 'yin_feng_huang', 'yinfenghuang', 'silver_phoenix'] },
  { key: 'zhang_ting_bei_liang_yin', label: '倍量阴', color: '#8b5cf6', aliases: ['倍量阴', '涨停倍量阴', 'zhang_ting_bei_liang_yin', 'beiliangyin', 'double_volume_bear'] },
  { key: 'er_ban_hui_tiao', label: '二板回调', color: '#ef4444', aliases: ['二板回调', 'er_ban_hui_tiao', 'erbanhuitiao', 'second_board_pullback'] },
] as const;

function normalizeScreenerId(value: string): string {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '')
    .replace(/[-_]/g, '');
}

function resolveScreenerKey(value: string): string | null {
  const source = normalizeScreenerId(value);
  for (const item of FIXED_SCREENERS) {
    if (item.aliases.some((a) => normalizeScreenerId(a) === source)) return item.key;
  }
  return null;
}

function getFailedCheckGroupLabel(check: FailedCheck): string {
  const rawKey = String(check.key || '').toLowerCase();
  if (rawKey === 'data') return '数据完整性';
  if (rawKey === 'window') return '时间窗口';
  const match = rawKey.match(/^signal_(\d+(?:_\d+)?)$/);
  if (match?.[1]) return `信号${match[1].replace(/_/g, '.')}`;
  return check.label || check.key || '其他条件';
}

async function fetchJson<T>(url: string, init?: RequestInit, timeoutMs = 12000): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      ...init,
      signal: controller.signal,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new Error(`HTTP ${res.status}: ${text.slice(0, 120)}`);
    }
    return res.json() as Promise<T>;
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new Error(`请求超时(${Math.round(timeoutMs / 1000)}s): ${url}`);
    }
    throw e;
  } finally {
    window.clearTimeout(timer);
  }
}

export default function FiveFlagsMonitor({ theme = 'dark' }: { theme?: 'dark' | 'light' }) {
  const isLight = theme === 'light';
  const palette = {
    pageBg: isLight ? '#f4f7fb' : '#0a0f1e',
    panelBg: isLight ? '#ffffff' : '#111827',
    text: isLight ? '#0f172a' : '#e5e7eb',
    dimText: isLight ? '#334155' : '#9ca3af',
    border: isLight ? '#dbe3ef' : '#1e2d3d',
    inputBg: isLight ? '#ffffff' : '#0f172a',
    inputBorder: isLight ? '#cbd5e1' : '#334155',
    activeRowBg: isLight ? 'rgba(37,99,235,0.08)' : 'rgba(255,203,5,0.08)',
    badge: isLight ? '#1e40af' : '#93c5fd',
    warnBg: isLight ? 'rgba(220,38,38,0.08)' : 'rgba(239,68,68,0.1)',
    warnText: isLight ? '#b91c1c' : '#fca5a5',
    title: isLight ? '#1e40af' : '#FFCB05',
  };
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [health, setHealth] = useState<FiveFlagsHealth | null>(null);
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [liveRun, setLiveRun] = useState<RunItem | null>(null);
  const [poolStocks, setPoolStocks] = useState<PoolStockItem[]>([]);
  const [hitStockCodeSet, setHitStockCodeSet] = useState<Set<string>>(new Set());
  const [resultsTotal, setResultsTotal] = useState(0);

  const today = formatDateOnly(new Date());
  const defaultPreset = MAX_WINDOW_DAYS;
  const [stockSearch, setStockSearch] = useState('');
  const [selectedStock, setSelectedStock] = useState('');
  const [visibleStockCount, setVisibleStockCount] = useState<10 | 15 | 20>(15);
  const [windowPreset, setWindowPreset] = useState<5 | 10 | 15 | 'custom'>(15);
  const [windowStart, setWindowStart] = useState(() => shiftDate(today, -(defaultPreset - 1)));
  const [windowEnd, setWindowEnd] = useState(today);
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);
  const [historyTimeline, setHistoryTimeline] = useState<TimelineResponse | null>(null);
  const [historyTimelineLoaded, setHistoryTimelineLoaded] = useState(false);
  const [historyTimelineLoading, setHistoryTimelineLoading] = useState(false);
  const [hoverCell, setHoverCell] = useState<{ date: string; screenerKey: string } | null>(null);
  const [pinnedCell, setPinnedCell] = useState<{ date: string; screenerKey: string } | null>(null);
  const [cellDiagCache, setCellDiagCache] = useState<Record<string, CellDiagnosisResponse>>({});
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [forceOverwrite, setForceOverwrite] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [manualRunning, setManualRunning] = useState(false);
  const [forceManualRun, setForceManualRun] = useState(false);
  const [actionHint, setActionHint] = useState<string | null>(null);
  const [showUploadHelp, setShowUploadHelp] = useState(false);
  const [runFeedbackDialog, setRunFeedbackDialog] = useState<RunFeedbackDialog>({
    visible: false,
    tone: 'info',
    title: '',
    message: '',
  });
  const [cronLogs, setCronLogs] = useState<CronLogsResponse | null>(null);
  const [cronLogsLoading, setCronLogsLoading] = useState(false);
  const [cronLogsCollapsed, setCronLogsCollapsed] = useState(true);
  const [leftPanelCollapsed, setLeftPanelCollapsed] = useState(false);
  const manualRunWatchTokenRef = useRef(0);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      const stockPageLimit = 2000;
      const [h, r, rs, ps] = await Promise.all([
        fetchJson<FiveFlagsHealth>('/api/five-flags/health'),
        fetchJson<{ items: RunItem[] }>('/api/five-flags/runs?limit=5'),
        fetchJson<{ items: FiveFlagsResult[]; total: number }>('/api/five-flags/results?limit=400'),
        fetchJson<{ items: PoolStockCompatItem[]; total: number }>(`/api/five-flags/pools?processed=all&dedupe_stock=1&hit_first=1&limit=${stockPageLimit}&offset=0`),
      ]);
      setHealth(h);
      setRuns(r.items || []);
      setLiveRun((r.items && r.items.length > 0) ? r.items[0] : null);
      setResultsTotal(rs.total || 0);
      const allPoolStocks: PoolStockCompatItem[] = [...(ps.items || [])];
      const hitStockCodes = new Set<string>((rs.items || []).map((x) => String(x.stock_code || '').trim()).filter(Boolean));
      let resultOffset = (rs.items || []).length;
      const resultTotal = Number(rs.total || resultOffset);
      while (resultOffset < resultTotal) {
        const page = await fetchJson<{ items: FiveFlagsResult[]; total: number }>(
          `/api/five-flags/results?limit=400&offset=${resultOffset}`
        );
        const pageItems = page.items || [];
        if (pageItems.length === 0) break;
        pageItems.forEach((x) => {
          const code = String(x.stock_code || '').trim();
          if (code) hitStockCodes.add(code);
        });
        resultOffset += pageItems.length;
      }
      setHitStockCodeSet(hitStockCodes);

      let nextOffset = allPoolStocks.length;
      const expectedTotal = Number(ps.total || allPoolStocks.length);
      while (nextOffset < expectedTotal) {
        const page = await fetchJson<{ items: PoolStockCompatItem[]; total: number }>(
          `/api/five-flags/pools?processed=all&dedupe_stock=1&hit_first=1&limit=${stockPageLimit}&offset=${nextOffset}`
        );
        const pageItems = page.items || [];
        if (pageItems.length === 0) break;
        allPoolStocks.push(...pageItems);
        nextOffset += pageItems.length;
      }
      const poolHasHitsField = allPoolStocks.some((item) => Object.prototype.hasOwnProperty.call(item, 'has_hits'));
      const uniqueStocks = new Map<string, PoolStockItem>();
      allPoolStocks.forEach((item) => {
        const code = String(item.stock_code || '').trim();
        if (!code) return;
        if (uniqueStocks.has(code)) return;
        uniqueStocks.set(code, {
          stock_code: code,
          stock_name: String(item.stock_name || code),
          sector_compound: String(item.sector_compound || '').trim(),
          start_date: String(item.start_date || ''),
          end_date: String(item.end_date || ''),
          unprocessed_count: Number(item.unprocessed_count || 0),
          has_hits: Number(item.has_hits || 0),
        });
      });

      // Backward compatibility: old backend pools API has no `has_hits` field.
      // In that case derive hit state from results API stock codes.
      if (!poolHasHitsField) {
        uniqueStocks.forEach((value, key) => {
          value.has_hits = hitStockCodes.has(key) ? 1 : 0;
          uniqueStocks.set(key, value);
        });
      }

      setPoolStocks(Array.from(uniqueStocks.values()));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Load failed');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCronLogs = useCallback(async () => {
    setCronLogsLoading(true);
    try {
      const resp = await fetchJson<CronLogsResponse>('/api/five-flags/cron-logs?tail=120');
      setCronLogs(resp);
    } catch (e) {
      setActionHint(e instanceof Error ? e.message : 'Cron 日志加载失败');
    } finally {
      setCronLogsLoading(false);
    }
  }, []);

  const watchManualRunResult = useCallback(async (jobId: string, initialRunId?: string | null) => {
    const watchToken = ++manualRunWatchTokenRef.current;
    let runId = initialRunId || null;
    const maxAttempts = 120;
    const sleepMs = 3000;

    for (let i = 0; i < maxAttempts; i += 1) {
      if (watchToken !== manualRunWatchTokenRef.current) return;
      try {
        const queueResp = await fetchJson<QueueDetailResponse>(`/api/five-flags/queue/${encodeURIComponent(jobId)}`);
        const job = queueResp.job;
        if (job?.run_id) runId = job.run_id;

        if (job?.status === 'queued') {
          setRunFeedbackDialog({
            visible: true,
            tone: 'info',
            title: '排队中',
            message: `任务已提交，等待调度执行。\njob: ${jobId}`,
          });
        } else if (job?.status === 'started') {
          let progressMsg = `任务已启动，正在执行。\njob: ${jobId}`;
          if (runId) {
            try {
              const detail = await fetchJson<RunDetailResponse>(`/api/five-flags/runs/${encodeURIComponent(runId)}`);
              const merged: RunItem = {
                ...detail.run,
                progress: detail.progress || detail.run.progress,
              };
              setLiveRun(merged);
              const processed = Number(merged.processed_stocks || merged.progress?.processed_stocks || 0);
              const total = Number(merged.total_stocks || merged.progress?.total_stocks || 0);
              const percent = Number(merged.progress?.percent || 0);
              progressMsg = `任务已启动，正在执行。\njob: ${jobId}\nrun: ${runId}\n进度: ${processed}/${total} (${percent.toFixed(2)}%)`;
            } catch {
              // Keep queue-only progress when run detail is transiently unavailable.
            }
          }
          setRunFeedbackDialog({
            visible: true,
            tone: 'info',
            title: '运行中',
            message: progressMsg,
          });
        } else if (job?.status === 'completed') {
          let doneMsg = '运行成功。\n筛查总数: -\n命中总数: -';
          if (runId) {
            try {
              const detail = await fetchJson<RunDetailResponse>(`/api/five-flags/runs/${encodeURIComponent(runId)}`);
              const merged: RunItem = {
                ...detail.run,
                progress: detail.progress || detail.run.progress,
              };
              setLiveRun(merged);
              const screened = Number(merged.processed_stocks || merged.progress?.processed_stocks || 0);
              const matches = Number(merged.total_matches || 0);
              const failed = Number(merged.failed_stocks || 0);
              if (screened === 0 && matches === 0 && failed === 0) {
                const skipMsg = '不运行。\n原因: 无可筛查数据（已是最新或无增量）。';
                setActionHint('不运行：无可筛查数据（已是最新或无增量）。');
                setRunFeedbackDialog({
                  visible: true,
                  tone: 'warning',
                  title: '无需运行',
                  message: skipMsg,
                });
                void loadData();
                return;
              }
              doneMsg = `运行成功。\n筛查总数: ${screened}\n命中总数: ${matches}`;
            } catch {
              doneMsg = '运行成功。\n筛查总数: -\n命中总数: -';
            }
          }
          setActionHint(doneMsg.replace(/\n/g, ' · '));
          setRunFeedbackDialog({
            visible: true,
            tone: 'success',
            title: '运行成功',
            message: doneMsg,
          });
          void loadData();
          return;
        } else if (job?.status === 'failed') {
          const failedReason = job.error || '请查看 Cron/后端日志定位原因。';
          const failedMsg = `运行失败。\n原因: ${failedReason}`;
          setActionHint(`运行失败：${failedReason}`);
          setRunFeedbackDialog({
            visible: true,
            tone: 'error',
            title: '运行失败',
            message: failedMsg,
          });
          void loadData();
          return;
        }
      } catch {
        // Keep polling on transient network/backend errors.
      }
      await new Promise<void>((resolve) => {
        window.setTimeout(resolve, sleepMs);
      });
    }

    if (watchToken !== manualRunWatchTokenRef.current) return;
    setRunFeedbackDialog({
      visible: true,
      tone: 'warning',
      title: '结果待确认',
      message: `任务已提交但在跟踪窗口内未结束，请稍后在运行区或日志区查看。\njob: ${jobId}`,
    });
  }, [loadData]);

  useEffect(() => {
    void loadData();
    void loadCronLogs();
  }, [loadData, loadCronLogs]);

  useEffect(() => {
    const timer = setInterval(() => {
      void loadData();
    }, 15000);
    return () => clearInterval(timer);
  }, [loadData]);

  useEffect(() => {
    const timer = setInterval(() => {
      void loadCronLogs();
    }, 30000);
    return () => clearInterval(timer);
  }, [loadCronLogs]);

  const activeRun = liveRun || runs[0] || null;
  const shouldLivePoll = activeRun?.status === 'running' || activeRun?.status === 'accepted';

  useEffect(() => {
    if (!shouldLivePoll) return;
    const runId = activeRun?.run_id || 'latest';
    const tick = async () => {
      try {
        const detail = await fetchJson<RunDetailResponse>(`/api/five-flags/runs/${encodeURIComponent(runId)}`);
        const merged: RunItem = {
          ...detail.run,
          progress: detail.progress || detail.run.progress,
        };
        setLiveRun(merged);
      } catch {
        // Keep existing state on transient poll failure.
      }
    };
    void tick();
    const timer = setInterval(() => {
      void tick();
    }, 2500);
    return () => clearInterval(timer);
  }, [activeRun?.run_id, shouldLivePoll]);

  useEffect(() => {
    if (!selectedStock) {
      setTimeline(null);
      return;
    }
    const start = new Date(`${windowStart}T00:00:00`);
    const end = new Date(`${windowEnd}T00:00:00`);
    const windowSpanDays = Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start > end
      ? MAX_WINDOW_DAYS
      : Math.max(1, Math.floor((end.getTime() - start.getTime()) / 86400000) + 1);
    const maxDiagCells = Math.max(320, windowSpanDays * FIXED_SCREENERS.length);
    const params = new URLSearchParams({
      stock_code: selectedStock,
      from: windowStart,
      to: windowEnd,
      include_miss_details: '1',
      max_diag_cells: String(maxDiagCells),
    });
    void fetchJson<TimelineResponse>(
      `/api/five-flags/timeline?${params.toString()}`
    )
      .then((resp) => {
        setTimeline(resp);
        const hasAnyHit = (resp.timeline || []).some((entry) => {
          if ((entry.hits || []).length > 0) return true;
          return (entry.items || []).some((cell) => !!cell.hit);
        });
        if (!hasAnyHit) return;
        setPoolStocks((prev) =>
          prev.map((item) => (
            item.stock_code === selectedStock && Number(item.has_hits) <= 0
              ? { ...item, has_hits: 1 }
              : item
          ))
        );
      })
      .catch(() => setTimeline(null));
  }, [selectedStock, windowStart, windowEnd]);

  useEffect(() => {
    setHistoryTimeline(null);
    setHistoryTimelineLoaded(false);
    setHistoryTimelineLoading(false);
  }, [selectedStock]);

  const loadHistoryTimeline = useCallback(async () => {
    if (!selectedStock || historyTimelineLoading) return;
    setHistoryTimelineLoading(true);
    try {
      const params = new URLSearchParams({
        stock_code: selectedStock,
        from: '1990-01-01',
        to: today,
        include_miss_details: '0',
      });
      const resp = await fetchJson<TimelineResponse>(`/api/five-flags/timeline?${params.toString()}`);
      setHistoryTimeline(resp);
      setHistoryTimelineLoaded(true);
    } catch {
      setHistoryTimeline(null);
      setHistoryTimelineLoaded(false);
    } finally {
      setHistoryTimelineLoading(false);
    }
  }, [historyTimelineLoading, selectedStock, today]);

  useEffect(() => {
    if (selectedStock || poolStocks.length === 0) return;
    const first = poolStocks[0];
    if (!first?.stock_code) return;
    setSelectedStock(first.stock_code);
  }, [poolStocks, selectedStock]);

  const latestRun = liveRun || runs[0] || null;
  const stockOptions = useMemo(() => {
    return (poolStocks || []).map((item) => ({
      code: item.stock_code,
      name: item.stock_name || item.stock_code,
      sectorCompound: String(item.sector_compound || '').trim(),
      hasHits: Number(item.has_hits) > 0 || hitStockCodeSet.has(String(item.stock_code || '').trim()),
    }));
  }, [poolStocks, hitStockCodeSet]);

  const filteredStockOptions = useMemo(() => {
    const key = stockSearch.trim().toLowerCase();
    if (!key) return stockOptions;
    return stockOptions.filter((item) =>
      item.code.toLowerCase().includes(key) || item.name.toLowerCase().includes(key)
    );
  }, [stockOptions, stockSearch]);

  const dateRangeInvalid = !!(windowStart && windowEnd && windowStart > windowEnd);

  const windowedTimeline = useMemo(() => {
    const rows = timeline?.timeline || [];
    if (dateRangeInvalid) return [];
    return rows.filter((row) => row.date >= windowStart && row.date <= windowEnd);
  }, [timeline, windowStart, windowEnd, dateRangeInvalid]);

  const dateColumns = useMemo(() => {
    const sorted = [...windowedTimeline].sort((a, b) => a.date.localeCompare(b.date));
    const dates = sorted.map((row) => row.date);
    if (dates.length > 0) return dates;
    if (!dateRangeInvalid) return buildDateRange(windowStart, windowEnd);
    return [];
  }, [windowStart, windowEnd, windowedTimeline, dateRangeInvalid]);

  const detailReasonMap = useMemo(() => {
    const map = new Map<string, string>();
    windowedTimeline.forEach((entry) => {
      entry.items?.forEach((cell) => {
        const key = resolveScreenerKey(cell.screener_id);
        if (!key) return;
        const mapKey = `${entry.date}|${key}`;
        if (cell.hit && cell.reason_hit) map.set(mapKey, cell.reason_hit);
      });
      entry.details.forEach((detail) => {
        const key = resolveScreenerKey(detail.screener_id);
        if (!key) return;
        const mapKey = `${entry.date}|${key}`;
        if (!map.has(mapKey)) map.set(mapKey, detail.reason_hit || detail.match_reason || '命中');
      });
    });
    return map;
  }, [windowedTimeline]);

  const missReasonMap = useMemo(() => {
    const map = new Map<string, string>();
    windowedTimeline.forEach((entry) => {
      entry.items?.forEach((cell) => {
        const key = resolveScreenerKey(cell.screener_id);
        if (!key) return;
        const mapKey = `${entry.date}|${key}`;
        if (!cell.hit && cell.reason_miss) map.set(mapKey, cell.reason_miss);
      });
    });
    return map;
  }, [windowedTimeline]);

  const missCheckMap = useMemo(() => {
    const map = new Map<string, FailedCheck[]>();
    windowedTimeline.forEach((entry) => {
      entry.items?.forEach((cell) => {
        const key = resolveScreenerKey(cell.screener_id);
        if (!key || cell.hit) return;
        const failed = cell.failed_checks?.filter((x) => !x.passed) || [];
        if (failed.length > 0) map.set(`${entry.date}|${key}`, failed);
      });
    });
    return map;
  }, [windowedTimeline]);

  const quoteByDate = useMemo(() => {
    const map = new Map<string, {
      trade_date: string;
      open: number;
      high: number;
      low: number;
      close: number;
      pct_change: number;
      volume: number;
      amount: number;
      turnover: number;
    }>();
    (timeline?.daily_quotes || []).forEach((item) => {
      if (item?.trade_date) map.set(item.trade_date, item);
    });
    return map;
  }, [timeline]);

  const missFirstCheckMap = useMemo(() => {
    const map = new Map<string, FailedCheck>();
    windowedTimeline.forEach((entry) => {
      entry.items?.forEach((cell) => {
        const key = resolveScreenerKey(cell.screener_id);
        if (!key || cell.hit) return;
        const first = cell.first_failed_check;
        if (first && !first.passed) map.set(`${entry.date}|${key}`, first);
      });
    });
    return map;
  }, [windowedTimeline]);

  const missHintMap = useMemo(() => {
    const map = new Map<string, string[]>();
    windowedTimeline.forEach((entry) => {
      entry.items?.forEach((cell) => {
        const key = resolveScreenerKey(cell.screener_id);
        if (!key || cell.hit) return;
        const hints = (cell.diagnostic_hints || []).filter((x) => String(x || '').trim().length > 0);
        if (hints.length > 0) map.set(`${entry.date}|${key}`, hints);
      });
    });
    return map;
  }, [windowedTimeline]);

  const hitKeySet = useMemo(() => {
    const set = new Set<string>();
    windowedTimeline.forEach((entry) => {
      entry.items?.forEach((cell) => {
        const key = resolveScreenerKey(cell.screener_id);
        if (key && cell.hit) set.add(`${entry.date}|${key}`);
      });
      entry.hits.forEach((hitId) => {
        const key = resolveScreenerKey(hitId);
        if (key) set.add(`${entry.date}|${key}`);
      });
      entry.details.forEach((detail) => {
        const key = resolveScreenerKey(detail.screener_id);
        if (key) set.add(`${entry.date}|${key}`);
      });
    });
    return set;
  }, [windowedTimeline]);

  const statusColor = useMemo(() => {
    const st = latestRun?.status || health?.status || 'unknown';
    if (st === 'running') return '#f59e0b';
    if (st === 'completed' || st === 'healthy') return '#22c55e';
    if (st === 'failed' || st === 'critical') return '#ef4444';
    return '#9ca3af';
  }, [latestRun?.status, health?.status]);

  const selectedStockMeta = useMemo(
    () => stockOptions.find((item) => item.code === selectedStock) || null,
    [selectedStock, stockOptions]
  );

  const historyStripDates = useMemo(() => {
    const rows = historyTimeline?.timeline || [];
    const sorted = [...rows].sort((a, b) => a.date.localeCompare(b.date));
    return sorted.map((row) => row.date);
  }, [historyTimeline]);

  const historyHitDateSet = useMemo(() => {
    const set = new Set<string>();
    (historyTimeline?.timeline || []).forEach((entry) => {
      let hit = (entry.hits || []).length > 0 || (entry.details || []).length > 0;
      if (!hit) {
        hit = (entry.items || []).some((cell) => !!cell.hit);
      }
      if (hit) set.add(entry.date);
    });
    return set;
  }, [historyTimeline]);

  const currentWindowSpanDays = useMemo(() => {
    const start = new Date(`${windowStart}T00:00:00`);
    const end = new Date(`${windowEnd}T00:00:00`);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start > end) return MAX_WINDOW_DAYS;
    const diffMs = end.getTime() - start.getTime();
    return Math.max(1, Math.floor(diffMs / 86400000) + 1);
  }, [windowStart, windowEnd]);

  const handlePresetClick = (days: 5 | 10 | 15) => {
    setWindowPreset(days);
    const anchorEnd = windowEnd || today;
    setWindowStart(shiftDate(anchorEnd, -(days - 1)));
    setHoverCell(null);
    setPinnedCell(null);
  };

  const shiftWindow = (direction: -1 | 1) => {
    const offset = currentWindowSpanDays * direction;
    setWindowPreset('custom');
    setWindowStart((prev) => shiftDate(prev, offset));
    setWindowEnd((prev) => shiftDate(prev, offset));
    setHoverCell(null);
    setPinnedCell(null);
  };

  const jumpWindowToDate = (date: string) => {
    setWindowPreset('custom');
    setWindowEnd(date);
    setWindowStart(shiftDate(date, -(currentWindowSpanDays - 1)));
    setHoverCell(null);
    setPinnedCell(null);
  };

  const activeCell = pinnedCell || hoverCell;
  const activeCellKey = activeCell ? `${activeCell.date}|${activeCell.screenerKey}` : '';
  const hasUnprocessedPools = Number(health?.pool_unprocessed_count || 0) > 0;

  const fetchAllPoolIds = useCallback(async (): Promise<number[]> => {
    const ids: number[] = [];
    const pageSize = 5000;
    let offset = 0;
    let total = 0;
    do {
      const resp = await fetchJson<PoolListResponse>(
        `/api/five-flags/pools?processed=all&dedupe_stock=0&limit=${pageSize}&offset=${offset}`
      );
      const pageItems = resp.items || [];
      pageItems.forEach((x) => {
        const id = Number(x.id || 0);
        if (id > 0) ids.push(id);
      });
      total = Number(resp.total || 0);
      offset += pageItems.length;
      if (pageItems.length === 0) break;
    } while (offset < total);
    return ids;
  }, []);

  const handleUploadPoolFile = async () => {
    if (!uploadFile) {
      setActionHint('请先选择上传文件。');
      return;
    }
    const lowerName = uploadFile.name.toLowerCase();
    if (!lowerName.endsWith('.xlsx') && !lowerName.endsWith('.xls')) {
      setActionHint('仅支持 .xlsx / .xls 文件。');
      return;
    }
    const fd = new FormData();
    fd.append('file', uploadFile);
    fd.append('force_overwrite', String(forceOverwrite));
    setUploading(true);
    setActionHint(null);
    try {
      const resp = await fetchJson<PoolUploadResponse>('/api/five-flags/pools/upload', {
        method: 'POST',
        body: fd,
      });
      const msg = [
        resp.upload?.message || '上传成功',
        resp.queue?.job_id ? `job: ${resp.queue.job_id}` : '',
        resp.queue?.status ? `状态: ${resp.queue.status}` : '',
      ].filter(Boolean).join(' · ');
      setActionHint(msg || '上传成功');
      setUploadFile(null);
      await loadData();
    } catch (e) {
      setActionHint(e instanceof Error ? e.message : '上传失败');
    } finally {
      setUploading(false);
    }
  };

  const handleManualRun = async () => {
    if (manualRunning) {
      setRunFeedbackDialog({
        visible: true,
        tone: 'info',
        title: '任务提交中',
        message: '手动筛查正在提交，请稍候查看最新状态。',
      });
      return;
    }
    setManualRunning(true);
    setActionHint(null);
    setRunFeedbackDialog({
      visible: true,
      tone: 'info',
      title: '运行中',
      message: '正在提交手动筛查任务...',
    });
    try {
      let payload: { pool_ids?: number[] } = {};
      if (forceManualRun) {
        const allPoolIds = await fetchAllPoolIds();
        if (allPoolIds.length === 0) {
          setActionHint('强制筛查未启动：股票池为空。');
          setRunFeedbackDialog({
            visible: true,
            tone: 'warning',
            title: '无需运行',
            message: '强制筛查未启动：股票池为空。',
          });
          return;
        }
        payload = { pool_ids: allPoolIds };
      }
      const resp = await fetchJson<ManualRunResponse>('/api/five-flags/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (resp.status === 'skipped') {
        const reason = String(resp.reason || '');
        if (reason === 'up_to_date') {
          setActionHint('未启动：已筛到最新交易日，无需补跑。');
          setRunFeedbackDialog({
            visible: true,
            tone: 'warning',
            title: '无需运行',
            message: '已筛到最新交易日，无需补跑。',
          });
        } else if (reason === 'no_pools') {
          setActionHint('未启动：股票池为空。');
          setRunFeedbackDialog({
            visible: true,
            tone: 'warning',
            title: '无需运行',
            message: '股票池为空，当前无需运行。',
          });
        } else if (reason === 'no_price_data') {
          setActionHint('未启动：行情数据为空，无法确定最近交易日。');
          setRunFeedbackDialog({
            visible: true,
            tone: 'warning',
            title: '无需运行',
            message: '行情数据为空，无法确定最近交易日。',
          });
        } else {
          setActionHint(`未启动：${resp.reason || '不满足就绪条件'}`);
          setRunFeedbackDialog({
            visible: true,
            tone: 'warning',
            title: '无需运行',
            message: `未启动：${resp.reason || '不满足就绪条件'}`,
          });
        }
      } else {
        const runMsg = [
          forceManualRun ? '强制筛查已提交' : '手动筛查已提交',
          resp.job_id ? `job: ${resp.job_id}` : '',
          resp.status ? `状态: ${resp.status}` : '',
        ].filter(Boolean).join(' · ');
        setActionHint(runMsg);
        setRunFeedbackDialog({
          visible: true,
          tone: 'success',
          title: '提交成功',
          message: `${runMsg || '任务已提交。'}\n正在跟踪执行结果...`,
        });
        if (resp.job_id) {
          void watchManualRunResult(resp.job_id, resp.run_id || null);
        }
      }
      // Do not keep the button disabled while waiting for full data refresh.
      void loadData();
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : '手动筛查启动失败';
      setActionHint(errMsg);
      setRunFeedbackDialog({
        visible: true,
        tone: 'error',
        title: '提交失败',
        message: errMsg,
      });
    } finally {
      setManualRunning(false);
    }
  };

  useEffect(() => {
    if (!activeCell || !selectedStock) return;
    const hit = hitKeySet.has(`${activeCell.date}|${activeCell.screenerKey}`);
    if (hit) return;
    const cacheKey = `${selectedStock}|${activeCell.date}|${activeCell.screenerKey}`;
    if (cellDiagCache[cacheKey]) return;

    const reasonMiss = missReasonMap.get(`${activeCell.date}|${activeCell.screenerKey}`) || '';
    const failedChecks = missCheckMap.get(`${activeCell.date}|${activeCell.screenerKey}`) || [];
    const firstFailed = missFirstCheckMap.get(`${activeCell.date}|${activeCell.screenerKey}`) || null;
    if (reasonMiss && (failedChecks.length > 0 || firstFailed)) return;

    const timer = window.setTimeout(() => {
      const params = new URLSearchParams({
        stock_code: selectedStock,
        date: activeCell.date,
        screener_id: activeCell.screenerKey,
      });
      void fetchJson<CellDiagnosisResponse>(`/api/five-flags/diagnose-cell?${params.toString()}`)
        .then((resp) => {
          setCellDiagCache((prev) => ({ ...prev, [cacheKey]: resp }));
        })
        .catch(() => {
          // Backward compatibility: old backend has no diagnose-cell endpoint.
          // Fallback to one-day timeline diagnostics extraction.
          const timelineParams = new URLSearchParams({
            stock_code: selectedStock,
            from: activeCell.date,
            to: activeCell.date,
            include_miss_details: '1',
            max_diag_cells: '20',
          });
          void fetchJson<TimelineResponse>(`/api/five-flags/timeline?${timelineParams.toString()}`)
            .then((timelineResp) => {
              const fallback = extractCellDiagnosisFromTimeline(timelineResp, activeCell.date, activeCell.screenerKey);
              if (!fallback) return;
              setCellDiagCache((prev) => ({ ...prev, [cacheKey]: fallback }));
            })
            .catch(() => {
              // Keep UI stable on fallback request failure.
            });
        });
    }, 120);

    return () => window.clearTimeout(timer);
  }, [activeCell, selectedStock, hitKeySet, missReasonMap, missCheckMap, missFirstCheckMap, cellDiagCache]);

  const hoverPayload = useMemo(() => {
    if (!activeCell) return null;
    const target = FIXED_SCREENERS.find((item) => item.key === activeCell.screenerKey);
    if (!target) return null;
    const hit = hitKeySet.has(`${activeCell.date}|${activeCell.screenerKey}`);
    const diagKey = `${selectedStock}|${activeCell.date}|${activeCell.screenerKey}`;
    const diag = cellDiagCache[diagKey];
    const reasonHit = detailReasonMap.get(`${activeCell.date}|${activeCell.screenerKey}`) || '';
    const reasonMissRaw = missReasonMap.get(`${activeCell.date}|${activeCell.screenerKey}`) || '';
    const failedChecksRaw = missCheckMap.get(`${activeCell.date}|${activeCell.screenerKey}`) || [];
    const firstFailedRaw = missFirstCheckMap.get(`${activeCell.date}|${activeCell.screenerKey}`) || null;
    const diagnosticHintsRaw = missHintMap.get(`${activeCell.date}|${activeCell.screenerKey}`) || [];
    const reasonMiss = reasonMissRaw || (diag?.reason_miss || '');
    const failedChecks = failedChecksRaw.length > 0 ? failedChecksRaw : (diag?.failed_checks || []);
    const firstFailedCheck = firstFailedRaw || diag?.first_failed_check || null;
    const diagnosticHints = diagnosticHintsRaw.length > 0 ? diagnosticHintsRaw : (diag?.diagnostic_hints || []);
    const quote = quoteByDate.get(activeCell.date) || diag?.daily_quote || null;
    return {
      date: activeCell.date,
      label: target.label,
      hit,
      failedChecks,
      firstFailedCheck,
      diagnosticHints,
      quote,
      stockName: selectedStockMeta?.name || diag?.stock_name || selectedStock,
      stockCode: selectedStockMeta?.code || selectedStock,
      pinned: !!pinnedCell,
      reason: hit
        ? (reasonHit || '命中该筛选器，接口未返回更详细的命中解释。')
        : (reasonMiss || `当日未命中「${target.label}」筛选条件。`),
    };
  }, [activeCell, pinnedCell, hitKeySet, detailReasonMap, missReasonMap, missCheckMap, missFirstCheckMap, missHintMap, quoteByDate, selectedStock, selectedStockMeta, cellDiagCache]);

  const groupedFailedChecks = useMemo(() => {
    if (!hoverPayload || hoverPayload.hit) return [] as Array<{ label: string; items: FailedCheck[] }>;
    const order: string[] = [];
    const grouped = new Map<string, FailedCheck[]>();
    hoverPayload.failedChecks.forEach((check) => {
      const label = getFailedCheckGroupLabel(check);
      if (!grouped.has(label)) {
        grouped.set(label, []);
        order.push(label);
      }
      grouped.get(label)?.push(check);
    });
    return order.map((label) => ({ label, items: grouped.get(label) || [] }));
  }, [hoverPayload]);

  const groupedDiagnosticHints = useMemo(() => {
    if (!hoverPayload || hoverPayload.hit) return [] as Array<{ label: string; items: string[] }>;
    const order: string[] = [];
    const grouped = new Map<string, string[]>();
    (hoverPayload.diagnosticHints || []).forEach((rawHint) => {
      const text = String(rawHint || '').trim();
      if (!text) return;
      const matched = text.match(/^([^:：]+)[:：]\s*(.+)$/);
      const label = matched ? matched[1].trim() : '附加提示';
      const content = matched ? matched[2].trim() : text;
      if (!grouped.has(label)) {
        grouped.set(label, []);
        order.push(label);
      }
      grouped.get(label)?.push(content);
    });
    return order.map((label) => ({ label, items: grouped.get(label) || [] }));
  }, [hoverPayload]);
  const detailBodyColor = isLight ? '#1f2937' : '#e2e8f0';
  const detailSecondaryColor = isLight ? '#334155' : '#cbd5e1';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: palette.pageBg, color: palette.text }}>
      <div style={{ borderBottom: `1px solid ${palette.border}`, padding: '10px 12px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
          <span style={{ color: palette.title, fontSize: 11, letterSpacing: 2, fontWeight: 700 }}>五图跟踪：老鸭头股票池</span>
          <span style={{ fontSize: 11, color: statusColor, fontWeight: 700 }}>
            {latestRun?.status || health?.status || 'unknown'}
          </span>
        </div>
        <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <input
            key={uploadFile ? `${uploadFile.name}-${uploadFile.size}` : 'no-file'}
            type="file"
            accept=".xls,.xlsx"
            onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
            style={{ fontSize: 11, color: palette.dimText, maxWidth: 260 }}
          />
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: palette.dimText }}>
            <input
              type="checkbox"
              checked={forceOverwrite}
              onChange={(e) => setForceOverwrite(e.target.checked)}
            />
            强制覆盖
          </label>
          <button
            onClick={() => { void handleUploadPoolFile(); }}
            disabled={uploading || !uploadFile}
            style={{
              border: `1px solid ${uploading || !uploadFile ? palette.inputBorder : palette.badge}`,
              color: uploading || !uploadFile ? palette.dimText : palette.badge,
              background: 'transparent',
              borderRadius: 999,
              padding: '2px 9px',
              cursor: uploading || !uploadFile ? 'not-allowed' : 'pointer',
              fontSize: 11,
              fontWeight: 700,
            }}
          >
            {uploading ? '上传中...' : '上传并入队'}
          </button>
          <button
            onClick={() => setShowUploadHelp((prev) => !prev)}
            style={{
              border: `1px solid ${palette.inputBorder}`,
              color: palette.dimText,
              background: 'transparent',
              borderRadius: 999,
              padding: '2px 8px',
              cursor: 'pointer',
              fontSize: 11,
            }}
          >
            {showUploadHelp ? '收起上传说明' : '上传说明'}
          </button>
        </div>
        {showUploadHelp && (
          <div style={{ marginTop: 6, fontSize: 11, color: palette.dimText }}>
            文件名: 老鸭头YYMMDD.xlsx / 老鸭头YYMMDD-YYMMDD.xlsx；表头支持 代码 / 名称（数字）
          </div>
        )}
      </div>

      {loading ? (
        <div style={{ padding: 16, color: palette.dimText }}>Loading...</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateRows: 'auto auto 1fr', height: '100%', overflow: 'hidden' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 4, padding: '4px 10px' }}>
            <StatCard label="命中股票数" value={hitStockCodeSet.size} theme={theme} compact />
            <StatCard label="处理股票数" value={health?.result_total_count ?? 0} theme={theme} compact />
            <StatCard label="总股票数" value={resultsTotal} theme={theme} compact />
          </div>

          <div style={{ padding: '0 10px 6px', borderBottom: `1px solid ${palette.border}` }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 8 }}>
              <input
                value={stockSearch}
                onChange={(e) => setStockSearch(e.target.value)}
                placeholder="搜索股票代码或名称"
                style={{ width: '100%', boxSizing: 'border-box', background: palette.inputBg, color: palette.text, border: `1px solid ${palette.inputBorder}`, borderRadius: 4, padding: '5px 8px', fontSize: 12 }}
              />
            </div>
            {actionHint && (
              <div style={{ marginTop: 6, fontSize: 11, color: palette.dimText }}>
                {actionHint}
              </div>
            )}
            <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 11, color: palette.dimText }}>快捷区间</span>
              {[5, 10, 15].map((d) => (
                <button
                  key={d}
                  onClick={() => handlePresetClick(d as 5 | 10 | 15)}
                  style={{
                    border: `1px solid ${windowPreset === d ? palette.badge : palette.inputBorder}`,
                    color: windowPreset === d ? palette.badge : palette.dimText,
                    background: windowPreset === d ? (isLight ? 'rgba(30,64,175,0.08)' : 'rgba(255,203,5,0.12)') : 'transparent',
                    borderRadius: 999,
                    padding: '2px 9px',
                    cursor: 'pointer',
                    fontSize: 11,
                    fontWeight: 700,
                  }}
                >
                  {d}
                </button>
              ))}
              <button
                onClick={() => shiftWindow(-1)}
                style={{
                  border: `1px solid ${palette.inputBorder}`,
                  color: palette.dimText,
                  background: 'transparent',
                  borderRadius: 999,
                  padding: '2px 9px',
                  cursor: 'pointer',
                  fontSize: 11,
                  fontWeight: 700,
                  marginLeft: 8,
                }}
              >
                上一窗
              </button>
              <button
                onClick={() => shiftWindow(1)}
                style={{
                  border: `1px solid ${palette.inputBorder}`,
                  color: palette.dimText,
                  background: 'transparent',
                  borderRadius: 999,
                  padding: '2px 9px',
                  cursor: 'pointer',
                  fontSize: 11,
                  fontWeight: 700,
                }}
              >
                下一窗
              </button>
              <span style={{ fontSize: 11, color: palette.dimText, marginLeft: 8 }}>列表可视条数</span>
              <select
                value={visibleStockCount}
                onChange={(e) => setVisibleStockCount(Number(e.target.value) as 10 | 15 | 20)}
                style={{ background: palette.inputBg, color: palette.text, border: `1px solid ${palette.inputBorder}`, borderRadius: 4, padding: '2px 6px', fontSize: 11 }}
              >
                <option value={10}>10</option>
                <option value={15}>15</option>
                <option value={20}>20</option>
              </select>
              <button
                onClick={() => setLeftPanelCollapsed((prev) => !prev)}
                style={{
                  border: `1px solid ${palette.inputBorder}`,
                  color: palette.dimText,
                  background: 'transparent',
                  borderRadius: 999,
                  padding: '2px 9px',
                  cursor: 'pointer',
                  fontSize: 11,
                  fontWeight: 700,
                }}
              >
                {leftPanelCollapsed ? '展开左区' : '收起左区'}
              </button>
              {selectedStockMeta && (
                <span style={{ marginLeft: 'auto', fontSize: 11, color: palette.dimText }}>
                  当前股票: <span style={{ color: palette.text }}>{selectedStockMeta.code} {selectedStockMeta.name} {selectedStockMeta.sectorCompound || '—'}</span>
                </span>
              )}
            </div>
          </div>

          <div style={{ minHeight: 0, overflow: 'hidden', display: 'grid', gridTemplateColumns: leftPanelCollapsed ? '36px 1fr' : '270px 1fr' }}>
            <div style={{ borderRight: `1px solid ${palette.border}`, padding: leftPanelCollapsed ? '10px 4px' : 10, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: leftPanelCollapsed ? 'center' : 'space-between', marginBottom: 8 }}>
                {!leftPanelCollapsed && (
                  <div style={{ fontSize: 11, color: palette.title, letterSpacing: 1 }}>STOCK WHEEL LIST</div>
                )}
                <button
                  onClick={() => setLeftPanelCollapsed((prev) => !prev)}
                  style={{
                    border: `1px solid ${palette.inputBorder}`,
                    background: 'transparent',
                    color: palette.text,
                    borderRadius: 999,
                    width: 24,
                    height: 24,
                    cursor: 'pointer',
                    fontSize: 11,
                    lineHeight: '22px',
                    padding: 0,
                  }}
                  title={leftPanelCollapsed ? '展开左区' : '折叠左区'}
                >
                  {leftPanelCollapsed ? '▶' : '◀'}
                </button>
              </div>
              {!leftPanelCollapsed && (
                <div style={{ border: `1px solid ${palette.border}`, borderRadius: 6, overflow: 'hidden', background: palette.panelBg }}>
                  <div style={{ maxHeight: visibleStockCount * 32, overflowY: 'auto' }}>
                    {filteredStockOptions.length === 0 ? (
                      <div style={{ padding: 10, fontSize: 12, color: palette.dimText }}>无股票</div>
                    ) : (
                      filteredStockOptions.map((item) => {
                        const active = item.code === selectedStock;
                        return (
                          <button
                            key={item.code}
                            onClick={() => {
                              setSelectedStock(item.code);
                              setHoverCell(null);
                              setPinnedCell(null);
                            }}
                            title={`${item.code} · ${item.hasHits ? '已被五旗选中过' : '尚未被五旗选中'}`}
                            style={{
                              width: '100%',
                              height: 32,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              border: 'none',
                              borderBottom: `1px solid ${palette.border}`,
                              background: active ? (isLight ? 'rgba(30,64,175,0.08)' : 'rgba(255,203,5,0.12)') : 'transparent',
                              color: active ? palette.text : palette.dimText,
                              cursor: 'pointer',
                              padding: '0 8px',
                              fontSize: 12,
                              textAlign: 'left',
                            }}
                          >
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, minWidth: 0 }}>
                              <span style={{ fontWeight: 700, color: active ? palette.badge : palette.text }}>{item.code}</span>
                              <span
                                style={{
                                  width: 9,
                                  height: 9,
                                  borderRadius: 999,
                                  background: item.hasHits ? '#22c55e' : '#94a3b8',
                                  border: item.hasHits ? '1px solid #166534' : '1px solid #475569',
                                  boxShadow: item.hasHits ? '0 0 0 2px rgba(34,197,94,0.28)' : 'none',
                                  display: 'inline-block',
                                  flexShrink: 0,
                                }}
                              />
                            </span>
                            <span style={{ marginLeft: 8, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {item.name}
                              <span
                                style={{
                                  marginLeft: 8,
                                  fontSize: 10,
                                  color: item.hasHits ? '#22c55e' : palette.dimText,
                                  fontWeight: item.hasHits ? 700 : 500,
                                }}
                              >
                                {item.hasHits ? '命中' : '未命中'}
                              </span>
                            </span>
                          </button>
                        );
                      })
                    )}
                  </div>
                </div>
              )}
            </div>

            <div style={{ minWidth: 0, padding: 10, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
              <div
                style={{
                  marginBottom: 8,
                  border: `1px solid ${palette.border}`,
                  borderRadius: 6,
                  background: palette.panelBg,
                  padding: '8px 10px',
                }}
              >
                <div style={{ fontSize: 11, color: palette.title, letterSpacing: 1, marginBottom: 6 }}>
                  五图运行控制
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <button
                    onClick={() => { void handleManualRun(); }}
                    style={{
                      border: `1px solid ${palette.badge}`,
                      color: palette.badge,
                      background: 'transparent',
                      borderRadius: 999,
                      padding: '2px 9px',
                      cursor: 'pointer',
                      fontSize: 11,
                      fontWeight: 700,
                    }}
                  >
                    {forceManualRun ? '强制筛查' : '手动筛查'}
                  </button>
                  <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: palette.dimText }}>
                    <input
                      type="checkbox"
                      checked={forceManualRun}
                      onChange={(e) => setForceManualRun(e.target.checked)}
                    />
                    强制筛查
                  </label>
                  <span style={{ fontSize: 11, color: palette.dimText }}>
                    {hasUnprocessedPools ? `存在未处理股票：${Number(health?.pool_unprocessed_count || 0)}` : '当前无未处理股票'}
                  </span>
                </div>
              </div>
              <div
                style={{
                  marginBottom: 8,
                  border: `1px solid ${palette.border}`,
                  borderRadius: 6,
                  background: palette.panelBg,
                  padding: '8px 10px',
                }}
              >
                <div style={{ fontSize: 11, color: palette.title, letterSpacing: 1, marginBottom: 6 }}>
                  当前上下文
                </div>
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 11, color: palette.dimText }}>
                  <span>
                    股票: <span style={{ color: palette.text }}>{selectedStockMeta ? `${selectedStockMeta.code} ${selectedStockMeta.name} ${selectedStockMeta.sectorCompound || '—'}` : (selectedStock || '—')}</span>
                  </span>
                  <span>
                    窗口: <span style={{ color: palette.text }}>{windowStart} - {windowEnd}</span>（{currentWindowSpanDays} 天）
                  </span>
                  <span>
                    诊断: <span style={{ color: palette.text }}>
                      {timeline?.diag_meta
                        ? (timeline.diag_meta.diagnostics_applied ? '已启用' : '未启用（窗口过大或未请求）')
                        : '待加载'}
                    </span>
                  </span>
                </div>
                {dateRangeInvalid && (
                  <div style={{ marginTop: 6, fontSize: 11, color: palette.warnText }}>
                    时间窗口无效：开始日期必须早于或等于结束日期。
                  </div>
                )}
                {!!timeline?.diag_meta && !timeline.diag_meta.diagnostics_applied && (
                  <div style={{ marginTop: 6, fontSize: 11, color: palette.warnText }}>
                    诊断细项未启用：当前窗口过大或未请求细项诊断，未命中详情将展示简化信息。
                  </div>
                )}
              </div>
              {runFeedbackDialog.visible && (
                <div
                  style={{
                    position: 'fixed',
                    inset: 0,
                    background: 'rgba(0, 0, 0, 0.45)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 1200,
                  }}
                >
                  <div
                    style={{
                      width: 'min(420px, calc(100vw - 24px))',
                      borderRadius: 8,
                      border: `1px solid ${palette.border}`,
                      background: palette.panelBg,
                      color: palette.text,
                      boxShadow: '0 14px 34px rgba(0,0,0,0.35)',
                      padding: 12,
                    }}
                  >
                    <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>
                      {runFeedbackDialog.title}
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        lineHeight: 1.5,
                        color: runFeedbackDialog.tone === 'error' ? palette.warnText : palette.dimText,
                        whiteSpace: 'pre-wrap',
                      }}
                    >
                      {runFeedbackDialog.message}
                    </div>
                    <div style={{ marginTop: 10, display: 'flex', justifyContent: 'flex-end' }}>
                      <button
                        onClick={() => setRunFeedbackDialog((prev) => ({ ...prev, visible: false }))}
                        style={{
                          border: `1px solid ${palette.inputBorder}`,
                          color: palette.text,
                          background: 'transparent',
                          borderRadius: 6,
                          padding: '4px 10px',
                          cursor: 'pointer',
                          fontSize: 12,
                        }}
                      >
                        关闭
                      </button>
                    </div>
                  </div>
                </div>
              )}
              {!!selectedStock && !historyTimelineLoaded && (
                <div style={{ marginBottom: 8, border: `1px solid ${palette.border}`, borderRadius: 6, background: palette.panelBg, padding: '8px 10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 11, color: palette.dimText }}>全历史提示条按需加载（减少外网初次加载时延）</span>
                  <button
                    onClick={() => { void loadHistoryTimeline(); }}
                    style={{
                      border: `1px solid ${palette.inputBorder}`,
                      color: palette.text,
                      background: 'transparent',
                      borderRadius: 999,
                      padding: '2px 9px',
                      cursor: 'pointer',
                      fontSize: 11,
                    }}
                  >
                    {historyTimelineLoading ? '加载中...' : '加载全历史提示条'}
                  </button>
                </div>
              )}
              {!!selectedStock && historyTimelineLoaded && historyStripDates.length > 0 && (
                <div style={{ marginBottom: 8, border: `1px solid ${palette.border}`, borderRadius: 6, background: palette.panelBg, padding: '8px 10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <span style={{ fontSize: 11, color: palette.dimText }}>全历史交易日提示条</span>
                    <span style={{ fontSize: 11, color: palette.dimText }}>
                      {historyStripDates[0]} - {historyStripDates[historyStripDates.length - 1]}
                    </span>
                  </div>
                  <div style={{ position: 'relative', height: 20 }}>
                    <div
                      style={{
                        position: 'absolute',
                        left: 0,
                        right: 0,
                        top: 9,
                        height: 2,
                        borderRadius: 999,
                        background: palette.inputBorder,
                      }}
                    />
                    {historyStripDates.map((date, idx) => {
                      const isHit = historyHitDateSet.has(date);
                      const left = historyStripDates.length <= 1 ? 0 : (idx / (historyStripDates.length - 1)) * 100;
                      const inCurrentWindow = date >= windowStart && date <= windowEnd;
                      return (
                        <button
                          key={`history-day-${date}`}
                          onClick={() => jumpWindowToDate(date)}
                          title={`${date} ${isHit ? '命中' : '未命中'}（点击跳转）`}
                          style={{
                            position: 'absolute',
                            left: `${left}%`,
                            top: inCurrentWindow ? 1 : 3,
                            transform: 'translateX(-50%)',
                            width: inCurrentWindow ? 11 : 9,
                            height: inCurrentWindow ? 11 : 9,
                            borderRadius: 999,
                            border: `1px solid ${
                              isHit
                                ? (inCurrentWindow ? '#f59e0b' : '#93c5fd')
                                : (inCurrentWindow ? '#6b7280' : '#475569')
                            }`,
                            background: isHit
                              ? (inCurrentWindow ? '#f59e0b' : '#2563eb')
                              : (inCurrentWindow ? '#9ca3af' : '#64748b'),
                            boxShadow: inCurrentWindow
                              ? `0 0 0 2px ${isHit ? 'rgba(245,158,11,0.28)' : 'rgba(100,116,139,0.28)'}`
                              : 'none',
                            cursor: 'pointer',
                            padding: 0,
                          }}
                        />
                      );
                    })}
                  </div>
                  <div style={{ marginTop: 6, fontSize: 11, color: palette.dimText }}>
                    交易日: {historyStripDates.length} 天 · 命中: {historyHitDateSet.size} 天（点击任意点可跳转）
                  </div>
                </div>
              )}
              <div style={{ fontSize: 11, color: palette.title, letterSpacing: 1, marginBottom: 8 }}>
                时间 × 五筛选器分节柱（命中彩色 / 未命中灰色）
              </div>
              <div style={{ marginBottom: 8, fontSize: 11, color: palette.dimText }}>
                操作: 悬停查看，点击格子可锁定详情，再点一次取消锁定。
              </div>
              {!selectedStock ? (
                <div style={{ padding: 16, fontSize: 12, color: palette.dimText }}>请先从左侧列表选择股票。</div>
              ) : dateColumns.length === 0 ? (
                <div style={{ padding: 16, fontSize: 12, color: palette.dimText }}>当前时间窗无可展示日期。</div>
              ) : (
                <div style={{ border: `1px solid ${palette.border}`, borderRadius: 6, overflow: 'auto', padding: 8 }}>
                  <div style={{ minWidth: Math.max(540, dateColumns.length * 28 + 120), display: 'grid', gridTemplateColumns: '90px 1fr', columnGap: 8 }}>
                    <div style={{ display: 'grid', gridTemplateRows: 'repeat(5, 18px) 18px', rowGap: 5, alignItems: 'center', position: 'sticky', left: 0, zIndex: 2, background: palette.panelBg, paddingRight: 8, borderRight: `1px solid ${palette.border}` }}>
                      {FIXED_SCREENERS.map((item) => (
                        <div key={item.key} style={{ fontSize: 11, color: palette.dimText }}>
                          {item.label}
                        </div>
                      ))}
                      <div style={{ fontSize: 10, color: palette.dimText }}>日期</div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                      {dateColumns.map((date) => (
                        <div key={date} style={{ display: 'grid', gridTemplateRows: 'repeat(5, 18px) 18px', rowGap: 5, justifyItems: 'center' }}>
                          {FIXED_SCREENERS.map((item) => {
                            const hit = hitKeySet.has(`${date}|${item.key}`);
                            const thisKey = `${date}|${item.key}`;
                            const active = thisKey === activeCellKey;
                            return (
                              <button
                                key={`${date}-${item.key}`}
                                onMouseEnter={() => setHoverCell({ date, screenerKey: item.key })}
                                onMouseLeave={() => setHoverCell(null)}
                                onClick={() => {
                                  setPinnedCell((prev) => {
                                    if (prev && prev.date === date && prev.screenerKey === item.key) return null;
                                    return { date, screenerKey: item.key };
                                  });
                                  setHoverCell({ date, screenerKey: item.key });
                                }}
                                style={{
                                  width: 18,
                                  height: 18,
                                  borderRadius: 4,
                                  border: `1px solid ${active ? '#111827' : (hit ? item.color : '#cbd5e1')}`,
                                  background: hit ? item.color : '#d1d5db',
                                  cursor: 'pointer',
                                  padding: 0,
                                  boxShadow: active ? (isLight ? '0 0 0 2px rgba(15,23,42,0.15)' : '0 0 0 2px rgba(255,255,255,0.2)') : 'none',
                                }}
                                title={`${date} · ${item.label} · ${hit ? '命中' : '未命中'}（点击可锁定）`}
                              />
                            );
                          })}
                          <div style={{ fontSize: 12, color: palette.text, fontWeight: 600, whiteSpace: 'nowrap' }}>{date.slice(5)}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
              <div style={{ marginTop: 8, fontSize: 11, color: palette.title, letterSpacing: 1 }}>
                单元详情
              </div>
              <div style={{ marginTop: 8, border: `1px solid ${palette.border}`, borderRadius: 6, background: palette.panelBg, minHeight: 0, flex: 1, overflow: 'auto' }}>
                {!hoverPayload ? (
                  <div style={{ padding: 12, fontSize: 12, color: detailSecondaryColor }}>
                    请选择上方格子查看该日期/筛选器的命中与未命中详情。
                  </div>
                ) : (
                  <div style={{ padding: 12 }}>
                    <div style={{ fontSize: 13, color: palette.text }}>
                      {hoverPayload.date} · {selectedStockMeta?.code || selectedStock} · {hoverPayload.label}
                    </div>
                    <div style={{ marginTop: 4, fontSize: 12, color: hoverPayload.hit ? '#16a34a' : '#ef4444', fontWeight: 700 }}>
                      {hoverPayload.hit ? '命中' : '未命中'} {hoverPayload.pinned ? '· 已锁定' : ''}
                    </div>
                    <div style={{ marginTop: 6, fontSize: 12, color: detailSecondaryColor, lineHeight: 1.45 }}>
                      基本信息: {hoverPayload.stockCode} {hoverPayload.stockName}
                    </div>
                    {hoverPayload.pinned && (
                      <div style={{ marginTop: 6 }}>
                        <button
                          onClick={() => setPinnedCell(null)}
                          style={{
                            border: `1px solid ${palette.inputBorder}`,
                            color: palette.text,
                            background: 'transparent',
                            borderRadius: 4,
                            padding: '2px 8px',
                            cursor: 'pointer',
                            fontSize: 12,
                          }}
                        >
                          取消锁定
                        </button>
                      </div>
                    )}
                    <div style={{ marginTop: 6, fontSize: 12, color: detailBodyColor, lineHeight: 1.5 }}>
                      {hoverPayload.reason}
                    </div>
                    {!hoverPayload.hit && hoverPayload.firstFailedCheck && (
                      <div style={{ marginTop: 8, fontSize: 12, color: palette.text }}>
                        首个失败条件: {hoverPayload.firstFailedCheck.label} - {hoverPayload.firstFailedCheck.message}
                      </div>
                    )}
                    {!hoverPayload.hit && groupedDiagnosticHints.length > 0 && (
                      <div style={{ marginTop: 8, fontSize: 12, color: detailBodyColor, lineHeight: 1.5 }}>
                        <div style={{ color: palette.text, fontWeight: 700 }}>附加诊断提示</div>
                        {groupedDiagnosticHints.map((group, idx) => (
                          <details key={`${hoverPayload.date}-hint-group-${group.label}`} open={idx === 0} style={{ marginTop: 4 }}>
                            <summary style={{ cursor: 'pointer', color: palette.text, fontWeight: 700 }}>{group.label}</summary>
                            {group.items.map((hint, hidx) => (
                              <div key={`${hoverPayload.date}-hint-${group.label}-${hidx}`} style={{ marginTop: 3, color: detailSecondaryColor }}>
                                - {hint}
                              </div>
                            ))}
                          </details>
                        ))}
                      </div>
                    )}
                    {!hoverPayload.hit && groupedFailedChecks.length > 0 && (
                      <div style={{ marginTop: 8, fontSize: 12, color: detailBodyColor, lineHeight: 1.5 }}>
                        {groupedFailedChecks.map((group, idx) => (
                          <details key={`${hoverPayload.date}-${group.label}`} open={idx < 2} style={{ marginBottom: 6 }}>
                            <summary style={{ cursor: 'pointer', color: palette.text, fontWeight: 700 }}>{group.label}</summary>
                            {group.items.map((check, cidx) => (
                              <div key={`${hoverPayload.date}-${group.label}-${cidx}`} style={{ marginTop: 3, color: detailSecondaryColor }}>
                                - {check.label}: {check.message}
                              </div>
                            ))}
                          </details>
                        ))}
                      </div>
                    )}
                    {!hoverPayload.hit && timeline?.diag_meta && !timeline.diag_meta.diagnostics_applied && (
                      <div style={{ marginTop: 8, fontSize: 12, color: palette.warnText }}>
                        当前窗口未开启细项诊断（窗口过大），请缩短时间范围后查看完整未命中细项原因。
                      </div>
                    )}
                    {hoverPayload.quote && (
                      <div style={{ marginTop: 8, fontSize: 12, color: detailSecondaryColor, lineHeight: 1.45 }}>
                        <div>当日行情: O {Number(hoverPayload.quote.open).toFixed(2)} / H {Number(hoverPayload.quote.high).toFixed(2)} / L {Number(hoverPayload.quote.low).toFixed(2)} / C {Number(hoverPayload.quote.close).toFixed(2)}</div>
                        <div>涨跌幅: {Number(hoverPayload.quote.pct_change).toFixed(2)}% · 换手: {Number(hoverPayload.quote.turnover).toFixed(2)}%</div>
                        <div>成交量: {Number(hoverPayload.quote.volume).toLocaleString()} · 成交额: {Number(hoverPayload.quote.amount).toLocaleString()}</div>
                      </div>
                    )}
                  </div>
                )}
              </div>
              <div style={{ marginTop: 8, border: `1px solid ${palette.border}`, borderRadius: 6, background: palette.panelBg, padding: '8px 10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                  <button
                    onClick={() => setCronLogsCollapsed((prev) => !prev)}
                    style={{
                      border: 'none',
                      background: 'transparent',
                      color: palette.title,
                      cursor: 'pointer',
                      fontSize: 11,
                      letterSpacing: 1,
                      padding: 0,
                      textAlign: 'left',
                    }}
                    title={cronLogsCollapsed ? '展开日志' : '折叠日志'}
                  >
                    {cronLogsCollapsed ? '▶' : '▼'} Cron 任务日志
                  </button>
                  <button
                    onClick={() => { void loadCronLogs(); }}
                    style={{
                      border: `1px solid ${palette.inputBorder}`,
                      color: palette.dimText,
                      background: 'transparent',
                      borderRadius: 999,
                      padding: '2px 8px',
                      cursor: 'pointer',
                      fontSize: 11,
                    }}
                  >
                    {cronLogsLoading ? '刷新中...' : '刷新'}
                  </button>
                </div>
                {!cronLogsCollapsed && (
                  <>
                    <div style={{ fontSize: 11, color: palette.dimText, marginTop: 6, marginBottom: 6 }}>
                      {cronLogs?.stdout?.updated_at ? `最近更新: ${cronLogs.stdout.updated_at}` : '暂无更新记录'}
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                      <div>
                        <div style={{ fontSize: 11, color: palette.dimText, marginBottom: 4 }}>标准输出</div>
                        <pre
                          style={{
                            margin: 0,
                            maxHeight: 120,
                            overflow: 'auto',
                            background: palette.inputBg,
                            border: `1px solid ${palette.inputBorder}`,
                            borderRadius: 4,
                            padding: 8,
                            fontSize: 11,
                            lineHeight: 1.35,
                            color: palette.text,
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                          }}
                        >
                          {(cronLogs?.stdout?.lines || []).join('') || '暂无日志'}
                        </pre>
                      </div>
                      <div>
                        <div style={{ fontSize: 11, color: palette.dimText, marginBottom: 4 }}>错误输出</div>
                        <pre
                          style={{
                            margin: 0,
                            maxHeight: 120,
                            overflow: 'auto',
                            background: palette.inputBg,
                            border: `1px solid ${palette.inputBorder}`,
                            borderRadius: 4,
                            padding: 8,
                            fontSize: 11,
                            lineHeight: 1.35,
                            color: palette.warnText,
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                          }}
                        >
                          {(cronLogs?.stderr?.lines || []).join('') || '暂无错误日志'}
                        </pre>
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div style={{ padding: '6px 10px', background: palette.warnBg, color: palette.warnText, fontSize: 11 }}>
          {error}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, theme = 'dark', compact = false }: { label: string; value: number | string; theme?: 'dark' | 'light'; compact?: boolean }) {
  const isLight = theme === 'light';
  return (
    <div style={{ border: `1px solid ${isLight ? '#dbe3ef' : '#1e2d3d'}`, borderRadius: 6, padding: compact ? '3px 6px' : 8, background: isLight ? '#ffffff' : '#111827' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <div style={{ fontSize: compact ? 10 : 11, color: isLight ? '#475569' : '#9ca3af', letterSpacing: 0.5 }}>{label}</div>
        <div style={{ fontSize: compact ? 13 : 16, fontWeight: 700, color: isLight ? '#1d4ed8' : '#93c5fd' }}>{value}</div>
      </div>
    </div>
  );
}
