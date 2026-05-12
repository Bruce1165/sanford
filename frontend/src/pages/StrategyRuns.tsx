import { useEffect, useMemo, useState } from 'react';
import { api, type StrategyId, type StrategyLabRecentSignalsSummaryResponse, type StrategyTaskType } from '../api';
import { CalendarWithButton } from '../components/Calendar';

const statusColor = (status: string): string => {
  const s = (status || '').toLowerCase();
  if (s === 'success') return '#22c55e';
  if (s === 'failed') return '#ef4444';
  if (s === 'running') return '#f59e0b';
  if (s === 'queued') return '#60a5fa';
  if (s === 'cancelled') return '#94a3b8';
  return '#9fb3c8';
};

const statusLabel = (status: string): string => {
  const s = (status || '').toLowerCase();
  if (s === 'success') return '成功';
  if (s === 'failed') return '失败';
  if (s === 'running') return '运行中';
  if (s === 'queued') return '排队中';
  if (s === 'cancelled') return '已取消';
  return status || '-';
};

const strategyLabel = (strategyId: string): string => {
  const s = String(strategyId || '').toLowerCase();
  if (s === 'triple_screen') return '三重滤网';
  if (s === 'neil_turtle_short') return '海龟短期';
  return strategyId || '-';
};

const taskLabel = (taskType: string): string => {
  const t = String(taskType || '').toLowerCase();
  if (t === 'daily') return '当日扫描';
  if (t === 'backfill') return '全量回溯';
  return taskType || '-';
};

const executeModeLabel = (executeMode: string): string => {
  const m = String(executeMode || '').toLowerCase();
  if (m === 'execute') return '执行入库';
  if (m === 'dry_run') return '试运行';
  return executeMode || '-';
};

const fmtNumber = (v: any, digits = 2): string => {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '-';
  return v.toFixed(digits);
};

const fmtInt = (v: any): string => {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '-';
  return String(Math.trunc(v));
};

const pct = (v: number | null | undefined): string => {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '-';
  return `${(v * 100).toFixed(2)}%`;
};

interface StrategyRunsViewProps {
  theme?: 'dark' | 'light';
  initialStrategyId?: StrategyId;
  embedded?: boolean;
}

export default function StrategyRunsView({ theme = 'dark', initialStrategyId, embedded = false }: StrategyRunsViewProps) {
  const isLight = theme === 'light';
  const colors = {
    pageBg: isLight ? '#f5f7fb' : 'transparent',
    panelBg: isLight ? '#ffffff' : '#0a0e1a',
    panelBorder: isLight ? '#d8e1ee' : '#1e2d45',
    panelSubBg: isLight ? '#f8fbff' : '#08111f',
    tableHeaderBg: isLight ? '#eaf1ff' : '#102034',
    tableHeaderText: isLight ? '#1f2937' : '#d7e2ef',
    textPrimary: isLight ? '#111827' : '#d7e2ef',
    textSecondary: isLight ? '#475569' : '#9fb3c8',
    selectedRow: isLight ? '#e9f2ff' : '#0f1f34',
    accent: isLight ? '#1d4ed8' : '#FFCB05',
    danger: '#ef4444',
    inputBg: isLight ? '#ffffff' : '#0f172a',
    inputText: isLight ? '#111827' : '#e5e7eb',
  };

  const buttonBase: React.CSSProperties = {
    borderRadius: 6,
    padding: '4px 10px',
    fontWeight: 600,
    border: '1px solid #3b82f6',
    background: '#2563eb',
    color: '#ffffff',
    cursor: 'pointer',
  };
  const buttonPrimary: React.CSSProperties = {
    ...buttonBase,
    height: 30,
    padding: '0 10px',
    fontSize: 12,
    lineHeight: '30px',
    whiteSpace: 'nowrap',
  };
  const buttonDisabled: React.CSSProperties = {
    border: '1px solid #94a3b8',
    background: '#cbd5e1',
    color: '#64748b',
    cursor: 'not-allowed',
  };
  const compactControl: React.CSSProperties = {
    background: colors.inputBg,
    color: colors.inputText,
    border: `1px solid ${colors.panelBorder}`,
    borderRadius: 6,
    padding: '4px 8px',
    fontSize: 12,
    height: 30,
    boxSizing: 'border-box',
  };
  const compactLabel: React.CSSProperties = {
    color: colors.textSecondary,
    fontSize: 12,
    height: 16,
    lineHeight: '16px',
    whiteSpace: 'nowrap',
  };
  const tabButton = (active: boolean): React.CSSProperties => ({
    ...buttonPrimary,
    background: 'transparent',
    border: active ? '1px solid #3b82f6' : `1px solid ${colors.panelBorder}`,
    color: active ? '#ffffff' : colors.textSecondary,
  });
  const compactGroup = (minWidth: number, flex: string): React.CSSProperties => ({
    display: 'grid',
    gridTemplateRows: '16px 30px',
    gap: 4,
    minWidth,
    flex,
    alignItems: 'stretch',
  });
  const [strategyId, setStrategyId] = useState<StrategyId>('triple_screen');
  const [viewTab, setViewTab] = useState<'runs' | 'params'>('runs');
  const [taskType, setTaskType] = useState<StrategyTaskType>('daily');
  const [executeMode, setExecuteMode] = useState<'dry_run' | 'execute'>('dry_run');
  const [asOfDate, setAsOfDate] = useState('');
  const [showAsOfCalendar, setShowAsOfCalendar] = useState(false);
  const [stockCodes, setStockCodes] = useState('');
  const [exportPdf, setExportPdf] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [listLoading, setListLoading] = useState(false);
  const [runs, setRuns] = useState<any[]>([]);
  const [errorText, setErrorText] = useState('');
  const [selectedRun, setSelectedRun] = useState<any>(null);
  const [logLines, setLogLines] = useState<string[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);

  const [filterTaskType, setFilterTaskType] = useState<'' | StrategyTaskType>('');
  const [filterStatus, setFilterStatus] = useState('');
  const [limit, setLimit] = useState(20);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [recentSummary, setRecentSummary] = useState<StrategyLabRecentSignalsSummaryResponse | null>(null);
  const [recentSummaryLoading, setRecentSummaryLoading] = useState(false);
  const [recentSummaryError, setRecentSummaryError] = useState('');

  useEffect(() => {
    if (!initialStrategyId) return;
    if (initialStrategyId !== strategyId) setStrategyId(initialStrategyId);
  }, [initialStrategyId, strategyId]);

  useEffect(() => {
    if (viewTab !== 'params') return;
    if (selectedRun) return;
    const latest = runs.find((r) => String(r?.strategy_id || '') === strategyId);
    if (latest?.run_id) void loadRunDetail(String(latest.run_id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewTab, selectedRun, runs, strategyId]);

  const hasPrev = offset > 0;
  const hasNext = useMemo(() => offset + limit < total, [offset, limit, total]);
  const summaryObj = selectedRun?.summary && typeof selectedRun.summary === 'object'
    ? (selectedRun.summary as Record<string, any>)
    : {};
  const hitCandidates = Array.isArray(summaryObj?.candidates) ? summaryObj.candidates : [];
  const hitSamples = Array.isArray(summaryObj?.sample) ? summaryObj.sample : [];
  const hitList = hitCandidates.length ? hitCandidates : hitSamples;
  const isSelectedDaily = String(selectedRun?.task_type || '').toLowerCase() === 'daily';
  const hasRsi = hitCandidates.some((x: any) => typeof x?.rsi14 === 'number' && Number.isFinite(x.rsi14));

  const copyText = async (text: string, okMessage: string) => {
    try {
      if (!text) return;
      await navigator.clipboard.writeText(text);
      setErrorText(okMessage);
    } catch {
      setErrorText('复制失败，请检查浏览器权限');
    }
  };

  const openDownload = (runId: string, kind: 'pdf' | 'md' | 'report_json') => {
    const q = new URLSearchParams();
    q.set('kind', kind);
    const url = `/api/strategy-runs/${encodeURIComponent(runId)}/download?${q.toString()}`;
    window.open(url, '_blank');
  };

  const goToHome = () => {
    const params = new URLSearchParams(window.location.search);
    params.set('tab', 'screeners');
    params.delete('screener');
    window.location.search = params.toString();
  };

  const loadRuns = async (opts?: { offset?: number }) => {
    setListLoading(true);
    setErrorText('');
    try {
      const effectiveOffset = typeof opts?.offset === 'number' ? opts.offset : offset;
      const data = await api.listStrategyRuns({
        strategy_id: strategyId,
        task_type: filterTaskType || undefined,
        status: filterStatus || undefined,
        limit,
        offset: effectiveOffset,
      });
      const nextRuns = Array.isArray(data?.items) ? data.items : [];
      setRuns(nextRuns);
      setTotal(Number(data?.total || 0));
      const selectedId = String(selectedRun?.run_id || '');
      const selectedStillInList = !!selectedId && nextRuns.some((r) => String(r?.run_id || '') === selectedId);
      if (!selectedStillInList && nextRuns.length > 0) {
        const firstRunId = String(nextRuns[0]?.run_id || '');
        if (firstRunId) void loadRunDetail(firstRunId);
      }
    } catch (err: any) {
      setErrorText(err?.message || '加载任务列表失败');
    } finally {
      setListLoading(false);
    }
  };

  const loadRecentSummary = async () => {
    setRecentSummaryLoading(true);
    setRecentSummaryError('');
    try {
      const data = await api.getStrategyLabRecentSignalsSummary({ strategy_id: strategyId, days: 5, per_day_limit: 200 });
      setRecentSummary(data);
    } catch (err: any) {
      setRecentSummary(null);
      setRecentSummaryError(err?.message || '加载最近5日汇总失败');
    } finally {
      setRecentSummaryLoading(false);
    }
  };

  useEffect(() => {
    void loadRuns();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strategyId, filterTaskType, filterStatus, limit, offset]);

  useEffect(() => {
    void loadRecentSummary();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strategyId]);

  useEffect(() => {
    setSelectedRun(null);
    setLogLines([]);
    setFilterTaskType('');
    setFilterStatus('');
    setOffset(0);
    void loadRuns({ offset: 0 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strategyId]);

  useEffect(() => {
    if (listLoading) return;
    if (!runs.length) {
      if (selectedRun) {
        setSelectedRun(null);
        setLogLines([]);
      }
      return;
    }
    const selectedId = String(selectedRun?.run_id || '');
    const selectedStillInList = !!selectedId && runs.some((r) => String(r?.run_id || '') === selectedId);
    if (selectedStillInList) return;
    const firstRunId = String(runs[0]?.run_id || '');
    if (!firstRunId) return;
    void loadRunDetail(firstRunId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runs, listLoading, selectedRun?.run_id]);

  const createRun = async () => {
    setSubmitting(true);
    setErrorText('');
    try {
      const payload: any = {
        strategy_id: strategyId,
        task_type: taskType,
        execute_mode: executeMode,
        export_pdf: exportPdf,
      };
      if (asOfDate.trim()) payload.as_of_date = asOfDate.trim();
      if (stockCodes.trim()) payload.stock_codes = stockCodes.trim();

      const data = await api.createStrategyRun(payload);
      setSelectedRun(data);
      setOffset(0);
      await loadRuns({ offset: 0 });
      await loadLogs(data.run_id);
    } catch (err: any) {
      setErrorText(err?.message || '创建任务失败');
      setOffset(0);
      try {
        await loadRuns({ offset: 0 });
      } catch {}
    } finally {
      setSubmitting(false);
    }
  };

  const loadRunDetail = async (runId: string) => {
    setErrorText('');
    try {
      const data = await api.getStrategyRun(runId, 120);
      setSelectedRun(data);
      setLogLines(Array.isArray(data?.log_tail) ? data.log_tail : []);
    } catch (err: any) {
      setErrorText(err?.message || '加载任务详情失败');
    }
  };

  const loadLogs = async (runId: string) => {
    setLogsLoading(true);
    try {
      const data = await api.getStrategyRunLogs(runId, 120);
      setLogLines(Array.isArray(data?.lines) ? data.lines : []);
    } catch (err: any) {
      setErrorText(err?.message || '加载日志失败');
    } finally {
      setLogsLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, height: embedded ? '100%' : '78vh', minHeight: embedded ? '100%' : '78vh', background: embedded ? 'transparent' : colors.pageBg }}>
      <section style={{ border: `1px solid ${colors.panelBorder}`, borderRadius: 8, background: colors.panelBg, padding: 10, flex: '0 0 180px', height: 180, overflow: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'nowrap', overflowX: 'auto', marginBottom: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'nowrap' }}>
            <h3 style={{ margin: 0, color: colors.accent, fontSize: 14, fontWeight: 800, whiteSpace: 'nowrap' }}>
              策略任务执行 <span style={{ color: colors.textSecondary, fontSize: 11, fontWeight: 700 }}>· {strategyLabel(strategyId)}</span>
            </h3>
            <div style={{ display: 'flex', gap: 8, marginBottom: 0, whiteSpace: 'nowrap' }}>
              <button style={tabButton(viewTab === 'runs')} onClick={() => setViewTab('runs')}>任务运行</button>
              <button style={tabButton(viewTab === 'params')} onClick={() => setViewTab('params')}>策略参数</button>
            </div>
          </div>
          {!embedded && (
            <button
              onClick={goToHome}
              style={{ ...buttonBase, padding: '4px 10px', fontSize: 12, whiteSpace: 'nowrap' }}
            >
              返回主页
            </button>
          )}
        </div>
        {viewTab === 'params' ? (
          <div style={{ display: 'grid', gap: 10 }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
              <button
                onClick={() => {
                  const latest = runs.find((r) => String(r?.strategy_id || '') === strategyId);
                  if (latest?.run_id) void loadRunDetail(String(latest.run_id));
                }}
                style={{ ...buttonBase, padding: '4px 10px', fontSize: 12 }}
              >
                加载最近参数快照
              </button>
            </div>
            <div style={{ border: `1px solid ${colors.panelBorder}`, borderRadius: 8, padding: 10, background: isLight ? '#ffffff' : '#050d1a' }}>
              <div style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 6 }}>参数快照来源：{selectedRun?.run_id ? `任务 ${String(selectedRun.run_id).slice(0, 10)}...` : '未选择任务'}</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 8, marginBottom: 10 }}>
                {[
                  { k: 'param_version', label: '版本' },
                  { k: 'timing_rsi_threshold', label: 'RSI阈值' },
                  { k: 'entry_lookback_days', label: '入场回看' },
                  { k: 'stop_lookback_days', label: '止损回看' },
                  { k: 'pool_size', label: '池大小' },
                ].map((x) => (
                  <div key={x.k} style={{ border: `1px solid ${colors.panelBorder}`, borderRadius: 8, padding: '6px 8px' }}>
                    <div style={{ color: colors.textSecondary, fontSize: 11 }}>{x.label}</div>
                    <div style={{ color: colors.textPrimary, fontSize: 14, fontWeight: 800 }}>{summaryObj && x.k in summaryObj ? String((summaryObj as any)[x.k]) : '-'}</div>
                  </div>
                ))}
              </div>
              <pre style={{ margin: 0, padding: 10, background: isLight ? '#f8fafc' : '#050d1a', border: `1px solid ${colors.panelBorder}`, color: isLight ? '#0f172a' : '#c9d6e3', fontSize: 12, lineHeight: 1.4, whiteSpace: 'pre-wrap', borderRadius: 8 }}>
                {selectedRun?.summary ? JSON.stringify(selectedRun.summary, null, 2) : '暂无参数快照：请先运行一次，或在“历史任务与日志”选择一个任务。'}
              </pre>
            </div>
          </div>
        ) : (
        <div style={{ display: 'grid', gap: 8 }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'flex-start' }}>
            <div style={compactGroup(170, '1 1 180px')}>
              <label style={compactLabel}>任务</label>
              <select
                value={taskType}
                onChange={(e) => setTaskType(e.target.value as StrategyTaskType)}
                style={{ ...compactControl, cursor: 'pointer' }}
              >
                <option value="daily">当日扫描</option>
                <option value="backfill">全量回溯</option>
              </select>
            </div>
            <div style={compactGroup(170, '1 1 180px')}>
              <label style={compactLabel}>执行模式</label>
              <select
                value={executeMode}
                onChange={(e) => setExecuteMode(e.target.value as 'dry_run' | 'execute')}
                style={{ ...compactControl, cursor: 'pointer' }}
              >
                <option value="dry_run">试运行</option>
                <option value="execute">执行入库</option>
              </select>
            </div>
            <div style={compactGroup(210, '1 1 220px')}>
              <label style={compactLabel}>截止日期（可选）</label>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, height: 30 }}>
                <CalendarWithButton
                  value={asOfDate}
                  onChange={setAsOfDate}
                  maxDate={new Date().toISOString().split('T')[0]}
                  showPicker={showAsOfCalendar}
                  onTogglePicker={() => setShowAsOfCalendar((v) => !v)}
                  onSelectDate={(d) => {
                    setAsOfDate(d);
                    setShowAsOfCalendar(false);
                  }}
                  inputStyle={compactControl}
                  buttonStyle={{ width: 30, height: 30, borderRadius: 6 }}
                />
              </div>
            </div>
            <div style={compactGroup(170, '1 1 180px')}>
              <label style={compactLabel}>股票代码筛选（可选）</label>
              <input
                value={stockCodes}
                onChange={(e) => setStockCodes(e.target.value)}
                style={{ ...compactControl, width: 170 }}
              />
            </div>
            <div style={compactGroup(260, '0 0 auto')}>
              <label style={compactLabel}>操作</label>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', height: 30 }}>
                <button
                  onClick={createRun}
                  disabled={submitting}
                  style={{ ...buttonPrimary, background: 'transparent', ...(submitting ? buttonDisabled : null) }}
                >
                  {submitting ? '执行中...' : '创建并执行'}
                </button>
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, height: 30, padding: '0 2px', color: colors.textSecondary, fontSize: 12, whiteSpace: 'nowrap' }}>
                  <input
                    type="checkbox"
                    checked={exportPdf}
                    onChange={(e) => setExportPdf(e.target.checked)}
                    style={{ margin: 0 }}
                  />
                  导出PDF
                </label>
              </div>
            </div>
          </div>
          {errorText && (
            <div style={{ marginTop: 8, color: colors.danger, fontSize: 12, whiteSpace: 'pre-wrap' }}>{errorText}</div>
          )}
        </div>
        )}
      </section>

      <section style={{ border: `1px solid ${colors.panelBorder}`, borderRadius: 8, background: colors.panelBg, padding: 10, overflow: 'hidden', flex: '1 1 auto', minHeight: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'nowrap', overflowX: 'auto', marginBottom: 6 }}>
          <h3 style={{ margin: 0, color: colors.accent, fontSize: 14, fontWeight: 800 }}>历史任务与日志</h3>
          <span style={{ color: colors.textSecondary, fontSize: 12, fontWeight: 700 }}>
            策略：{strategyLabel(strategyId)}
          </span>
          <select
            value={filterTaskType}
            onChange={(e) => { setOffset(0); setFilterTaskType(e.target.value as '' | StrategyTaskType); }}
            style={{ background: colors.inputBg, color: colors.inputText, border: `1px solid ${colors.panelBorder}`, borderRadius: 6, padding: '3px 8px', fontSize: 12 }}
          >
            <option value="">全部任务</option>
            <option value="daily">当日扫描</option>
            <option value="backfill">全量回溯</option>
          </select>
          <button
            onClick={() => void loadRuns({ offset: 0 })}
            disabled={listLoading}
            style={{ ...buttonPrimary, background: 'transparent', ...(listLoading ? buttonDisabled : null) }}
          >
            {listLoading ? '刷新中...' : '刷新列表'}
          </button>
          <input
            value={filterStatus}
            onChange={(e) => { setOffset(0); setFilterStatus(e.target.value); }}
            placeholder="状态筛选"
            style={{ ...compactControl, width: 90 }}
          />
          <select
            value={limit}
            onChange={(e) => { setOffset(0); setLimit(Number(e.target.value)); }}
            style={{ background: colors.inputBg, color: colors.inputText, border: `1px solid ${colors.panelBorder}`, borderRadius: 6, padding: '3px 8px', fontSize: 12 }}
          >
            <option value={20}>20 / 页</option>
            <option value={50}>50 / 页</option>
            <option value={100}>100 / 页</option>
          </select>
          <button
            onClick={() => setOffset(Math.max(0, offset - limit))}
            disabled={!hasPrev}
            style={{ ...buttonPrimary, ...(!hasPrev ? buttonDisabled : null) }}
          >
            上一页
          </button>
          <button
            onClick={() => setOffset(offset + limit)}
            disabled={!hasNext}
            style={{ ...buttonPrimary, ...(!hasNext ? buttonDisabled : null) }}
          >
            下一页
          </button>
          <span style={{ color: colors.textSecondary, fontSize: 12 }}>总数：{total}，当前偏移：{offset}</span>
        </div>

        <div style={{ border: `1px solid ${colors.panelBorder}`, borderRadius: 8, padding: 10, background: colors.panelSubBg, marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap', marginBottom: 6 }}>
            <div style={{ color: colors.textPrimary, fontSize: 12, fontWeight: 800 }}>
              最近5日筛选汇总
              <span style={{ color: colors.textSecondary, fontWeight: 700 }}>
                {recentSummary?.meta?.latest_close_date ? `（涨跌幅截至 ${recentSummary.meta.latest_close_date}）` : ''}
              </span>
            </div>
            <button
              onClick={() => void loadRecentSummary()}
              disabled={recentSummaryLoading}
              style={{ ...buttonBase, padding: '2px 8px', fontSize: 11, ...(recentSummaryLoading ? buttonDisabled : null) }}
            >
              {recentSummaryLoading ? '刷新中...' : '刷新'}
            </button>
          </div>
          {recentSummaryError && (
            <div style={{ color: colors.danger, fontSize: 12, whiteSpace: 'pre-wrap', marginBottom: 6 }}>{recentSummaryError}</div>
          )}
          {!recentSummaryLoading && (!recentSummary?.items || !recentSummary.items.length) ? (
            <div style={{ color: colors.textSecondary, fontSize: 12 }}>暂无数据（最近5个交易日无 daily 信号）</div>
          ) : (
            <div style={{ display: 'grid', gap: 6 }}>
              {(recentSummary?.items || []).map((d) => {
                const stocks = (d.stocks || []).slice().sort((a, b) => {
                  const av = typeof a.return_pct === 'number' && Number.isFinite(a.return_pct) ? a.return_pct : -999;
                  const bv = typeof b.return_pct === 'number' && Number.isFinite(b.return_pct) ? b.return_pct : -999;
                  return bv - av;
                });
                return (
                  <details key={d.trade_date} style={{ border: `1px solid ${colors.panelBorder}`, borderRadius: 8, padding: 8, background: isLight ? '#ffffff' : '#050d1a' }}>
                    <summary style={{ cursor: 'pointer', color: colors.textPrimary, fontSize: 12, fontWeight: 800 }}>
                      {d.trade_date} · 命中 {d.count} · 平均 {pct(d.avg_return_pct)} · ↑{d.up_n} ↓{d.down_n} ={d.flat_n}
                    </summary>
                    <div style={{ marginTop: 8, overflow: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                        <thead>
                          <tr style={{ background: colors.tableHeaderBg, color: colors.tableHeaderText }}>
                            <th style={{ textAlign: 'left', padding: 6 }}>代码</th>
                            <th style={{ textAlign: 'left', padding: 6 }}>名称</th>
                            <th style={{ textAlign: 'right', padding: 6 }}>筛选日收盘</th>
                            <th style={{ textAlign: 'right', padding: 6 }}>最新收盘</th>
                            <th style={{ textAlign: 'right', padding: 6 }}>涨跌幅</th>
                          </tr>
                        </thead>
                        <tbody>
                          {stocks.map((s, idx) => {
                            const r = typeof s.return_pct === 'number' && Number.isFinite(s.return_pct) ? s.return_pct : null;
                            const color = r == null ? colors.textSecondary : (r >= 0 ? '#22c55e' : '#ef4444');
                            return (
                              <tr key={`${d.trade_date}-${s.stock_code}-${idx}`} style={{ borderTop: `1px solid ${colors.panelBorder}` }}>
                                <td style={{ padding: 6, fontFamily: 'monospace' }}>{s.stock_code}</td>
                                <td style={{ padding: 6 }}>{s.stock_name || '-'}</td>
                                <td style={{ padding: 6, textAlign: 'right' }}>{fmtNumber(s.entry_close, 2)}</td>
                                <td style={{ padding: 6, textAlign: 'right' }}>{fmtNumber(s.latest_close, 2)}</td>
                                <td style={{ padding: 6, textAlign: 'right', color, fontWeight: 800 }}>{pct(r)}</td>
                              </tr>
                            );
                          })}
                          {!stocks.length && (
                            <tr><td style={{ padding: 6, color: colors.textSecondary }} colSpan={5}>当日无信号</td></tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </details>
                );
              })}
            </div>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, height: '100%' }}>
          <div style={{ border: `1px solid ${colors.panelBorder}`, borderRadius: 6, overflow: 'auto', height: '100%' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ background: colors.tableHeaderBg, color: colors.tableHeaderText }}>
                  <th style={{ textAlign: 'left', padding: 6 }}>筛选日期</th>
                  <th style={{ textAlign: 'left', padding: 6 }}>执行</th>
                  <th style={{ textAlign: 'left', padding: 6 }}>状态</th>
                  <th style={{ textAlign: 'left', padding: 6 }}>类型</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>命中/信号</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr
                    key={r.run_id}
                    onClick={() => void loadRunDetail(r.run_id)}
                    style={{
                      cursor: 'pointer',
                      borderTop: `1px solid ${colors.panelBorder}`,
                      background: selectedRun?.run_id === r.run_id ? colors.selectedRow : 'transparent',
                      color: colors.textPrimary,
                    }}
                  >
                    <td style={{ padding: 6 }}>
                      {r.as_of_date
                        ? String(r.as_of_date).slice(0, 10)
                        : (r.summary?.target_trade_date ? String(r.summary.target_trade_date).slice(0, 10) : '-')}
                    </td>
                    <td style={{ padding: 6 }}>
                      <span style={{
                        color: String(r.execute_mode || '').toLowerCase() === 'execute' ? '#22c55e' : colors.textSecondary,
                        border: `1px solid ${String(r.execute_mode || '').toLowerCase() === 'execute' ? '#22c55e' : colors.panelBorder}`,
                        borderRadius: 10,
                        padding: '1px 8px',
                        fontSize: 11,
                        display: 'inline-block',
                      }}>
                        {executeModeLabel(String(r.execute_mode || ''))}
                      </span>
                    </td>
                    <td style={{ padding: 6 }}>
                      <span style={{
                        color: statusColor(String(r.status || '')),
                        border: `1px solid ${statusColor(String(r.status || ''))}`,
                        borderRadius: 10,
                        padding: '1px 8px',
                        fontSize: 11,
                        display: 'inline-block',
                      }}>
                        {statusLabel(String(r.status || ''))}
                      </span>
                    </td>
                    <td style={{ padding: 6 }}>{taskLabel(String(r.task_type || ''))}</td>
                    <td style={{ padding: 6, textAlign: 'right', color: colors.textSecondary, fontWeight: 800 }}>
                      {(() => {
                        const s = r?.summary && typeof r.summary === 'object' ? r.summary : {};
                        const t = String(r?.task_type || '').toLowerCase();
                        if (t === 'daily') return String(s?.new_entry_count ?? '-');
                        if (t === 'backfill') return String(s?.total_entry_signals ?? '-');
                        return '-';
                      })()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ border: `1px solid ${colors.panelBorder}`, borderRadius: 6, padding: 6, overflow: 'auto', height: '100%' }}>
            {!selectedRun ? (
              <div style={{ color: colors.textSecondary, fontSize: 14, fontWeight: 800 }}>请先在左侧选择一个任务</div>
            ) : (
              <>
                <div style={{ color: colors.textPrimary, fontSize: 12, marginBottom: 8 }}>
                  <div>
                    <b>任务ID:</b> <span style={{ fontFamily: 'monospace' }}>{selectedRun.run_id}</span>
                    <button
                      onClick={() => void copyText(String(selectedRun.run_id || ''), '已复制任务ID')}
                      style={{ ...buttonBase, marginLeft: 8, padding: '2px 8px', fontSize: 11 }}
                    >
                      复制任务ID
                    </button>
                  </div>
                  <div><b>运行日期:</b> {selectedRun.requested_at ? String(selectedRun.requested_at).slice(0, 10) : '-'}</div>
                  <div>
                    <b>状态:</b>{' '}
                    <span style={{
                      color: statusColor(String(selectedRun.status || '')),
                      border: `1px solid ${statusColor(String(selectedRun.status || ''))}`,
                      borderRadius: 10,
                      padding: '1px 8px',
                      fontSize: 11,
                      display: 'inline-block',
                    }}>
                      {statusLabel(String(selectedRun.status || ''))}
                    </span>
                  </div>
                  <div><b>策略:</b> {strategyLabel(String(selectedRun.strategy_id || ''))}</div>
                  <div><b>类型:</b> {taskLabel(String(selectedRun.task_type || ''))}</div>
                  <div><b>执行:</b> {executeModeLabel(String(selectedRun.execute_mode || ''))}</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
                    <b>结果文件下载:</b>
                    <button
                      onClick={() => openDownload(String(selectedRun.run_id), 'pdf')}
                      style={{ ...buttonBase, padding: '2px 8px', fontSize: 11 }}
                    >
                      PDF
                    </button>
                    <button
                      onClick={() => openDownload(String(selectedRun.run_id), 'md')}
                      style={{ ...buttonBase, padding: '2px 8px', fontSize: 11 }}
                    >
                      Markdown
                    </button>
                    <button
                      onClick={() => openDownload(String(selectedRun.run_id), 'report_json')}
                      style={{ ...buttonBase, padding: '2px 8px', fontSize: 11 }}
                    >
                      JSON
                    </button>
                  </div>
                </div>
                <div style={{ color: colors.textPrimary, fontSize: 12, marginBottom: 8 }}>
                  <div style={{ marginBottom: 4 }}><b>摘要（命中股票列表）:</b></div>
                  {hitList.length ? (
                    <div style={{ padding: 8, border: `1px solid ${colors.panelBorder}`, borderRadius: 4, background: colors.panelSubBg }}>
                      {hitList.map((it: any, idx: number) => (
                        <div key={`${it.stock_code || it.code || idx}-${idx}`} style={{ marginBottom: 2 }}>
                          <span style={{ color: colors.textSecondary }}>{idx + 1}.</span>{' '}
                          <span>{it.stock_code || it.code || '-'}</span>{' '}
                          <span>{it.stock_name || it.name || '-'}</span>{' '}
                          <span style={{ color: colors.textSecondary }}>{it.trade_date || it.first_date || '-'}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ color: colors.textSecondary }}>暂无命中股票</div>
                  )}
                </div>
                <div style={{ border: `1px solid ${colors.panelBorder}`, borderRadius: 6, padding: 8, background: colors.panelSubBg, color: colors.textPrimary, fontSize: 12, marginBottom: 8 }}>
                  <div style={{ fontWeight: 800, marginBottom: 6 }}>仿真/回测（任务输出明细）</div>
                  {isSelectedDaily ? (
                    hitCandidates.length ? (
                      <div style={{ overflow: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                          <thead>
                            <tr style={{ background: colors.tableHeaderBg, color: colors.tableHeaderText }}>
                              <th style={{ textAlign: 'left', padding: 6 }}>代码</th>
                              <th style={{ textAlign: 'left', padding: 6 }}>名称</th>
                              <th style={{ textAlign: 'left', padding: 6 }}>日期</th>
                              <th style={{ textAlign: 'right', padding: 6 }}>收盘价</th>
                              <th style={{ textAlign: 'right', padding: 6 }}>入场位</th>
                              {hasRsi && <th style={{ textAlign: 'right', padding: 6 }}>RSI14</th>}
                            </tr>
                          </thead>
                          <tbody>
                            {hitCandidates.map((it: any, idx: number) => (
                              <tr key={`${it.stock_code || it.code || idx}-${idx}`} style={{ borderTop: `1px solid ${colors.panelBorder}` }}>
                                <td style={{ padding: 6, fontFamily: 'monospace' }}>{String(it.stock_code || it.code || '-')}</td>
                                <td style={{ padding: 6 }}>{String(it.stock_name || it.name || '-')}</td>
                                <td style={{ padding: 6, color: colors.textSecondary }}>{String(it.trade_date || it.first_date || '-')}</td>
                                <td style={{ padding: 6, textAlign: 'right' }}>{fmtNumber(it.close_price, 2)}</td>
                                <td style={{ padding: 6, textAlign: 'right' }}>{fmtNumber(it.entry_price, 2)}</td>
                                {hasRsi && <td style={{ padding: 6, textAlign: 'right' }}>{fmtNumber(it.rsi14, 2)}</td>}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div style={{ color: colors.textSecondary }}>当日无新触发（candidates 为空）</div>
                    )
                  ) : (
                    hitSamples.length ? (
                      <div style={{ overflow: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                          <thead>
                            <tr style={{ background: colors.tableHeaderBg, color: colors.tableHeaderText }}>
                              <th style={{ textAlign: 'left', padding: 6 }}>代码</th>
                              <th style={{ textAlign: 'left', padding: 6 }}>名称</th>
                              <th style={{ textAlign: 'right', padding: 6 }}>入场信号数</th>
                              <th style={{ textAlign: 'left', padding: 6 }}>首次</th>
                              <th style={{ textAlign: 'left', padding: 6 }}>最近</th>
                            </tr>
                          </thead>
                          <tbody>
                            {hitSamples.map((it: any, idx: number) => (
                              <tr key={`${it.stock_code || it.code || idx}-${idx}`} style={{ borderTop: `1px solid ${colors.panelBorder}` }}>
                                <td style={{ padding: 6, fontFamily: 'monospace' }}>{String(it.stock_code || it.code || '-')}</td>
                                <td style={{ padding: 6 }}>{String(it.stock_name || it.name || '-')}</td>
                                <td style={{ padding: 6, textAlign: 'right' }}>{fmtInt(it.entry_signals)}</td>
                                <td style={{ padding: 6, color: colors.textSecondary }}>{String(it.first_date || '-')}</td>
                                <td style={{ padding: 6, color: colors.textSecondary }}>{String(it.last_date || '-')}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div style={{ color: colors.textSecondary }}>回溯样本为空（sample 为空）</div>
                    )
                  )}
                </div>
                <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                  <button
                    onClick={() => void loadLogs(selectedRun.run_id)}
                    disabled={logsLoading}
                    style={{ ...buttonBase, ...(logsLoading ? buttonDisabled : null) }}
                  >
                    {logsLoading ? '日志加载中...' : '刷新日志'}
                  </button>
                </div>
                <div style={{ border: `1px solid ${colors.panelBorder}`, borderRadius: 6, padding: 8, background: colors.panelSubBg, color: colors.textPrimary, fontSize: 12, marginBottom: 8 }}>
                  <div style={{ fontWeight: 800, marginBottom: 6 }}>关键摘要</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 6 }}>
                    {[
                      { k: 'target_trade_date', label: '目标交易日' },
                      { k: 'processed_stocks', label: '处理股票数' },
                      { k: 'new_entry_count', label: '新增入场' },
                      { k: 'db_upserts', label: '入库写入' },
                      { k: 'stocks_without_price_data', label: '缺行情' },
                      { k: 'stocks_without_target_date', label: '缺目标日' },
                    ].map((x) => (
                      <div key={x.k} style={{ border: `1px solid ${colors.panelBorder}`, borderRadius: 6, padding: '6px 8px' }}>
                        <div style={{ color: colors.textSecondary, fontSize: 11 }}>{x.label}</div>
                        <div style={{ color: colors.textPrimary, fontSize: 13, fontWeight: 800 }}>
                          {summaryObj && x.k in summaryObj ? String((summaryObj as any)[x.k]) : '-'}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <details>
                  <summary style={{ cursor: 'pointer', color: colors.textSecondary, fontSize: 12, fontWeight: 800 }}>日志（尾部）</summary>
                  <pre style={{
                    margin: '8px 0 0',
                    padding: 8,
                    background: isLight ? '#f8fbff' : '#050d1a',
                    border: `1px solid ${colors.panelBorder}`,
                    color: isLight ? '#1f2937' : '#c9d6e3',
                    fontSize: 12,
                    lineHeight: 1.4,
                    whiteSpace: 'pre-wrap',
                    borderRadius: 6,
                  }}>
                    {logLines.length ? logLines.join('\n') : '暂无日志'}
                  </pre>
                </details>
              </>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
