import { useCallback, useEffect, useMemo, useState } from 'react';

interface FiveFlagsHealth {
  status: string;
  timestamp: string;
  pool_total_count: number;
  pool_unprocessed_count: number;
  result_total_count: number;
  latest_result_date: string | null;
}

interface UnprocessedSummary {
  unprocessed_pools: number;
  unprocessed_dates_estimate: number;
  by_file_name: { file_name: string; cnt: number }[];
}

interface PoolItem {
  id: number;
  stock_code: string;
  stock_name: string;
  start_date: string;
  end_date: string;
  file_name: string;
  processed: number;
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
  close_price: number;
  pool_id: number;
  created_at: string;
}

interface TimelineEntry {
  date: string;
  hits: string[];
  details: TimelineDetail[];
}

interface TimelineResponse {
  stock_code: string;
  timeline: TimelineEntry[];
}

interface RunDetailResponse {
  run: RunItem;
  progress?: {
    percent?: number;
    processed_stocks?: number;
    total_stocks?: number;
  };
}

function fmtTs(value?: string | null): string {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString('zh-CN', { hour12: false });
}

function fmtPrice(value: number): string {
  return Number.isFinite(value) ? value.toFixed(2) : '—';
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${text.slice(0, 120)}`);
  }
  return res.json() as Promise<T>;
}

export default function FiveFlagsMonitor() {
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [health, setHealth] = useState<FiveFlagsHealth | null>(null);
  const [summary, setSummary] = useState<UnprocessedSummary | null>(null);
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [liveRun, setLiveRun] = useState<RunItem | null>(null);
  const [lastTickAt, setLastTickAt] = useState<string | null>(null);
  const [unprocessedPools, setUnprocessedPools] = useState<PoolItem[]>([]);
  const [results, setResults] = useState<FiveFlagsResult[]>([]);
  const [resultsTotal, setResultsTotal] = useState(0);

  const [stockFilter, setStockFilter] = useState('');
  const [screenerFilter, setScreenerFilter] = useState('');
  const [selectedStock, setSelectedStock] = useState('');
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      const [h, s, r, p, rs] = await Promise.all([
        fetchJson<FiveFlagsHealth>('/api/five-flags/health'),
        fetchJson<UnprocessedSummary>('/api/five-flags/unprocessed-summary'),
        fetchJson<{ items: RunItem[] }>('/api/five-flags/runs?limit=5'),
        fetchJson<{ items: PoolItem[] }>('/api/five-flags/pools?processed=0&limit=20'),
        fetchJson<{ items: FiveFlagsResult[]; total: number }>(
          `/api/five-flags/results?limit=100${stockFilter ? `&stock_code=${encodeURIComponent(stockFilter)}` : ''}`
        ),
      ]);
      setHealth(h);
      setSummary(s);
      setRuns(r.items || []);
      setLiveRun((r.items && r.items.length > 0) ? r.items[0] : null);
      setUnprocessedPools(p.items || []);
      setResults(rs.items || []);
      setResultsTotal(rs.total || 0);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Load failed');
    } finally {
      setLoading(false);
    }
  }, [stockFilter]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    const timer = setInterval(() => {
      void loadData();
    }, 15000);
    return () => clearInterval(timer);
  }, [loadData]);

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
        setLastTickAt(new Date().toISOString());
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
    void fetchJson<TimelineResponse>(
      `/api/five-flags/timeline?stock_code=${encodeURIComponent(selectedStock)}`
    )
      .then(setTimeline)
      .catch(() => setTimeline(null));
  }, [selectedStock]);

  const latestRun = liveRun || runs[0] || null;
  const canRunOnePool = unprocessedPools.length > 0;
  const filteredResults = useMemo(() => {
    if (!screenerFilter.trim()) return results;
    const key = screenerFilter.trim().toLowerCase();
    return results.filter((item) => item.screener_id.toLowerCase().includes(key));
  }, [results, screenerFilter]);

  const statusColor = useMemo(() => {
    const st = latestRun?.status || health?.status || 'unknown';
    if (st === 'running') return '#f59e0b';
    if (st === 'completed' || st === 'healthy') return '#22c55e';
    if (st === 'failed' || st === 'critical') return '#ef4444';
    return '#9ca3af';
  }, [latestRun?.status, health?.status]);

  const triggerRun = useCallback(async (dryRun: boolean) => {
    if (!dryRun && !canRunOnePool) return;
    try {
      setRunning(true);
      setError(null);
      const body = dryRun
        ? { dry_run: true, snapshot_id: `ui_${Date.now()}` }
        : {
            dry_run: false,
            max_workers: 1,
            pool_ids: [unprocessedPools[0].id],
            snapshot_id: `ui_${Date.now()}`,
          };
      await fetchJson('/api/five-flags/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      await loadData();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Run failed');
    } finally {
      setRunning(false);
    }
  }, [canRunOnePool, loadData, unprocessedPools]);

  const latestRunSummary = useMemo(() => {
    if (!latestRun) return 'No run yet';
    const status = latestRun.status || 'unknown';
    const processed = latestRun.progress?.processed_stocks ?? latestRun.processed_stocks ?? 0;
    const total = latestRun.progress?.total_stocks ?? latestRun.total_stocks ?? 0;
    const matches = latestRun.total_matches ?? 0;
    return `${status} · ${processed}/${total} pools · ${matches} matches`;
  }, [latestRun]);

  const progressPercent = useMemo(() => {
    const fromProgress = latestRun?.progress?.percent;
    if (typeof fromProgress === 'number') return Math.max(0, Math.min(100, fromProgress));
    const processed = latestRun?.progress?.processed_stocks ?? latestRun?.processed_stocks ?? 0;
    const total = latestRun?.progress?.total_stocks ?? latestRun?.total_stocks ?? 0;
    if (!total) return 0;
    return Math.max(0, Math.min(100, Number(((processed / total) * 100).toFixed(2))));
  }, [latestRun]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#0a0f1e', color: '#e5e7eb' }}>
      <div style={{ borderBottom: '1px solid #1e2d3d', padding: '10px 12px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
          <span style={{ color: '#FFCB05', fontSize: 11, letterSpacing: 2, fontWeight: 700 }}>FIVE-FLAGS MONITOR</span>
          <span style={{ fontSize: 11, color: statusColor, fontWeight: 700 }}>
            {latestRun?.status || health?.status || 'unknown'}
          </span>
        </div>
        <div style={{ marginTop: 6, fontSize: 11, color: '#9ca3af' }}>{latestRunSummary}</div>
        <div style={{ marginTop: 7 }}>
          <div style={{ height: 6, borderRadius: 999, background: '#1f2937', overflow: 'hidden' }}>
            <div
              style={{
                height: '100%',
                width: `${progressPercent}%`,
                background: statusColor,
                transition: 'width 220ms ease-out',
              }}
            />
          </div>
          <div style={{ marginTop: 4, fontSize: 10, color: '#94a3b8' }}>
            Progress {progressPercent.toFixed(1)}% · Last tick {fmtTs(lastTickAt)}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button
            onClick={() => void triggerRun(true)}
            disabled={running}
            style={{ background: '#1f2937', color: '#e5e7eb', border: '1px solid #374151', borderRadius: 4, padding: '4px 8px', cursor: 'pointer', fontSize: 11 }}
          >
            Dry Run
          </button>
          <button
            onClick={() => void triggerRun(false)}
            disabled={running || !canRunOnePool}
            style={{ background: '#1f2937', color: '#e5e7eb', border: '1px solid #374151', borderRadius: 4, padding: '4px 8px', cursor: 'pointer', fontSize: 11 }}
          >
            Run 1 Pool
          </button>
          <button
            onClick={() => void loadData()}
            disabled={running}
            style={{ background: '#1f2937', color: '#e5e7eb', border: '1px solid #374151', borderRadius: 4, padding: '4px 8px', cursor: 'pointer', fontSize: 11 }}
          >
            Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ padding: 16, color: '#9ca3af' }}>Loading...</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateRows: 'auto auto auto 1fr auto', height: '100%', overflow: 'hidden' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, padding: 10 }}>
            <StatCard label="Unprocessed" value={summary?.unprocessed_pools ?? 0} />
            <StatCard label="Results" value={health?.result_total_count ?? 0} />
            <StatCard label="Rows" value={resultsTotal} />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, padding: '0 10px 8px' }}>
            <StatCard label="Latest Date" value={health?.latest_result_date ?? '—'} />
            <StatCard label="Date Points" value={summary?.unprocessed_dates_estimate ?? 0} />
          </div>

          <div style={{ padding: '0 10px 8px', fontSize: 11, color: '#9ca3af' }}>
            <div style={{ marginBottom: 4 }}>
              <span style={{ color: '#e5e7eb' }}>Run ID:</span> {latestRun?.run_id || '—'}
            </div>
            <div style={{ marginBottom: 4 }}>
              <span style={{ color: '#e5e7eb' }}>Started:</span> {fmtTs(latestRun?.started_at)}
              {' · '}
              <span style={{ color: '#e5e7eb' }}>Completed:</span> {fmtTs(latestRun?.completed_at)}
            </div>
            <div style={{ marginBottom: 4 }}>
              <span style={{ color: '#e5e7eb' }}>Failed:</span> {latestRun?.failed_stocks ?? 0}
              {' · '}
              <span style={{ color: '#e5e7eb' }}>Top File:</span> {summary?.by_file_name?.[0]?.file_name || '—'}
            </div>
          </div>

          <div style={{ padding: '0 10px 8px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <input
              value={stockFilter}
              onChange={(e) => setStockFilter(e.target.value.trim())}
              placeholder="Stock code"
              style={{ width: '100%', boxSizing: 'border-box', background: '#0f172a', color: '#e5e7eb', border: '1px solid #334155', borderRadius: 4, padding: '6px 8px', fontSize: 12 }}
            />
            <input
              value={screenerFilter}
              onChange={(e) => setScreenerFilter(e.target.value)}
              placeholder="Screener id"
              style={{ width: '100%', boxSizing: 'border-box', background: '#0f172a', color: '#e5e7eb', border: '1px solid #334155', borderRadius: 4, padding: '6px 8px', fontSize: 12 }}
            />
          </div>

          <div style={{ overflowY: 'auto', borderTop: '1px solid #1e2d3d', borderBottom: '1px solid #1e2d3d' }}>
            {filteredResults.length === 0 ? (
              <div style={{ padding: 16, color: '#9ca3af', fontSize: 12 }}>No results</div>
            ) : (
              filteredResults.map((item) => {
                const active = selectedStock === item.stock_code;
                return (
                  <div
                    key={item.id}
                    onClick={() => setSelectedStock(item.stock_code)}
                    style={{
                      padding: '8px 10px',
                      borderBottom: '1px solid #1e2d3d',
                      background: active ? 'rgba(255,203,5,0.08)' : 'transparent',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                      <span style={{ fontSize: 12, fontWeight: 700 }}>{item.stock_code} {item.stock_name}</span>
                      <span style={{ fontSize: 11, color: '#93c5fd' }}>{item.screener_id}</span>
                    </div>
                    <div style={{ marginTop: 4, fontSize: 11, color: '#9ca3af' }}>
                      {item.screen_date} · {fmtPrice(item.close_price)} · pool #{item.pool_id}
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <div style={{ padding: 10, minHeight: 80, overflowY: 'auto' }}>
            <div style={{ fontSize: 11, color: '#FFCB05', letterSpacing: 1, marginBottom: 6 }}>TIMELINE</div>
            {!selectedStock ? (
              <div style={{ fontSize: 12, color: '#9ca3af' }}>Select a stock to view timeline.</div>
            ) : timeline?.timeline?.length ? (
              timeline.timeline.slice(-6).map((t) => (
                <div key={`${selectedStock}-${t.date}`} style={{ marginBottom: 8, fontSize: 12, borderBottom: '1px dashed #1e2d3d', paddingBottom: 6 }}>
                  <div>
                    <span style={{ color: '#93c5fd' }}>{t.date}</span>
                    <span style={{ color: '#9ca3af' }}> · {t.hits.join(', ')}</span>
                  </div>
                  {t.details.slice(0, 3).map((d) => (
                    <div key={`${t.date}-${d.screener_id}-${d.created_at}`} style={{ marginTop: 3, fontSize: 11, color: '#94a3b8' }}>
                      {d.screener_id} · {fmtPrice(d.close_price)} · pool #{d.pool_id}
                    </div>
                  ))}
                </div>
              ))
            ) : (
              <div style={{ fontSize: 12, color: '#9ca3af' }}>No timeline data for {selectedStock}.</div>
            )}
          </div>
        </div>
      )}

      {error && (
        <div style={{ padding: '6px 10px', background: 'rgba(239,68,68,0.1)', color: '#fca5a5', fontSize: 11 }}>
          {error}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div style={{ border: '1px solid #1e2d3d', borderRadius: 6, padding: 8, background: '#111827' }}>
      <div style={{ fontSize: 10, color: '#9ca3af', letterSpacing: 1 }}>{label}</div>
      <div style={{ marginTop: 4, fontSize: 16, fontWeight: 700, color: '#e5e7eb' }}>{value}</div>
    </div>
  );
}
