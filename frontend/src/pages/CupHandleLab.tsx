import { useEffect, useMemo, useState } from 'react';
import {
  api,
  type CupHandleLabSummaryResponse,
  type CupHandleLabDailyItem,
  type CupHandleLabDiffItem,
  type CupHandleLabAuditResponse,
  type CupHandleLabStockItem,
  type CupHandleLabAlignmentResponse,
  type CupHandleLabV4PoolCompareResponse,
} from '../api';

interface CupHandleLabProps {
  theme?: 'dark' | 'light';
}

const pct = (v: number | null | undefined): string => {
  if (typeof v !== 'number' || Number.isNaN(v)) return '-';
  return `${(v * 100).toFixed(2)}%`;
};

const num = (v: number | null | undefined): string => {
  if (typeof v !== 'number' || Number.isNaN(v)) return '-';
  return String(v);
};

const stateLabel = (raw: string): string => {
  if (raw === 'S1_risk_on') return 'S1 风险偏好';
  if (raw === 'S2_neutral') return 'S2 中性';
  if (raw === 'S3_risk_off') return 'S3 风险收敛';
  return raw || '-';
};

const segmentLabel = (raw: string): string => {
  if (raw === 'narrow_shallow') return '窄杯浅杯';
  if (raw === 'narrow_deep') return '窄杯深杯';
  if (raw === 'wide_shallow') return '宽杯浅杯';
  if (raw === 'wide_deep') return '宽杯深杯';
  return raw || '-';
};

export default function CupHandleLab({ theme = 'dark' }: CupHandleLabProps) {
  const isLight = theme === 'light';
  const c = {
    pageBg: isLight ? '#f5f7fb' : 'transparent',
    panelBg: isLight ? '#ffffff' : '#0a0e1a',
    border: isLight ? '#d8e1ee' : '#1e2d45',
    text: isLight ? '#0f172a' : '#d7e2ef',
    dim: isLight ? '#475569' : '#9fb3c8',
    accent: isLight ? '#1d4ed8' : '#FFCB05',
    tableHead: isLight ? '#eaf1ff' : '#102034',
    good: '#22c55e',
    bad: '#ef4444',
    warn: '#f59e0b',
  };
  const panel = {
    border: `1px solid ${c.border}`,
    borderRadius: 8,
    background: c.panelBg,
    boxShadow: isLight ? '0 2px 10px rgba(30,64,175,0.08)' : '0 4px 18px rgba(0,0,0,0.28)',
  } as const;
  const sectionTitle = {
    margin: '0 0 8px 0',
    color: c.accent,
    fontSize: 15,
    letterSpacing: '0.04em',
    fontWeight: 700,
  } as const;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [summary, setSummary] = useState<CupHandleLabSummaryResponse | null>(null);
  const [daily, setDaily] = useState<CupHandleLabDailyItem[]>([]);
  const [diff, setDiff] = useState<CupHandleLabDiffItem[]>([]);
  const [audit, setAudit] = useState<CupHandleLabAuditResponse | null>(null);
  const [stocks, setStocks] = useState<CupHandleLabStockItem[]>([]);
  const [entryWindows, setEntryWindows] = useState<Array<{ entry_id: string; entry_desc: string; pick_n: number; avg_dynamic_score: number; estimated_win_rate: number }>>([]);
  const [stockMeta, setStockMeta] = useState<{
    latest_signal_date?: string | null;
    window_mode?: string;
    window_days?: number;
    used_date_count?: number;
    requested_signal_date?: string | null;
    available_signal_dates?: string[];
    source_mode?: string;
    excluded_not_in_v4_n?: number;
    v4_pool_total_n?: number;
    v42_candidate_rows_n?: number;
    v42_rows_in_v4_n?: number;
    v4_baseline_missing_dates?: string[];
    v4_baseline_missing_dates_n?: number;
    v4_baseline_available_dates_n?: number;
  }>({});
  const [alignment, setAlignment] = useState<CupHandleLabAlignmentResponse | null>(null);
  const [alignmentDate, setAlignmentDate] = useState('');
  const [poolCompare, setPoolCompare] = useState<CupHandleLabV4PoolCompareResponse | null>(null);
  const [poolCompareDate, setPoolCompareDate] = useState('');
  const [poolCompareLoading, setPoolCompareLoading] = useState(false);
  const [deliveryView, setDeliveryView] = useState<'hardened' | 'v4'>('hardened');
  const [mainView, setMainView] = useState<'delivery' | 'replay'>('delivery');
  const [replaySignalDate, setReplaySignalDate] = useState('');
  const [themeMode, setThemeMode] = useState<'off' | 'prefer' | 'only'>('off');
  const [selectedThemes, setSelectedThemes] = useState<string[]>(['AiDC', '绿能新能', '算电结合', '国产替代', '储能', '新型医药']);
  const [stockWindowMode, setStockWindowMode] = useState<'adaptive' | 'latest' | 'fixed'>('adaptive');
  const [stockWindowDays, setStockWindowDays] = useState<number>(20);
  const [entryFilter, setEntryFilter] = useState('');
  const [selectedStockCode, setSelectedStockCode] = useState('');
  const [openCards, setOpenCards] = useState<{ stock: boolean; process: boolean; microscope: boolean; audit: boolean; trend: boolean }>({
    stock: true,
    process: false,
    microscope: false,
    audit: false,
    trend: false,
  });

  const [renderVersion, setRenderVersion] = useState<string>('');
  const [pendingVersion, setPendingVersion] = useState<string>('');
  const [hasNewSnapshot, setHasNewSnapshot] = useState(false);
  const [compactMode, setCompactMode] = useState(true);
  const [showSecondary, setShowSecondary] = useState(false);
  const pagePad = compactMode ? 8 : 12;
  const blockGap = compactMode ? 8 : 10;
  const cardPad = compactMode ? 8 : 10;
  const tableMaxHeight = compactMode ? 260 : 360;
  const pageViewportHeight = 'calc(100vh - 70px)';

  const loadAll = async () => {
    setLoading(true);
    setError('');
    try {
      const [s, d, f, a] = await Promise.all([
        api.getCupHandleLabSummary(),
        api.getCupHandleLabDaily(80),
        api.getCupHandleLabDiff(80),
        api.getCupHandleLabAudit(),
      ]);
      const st = await api.getCupHandleLabStocks({
        limit: 240,
        entry: entryFilter || undefined,
        latest_only: stockWindowMode === 'latest' ? true : stockWindowMode === 'fixed' ? false : undefined,
        window_days: stockWindowMode === 'fixed' ? stockWindowDays : undefined,
        signal_date: mainView === 'replay' && replaySignalDate ? replaySignalDate : undefined,
        preferred_themes: selectedThemes,
        theme_mode: themeMode,
      });
      let al: CupHandleLabAlignmentResponse | null = null;
      try {
        al = await api.getCupHandleLabAlignment({ date: alignmentDate || undefined });
      } catch {
        // Backward compatible: older backend may not expose alignment endpoint yet.
        al = null;
      }
      let pc: CupHandleLabV4PoolCompareResponse | null = null;
      try {
        pc = await api.getCupHandleLabV4PoolCompare({ date: poolCompareDate || undefined, persist: true });
      } catch {
        pc = null;
      }
      setSummary(s);
      setDaily(Array.isArray(d.items) ? d.items : []);
      setDiff(Array.isArray(f.items) ? f.items : []);
      setAudit(a);
      setAlignment(al);
      setPoolCompare(pc);
      const stockItems = Array.isArray(st.items) ? st.items : [];
      setStocks(stockItems);
      setEntryWindows(Array.isArray(st.entry_windows) ? st.entry_windows : []);
      setStockMeta(st.meta || {});
      setSelectedStockCode((prev) => {
        if (prev && stockItems.some((x) => x.stock_code === prev)) return prev;
        return stockItems[0]?.stock_code || '';
      });
      const v = String(s?.meta?.latest_hardened_version || '');
      setRenderVersion(v);
      setPendingVersion(v);
      setHasNewSnapshot(false);
    } catch (e: any) {
      setError(e?.message || '加载研究数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadAll();
  }, [entryFilter, alignmentDate, poolCompareDate, themeMode, selectedThemes.join('|'), stockWindowMode, stockWindowDays, mainView, replaySignalDate]);

  const runPoolCompare = async () => {
    setPoolCompareLoading(true);
    try {
      const pc = await api.getCupHandleLabV4PoolCompare({ date: poolCompareDate || undefined, persist: true });
      setPoolCompare(pc);
    } catch (e: any) {
      setError(e?.message || 'V4池内运行V4.2失败');
    } finally {
      setPoolCompareLoading(false);
    }
  };

  const exportRowsAsCsv = (filename: string, rows: Array<Record<string, any>>) => {
    if (!rows.length) return;
    const headers = Object.keys(rows[0]);
    const esc = (v: any) => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const lines = [headers.join(','), ...rows.map((r) => headers.map((h) => esc(r[h])).join(','))];
    const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    // 默认手动刷新；仅做轻量版本检测提示，不强制覆盖当前页面。
    const t = window.setInterval(async () => {
      try {
        const s = await api.getCupHandleLabSummary();
        const v = String(s?.meta?.latest_hardened_version || '');
        if (v && renderVersion && v !== renderVersion) {
          setPendingVersion(v);
          setHasNewSnapshot(true);
        }
      } catch {
        // silent
      }
    }, 60000);
    return () => window.clearInterval(t);
  }, [renderVersion]);

  const recentDiff = useMemo(() => diff.slice(0, compactMode ? 8 : 20), [diff, compactMode]);
  const recentDaily = useMemo(() => daily.slice(0, compactMode ? 8 : 20), [daily, compactMode]);
  const topRules = useMemo(() => (audit?.rules || []).slice(0, 6), [audit]);
  const replayDates = useMemo(() => {
    const metaDates = Array.isArray(stockMeta.available_signal_dates) ? stockMeta.available_signal_dates : [];
    if (metaDates.length) return metaDates.slice().sort().reverse();
    const latest = String(stockMeta.latest_signal_date || '').trim();
    if (latest) return [latest];
    const s = new Set<string>();
    stocks.forEach((x) => {
      const d = String(x.signal_date || '').trim();
      if (d) s.add(d);
    });
    return Array.from(s).sort().reverse();
  }, [stocks, stockMeta.available_signal_dates]);
  const replayStocksView = useMemo(() => {
    return stocks;
  }, [stocks]);
  const selectedStock = useMemo(() => {
    const base = mainView === 'replay' ? replayStocksView : stocks;
    return base.find((s) => s.stock_code === selectedStockCode) || base[0] || null;
  }, [mainView, replayStocksView, stocks, selectedStockCode]);
  const poolCompareView = useMemo<CupHandleLabV4PoolCompareResponse | null>(() => {
    if (poolCompare) return poolCompare;
    if (!stocks.length) return null;
    const target = stockMeta.latest_signal_date || stocks[0]?.signal_date || '';
    const hardened = stocks.slice(0, 120).map((x) => ({
      signal_date: x.signal_date || target || '',
      stock_code: x.stock_code,
      stock_name: x.stock_name,
      segment_id: (x.entries && x.entries[0] && x.entries[0].segment_id) || '',
      dynamic_score: x.dynamic_score,
      gate_count: 0,
      route: (x.entries && x.entries[0] && x.entries[0].entry_id) || '',
    }));
    return {
      meta: {
        target_date: target,
        requested_date: null,
        latest_v4_run_date: null,
        latest_trade_date: null,
        fallback_to_effective_trade_date: false,
        candidate_dates: [],
        market_state: '',
        route_cluster_id: '',
        route_desc: '',
        lab_mode: 'frontend_fallback_from_stocks',
      },
      counts: {
        v4_count: 0,
        v42_base_count: hardened.length,
        v42_hardened_count: hardened.length,
      },
      ratios: {
        base_vs_v4: 0,
        hardened_vs_v4: 0,
        hardened_vs_base: 1,
      },
      quality: {
        label_spec: { strength: 0.04, drawdown: 0.03, up_days_min: 5 },
        base_ready_n: 0,
        base_success_n: 0,
        base_success_rate: 0,
        hard_ready_n: 0,
        hard_success_n: 0,
        hard_success_rate: 0,
        delta_success_rate: 0,
      },
      process: {
        route_miss: 0,
        hard_fail: 0,
        base_pass: hardened.length,
        hard_pass: hardened.length,
      },
      samples: {
        kept_top: [],
        removed_top: [],
      },
      delivery_pool: {
        limit: 240,
        v4_today: [],
        v42_base_today: hardened,
        v42_hardened_today: hardened,
      },
      history_tail: [],
      warnings: ['后端未返回 v4-pool-compare（当前为降级视图，仅展示V4.2候选交付池）'],
    };
  }, [poolCompare, stocks, stockMeta.latest_signal_date]);
  const sparkline = (values: number[], width = 140, height = 34): string => {
    if (!values.length) return '';
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    const dx = (width - 2) / Math.max(1, values.length - 1);
    return values
      .map((v, i) => {
        const x = 1 + i * dx;
        const y = 1 + (height - 2) * (1 - (v - min) / span);
        return `${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(' ');
  };

  const CollapsibleCard = (props: { title: string; open: boolean; onToggle: () => void; badge?: string; children: any }) => (
    <section style={{ ...panel, padding: cardPad }}>
      <button
        onClick={props.onToggle}
        style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, border: 'none', background: 'transparent', padding: 0, cursor: 'pointer' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: c.accent, fontSize: 13, fontWeight: 800 }}>{props.title}</span>
          {props.badge && (
            <span style={{ fontSize: 11, padding: '1px 8px', borderRadius: 999, border: `1px solid ${c.border}`, color: c.dim }}>
              {props.badge}
            </span>
          )}
        </div>
        <span style={{ color: c.dim, fontSize: 12, fontWeight: 800 }}>{props.open ? '收起' : '展开'}</span>
      </button>
      {props.open && <div style={{ marginTop: 8 }}>{props.children}</div>}
    </section>
  );

  const themeCatalog = useMemo(() => ['AiDC', '绿能新能', '算电结合', '国产替代', '储能', '新型医药'], []);
  const dailySeries = useMemo(() => recentDaily.slice().reverse().map((x) => Number(x.success_rate || 0)).filter((x) => Number.isFinite(x)), [recentDaily]);
  const deliveryCounts = useMemo(() => {
    const pv = poolCompareView;
    return {
      hardened: pv?.delivery_pool?.v42_hardened_today?.length || 0,
      v4: pv?.delivery_pool?.v4_today?.length || 0,
    };
  }, [poolCompareView]);
  const replayCount = useMemo(() => replayStocksView.length, [replayStocksView]);
  const mainRows = useMemo(() => {
    if (mainView === 'replay') return replayStocksView;
    const pv = poolCompareView;
    if (!pv) return [];
    if (deliveryView === 'v4') return pv.delivery_pool?.v4_today || [];
    return pv.delivery_pool?.v42_hardened_today || [];
  }, [mainView, replayStocksView, poolCompareView, deliveryView]);

  useEffect(() => {
    if (mainView !== 'replay') return;
    if (!replaySignalDate) {
      const latest = String(stockMeta.latest_signal_date || '').trim();
      if (latest) setReplaySignalDate(latest);
      return;
    }
    if (selectedStockCode && replayStocksView.some((x) => x.stock_code === selectedStockCode)) return;
    setSelectedStockCode(replayStocksView[0]?.stock_code || '');
  }, [mainView, replaySignalDate, replayStocksView, selectedStockCode, stockMeta.latest_signal_date]);

  const sectorCounts = useMemo(() => {
    const m = new Map<string, number>();
    (mainRows as any[]).forEach((r: any) => {
      const k = String(r?.sector_lv1 || r?.sector_lv2 || '').trim();
      if (!k) return;
      m.set(k, (m.get(k) || 0) + 1);
    });
    return m;
  }, [mainRows]);

  const workbench = (
    <div style={{ display: 'grid', gridTemplateColumns: compactMode ? '1fr 360px' : '1fr 380px', gap: blockGap, marginBottom: blockGap }}>

      <section style={{ ...panel, padding: cardPad }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
          <h3 style={{ ...sectionTitle, marginBottom: 0 }}>{mainView === 'delivery' ? '当日交付池' : '验证回放池'}</h3>
          <button
            onClick={() => {
              const td = poolCompareView?.meta?.target_date || stockMeta.latest_signal_date || 'unknown';
              if (mainView === 'delivery') {
                exportRowsAsCsv(
                  `cup_lab_delivery_${deliveryView}_${td}.csv`,
                  (mainRows as any[]).map((x) => ({
                    signal_date: x.signal_date || td,
                    stock_code: x.stock_code,
                    stock_name: x.stock_name,
                    sector_lv1: x.sector_lv1,
                    sector_lv2: x.sector_lv2,
                    history_has_success: x.history_has_success,
                    history_cup_n: x.history_cup_n,
                    history_success_n: x.history_success_n,
                    segment_id: x.segment_id,
                    dynamic_score: x.dynamic_score,
                    gate_count: x.gate_count,
                    route: x.route,
                  }))
                );
              } else {
                exportRowsAsCsv(
                  `cup_lab_replay_${td}.csv`,
                  (mainRows as any[]).map((x) => ({
                    signal_date: x.signal_date,
                    stock_code: x.stock_code,
                    stock_name: x.stock_name,
                    is_success_strict: x.is_success_strict,
                    end_return_t8: x.end_return_t8,
                    drawdown_mag_t1_t8: x.drawdown_mag_t1_t8,
                    estimated_win_rate: x.estimated_win_rate,
                    dynamic_score: x.dynamic_score,
                    sample_n: x.sample_n,
                    entry_count: x.entry_count,
                  }))
                );
              }
            }}
            style={{ border: `1px solid ${c.border}`, background: 'transparent', color: c.dim, borderRadius: 6, padding: '4px 10px', cursor: 'pointer', fontWeight: 900, fontSize: 12 }}
          >
            导出CSV
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ border: `1px solid ${c.border}`, borderRadius: 8, padding: '6px 8px', minWidth: 120 }}>
                <div style={{ color: c.dim, fontSize: 11 }}>当前胜率</div>
                <div style={{ color: c.good, fontSize: 16, fontWeight: 900 }}>{pct(summary?.quality?.hardened_success_rate)}</div>
              </div>
              <div style={{ border: `1px solid ${c.border}`, borderRadius: 8, padding: '6px 8px', minWidth: 120 }}>
                <div style={{ color: c.dim, fontSize: 11 }}>对比基线</div>
                <div style={{ color: (summary?.quality?.delta_vs_base || 0) >= 0 ? c.good : c.bad, fontSize: 16, fontWeight: 900 }}>
                  {summary?.quality?.delta_vs_base == null ? '-' : `${summary.quality.delta_vs_base >= 0 ? '+' : ''}${(summary.quality.delta_vs_base * 100).toFixed(2)}pp`}
                </div>
              </div>
            </div>
            <div style={{ border: `1px solid ${c.border}`, borderRadius: 8, padding: '6px 8px' }}>
              <div style={{ color: c.dim, fontSize: 11, marginBottom: 4 }}>近N日胜率</div>
              <svg width={140} height={34} viewBox="0 0 140 34">
                <polyline fill="none" stroke={c.accent} strokeWidth="2" points={sparkline(dailySeries, 140, 34)} />
              </svg>
            </div>
          </div>
        </div>
        <div style={{ overflow: 'auto', maxHeight: compactMode ? '62vh' : 520 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ background: c.tableHead, color: c.text }}>
                <th style={{ textAlign: 'left', padding: 6 }}>代码</th>
                <th style={{ textAlign: 'left', padding: 6 }}>名称</th>
                <th style={{ textAlign: 'left', padding: 6 }}>板块</th>
                {mainView === 'replay' && <th style={{ textAlign: 'center', padding: 6 }}>结果</th>}
                <th style={{ textAlign: 'center', padding: 6 }}>历史胜出</th>
                <th style={{ textAlign: 'right', padding: 6 }}>杯柄次数</th>
                <th style={{ textAlign: 'right', padding: 6 }}>板块热度</th>
                {mainView === 'replay' && <th style={{ textAlign: 'right', padding: 6 }}>估计胜率</th>}
                <th style={{ textAlign: 'right', padding: 6 }}>{mainView === 'delivery' ? (deliveryView === 'v4' ? '门控' : '评分') : '评分'}</th>
              </tr>
            </thead>
            <tbody>
              {(mainRows as any[]).map((r: any) => {
                const code = String(r.stock_code || '');
                const selected = code && selectedStock?.stock_code === code;
                const scoreCell =
                  mainView === 'delivery'
                    ? (deliveryView === 'v4' ? num(r.gate_count) : Number(r.dynamic_score || 0).toFixed(2))
                    : Number(r.dynamic_score || 0).toFixed(2);
                const winCell = mainView === 'replay' ? pct(r.estimated_win_rate) : null;
                const succ = r.is_success_strict;
                const resultBadge = mainView !== 'replay'
                  ? null
                  : (
                    <span style={{
                      color: succ == null ? c.dim : (Number(succ) === 1 ? c.good : c.bad),
                      border: `1px solid ${succ == null ? c.border : (Number(succ) === 1 ? c.good : c.bad)}`,
                      borderRadius: 10,
                      padding: '1px 8px',
                      fontSize: 11,
                      display: 'inline-block',
                      fontWeight: 800,
                      background: succ == null ? 'transparent' : (Number(succ) === 1 ? (isLight ? 'rgba(34,197,94,0.10)' : 'rgba(34,197,94,0.12)') : (isLight ? 'rgba(239,68,68,0.10)' : 'rgba(239,68,68,0.12)')),
                    }}>
                      {succ == null ? '未到期' : (Number(succ) === 1 ? '成功' : '失败')}
                    </span>
                  );
                const sector = String(r?.sector_lv1 || r?.sector_lv2 || '-');
                const sectorN = sector && sector !== '-' ? (sectorCounts.get(sector) || 0) : 0;
                const histHas = r?.history_has_success;
                const histBadge = (
                  <span style={{
                    color: histHas ? c.good : c.dim,
                    border: `1px solid ${histHas ? c.good : c.border}`,
                    borderRadius: 10,
                    padding: '1px 8px',
                    fontSize: 11,
                    display: 'inline-block',
                    fontWeight: 800,
                    background: histHas ? (isLight ? 'rgba(34,197,94,0.10)' : 'rgba(34,197,94,0.12)') : 'transparent',
                  }}>
                    {histHas ? '有' : '无'}
                  </span>
                );
                const cupN = Number(r?.history_cup_n || 0) || 0;
                return (
                  <tr
                    key={`${mainView}-${deliveryView}-${code}`}
                    onClick={() => code && setSelectedStockCode(code)}
                    style={{ borderTop: `1px solid ${c.border}`, cursor: 'pointer', background: selected ? (isLight ? 'rgba(30,64,175,0.08)' : 'rgba(255,203,5,0.08)') : 'transparent' }}
                  >
                    <td style={{ padding: 6, color: c.text, whiteSpace: 'nowrap', fontFamily: 'monospace' }}>{code}</td>
                    <td style={{ padding: 6, color: c.text, whiteSpace: 'nowrap' }}>{r.stock_name || '-'}</td>
                    <td style={{ padding: 6, color: c.dim, whiteSpace: 'nowrap' }}>{sector}</td>
                    {mainView === 'replay' && <td style={{ padding: 6, textAlign: 'center' }}>{resultBadge}</td>}
                    <td style={{ padding: 6, textAlign: 'center' }}>{histBadge}</td>
                    <td style={{ padding: 6, textAlign: 'right', color: c.text, fontWeight: 800 }}>{cupN || '-'}</td>
                    <td style={{ padding: 6, textAlign: 'right', color: c.dim }}>{sectorN ? `${sectorN}` : '-'}</td>
                    {mainView === 'replay' && <td style={{ padding: 6, color: c.good, textAlign: 'right', fontWeight: 800 }}>{winCell}</td>}
                    <td style={{ padding: 6, color: mainView === 'delivery' && deliveryView !== 'v4' ? c.good : c.text, textAlign: 'right', fontWeight: 800 }}>{scoreCell}</td>
                  </tr>
                );
              })}
              {!mainRows.length && (
                <tr>
                  <td style={{ padding: 8, color: c.warn, lineHeight: 1.5 }} colSpan={mainView === 'replay' ? 9 : 8}>
                    {mainView === 'replay' && Number(stockMeta?.v42_candidate_rows_n || 0) > 0 && Number(stockMeta?.v42_rows_in_v4_n || 0) === 0
                      ? (
                        <>
                          <div style={{ fontWeight: 800, color: c.warn }}>暂无数据（被 V4 基池硬约束过滤为空）</div>
                          <div style={{ color: c.dim, fontSize: 11 }}>
                            回放日期：{stockMeta?.latest_signal_date || '-'} · V4.2 候选行：{Number(stockMeta?.v42_candidate_rows_n || 0)} · 命中 V4：0 · V4 基池总量（窗口内累计）：{Number(stockMeta?.v4_pool_total_n || 0)}
                          </div>
                          <div style={{ color: c.dim, fontSize: 11 }}>
                            说明：当前回放池来自标签可用的历史日期（如 2026-04-20），但 dashboard.db 中该日期可能没有完成的 V4 运行记录，因此无法做“V4.2 ⊆ V4”匹配，结果会显示为空。
                          </div>
                        </>
                      )
                      : '暂无数据'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <div style={{ display: 'grid', gap: blockGap, alignContent: 'start' }}>
        <section style={{ ...panel, padding: cardPad }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <h3 style={{ ...sectionTitle, marginBottom: 0 }}>工作台</h3>
            <span style={{ color: c.dim, fontSize: 12 }}>主视图</span>
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
            <button
              onClick={() => setMainView('delivery')}
              style={{ border: `1px solid ${mainView === 'delivery' ? c.accent : c.border}`, background: mainView === 'delivery' ? c.accent : 'transparent', color: mainView === 'delivery' ? (isLight ? '#fff' : '#050d1a') : c.dim, borderRadius: 999, padding: '2px 10px', cursor: 'pointer', fontSize: 12, fontWeight: 800 }}
            >
              交付池 ({mainView === 'delivery' ? mainRows.length : (deliveryView === 'v4' ? deliveryCounts.v4 : deliveryCounts.hardened)})
            </button>
            <button
              onClick={() => setMainView('replay')}
              style={{ border: `1px solid ${mainView === 'replay' ? c.accent : c.border}`, background: mainView === 'replay' ? c.accent : 'transparent', color: mainView === 'replay' ? (isLight ? '#fff' : '#050d1a') : c.dim, borderRadius: 999, padding: '2px 10px', cursor: 'pointer', fontSize: 12, fontWeight: 800 }}
            >
              回放池 ({replayCount})
            </button>
          </div>
          {mainView === 'replay' && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span style={{ color: c.dim, fontSize: 12 }}>有效日期</span>
              <select
                value={replaySignalDate}
                onChange={(e) => setReplaySignalDate(e.target.value)}
                style={{ background: isLight ? '#fff' : '#0f1f33', color: c.text, border: `1px solid ${c.border}`, borderRadius: 6, padding: '2px 8px', fontSize: 12, minWidth: 0, width: 170 }}
              >
                {replayDates.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>
          )}
          {mainView === 'delivery' && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
              <button
                onClick={() => setDeliveryView('hardened')}
                style={{ border: `1px solid ${deliveryView === 'hardened' ? c.accent : c.border}`, background: deliveryView === 'hardened' ? (isLight ? 'rgba(30,64,175,0.10)' : 'rgba(255,203,5,0.12)') : 'transparent', color: deliveryView === 'hardened' ? c.accent : c.dim, borderRadius: 999, padding: '2px 10px', cursor: 'pointer', fontSize: 11, fontWeight: 800 }}
              >
                V4.2加固 ({deliveryCounts.hardened})
              </button>
              <button
                onClick={() => setDeliveryView('v4')}
                style={{ border: `1px solid ${deliveryView === 'v4' ? c.accent : c.border}`, background: deliveryView === 'v4' ? (isLight ? 'rgba(30,64,175,0.10)' : 'rgba(255,203,5,0.12)') : 'transparent', color: deliveryView === 'v4' ? c.accent : c.dim, borderRadius: 999, padding: '2px 10px', cursor: 'pointer', fontSize: 11, fontWeight: 800 }}
              >
                V4基池 ({deliveryCounts.v4})
              </button>
            </div>
          )}
          <div style={{ color: c.dim, fontSize: 11, lineHeight: 1.5 }}>
            日期 {poolCompareView?.meta?.target_date || stockMeta.latest_signal_date || '-'} · 回退 {poolCompareView?.meta?.fallback_to_effective_trade_date ? '是' : '否'} · 最新交易 {poolCompareView?.meta?.latest_trade_date || '-'}
          </div>
        </section>

        <section style={{ ...panel, padding: cardPad }}>
          <h3 style={{ ...sectionTitle, marginBottom: 8 }}>筛选与约束</h3>
          <div style={{ display: 'grid', gap: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
              <span style={{ color: c.dim, fontSize: 12 }}>入口</span>
              <select
                value={entryFilter}
                onChange={(e) => setEntryFilter(e.target.value)}
                style={{ background: isLight ? '#fff' : '#0f1f33', color: c.text, border: `1px solid ${c.border}`, borderRadius: 6, padding: '2px 8px', fontSize: 12, minWidth: 0, width: 170 }}
              >
                <option value="">全部入口</option>
                {entryWindows.map((w) => (
                  <option key={w.entry_id} value={w.entry_id}>
                    {w.entry_id} ({w.pick_n})
                  </option>
                ))}
              </select>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
              <span style={{ color: c.dim, fontSize: 12 }}>回放窗口</span>
              <select
                value={stockWindowMode}
                onChange={(e) => setStockWindowMode(e.target.value as 'adaptive' | 'latest' | 'fixed')}
                style={{ background: isLight ? '#fff' : '#0f1f33', color: c.text, border: `1px solid ${c.border}`, borderRadius: 6, padding: '2px 8px', fontSize: 12, minWidth: 0, width: 170 }}
              >
                <option value="adaptive">自适应</option>
                <option value="latest">仅最新</option>
                <option value="fixed">固定窗口</option>
              </select>
            </div>
            {stockWindowMode === 'fixed' && (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                <span style={{ color: c.dim, fontSize: 12 }}>窗口大小</span>
                <select
                  value={stockWindowDays}
                  onChange={(e) => setStockWindowDays(Number(e.target.value || 20))}
                  style={{ background: isLight ? '#fff' : '#0f1f33', color: c.text, border: `1px solid ${c.border}`, borderRadius: 6, padding: '2px 8px', fontSize: 12, minWidth: 0, width: 170 }}
                >
                  {[10, 20, 30, 40, 60].map((d) => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
              <span style={{ color: c.dim, fontSize: 12 }}>主题</span>
              <select
                value={themeMode}
                onChange={(e) => setThemeMode(e.target.value as 'off' | 'prefer' | 'only')}
                style={{ background: isLight ? '#fff' : '#0f1f33', color: c.text, border: `1px solid ${c.border}`, borderRadius: 6, padding: '2px 8px', fontSize: 12, minWidth: 0, width: 170 }}
              >
                <option value="off">关闭</option>
                <option value="prefer">倾向排序</option>
                <option value="only">只看匹配</option>
              </select>
            </div>
            {themeMode !== 'off' && (
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {themeCatalog.map((t) => {
                  const on = selectedThemes.includes(t);
                  return (
                    <button
                      key={t}
                      onClick={() => setSelectedThemes((prev) => (prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]))}
                      style={{
                        border: `1px solid ${on ? c.accent : c.border}`,
                        background: on ? (isLight ? 'rgba(30,64,175,0.10)' : 'rgba(255,203,5,0.12)') : 'transparent',
                        color: on ? c.accent : c.dim,
                        borderRadius: 999,
                        padding: '2px 8px',
                        cursor: 'pointer',
                        fontSize: 11,
                        fontWeight: 800,
                      }}
                    >
                      {t}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </section>

        {CollapsibleCard({
          title: '选中股票',
          open: openCards.stock,
          onToggle: () => setOpenCards((p) => ({ ...p, stock: !p.stock })),
          badge: selectedStock?.stock_code || '',
          children: selectedStock ? (
            <>
              <div style={{ color: c.text, fontSize: 13, fontWeight: 900, marginBottom: 6 }}>
                {selectedStock.stock_code} {selectedStock.stock_name}
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                {(selectedStock.reason_tags || []).map((t) => (
                  <span key={t} style={{ fontSize: 11, border: `1px solid ${c.border}`, borderRadius: 999, padding: '2px 8px', color: c.text, background: isLight ? 'rgba(30,64,175,0.07)' : 'rgba(255,255,255,0.04)' }}>
                    {t}
                  </span>
                ))}
                {(selectedStock.matched_themes || []).map((t) => (
                  <span key={`theme-${t}`} style={{ fontSize: 11, border: `1px solid ${c.accent}`, borderRadius: 999, padding: '2px 8px', color: c.accent, background: isLight ? 'rgba(30,64,175,0.12)' : 'rgba(255,203,5,0.12)' }}>
                    主题:{t}
                  </span>
                ))}
              </div>
              <div style={{ color: c.dim, fontSize: 12, marginBottom: 6 }}>
                估计胜率 {pct(selectedStock.estimated_win_rate)} · 动态评分 {selectedStock.dynamic_score.toFixed(2)} · 形态 {segmentLabel((selectedStock.entries && selectedStock.entries[0] && selectedStock.entries[0].segment_id) || '')}
              </div>
              <div style={{ maxHeight: compactMode ? 320 : 380, overflow: 'auto', display: 'grid', gap: 6 }}>
                {(selectedStock.entries || []).slice(0, compactMode ? 8 : 12).map((e, idx) => (
                  <div key={`${e.entry_id}-${idx}`} style={{ border: `1px solid ${c.border}`, borderRadius: 6, padding: '6px 8px' }}>
                    <div style={{ color: c.text, fontSize: 12, fontWeight: 900 }}>{e.entry_id}</div>
                    <div style={{ color: c.dim, fontSize: 11 }}>
                      {stateLabel(e.market_state)} · {e.segment_id || '-'} · 胜率估计 {pct(e.estimated_win_rate)}
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div style={{ color: c.dim, fontSize: 12 }}>请选择中间主表中的股票</div>
          ),
        })}

        {CollapsibleCard({
          title: '过程摊开',
          open: openCards.process,
          onToggle: () => setOpenCards((p) => ({ ...p, process: !p.process })),
          badge: poolCompareView?.meta?.lab_mode === 'frontend_fallback_from_stocks' ? '降级' : '对比',
          children: (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                {!!poolCompareView?.meta?.candidate_dates?.length ? (
                  <select
                    value={poolCompareDate}
                    onChange={(e) => setPoolCompareDate(e.target.value)}
                    style={{ background: isLight ? '#fff' : '#0f1f33', color: c.text, border: `1px solid ${c.border}`, borderRadius: 6, padding: '2px 8px', fontSize: 12 }}
                  >
                    <option value="">最新V4完成日</option>
                    {(poolCompareView.meta.candidate_dates || []).slice().reverse().map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                ) : (
                  <span style={{ color: c.dim, fontSize: 12 }}>日期 {poolCompareView?.meta?.target_date || '-'}</span>
                )}
                <button
                  onClick={() => void runPoolCompare()}
                  style={{ border: `1px solid ${c.accent}`, background: c.accent, color: isLight ? '#fff' : '#050d1a', borderRadius: 6, padding: '4px 10px', cursor: 'pointer', fontWeight: 900, fontSize: 12 }}
                >
                  {poolCompareLoading ? '运行中...' : '运行对比'}
                </button>
              </div>
              <div style={{ color: c.dim, fontSize: 11, lineHeight: 1.6 }}>
                日期 {poolCompareView?.meta?.target_date || '-'} · 市场状态 {stateLabel(poolCompareView?.meta?.market_state || '')} · 路由 {poolCompareView?.meta?.route_cluster_id || '-'}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 8, marginTop: 8 }}>
                <div style={{ border: `1px solid ${c.border}`, borderRadius: 8, padding: '6px 8px' }}>
                  <div style={{ color: c.dim, fontSize: 11 }}>V4</div>
                  <div style={{ color: c.text, fontSize: 16, fontWeight: 900 }}>{num(poolCompareView?.counts?.v4_count)}</div>
                </div>
                <div style={{ border: `1px solid ${c.border}`, borderRadius: 8, padding: '6px 8px' }}>
                  <div style={{ color: c.dim, fontSize: 11 }}>V4.2 Hardened</div>
                  <div style={{ color: c.accent, fontSize: 16, fontWeight: 900 }}>{num(poolCompareView?.counts?.v42_hardened_count)}</div>
                </div>
              </div>
              {!!poolCompareView?.warnings?.length && (
                <div style={{ marginTop: 8, color: c.warn, fontSize: 12, fontWeight: 900 }}>
                  {poolCompareView.warnings.join(' | ')}
                </div>
              )}
            </>
          ),
        })}

        {CollapsibleCard({
          title: '显微镜对照',
          open: openCards.microscope,
          onToggle: () => setOpenCards((p) => ({ ...p, microscope: !p.microscope })),
          badge: alignment?.meta?.target_date || '',
          children: alignment ? (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                <span style={{ color: c.dim, fontSize: 12 }}>对照日期 {alignment.meta.target_date || '-'}</span>
                {!!alignment?.meta?.candidate_dates?.length && (
                  <select
                    value={alignmentDate}
                    onChange={(e) => setAlignmentDate(e.target.value)}
                    style={{ background: isLight ? '#fff' : '#0f1f33', color: c.text, border: `1px solid ${c.border}`, borderRadius: 6, padding: '2px 8px', fontSize: 12 }}
                  >
                    <option value="">最近有效同日</option>
                    {(alignment.meta.candidate_dates || []).slice().reverse().map((d) => (
                      <option key={d.date} value={d.date}>
                        {d.date} | V4 {d.v4_count} | H {d.v42_hardened_count}
                      </option>
                    ))}
                  </select>
                )}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 8 }}>
                <div style={{ border: `1px solid ${c.border}`, borderRadius: 8, padding: '6px 8px' }}>
                  <div style={{ color: c.dim, fontSize: 11 }}>H/V4</div>
                  <div style={{ color: c.text, fontSize: 16, fontWeight: 900 }}>{pct(alignment.ratios.hardened_vs_v4)}</div>
                </div>
                <div style={{ border: `1px solid ${c.border}`, borderRadius: 8, padding: '6px 8px' }}>
                  <div style={{ color: c.dim, fontSize: 11 }}>Δ胜率</div>
                  <div style={{ color: (alignment.quality.delta_success_rate || 0) >= 0 ? c.good : c.bad, fontSize: 16, fontWeight: 900 }}>
                    {`${alignment.quality.delta_success_rate >= 0 ? '+' : ''}${(alignment.quality.delta_success_rate * 100).toFixed(2)}pp`}
                  </div>
                </div>
              </div>
              {!!alignment?.warnings?.length && (
                <div style={{ marginTop: 8, color: c.warn, fontSize: 12, fontWeight: 900 }}>
                  {alignment.warnings.join(' | ')}
                </div>
              )}
            </>
          ) : (
            <div style={{ color: c.dim, fontSize: 12 }}>暂无对照数据</div>
          ),
        })}

        {CollapsibleCard({
          title: '规则审计',
          open: openCards.audit,
          onToggle: () => setOpenCards((p) => ({ ...p, audit: !p.audit })),
          children: (
            <div style={{ display: 'grid', gap: 6, maxHeight: compactMode ? 260 : 320, overflow: 'auto' }}>
              {topRules.map((r, idx) => (
                <div key={`${r.market_state || idx}`} style={{ border: `1px solid ${c.border}`, borderRadius: 6, padding: 8 }}>
                  <div style={{ color: c.text, fontWeight: 900 }}>{stateLabel(String(r.market_state || '-'))}</div>
                  <div style={{ color: c.dim, fontSize: 12 }}>规则：{String(r.harden_rule || '-')}</div>
                  <div style={{ color: c.dim, fontSize: 12 }}>
                    样本 {String(r.base_pick_n || '-')} → {String(r.hardened_pick_n || '-')}，胜率 {pct(Number(r.base_success_rate || 0))} → {pct(Number(r.hardened_success_rate || 0))}
                  </div>
                </div>
              ))}
              {!topRules.length && <div style={{ color: c.dim, fontSize: 12 }}>暂无门槛审计数据</div>}
            </div>
          ),
        })}

        {CollapsibleCard({
          title: '趋势与回放',
          open: openCards.trend,
          onToggle: () => setOpenCards((p) => ({ ...p, trend: !p.trend })),
          children: (
            <div style={{ overflow: 'auto', maxHeight: compactMode ? 280 : 340 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ background: c.tableHead, color: c.text }}>
                    <th style={{ textAlign: 'left', padding: 6 }}>日期</th>
                    <th style={{ textAlign: 'right', padding: 6 }}>样本</th>
                    <th style={{ textAlign: 'right', padding: 6 }}>胜率</th>
                  </tr>
                </thead>
                <tbody>
                  {recentDaily.map((r, idx) => (
                    <tr key={`${r.signal_date}-${idx}`} style={{ borderTop: `1px solid ${c.border}` }}>
                      <td style={{ padding: 6, color: c.text }}>{r.signal_date}</td>
                      <td style={{ padding: 6, color: c.dim, textAlign: 'right' }}>{r.pick_n}</td>
                      <td style={{ padding: 6, color: c.good, textAlign: 'right', fontWeight: 900 }}>{pct(r.success_rate)}</td>
                    </tr>
                  ))}
                  {!recentDaily.length && <tr><td style={{ padding: 6, color: c.dim }} colSpan={3}>暂无数据</td></tr>}
                </tbody>
              </table>
            </div>
          ),
        })}
      </div>
    </div>
  );
  const corePillars = useMemo(
    () => [
      {
        code: 'A',
        title: '多入口',
        desc: '形态成熟度、量价节奏、状态分型同时进入，不依赖单一信号。',
        tint: isLight ? 'linear-gradient(135deg, rgba(30,64,175,0.10), rgba(30,64,175,0.03))' : 'linear-gradient(135deg, rgba(255,203,5,0.14), rgba(255,203,5,0.03))',
      },
      {
        code: 'B',
        title: '多层次',
        desc: '先做基础过滤，再做状态路由和白名单强化，逐层提升命中质量。',
        tint: isLight ? 'linear-gradient(135deg, rgba(2,132,199,0.10), rgba(2,132,199,0.03))' : 'linear-gradient(135deg, rgba(0,212,255,0.14), rgba(0,212,255,0.03))',
      },
      {
        code: 'C',
        title: '动态匹配',
        desc: '按市场状态切换匹配路径，并通过回放结果持续修正参数与门槛。',
        tint: isLight ? 'linear-gradient(135deg, rgba(34,197,94,0.10), rgba(34,197,94,0.03))' : 'linear-gradient(135deg, rgba(34,197,94,0.14), rgba(34,197,94,0.03))',
      },
    ],
    [isLight]
  );
  const flowSteps = useMemo(
    () => [
      { id: '01', name: '输入层', detail: 'V4 候选池 + 市场状态分型', tint: isLight ? 'rgba(30,64,175,0.10)' : 'rgba(255,203,5,0.10)' },
      { id: '02', name: '过滤层', detail: '形态/量价/节奏基础条件 + 白名单门槛', tint: isLight ? 'rgba(2,132,199,0.10)' : 'rgba(0,212,255,0.10)' },
      { id: '03', name: '匹配层', detail: '按 S1/S2/S3 动态路由到不同强化策略', tint: isLight ? 'rgba(34,197,94,0.10)' : 'rgba(34,197,94,0.12)' },
      { id: '04', name: '学习层', detail: '回放复盘 base vs hardened 差异，持续迭代', tint: isLight ? 'rgba(245,158,11,0.12)' : 'rgba(245,158,11,0.14)' },
    ],
    [isLight]
  );

  return (
    <div
      style={{
        padding: pagePad,
        background: c.pageBg,
        minHeight: '78vh',
        height: pageViewportHeight,
        overflowY: 'auto',
        overflowX: 'hidden',
        scrollbarGutter: 'stable',
      }}
    >
      <div
        style={{
          ...panel,
          padding: compactMode ? 10 : 12,
          marginBottom: blockGap,
          background: isLight ? 'linear-gradient(90deg,#f8fbff,#eef4ff)' : 'linear-gradient(90deg,#081222,#0a1628)',
          position: 'sticky',
          top: 0,
          zIndex: 8,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <div style={{ color: c.accent, fontSize: 13, fontWeight: 900, letterSpacing: '0.06em' }}>CUP HANDLE LAB</div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                border: `1px solid ${c.border}`,
                borderRadius: 999,
                padding: 2,
                background: isLight ? 'rgba(255,255,255,0.72)' : 'rgba(255,255,255,0.04)',
                boxShadow: isLight ? 'inset 0 1px 0 rgba(255,255,255,0.9)' : 'inset 0 1px 0 rgba(255,255,255,0.06)',
              }}
            >
              <button
                onClick={() => setCompactMode(false)}
                style={{
                  border: 'none',
                  borderRadius: 999,
                  padding: '4px 10px',
                  cursor: 'pointer',
                  fontWeight: 700,
                  fontSize: 12,
                  color: compactMode ? c.dim : (isLight ? '#fff' : '#050d1a'),
                  background: compactMode ? 'transparent' : c.accent,
                }}
              >
                标准
              </button>
              <button
                onClick={() => setCompactMode(true)}
                style={{
                  border: 'none',
                  borderRadius: 999,
                  padding: '4px 10px',
                  cursor: 'pointer',
                  fontWeight: 700,
                  fontSize: 12,
                  color: compactMode ? (isLight ? '#fff' : '#050d1a') : c.dim,
                  background: compactMode ? c.accent : 'transparent',
                }}
              >
                简洁
              </button>
            </div>
            <button
              onClick={() => void loadAll()}
              style={{ border: `1px solid ${c.accent}`, background: c.accent, color: isLight ? '#fff' : '#050d1a', borderRadius: 6, padding: '4px 10px', cursor: 'pointer', fontWeight: 700 }}
            >
              {loading ? '刷新中...' : '手动刷新'}
            </button>
            {hasNewSnapshot && (
              <span style={{ color: c.warn, fontSize: 12 }}>
                检测到新快照 {pendingVersion}，可点击“手动刷新”加载
              </span>
            )}
            <span style={{ color: c.dim, fontSize: 12 }}>
              当前版本：{summary?.meta?.latest_hardened_version || '-'}
            </span>
            <button
              onClick={() => setShowSecondary((v) => !v)}
              style={{ border: `1px solid ${c.border}`, background: 'transparent', color: c.dim, borderRadius: 6, padding: '4px 10px', cursor: 'pointer', fontWeight: 700, fontSize: 12 }}
            >
              {showSecondary ? '收起次要信息' : '展开次要信息'}
            </button>
            {showSecondary && (
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <div style={{ color: c.dim, fontSize: 12 }}>
                  目标：持续提升候选股票在未来数日进入上行启动段的概率（研究指标，不直接下交易指令）
                </div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: isLight ? 'rgba(30,64,175,0.12)' : 'rgba(255,203,5,0.14)', color: c.accent }}>多入口</span>
                  <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: isLight ? 'rgba(2,132,199,0.12)' : 'rgba(0,212,255,0.14)', color: isLight ? '#0c4a6e' : '#00d4ff' }}>多层次</span>
                  <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: isLight ? 'rgba(34,197,94,0.12)' : 'rgba(34,197,94,0.14)', color: c.good }}>动态匹配</span>
                  <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: isLight ? 'rgba(245,158,11,0.14)' : 'rgba(245,158,11,0.18)', color: c.warn }}>持续学习</span>
                  {compactMode && (
                    <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: isLight ? 'rgba(2,132,199,0.12)' : 'rgba(2,132,199,0.18)', color: isLight ? '#0c4a6e' : '#67e8f9' }}>
                      简洁视图
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
        {error && (
          <div style={{ marginTop: 8, color: c.bad, fontSize: 12 }}>{error}</div>
        )}
      </div>

      {workbench}

      {showSecondary && (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: blockGap, marginBottom: blockGap }}>
        <section style={{ ...panel, padding: cardPad }}>
          <h3 style={sectionTitle}>核心思想（First Look）</h3>
          <div style={{ color: c.dim, fontSize: 12, lineHeight: 1.6, marginBottom: 8 }}>
            研究目标不是“找得多”，而是“选出来更容易走出先调整后启动的路径”。
          </div>
          <div style={{ display: 'grid', gap: 6 }}>
            {corePillars.map((p) => (
              <div key={p.title} style={{ border: `1px solid ${c.border}`, borderRadius: 6, padding: '6px 8px', background: p.tint, boxShadow: isLight ? 'inset 0 1px 0 rgba(255,255,255,0.6)' : 'inset 0 1px 0 rgba(255,255,255,0.06)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                  <span style={{ display: 'inline-block', minWidth: 22, textAlign: 'center', borderRadius: 4, fontSize: 11, fontWeight: 700, padding: '1px 6px', background: isLight ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.08)', color: c.accent }}>
                    {p.code}
                  </span>
                  <span style={{ color: c.text, fontSize: 13, fontWeight: 700 }}>{p.title}</span>
                </div>
                {!compactMode && <div style={{ color: c.dim, fontSize: 12, lineHeight: 1.5 }}>{p.desc}</div>}
              </div>
            ))}
          </div>
          {!compactMode && (
            <div style={{ color: c.dim, fontSize: 12, lineHeight: 1.6, marginTop: 8 }}>
            {summary?.self_explanatory?.goal || '提升候选池在未来数日的上行启动概率。'}
            </div>
          )}
        </section>
        <section style={{ ...panel, padding: cardPad }}>
          <h3 style={sectionTitle}>研究流程（Self Explanatory）</h3>
          <div style={{ display: 'grid', gap: 6 }}>
            {flowSteps.map((step, idx) => (
              <div key={step.id}>
                <div
                  style={{
                    border: `1px solid ${c.border}`,
                    borderRadius: 6,
                    padding: '6px 8px',
                    color: c.text,
                    fontSize: 12,
                    lineHeight: 1.5,
                    background: step.tint,
                  }}
                >
                  <span
                    style={{
                      display: 'inline-block',
                      minWidth: 28,
                      textAlign: 'center',
                      borderRadius: 4,
                      fontSize: 11,
                      fontWeight: 700,
                      marginRight: 8,
                      padding: '1px 6px',
                      background: isLight ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.08)',
                      color: c.accent,
                    }}
                  >
                    {step.id}
                  </span>
                  <span style={{ fontWeight: 700 }}>{step.name}</span>
                  {!compactMode && <span style={{ color: c.dim }}>：{step.detail}</span>}
                </div>
                {idx < flowSteps.length - 1 && (
                  <div style={{ color: c.dim, fontSize: 11, textAlign: 'center', lineHeight: 1.2, margin: '2px 0' }}>↓</div>
                )}
              </div>
            ))}
          </div>
          {!compactMode && (
            <div style={{ color: c.dim, fontSize: 12, lineHeight: 1.6, marginTop: 8 }}>
              方法口径：{summary?.self_explanatory?.method || 'V4 与 V4.2 并行对照，持续回放与样本外验证。'}
            </div>
          )}
        </section>
      </div>
      )}

      {showSecondary && (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: blockGap, marginBottom: blockGap }}>
        <div style={{ ...panel, padding: cardPad }}>
          <div style={{ color: c.dim, fontSize: 12 }}>当前胜率（Hardened）</div>
          <div style={{ color: c.good, fontSize: 24, fontWeight: 700 }}>{pct(summary?.quality?.hardened_success_rate)}</div>
          <div style={{ color: c.dim, fontSize: 12 }}>样本 {num(summary?.quality?.hardened_pick_n)} / 命中 {num(summary?.quality?.hardened_success_n)}</div>
        </div>
        <div style={{ ...panel, padding: cardPad }}>
          <div style={{ color: c.dim, fontSize: 12 }}>对比基线（V4）</div>
          <div style={{ color: (summary?.quality?.delta_vs_base || 0) >= 0 ? c.good : c.bad, fontSize: 24, fontWeight: 700 }}>
            {summary?.quality?.delta_vs_base == null ? '-' : `${summary.quality.delta_vs_base >= 0 ? '+' : ''}${(summary.quality.delta_vs_base * 100).toFixed(2)}pp`}
          </div>
          <div style={{ color: c.dim, fontSize: 12 }}>基线胜率 {pct(summary?.quality?.base_success_rate)}</div>
        </div>
        <div style={{ ...panel, padding: cardPad }}>
          <div style={{ color: c.dim, fontSize: 12 }}>近4周趋势（窗口）</div>
          <div style={{ color: c.text, fontSize: 14, lineHeight: 1.6 }}>
            {(summary?.trend_4w || []).map((w) => `${w.window}:${pct(w.success_rate)}`).join(' · ') || '-'}
          </div>
        </div>
        <div style={{ ...panel, padding: cardPad }}>
          <div style={{ color: c.dim, fontSize: 12 }}>波段语义映射</div>
          <div style={{ color: c.text, fontSize: 13, lineHeight: 1.5 }}>
            关注“先调整、后启动”的路径质量，可映射到 3浪/5浪/B浪语义；{summary?.self_explanatory?.note || '当前用于筛选研究，不作硬交易规则。'}
          </div>
        </div>
      </div>
      )}

      {showSecondary && (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: blockGap, marginBottom: blockGap }}>
        <section style={{ ...panel, padding: cardPad }}>
          <h3 style={sectionTitle}>分状态胜率</h3>
          <div style={{ display: 'grid', gap: 6 }}>
            {(summary?.states || []).map((s) => (
              <div key={s.state} style={{ display: 'flex', justifyContent: 'space-between', border: `1px solid ${c.border}`, borderRadius: 6, padding: '6px 8px' }}>
                <span style={{ color: c.text }}>{stateLabel(s.state)}</span>
                <span style={{ color: c.good, fontWeight: 700 }}>{pct(s.success_rate)}</span>
                <span style={{ color: c.dim }}>样本 {s.pick_n}</span>
              </div>
            ))}
          </div>
        </section>
        <section style={{ ...panel, padding: cardPad }}>
          <h3 style={sectionTitle}>白名单门槛（可审计）</h3>
          <div style={{ color: c.dim, fontSize: 12, marginBottom: 6 }}>目标：解释“删了谁、换来了什么”</div>
          <div style={{ display: 'grid', gap: 6, maxHeight: 220, overflow: 'auto' }}>
            {topRules.map((r, idx) => (
              <div key={`${r.market_state || idx}`} style={{ border: `1px solid ${c.border}`, borderRadius: 6, padding: 8 }}>
                <div style={{ color: c.text, fontWeight: 700 }}>{stateLabel(String(r.market_state || '-'))}</div>
                <div style={{ color: c.dim, fontSize: 12 }}>规则：{String(r.harden_rule || '-')}</div>
                <div style={{ color: c.dim, fontSize: 12 }}>
                  样本 {String(r.base_pick_n || '-')} → {String(r.hardened_pick_n || '-')}，胜率 {pct(Number(r.base_success_rate || 0))} → {pct(Number(r.hardened_success_rate || 0))}
                </div>
              </div>
            ))}
            {!topRules.length && <div style={{ color: c.dim, fontSize: 12 }}>暂无门槛审计数据</div>}
          </div>
        </section>
      </div>
      )}

      {showSecondary && (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: blockGap }}>
        <section style={{ ...panel, padding: cardPad }}>
          <h3 style={sectionTitle}>最近日级筛选表现</h3>
          <div style={{ overflow: 'auto', maxHeight: tableMaxHeight }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ background: c.tableHead, color: c.text }}>
                  <th style={{ textAlign: 'left', padding: 6 }}>日期</th>
                  <th style={{ textAlign: 'left', padding: 6 }}>状态</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>样本</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>胜率</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>均值收益</th>
                </tr>
              </thead>
              <tbody>
                {recentDaily.map((r, idx) => (
                  <tr key={`${r.signal_date}-${idx}`} style={{ borderTop: `1px solid ${c.border}` }}>
                    <td style={{ padding: 6, color: c.text }}>{r.signal_date}</td>
                    <td style={{ padding: 6, color: c.dim }}>{stateLabel(r.market_state)}</td>
                    <td style={{ padding: 6, color: c.text, textAlign: 'right' }}>{r.pick_n}</td>
                    <td style={{ padding: 6, color: c.good, textAlign: 'right' }}>{pct(r.success_rate)}</td>
                    <td style={{ padding: 6, color: r.avg_end_return_t8 >= 0 ? c.good : c.bad, textAlign: 'right' }}>{pct(r.avg_end_return_t8)}</td>
                  </tr>
                ))}
                {!recentDaily.length && (
                  <tr><td style={{ padding: 6, color: c.dim }} colSpan={5}>暂无数据</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
        <section style={{ ...panel, padding: cardPad }}>
          <h3 style={sectionTitle}>Base vs Hardened 日差异</h3>
          <div style={{ overflow: 'auto', maxHeight: tableMaxHeight }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ background: c.tableHead, color: c.text }}>
                  <th style={{ textAlign: 'left', padding: 6 }}>日期</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>Base</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>Hard</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>Δ胜率</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>移除</th>
                </tr>
              </thead>
              <tbody>
                {recentDiff.map((r, idx) => {
                  const delta = r.hard_rate - r.base_rate;
                  return (
                    <tr key={`${r.signal_date}-${idx}`} style={{ borderTop: `1px solid ${c.border}` }}>
                      <td style={{ padding: 6, color: c.text }}>{r.signal_date}</td>
                      <td style={{ padding: 6, color: c.dim, textAlign: 'right' }}>{pct(r.base_rate)}</td>
                      <td style={{ padding: 6, color: c.good, textAlign: 'right' }}>{pct(r.hard_rate)}</td>
                      <td style={{ padding: 6, color: delta >= 0 ? c.good : c.bad, textAlign: 'right' }}>
                        {`${delta >= 0 ? '+' : ''}${(delta * 100).toFixed(2)}pp`}
                      </td>
                      <td style={{ padding: 6, color: c.dim, textAlign: 'right' }}>{r.removed_n}</td>
                    </tr>
                  );
                })}
                {!recentDiff.length && (
                  <tr><td style={{ padding: 6, color: c.dim }} colSpan={5}>暂无数据</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
      )}
    </div>
  );
}
