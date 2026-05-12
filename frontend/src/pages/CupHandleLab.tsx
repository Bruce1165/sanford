import { useEffect, useMemo, useState } from 'react';
import {
  api,
  type CupHandleLabSummaryResponse,
  type CupHandleLabDailyItem,
  type CupHandleLabDiffItem,
  type CupHandleLabAuditResponse,
  type CupHandleLabWatchPoolItem,
  type CupHandleLabAlignmentResponse,
  type CupHandleLabV4PoolCompareResponse,
  type CupHandleLabFeedbackItem,
  type CupHandleLabDailyBriefResponse,
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

const fmtDateTime = (raw: any): string => {
  const s = String(raw ?? '').trim();
  if (!s) return '-';
  return s.slice(0, 10);
};

const normalizeStockCode = (raw: any): string => {
  const s = String(raw ?? '').trim();
  if (!s) return '';
  const m = /^(\d+)\.0+$/.exec(s);
  return m ? m[1] : s;
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

const sectorHeatLabel = (count: number): '低' | '中' | '高' => {
  if (count >= 6) return '高';
  if (count >= 3) return '中';
  return '低';
};

const ruleToZh = (raw: string): string => {
  const s = String(raw || '').trim();
  if (!s) return '';
  const normalized = s.replace(/\s+/g, '');
  const parts = normalized.split('&').map((x) => x.trim()).filter(Boolean);
  const out: string[] = [];
  for (const p of parts) {
    let m: RegExpExecArray | null = null;
    m = /^rim<=([0-9.]+)$/.exec(p);
    if (m) {
      out.push(`杯宽(天)≤${m[1]}`);
      continue;
    }
    m = /^([0-9.]+)<rim<=([0-9.]+)$/.exec(p);
    if (m) {
      out.push(`杯宽(天)${m[1]}~${m[2]}`);
      continue;
    }
    m = /^cup>([0-9.]+)$/.exec(p);
    if (m) {
      out.push(`杯深>${(Number(m[1]) * 100).toFixed(0)}%`);
      continue;
    }
    m = /^([0-9.]+)<cup<=([0-9.]+)$/.exec(p);
    if (m) {
      out.push(`杯深${(Number(m[1]) * 100).toFixed(0)}%~${(Number(m[2]) * 100).toFixed(0)}%`);
      continue;
    }
    m = /^amount<=([0-9.]+)$/.exec(p);
    if (m) {
      out.push(`成交额比(升/跌)≤${m[1]}`);
      continue;
    }
    out.push(p);
  }
  return out.join(' · ');
};

const entryIdLabelFallback = (raw: string): string => {
  const s = String(raw || '').trim();
  if (!s) return '-';
  const parts = s.split('_').filter(Boolean);
  if (!parts.length) return s;
  const mapped = parts
    .map((p) => {
      if (/^C\d+$/i.test(p)) return '';
      if (p === 'precision') return '';
      if (p === 'defensive') return '';
      const m = /^([a-z]+)(\d+)$/i.exec(p);
      if (!m) return '';
      const key = m[1].toLowerCase();
      const n = m[2];
      if (key === 'rim') return `杯宽(天)≤${n}`;
      if (key === 'cup') return `杯深>${n}%`;
      if (key === 'amt') return `成交额比(升/跌)≤${(Number(n) / 100).toFixed(2)}`;
      return '';
    })
    .filter(Boolean);
  return mapped.join(' · ') || s;
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
  const [watchItems, setWatchItems] = useState<CupHandleLabWatchPoolItem[]>([]);
  const [watchMeta, setWatchMeta] = useState<{
    latest_signal_date?: string | null;
    available_signal_dates?: string[];
    requested_signal_date?: string | null;
    window_mode?: string;
  }>({});
  const [entryWindows, setEntryWindows] = useState<Array<{ entry_id: string; entry_desc: string; pick_n: number; avg_dynamic_score: number; estimated_win_rate: number }>>([]);
  const [alignment, setAlignment] = useState<CupHandleLabAlignmentResponse | null>(null);
  const [alignmentDate, setAlignmentDate] = useState('');
  const [poolCompare, setPoolCompare] = useState<CupHandleLabV4PoolCompareResponse | null>(null);
  const [poolCompareDate, setPoolCompareDate] = useState('');
  const [poolCompareLoading, setPoolCompareLoading] = useState(false);
  const [poolCompareError, setPoolCompareError] = useState('');
  const deliveryView = 'hardened' as const;
  const [mainView, setMainView] = useState<'delivery' | 'replay'>('delivery');
  const [replaySignalDate, setReplaySignalDate] = useState('');
  const [replayDateLocked, setReplayDateLocked] = useState(false);
  const [themeMode, setThemeMode] = useState<'off' | 'prefer' | 'only'>('off');
  const [selectedThemes, setSelectedThemes] = useState<string[]>(['AiDC', '绿能新能', '算电结合', '国产替代', '储能', '新型医药']);
  const [stockWindowMode, setStockWindowMode] = useState<'adaptive' | 'latest' | 'fixed'>('adaptive');
  const [stockWindowDays, setStockWindowDays] = useState<number>(20);
  const [entryFilter, setEntryFilter] = useState('');
  const [selectedReplayStockCode, setSelectedReplayStockCode] = useState('');
  const [selectedDeliveryStockCode, setSelectedDeliveryStockCode] = useState('');

  // Questionnaire feedback (v1): structured to avoid noisy free-form input.
  const [feedbackItems, setFeedbackItems] = useState<CupHandleLabFeedbackItem[]>([]);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [feedbackError, setFeedbackError] = useState('');
  const [fbQ1, setFbQ1] = useState<'should' | 'should_not' | 'unsure'>('unsure');
  const [fbQ2, setFbQ2] = useState<string[]>([]);
  const [fbQ3, setFbQ3] = useState<'' | 'shape' | 'volume' | 'market' | 'sector' | 'risk_reward'>('');
  const [fbQ4, setFbQ4] = useState<'t5' | 't8' | 't13'>('t8');
  const [fbQ5, setFbQ5] = useState<'low' | 'mid' | 'high'>('mid');
  const [fbLastSubmitMsg, setFbLastSubmitMsg] = useState('');
  const [dailyBrief, setDailyBrief] = useState<CupHandleLabDailyBriefResponse | null>(null);
  const [dailyBriefLoading, setDailyBriefLoading] = useState(false);
  const [dailyBriefError, setDailyBriefError] = useState('');
  const [openCards, setOpenCards] = useState<{ stock: boolean; process: boolean; microscope: boolean; audit: boolean; trend: boolean }>({
    stock: true,
    process: true,
    microscope: false,
    audit: false,
    trend: false,
  });

  const [renderVersion, setRenderVersion] = useState<string>('');
  const [pendingVersion, setPendingVersion] = useState<string>('');
  const [hasNewSnapshot, setHasNewSnapshot] = useState(false);
  const [compactMode] = useState(true);
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
        signal_date: mainView === 'replay' && replayDateLocked && replaySignalDate ? replaySignalDate : undefined,
        preferred_themes: selectedThemes,
        theme_mode: themeMode,
      });
      const wt = await api.getCupHandleLabWatchPool({
        limit: 800,
        signal_date: mainView === 'replay' && replayDateLocked && replaySignalDate ? replaySignalDate : undefined,
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
        setPoolCompareError('');
        pc = await api.getCupHandleLabV4PoolCompare({ date: poolCompareDate || undefined, persist: true });
      } catch (e: any) {
        setPoolCompareError(e?.message || '新入池对比数据获取失败（请在“过程摊开”里点击“运行”重试）');
        pc = null;
      }
      setSummary(s);
      setDaily(Array.isArray(d.items) ? d.items : []);
      setDiff(Array.isArray(f.items) ? f.items : []);
      setAudit(a);
      setAlignment(al);
      setPoolCompare(pc);
      setWatchItems(Array.isArray(wt.items) ? wt.items : []);
      setWatchMeta(wt.meta || {});
      setEntryWindows(Array.isArray(st.entry_windows) ? st.entry_windows : []);
      if (mainView === 'replay') {
        setSelectedReplayStockCode((prev) => {
          const p = normalizeStockCode(prev);
          const rows = Array.isArray(wt.items) ? wt.items : [];
          if (p && rows.some((x) => normalizeStockCode(x.stock_code) === p)) return p;
          return normalizeStockCode(rows[0]?.stock_code || '');
        });
      }
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
  }, [entryFilter, alignmentDate, poolCompareDate, themeMode, selectedThemes.join('|'), stockWindowMode, stockWindowDays, mainView, replaySignalDate, replayDateLocked]);

  const runPoolCompare = async () => {
    setPoolCompareLoading(true);
    try {
      setPoolCompareError('');
      const pc = await api.getCupHandleLabV4PoolCompare({ date: poolCompareDate || undefined, persist: true });
      setPoolCompare(pc);
    } catch (e: any) {
      const msg = e?.message || '新入池对比计算失败';
      setPoolCompareError(msg);
      setError(msg);
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
    const metaDates = Array.isArray(watchMeta.available_signal_dates) ? watchMeta.available_signal_dates : [];
    if (metaDates.length) return metaDates.slice().sort().reverse();
    const latest = String(watchMeta.latest_signal_date || '').trim();
    if (latest) return [latest];
    const s = new Set<string>();
    watchItems.forEach((x) => {
      const d = String(x.signal_date || '').trim();
      if (d) s.add(d);
    });
    return Array.from(s).sort().reverse();
  }, [watchItems, watchMeta.available_signal_dates, watchMeta.latest_signal_date]);
  const poolCompareView = useMemo<CupHandleLabV4PoolCompareResponse | null>(() => {
    return poolCompare;
  }, [poolCompare]);
  const replayStocksView = useMemo(() => {
    const grouped = new Map<string, any>();
    watchItems.forEach((it) => {
      const code = normalizeStockCode(it.stock_code);
      const d = String(it.signal_date || '').trim();
      if (!code || !d) return;
      const k = `${d}__${code}`;
      const cur = grouped.get(k) || {
        stock_code: code,
        stock_name: it.stock_name || '',
        signal_date: d,
        entered_at: String(it.created_at || '').trim(),
        dynamic_score: (typeof it.dynamic_score === 'number' ? it.dynamic_score : 0),
        gate_count: (typeof it.gate_count === 'number' ? it.gate_count : 0),
        segment_id: it.segment_id || '',
        v42_pass: false,
        is_success_strict: it.is_success_strict ?? null,
        end_return_t8: it.end_return_t8 ?? null,
        drawdown_mag_t1_t8: it.drawdown_mag_t1_t8 ?? null,
      };
      if (it.source_pool === 'hardened') cur.v42_pass = true;
      const enteredAt = String(it.created_at || '').trim();
      if (!cur.entered_at && enteredAt) cur.entered_at = enteredAt;
      else if (enteredAt && cur.entered_at && enteredAt < cur.entered_at) cur.entered_at = enteredAt;
      const score = typeof it.dynamic_score === 'number' ? it.dynamic_score : 0;
      if (score >= Number(cur.dynamic_score || 0)) {
        cur.dynamic_score = score;
        cur.gate_count = typeof it.gate_count === 'number' ? it.gate_count : cur.gate_count;
        cur.segment_id = it.segment_id || cur.segment_id;
        cur.is_success_strict = it.is_success_strict ?? cur.is_success_strict;
        cur.end_return_t8 = (it.end_return_t8 ?? cur.end_return_t8);
        cur.drawdown_mag_t1_t8 = (it.drawdown_mag_t1_t8 ?? cur.drawdown_mag_t1_t8);
      }
      grouped.set(k, cur);
    });
    const items = Array.from(grouped.values());
    items.sort((a, b) => {
      if (a.signal_date !== b.signal_date) return String(b.signal_date).localeCompare(String(a.signal_date));
      if ((b.v42_pass ? 1 : 0) !== (a.v42_pass ? 1 : 0)) return (b.v42_pass ? 1 : 0) - (a.v42_pass ? 1 : 0);
      return Number(b.dynamic_score || 0) - Number(a.dynamic_score || 0);
    });
    return items;
  }, [watchItems]);
  const selectedStockCode = normalizeStockCode(mainView === 'replay' ? selectedReplayStockCode : selectedDeliveryStockCode);
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
  const mainRows = useMemo(() => {
    if (mainView === 'replay') return replayStocksView;
    const pv = poolCompareView;
    if (!pv) return [];
    return pv.delivery_pool?.v42_hardened_today || [];
  }, [mainView, replayStocksView, poolCompareView]);
  const replayButtonCountLabel = String(replayStocksView.length);
  const selectedRow = useMemo<any>(() => {
    const rows = (mainRows as any[]) || [];
    if (!rows.length) return null;
    if (!selectedStockCode) return rows[0] || null;
    const hit = rows.find((x: any) => normalizeStockCode(x?.stock_code) === selectedStockCode);
    return hit || rows[0] || null;
  }, [mainRows, selectedStockCode]);
  const selectedDetail = useMemo(() => {
    // Replay detail comes from normalized watch-pool rows.
    if (mainView !== 'replay') return null;
    const want = normalizeStockCode(selectedStockCode);
    if (!want) return null;
    return replayStocksView.find((s: any) => normalizeStockCode(s.stock_code) === want) || null;
  }, [replayStocksView, selectedStockCode, mainView]);
  const selectedStock = selectedRow;

  const feedbackQ2Options: Array<{ id: string; label: string }> = useMemo(
    () => [
      { id: 'shape_quality', label: '形态质量不足（杯体/柄部不理想）' },
      { id: 'volume_rhythm', label: '量价节奏不匹配（突破前后量能异常）' },
      { id: 'market_state', label: '市场状态不匹配（当日环境不支持）' },
      { id: 'sector_theme', label: '板块/主题一致性弱' },
      { id: 'drawdown_risk', label: '回撤风险不可接受' },
      { id: 'other_structural', label: '其他结构性风险' },
    ],
    []
  );
  const fbQ1Label = (v: string) => (v === 'should' ? '应该' : v === 'should_not' ? '不应该' : v === 'unsure' ? '不确定' : v || '-');
  const fbQ3Label = (v: string) => {
    if (v === 'shape') return '形态风险';
    if (v === 'volume') return '量价风险';
    if (v === 'market') return '市场状态风险';
    if (v === 'sector') return '板块一致性风险';
    if (v === 'risk_reward') return '风险收益比失衡';
    return v || '-';
  };
  const fbQ4Label = (v: string) => (v === 't5' ? 'T+5' : v === 't8' ? 'T+8' : v === 't13' ? 'T+13' : v || '-');
  const fbQ5Label = (v: string) => (v === 'low' ? '低(<=3%)' : v === 'mid' ? '中(3%~6%)' : v === 'high' ? '高(>6%)' : v || '-');

  const loadFeedback = async (code: string) => {
    const want = normalizeStockCode(code);
    if (!want) {
      setFeedbackItems([]);
      return;
    }
    setFeedbackLoading(true);
    setFeedbackError('');
    try {
      const r = await api.getCupHandleLabFeedback({ stock_code: want, limit: 10, offset: 0 });
      setFeedbackItems(Array.isArray(r.items) ? r.items : []);
    } catch (e: any) {
      setFeedbackError(e?.message || '反馈列表加载失败');
      setFeedbackItems([]);
    } finally {
      setFeedbackLoading(false);
    }
  };

  const loadDailyBrief = async () => {
    setDailyBriefLoading(true);
    setDailyBriefError('');
    try {
      const reqDate = String(poolCompareDate || poolCompareView?.meta?.target_date || '').trim() || undefined;
      const r = await api.getCupHandleLabDailyBrief({ date: reqDate });
      setDailyBrief(r);
    } catch (e: any) {
      setDailyBrief(null);
      setDailyBriefError(e?.message || '每日小结加载失败');
    } finally {
      setDailyBriefLoading(false);
    }
  };

  useEffect(() => {
    void loadFeedback(selectedStockCode);
    // Reset form to sensible defaults per selected stock.
    setFbQ1('unsure');
    setFbQ2([]);
    setFbQ3('');
    setFbQ4('t8');
    setFbQ5('mid');
    setFbLastSubmitMsg('');
  }, [selectedStockCode]);

  useEffect(() => {
    void loadDailyBrief();
  }, [poolCompareDate, replaySignalDate, mainView]);

  const submitFeedback = async () => {
    const code = normalizeStockCode(selectedStockCode);
    if (!code) return;
    setFeedbackLoading(true);
    setFeedbackError('');
    setFbLastSubmitMsg('');
    try {
      const signalDate = String(
        (selectedRow as any)?.signal_date ||
        (selectedStock as any)?.signal_date ||
        poolCompareView?.meta?.target_date ||
        watchMeta.latest_signal_date ||
        ''
      ).trim();
      await api.submitCupHandleLabFeedback({
        stock_code: code,
        stock_name: String((selectedStock as any)?.stock_name || (selectedRow as any)?.stock_name || '').trim() || undefined,
        signal_date: signalDate || undefined,
        main_view: mainView,
        delivery_view: mainView === 'delivery' ? deliveryView : undefined,
        q1_should_enter: fbQ1,
        q2_reasons: fbQ2,
        q3_primary_risk: fbQ3 || undefined,
        q4_horizon: fbQ4,
        q5_drawdown_tolerance: fbQ5,
      });
      setFbLastSubmitMsg('已提交');
      await loadFeedback(code);
    } catch (e: any) {
      setFeedbackError(e?.message || '提交失败');
    } finally {
      setFeedbackLoading(false);
    }
  };

  useEffect(() => {
    if (mainView !== 'replay') return;
    const rows = replayStocksView;
    if (!replaySignalDate) {
      const latest = String(watchMeta.latest_signal_date || '').trim();
      if (latest) setReplaySignalDate(latest);
      return;
    }
    if (!rows.length) {
      setSelectedReplayStockCode('');
      return;
    }
    const cur = normalizeStockCode(selectedReplayStockCode);
    if (cur && rows.some((x) => normalizeStockCode(x.stock_code) === cur)) return;
    setSelectedReplayStockCode(normalizeStockCode(rows[0]?.stock_code || ''));
  }, [mainView, replaySignalDate, replayStocksView, selectedReplayStockCode, watchMeta.latest_signal_date]);

  useEffect(() => {
    if (mainView !== 'delivery') return;
    const rows = mainRows as any[];
    if (!rows.length) {
      setSelectedDeliveryStockCode('');
      return;
    }
    const cur = normalizeStockCode(selectedDeliveryStockCode);
    if (cur && rows.some((x: any) => normalizeStockCode(x?.stock_code) === cur)) return;
    setSelectedDeliveryStockCode(normalizeStockCode(rows[0]?.stock_code || ''));
  }, [mainView, mainRows, selectedDeliveryStockCode]);

  const sectorCounts = useMemo(() => {
    const m = new Map<string, number>();
    (mainRows as any[]).forEach((r: any) => {
      if (mainView !== 'delivery') return;
      const k = String(r?.sector_lv1 || r?.sector_lv2 || '').trim();
      if (!k) return;
      m.set(k, (m.get(k) || 0) + 1);
    });
    return m;
  }, [mainRows, mainView]);

  const workbench = (
    <div style={{ display: 'grid', gridTemplateColumns: compactMode ? '61% 39%' : '61% 39%', gap: blockGap, marginBottom: blockGap }}>

      <section style={{ ...panel, padding: cardPad }}>
        <div style={{ border: `1px solid ${c.border}`, borderRadius: 8, padding: '8px 10px', marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <div style={{ color: c.accent, fontSize: 12, fontWeight: 900 }}>每日学习小结</div>
            <div style={{ color: c.dim, fontSize: 11 }}>
              {dailyBrief?.meta?.target_date || '-'} · 更新 {String(dailyBrief?.meta?.latest_updated_at || '-').replace('T', ' ').slice(0, 19)}
            </div>
          </div>
          {!!dailyBriefError && <div style={{ color: c.warn, fontSize: 12, marginBottom: 6 }}>{dailyBriefError}</div>}
          {dailyBriefLoading && !dailyBrief ? (
            <div style={{ color: c.dim, fontSize: 12 }}>加载中...</div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 8 }}>
              <div style={{ color: c.text, fontSize: 12 }}>
                新入观察 {num(dailyBrief?.daily_action?.new_watch_n)} · 反馈处理 {num(dailyBrief?.daily_action?.feedback_processed_n)}
              </div>
              <div style={{ color: c.text, fontSize: 12 }}>
                T+8 {pct(dailyBrief?.forward_summary?.t8_success_rate)}（{dailyBrief?.forward_summary?.t8_success_trend || '-'}）
              </div>
              <div style={{ color: c.text, fontSize: 12 }}>
                收益均值 {pct(dailyBrief?.forward_summary?.avg_return_t8)} · 回撤均值 {pct(dailyBrief?.forward_summary?.avg_drawdown_t1_t8)}
              </div>
              <div style={{ color: c.dim, fontSize: 12 }}>
                参数更新 {dailyBrief?.model_iteration?.param_update_n == null ? '待接入' : num(dailyBrief.model_iteration.param_update_n)} · 入口完善 {dailyBrief?.model_iteration?.entry_improve_pct == null ? '待接入' : pct(dailyBrief.model_iteration.entry_improve_pct)}
              </div>
              <div style={{ color: c.text, fontSize: 12 }}>
                变更结论 {dailyBrief?.strategy_audit?.decision === 'keep' ? '保留' : dailyBrief?.strategy_audit?.decision === 'rollback' ? '回滚' : '继续观察'}
                {' '}· Δ胜率 {typeof dailyBrief?.strategy_audit?.delta_success_rate_pp === 'number' ? `${dailyBrief.strategy_audit.delta_success_rate_pp >= 0 ? '+' : ''}${dailyBrief.strategy_audit.delta_success_rate_pp.toFixed(2)}pp` : '待补'}
                {' '}· 样本 {dailyBrief?.strategy_audit?.ready_n ?? '-'} / {dailyBrief?.strategy_audit?.min_ready_n ?? 30}
              </div>
              <div style={{ color: c.dim, fontSize: 12 }}>
                回撤闸门{' '}
                <span
                  title={String(dailyBrief?.strategy_audit?.decision_reason || '暂无判定说明')}
                  style={{
                    display: 'inline-block',
                    borderRadius: 10,
                    padding: '1px 8px',
                    fontSize: 11,
                    fontWeight: 800,
                    border: `1px solid ${
                      dailyBrief?.strategy_audit?.drawdown_gate_status === 'pass'
                        ? c.good
                        : dailyBrief?.strategy_audit?.drawdown_gate_status === 'fail'
                        ? c.bad
                        : c.border
                    }`,
                    color:
                      dailyBrief?.strategy_audit?.drawdown_gate_status === 'pass'
                        ? c.good
                        : dailyBrief?.strategy_audit?.drawdown_gate_status === 'fail'
                        ? c.bad
                        : c.dim,
                    background:
                      dailyBrief?.strategy_audit?.drawdown_gate_status === 'pass'
                        ? (isLight ? 'rgba(34,197,94,0.10)' : 'rgba(34,197,94,0.12)')
                        : dailyBrief?.strategy_audit?.drawdown_gate_status === 'fail'
                        ? (isLight ? 'rgba(239,68,68,0.10)' : 'rgba(239,68,68,0.12)')
                        : 'transparent',
                  }}
                >
                  {dailyBrief?.strategy_audit?.drawdown_gate_status === 'pass'
                    ? '通过'
                    : dailyBrief?.strategy_audit?.drawdown_gate_status === 'fail'
                    ? '未通过'
                    : '待补'}
                </span>
                {' '}· Δ回撤 {typeof dailyBrief?.strategy_audit?.drawdown_delta_pp === 'number' ? `${dailyBrief.strategy_audit.drawdown_delta_pp >= 0 ? '+' : ''}${dailyBrief.strategy_audit.drawdown_delta_pp.toFixed(2)}pp` : '待补'}
                {' '}· 阈值 {typeof dailyBrief?.strategy_audit?.drawdown_threshold_pp === 'number' ? `<=${dailyBrief.strategy_audit.drawdown_threshold_pp.toFixed(2)}pp` : '待补'}
              </div>
              <div style={{ color: c.dim, fontSize: 11 }}>
                判定说明：{dailyBrief?.strategy_audit?.decision_reason || '暂无判定说明'}
              </div>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
          <h3 style={{ ...sectionTitle, marginBottom: 0 }}>{mainView === 'delivery' ? '新入池杯柄' : '跟踪观察池'}</h3>
          <button
            onClick={() => {
              const td = poolCompareView?.meta?.target_date || watchMeta.latest_signal_date || 'unknown';
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
                    v42_pass: x.v42_pass ? 1 : 0,
                    dynamic_score: x.dynamic_score,
                    gate_count: x.gate_count,
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
                {mainView === 'delivery' && <th style={{ textAlign: 'left', padding: 6 }}>板块</th>}
                {mainView === 'replay' && <th style={{ textAlign: 'left', padding: 6 }}>入池时间</th>}
                {mainView === 'replay' && <th style={{ textAlign: 'center', padding: 6 }}>V4.2/强化</th>}
                {mainView === 'replay' && <th style={{ textAlign: 'center', padding: 6 }}>结果</th>}
                {mainView === 'delivery' && <th style={{ textAlign: 'center', padding: 6 }}>历史胜出</th>}
                {mainView === 'delivery' && <th style={{ textAlign: 'right', padding: 6 }}>杯柄次数</th>}
                {mainView === 'delivery' && <th style={{ textAlign: 'right', padding: 6 }}>板块热度</th>}
                <th style={{ textAlign: 'right', padding: 6 }}>评分</th>
              </tr>
            </thead>
            <tbody>
              {!mainRows.length ? (
                <tr style={{ borderTop: `1px solid ${c.border}` }}>
                  <td style={{ padding: 10, color: c.dim }} colSpan={mainView === 'replay' ? 6 : 8}>
                    {mainView === 'delivery'
                      ? (poolCompareView
                        ? '新入池暂无数据'
                        : (poolCompareError || '新入池对比数据未加载：请在右侧“过程摊开”点击“运行”'))
                      : '观察池暂无数据'}
                  </td>
                </tr>
              ) : null}
              {(mainRows as any[]).map((r: any) => {
                const code = normalizeStockCode(r.stock_code);
                const selected = code && normalizeStockCode(selectedStockCode) === code;
                const scoreCell = Number(r.dynamic_score || 0).toFixed(2);
                const succ = r.is_success_strict;
                const v42Badge = mainView !== 'replay'
                  ? null
                  : (
                    <span style={{
                      color: r.v42_pass ? c.good : c.dim,
                      border: `1px solid ${r.v42_pass ? c.good : c.border}`,
                      borderRadius: 10,
                      padding: '1px 8px',
                      fontSize: 11,
                      display: 'inline-block',
                      fontWeight: 800,
                      background: r.v42_pass ? (isLight ? 'rgba(34,197,94,0.10)' : 'rgba(34,197,94,0.12)') : 'transparent',
                    }}>
                      {r.v42_pass ? '通过' : '未通过'}
                    </span>
                  );
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
                    key={`${mainView}-${r.signal_date || ''}-${code}`}
                    onClick={() => {
                      if (!code) return;
                      if (mainView === 'replay') {
                        setSelectedReplayStockCode(code);
                      } else {
                        setSelectedDeliveryStockCode(code);
                      }
                    }}
                    style={{ borderTop: `1px solid ${c.border}`, cursor: 'pointer', background: selected ? (isLight ? 'rgba(30,64,175,0.08)' : 'rgba(255,203,5,0.08)') : 'transparent' }}
                  >
                    <td style={{ padding: 6, color: c.text, whiteSpace: 'nowrap', fontFamily: 'monospace' }}>{code}</td>
                    <td style={{ padding: 6, color: c.text, whiteSpace: 'nowrap' }}>{r.stock_name || '-'}</td>
                    {mainView === 'delivery' && <td style={{ padding: 6, color: c.dim, whiteSpace: 'nowrap' }}>{sector}</td>}
                    {mainView === 'replay' && <td style={{ padding: 6, color: c.dim, whiteSpace: 'nowrap' }}>{fmtDateTime(r.entered_at)}</td>}
                    {mainView === 'replay' && <td style={{ padding: 6, textAlign: 'center' }}>{v42Badge}</td>}
                    {mainView === 'replay' && <td style={{ padding: 6, textAlign: 'center' }}>{resultBadge}</td>}
                    {mainView === 'delivery' && <td style={{ padding: 6, textAlign: 'center' }}>{histBadge}</td>}
                    {mainView === 'delivery' && <td style={{ padding: 6, textAlign: 'right', color: c.text, fontWeight: 800 }}>{cupN || '-'}</td>}
                    {mainView === 'delivery' && (
                      <td style={{ padding: 6, textAlign: 'right', color: c.dim, fontWeight: 800 }}>
                        {(() => {
                          const n = sectorCounts.get(sector) || 0;
                          return n > 0 ? sectorHeatLabel(n) : '-';
                        })()}
                      </td>
                    )}
                    <td style={{ padding: 6, color: mainView === 'delivery' ? c.good : c.text, textAlign: 'right', fontWeight: 800 }}>{scoreCell}</td>
                  </tr>
                );
              })}
              {!mainRows.length && (
                <tr>
                  <td style={{ padding: 8, color: c.warn, lineHeight: 1.5 }} colSpan={mainView === 'replay' ? 6 : 8}>
                    暂无数据
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
              onClick={() => {
                setSelectedDeliveryStockCode('');
                setMainView('delivery');
              }}
              style={{ border: `1px solid ${mainView === 'delivery' ? c.accent : c.border}`, background: mainView === 'delivery' ? c.accent : 'transparent', color: mainView === 'delivery' ? (isLight ? '#fff' : '#050d1a') : c.dim, borderRadius: 999, padding: '2px 10px', cursor: 'pointer', fontSize: 12, fontWeight: 800 }}
            >
              新入池 ({mainView === 'delivery' ? mainRows.length : deliveryCounts.hardened})
            </button>
            <button
              onClick={() => {
                setSelectedReplayStockCode('');
                setMainView('replay');
              }}
              style={{ border: `1px solid ${mainView === 'replay' ? c.accent : c.border}`, background: mainView === 'replay' ? c.accent : 'transparent', color: mainView === 'replay' ? (isLight ? '#fff' : '#050d1a') : c.dim, borderRadius: 999, padding: '2px 10px', cursor: 'pointer', fontSize: 12, fontWeight: 800 }}
            >
              观察池 ({replayButtonCountLabel})
            </button>
          </div>
          <div style={{ color: c.dim, fontSize: 11, lineHeight: 1.5, marginBottom: 8 }}>
            {mainView === 'delivery'
              ? '关系：新入池杯柄=当日强化口径候选；基池口径仅在“杯柄池（基础→强化）比较”中查看。'
              : '关系：跟踪观察池=按入池事件持久化累计（同股可多时段重复入池）；默认展示可用日期范围，锁定日期用于单日查询。'}
          </div>
          {mainView === 'replay' && (
            <div style={{ display: 'grid', gap: 8, marginBottom: 8 }}>
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: c.text, fontSize: 12, cursor: 'pointer' }}>
                <input type="checkbox" checked={replayDateLocked} onChange={(e) => setReplayDateLocked(e.target.checked)} />
                <span>锁定日期查询</span>
              </label>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                <span style={{ color: c.dim, fontSize: 12 }}>观察日期</span>
                <input
                  type="date"
                  value={replaySignalDate}
                  onChange={(e) => setReplaySignalDate(e.target.value)}
                  disabled={!replayDateLocked}
                  min={replayDates.length ? replayDates[replayDates.length - 1] : undefined}
                  max={replayDates.length ? replayDates[0] : undefined}
                  style={{ background: isLight ? '#fff' : '#0f1f33', color: c.text, border: `1px solid ${c.border}`, borderRadius: 6, padding: '2px 8px', fontSize: 12, minWidth: 0, width: 170, opacity: replayDateLocked ? 1 : 0.6 }}
                />
              </div>
            </div>
          )}
          <div style={{ color: c.dim, fontSize: 11, lineHeight: 1.5 }}>
            日期 {poolCompareView?.meta?.target_date || watchMeta.latest_signal_date || '-'} · 回退 {poolCompareView?.meta?.fallback_to_effective_trade_date ? '是' : '否'} · 最新交易 {poolCompareView?.meta?.latest_trade_date || '-'}
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
              {mainView === 'delivery' && (
                <div style={{ color: c.dim, fontSize: 12, marginBottom: 6, lineHeight: 1.5 }}>
                  视图：新入池 · V4.2强化口径 · 日期 {selectedRow?.signal_date || poolCompareView?.meta?.target_date || '-'}
                </div>
              )}
              <div style={{ color: c.dim, fontSize: 12, marginBottom: 6 }}>
                {mainView === 'replay'
                  ? (
                    <>
                      强化通过 {(selectedRow as any)?.v42_pass ? '是' : '否'} · 评分 {typeof selectedDetail?.dynamic_score === 'number' ? Number(selectedDetail.dynamic_score).toFixed(2) : '-'} · 形态 {segmentLabel(String((selectedDetail as any)?.segment_id || ''))}
                    </>
                  )
                  : (
                    <>
                      评分 {typeof selectedRow?.dynamic_score === 'number' ? Number(selectedRow.dynamic_score).toFixed(2) : '-'} · 形态 {segmentLabel(String(selectedRow?.segment_id || ''))}
                    </>
                  )}
              </div>
              <div style={{ maxHeight: compactMode ? 320 : 380, overflow: 'auto', display: 'grid', gap: 6 }}>
                {mainView === 'delivery' && (
                  <div style={{ color: c.dim, fontSize: 12 }}>
                    新入池杯柄仅展示当日候选结果，后续推进请在“跟踪观察池”查看。
                  </div>
                )}
              </div>

              <div style={{ marginTop: 10, borderTop: `1px dashed ${c.border}`, paddingTop: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <div style={{ color: c.accent, fontSize: 12, fontWeight: 900 }}>反馈问卷（误判归因）</div>
                  <button
                    onClick={() => void submitFeedback()}
                    disabled={feedbackLoading || !selectedStockCode}
                    style={{
                      border: `1px solid ${c.accent}`,
                      background: feedbackLoading ? 'transparent' : c.accent,
                      color: feedbackLoading ? c.dim : (isLight ? '#fff' : '#050d1a'),
                      borderRadius: 6,
                      padding: '4px 10px',
                      cursor: feedbackLoading ? 'not-allowed' : 'pointer',
                      fontWeight: 900,
                      fontSize: 12,
                      opacity: feedbackLoading ? 0.75 : 1,
                    }}
                  >
                    {feedbackLoading ? '提交中...' : '提交'}
                  </button>
                </div>
                {!!feedbackError && <div style={{ color: c.warn, fontSize: 12, marginBottom: 8 }}>{feedbackError}</div>}
                {!!fbLastSubmitMsg && <div style={{ color: c.good, fontSize: 12, marginBottom: 8 }}>{fbLastSubmitMsg}</div>}

                <div style={{ display: 'grid', gap: 8 }}>
                  <div style={{ border: `1px solid ${c.border}`, borderRadius: 8, padding: '8px 10px' }}>
                    <div style={{ color: c.dim, fontSize: 12, marginBottom: 6 }}>Q1 这只股票应不应该进入强化池？</div>
                    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', color: c.text, fontSize: 12 }}>
                      {[
                        { v: 'should', t: '应该' },
                        { v: 'should_not', t: '不应该' },
                        { v: 'unsure', t: '不确定' },
                      ].map((opt) => (
                        <label key={opt.v} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                          <input type="radio" name="fb_q1" checked={fbQ1 === (opt.v as any)} onChange={() => setFbQ1(opt.v as any)} />
                          <span>{opt.t}</span>
                        </label>
                      ))}
                    </div>
                  </div>

                  <div style={{ border: `1px solid ${c.border}`, borderRadius: 8, padding: '8px 10px' }}>
                    <div style={{ color: c.dim, fontSize: 12, marginBottom: 6 }}>Q2 主要问题是什么？（可多选）</div>
                    <div style={{ display: 'grid', gap: 6, color: c.text, fontSize: 12 }}>
                      {feedbackQ2Options.map((opt) => {
                        const on = fbQ2.includes(opt.id);
                        return (
                          <label key={opt.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                            <input
                              type="checkbox"
                              checked={on}
                              onChange={() => setFbQ2((prev) => (prev.includes(opt.id) ? prev.filter((x) => x !== opt.id) : [...prev, opt.id]))}
                            />
                            <span>{opt.label}</span>
                          </label>
                        );
                      })}
                    </div>
                  </div>

                  <div style={{ border: `1px solid ${c.border}`, borderRadius: 8, padding: '8px 10px' }}>
                    <div style={{ color: c.dim, fontSize: 12, marginBottom: 6 }}>Q3 首要风险类型（单选）</div>
                    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', color: c.text, fontSize: 12 }}>
                      {[
                        { v: 'shape', t: '形态' },
                        { v: 'volume', t: '量价' },
                        { v: 'market', t: '市场状态' },
                        { v: 'sector', t: '板块一致性' },
                        { v: 'risk_reward', t: '风险收益比' },
                      ].map((opt) => (
                        <label key={opt.v} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                          <input type="radio" name="fb_q3" checked={fbQ3 === (opt.v as any)} onChange={() => setFbQ3(opt.v as any)} />
                          <span>{opt.t}</span>
                        </label>
                      ))}
                    </div>
                  </div>

                  <div style={{ border: `1px solid ${c.border}`, borderRadius: 8, padding: '8px 10px' }}>
                    <div style={{ color: c.dim, fontSize: 12, marginBottom: 6 }}>Q4 观察窗口（单选）</div>
                    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', color: c.text, fontSize: 12 }}>
                      {[
                        { v: 't5', t: 'T+5' },
                        { v: 't8', t: 'T+8' },
                        { v: 't13', t: 'T+13' },
                      ].map((opt) => (
                        <label key={opt.v} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                          <input type="radio" name="fb_q4" checked={fbQ4 === (opt.v as any)} onChange={() => setFbQ4(opt.v as any)} />
                          <span>{opt.t}</span>
                        </label>
                      ))}
                    </div>
                  </div>

                  <div style={{ border: `1px solid ${c.border}`, borderRadius: 8, padding: '8px 10px' }}>
                    <div style={{ color: c.dim, fontSize: 12, marginBottom: 6 }}>Q5 短期回撤容忍（单选）</div>
                    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', color: c.text, fontSize: 12 }}>
                      {[
                        { v: 'low', t: '低(<=3%)' },
                        { v: 'mid', t: '中(3%~6%)' },
                        { v: 'high', t: '高(>6%)' },
                      ].map((opt) => (
                        <label key={opt.v} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                          <input type="radio" name="fb_q5" checked={fbQ5 === (opt.v as any)} onChange={() => setFbQ5(opt.v as any)} />
                          <span>{opt.t}</span>
                        </label>
                      ))}
                    </div>
                  </div>

                  <div style={{ border: `1px solid ${c.border}`, borderRadius: 8, padding: '8px 10px' }}>
                    <div style={{ color: c.dim, fontSize: 12, marginBottom: 6 }}>最近反馈</div>
                    {!feedbackItems.length ? (
                      <div style={{ color: c.dim, fontSize: 12 }}>{feedbackLoading ? '加载中...' : '暂无反馈'}</div>
                    ) : (
                      <div style={{ display: 'grid', gap: 6 }}>
                        {feedbackItems.slice(0, 6).map((it) => (
                          <div key={it.id} style={{ border: `1px solid ${c.border}`, borderRadius: 6, padding: '6px 8px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, color: c.text, fontSize: 12, fontWeight: 800 }}>
                              <span>{it.created_at?.slice?.(0, 16) || it.created_at}</span>
                              <span>{fbQ1Label(String(it.q1_should_enter || ''))}</span>
                            </div>
                            <div style={{ color: c.dim, fontSize: 11, lineHeight: 1.5 }}>
                              风险 {fbQ3Label(String(it.q3_primary_risk || ''))} · 窗口 {fbQ4Label(String(it.q4_horizon || ''))} · 回撤 {fbQ5Label(String(it.q5_drawdown_tolerance || ''))}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div style={{ color: c.dim, fontSize: 12 }}>请选择中间主表中的股票</div>
          ),
        })}

        {CollapsibleCard({
          title: '杯柄池（基础→强化）比较',
          open: openCards.process,
          onToggle: () => setOpenCards((p) => ({ ...p, process: !p.process })),
          badge: poolCompareLoading ? '运行中' : (poolCompareView ? '已加载' : '缺失'),
          children: (
            <>
              {!!poolCompareError && (
                <div style={{ marginBottom: 8, color: c.warn, fontSize: 12, fontWeight: 900 }}>
                  {poolCompareError}
                </div>
              )}
              <div style={{ color: c.dim, fontSize: 12, marginBottom: 8 }}>
                操作入口已上移到页面顶部：选择“比较基准日”并点击“运行”。
              </div>
              <div style={{ border: `1px solid ${c.border}`, borderRadius: 8, padding: '8px 10px', marginBottom: 8 }}>
                <div style={{ color: c.accent, fontSize: 12, fontWeight: 800, marginBottom: 4 }}>核心三问</div>
                <div style={{ color: c.text, fontSize: 12, lineHeight: 1.6 }}>
                  1. 今日路由：{stateLabel(poolCompareView?.meta?.market_state || '')} · {ruleToZh(poolCompareView?.meta?.route_desc || '') || '-'}
                </div>
                <div style={{ color: c.text, fontSize: 12, lineHeight: 1.6 }}>
                  2. 数量变化：V4 {num(poolCompareView?.counts?.v4_count)} → 基础 {num(poolCompareView?.counts?.v42_base_count)} → 强化 {num(poolCompareView?.counts?.v42_hardened_count)}
                </div>
                <div style={{ color: c.text, fontSize: 12, lineHeight: 1.6 }}>
                  3. 质量变化：基池 {pct(poolCompareView?.quality?.base_success_rate)} → 强化 {pct(poolCompareView?.quality?.hard_success_rate)} · Δ {poolCompareView?.quality?.delta_success_rate == null ? '-' : `${poolCompareView.quality.delta_success_rate >= 0 ? '+' : ''}${(poolCompareView.quality.delta_success_rate * 100).toFixed(2)}pp`}
                </div>
                <div style={{ color: c.dim, fontSize: 11, lineHeight: 1.6 }}>
                  可验证样本：基池 {num(poolCompareView?.quality?.base_ready_n)} · 强化 {num(poolCompareView?.quality?.hard_ready_n)}
                </div>
              </div>
              <div style={{ color: c.dim, fontSize: 11, lineHeight: 1.6 }}>
                口径：杯宽(天)=右沿-左沿；杯深=(左沿-杯底)/左沿；成交额比(升/跌)=上涨段成交额/下跌段成交额
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8, marginTop: 8 }}>
                <div style={{ border: `1px solid ${c.border}`, borderRadius: 8, padding: '6px 8px' }}>
                  <div style={{ color: c.dim, fontSize: 11 }}>V4</div>
                  <div style={{ color: c.text, fontSize: 16, fontWeight: 900 }}>{num(poolCompareView?.counts?.v4_count)}</div>
                </div>
                <div style={{ border: `1px solid ${c.border}`, borderRadius: 8, padding: '6px 8px' }}>
                  <div style={{ color: c.dim, fontSize: 11 }}>V4.2基础池</div>
                  <div style={{ color: c.text, fontSize: 16, fontWeight: 900 }}>{num(poolCompareView?.counts?.v42_base_count)}</div>
                </div>
                <div style={{ border: `1px solid ${c.border}`, borderRadius: 8, padding: '6px 8px' }}>
                  <div style={{ color: c.dim, fontSize: 11 }}>V4.2强化池</div>
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

        {showSecondary && (
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
                    {ruleToZh(w.entry_desc || '') || entryIdLabelFallback(w.entry_id)} ({w.pick_n})
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
        )}

        {showSecondary && CollapsibleCard({
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
                        {d.date} | V4 {d.v4_count} | 强化 {d.v42_hardened_count}
                      </option>
                    ))}
                  </select>
                )}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 8 }}>
                <div style={{ border: `1px solid ${c.border}`, borderRadius: 8, padding: '6px 8px' }}>
                  <div style={{ color: c.dim, fontSize: 11 }}>强化/V4</div>
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

        {showSecondary && CollapsibleCard({
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

        {showSecondary && CollapsibleCard({
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
      { id: '04', name: '学习层', detail: '回放复盘 基池 vs 强化池 差异，持续迭代', tint: isLight ? 'rgba(245,158,11,0.12)' : 'rgba(245,158,11,0.14)' },
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
            {(poolCompareView?.meta?.candidate_dates?.length || 0) > 0 && (
              <select
                value={poolCompareDate}
                onChange={(e) => setPoolCompareDate(e.target.value)}
                style={{ background: isLight ? '#fff' : '#0f1f33', color: c.text, border: `1px solid ${c.border}`, borderRadius: 6, padding: '2px 8px', fontSize: 12 }}
                title="比较基准日（影响V4基池与V4.2强化池）"
              >
                <option value="">比较基准日：最新V4完成日</option>
                {(poolCompareView?.meta?.candidate_dates || []).slice().reverse().map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            )}
            <button
              onClick={() => void runPoolCompare()}
              style={{ border: `1px solid ${c.accent}`, background: c.accent, color: isLight ? '#fff' : '#050d1a', borderRadius: 6, padding: '4px 10px', cursor: 'pointer', fontWeight: 900, fontSize: 12 }}
            >
              {poolCompareLoading ? '运行中...' : '运行'}
            </button>
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
          <div style={{ color: c.dim, fontSize: 12 }}>当前胜率（强化池）</div>
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
                  <th style={{ textAlign: 'left', padding: 6 }}>簇</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>样本</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>胜率</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>均值评分</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>均值收益</th>
                </tr>
              </thead>
              <tbody>
                {recentDaily.map((r, idx) => (
                  <tr key={`${r.signal_date}-${idx}`} style={{ borderTop: `1px solid ${c.border}` }}>
                    <td style={{ padding: 6, color: c.text }}>{r.signal_date}</td>
                    <td style={{ padding: 6, color: c.dim }}>{stateLabel(r.market_state)}</td>
                    <td style={{ padding: 6, color: c.dim }} title={String(r.cluster_desc || '')}>{ruleToZh(String(r.cluster_desc || '')) || '-'}</td>
                    <td style={{ padding: 6, color: c.text, textAlign: 'right' }}>{r.pick_n}</td>
                    <td style={{ padding: 6, color: c.good, textAlign: 'right' }}>{pct(r.success_rate)}</td>
                    <td style={{ padding: 6, color: c.text, textAlign: 'right', fontWeight: 800 }}>{Number(r.avg_dynamic_score || 0).toFixed(2)}</td>
                    <td style={{ padding: 6, color: r.avg_end_return_t8 >= 0 ? c.good : c.bad, textAlign: 'right' }}>{pct(r.avg_end_return_t8)}</td>
                  </tr>
                ))}
                {!recentDaily.length && (
                  <tr><td style={{ padding: 6, color: c.dim }} colSpan={7}>暂无数据</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
        <section style={{ ...panel, padding: cardPad }}>
          <h3 style={sectionTitle}>基池 vs 强化池 日差异</h3>
          <div style={{ overflow: 'auto', maxHeight: tableMaxHeight }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ background: c.tableHead, color: c.text }}>
                  <th style={{ textAlign: 'left', padding: 6 }}>日期</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>基池</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>强化池</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>Δ胜率</th>
                  <th style={{ textAlign: 'right', padding: 6 }}>新增</th>
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
                      <td style={{ padding: 6, color: c.dim, textAlign: 'right' }}>{r.added_n}</td>
                      <td style={{ padding: 6, color: c.dim, textAlign: 'right' }}>{r.removed_n}</td>
                    </tr>
                  );
                })}
                {!recentDiff.length && (
                  <tr><td style={{ padding: 6, color: c.dim }} colSpan={6}>暂无数据</td></tr>
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
