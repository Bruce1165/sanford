// MonitorV2.tsx – NeoTrade Screener Monitor v2  (Phase 4 – Mockup aligned)
import { useState, useEffect, useCallback } from 'react';

/* ──────────────────────────────────────────
   Interfaces
────────────────────────────────────────── */
interface Pick {
  id: number;
  screener_id: string;
  stock_code: string;
  stock_name: string;
  entry_date: string;
  entry_price: number;
  expected_exit_date: string;
  status: string;
  exit_date: string | null;
  exit_reason: string | null;
  daily_checks: { day?: number; close_price?: number; status?: string }[];
  created_at: string;
  cup_rim_price: number | null;
  cup_bottom_price: number | null;
  max_price_seen: number | null;
  industry?: string | null;
  market_cap?: number | null;
  pe?: number | null;
  pct_change?: number | null;
}

/* ──────────────────────────────────────────
   Tab configuration
   Maps stage values from API → tab keys
────────────────────────────────────────── */
type TabKey = 'newbie' | 'watching' | 'graduated' | 'failed';

const TAB_CONFIG: { key: TabKey; label: string; stages: string[]; color: string }[] = [
  { key: 'newbie',    label: 'ACTIVE',    stages: ['active'],             color: '#3b82f6' },
  { key: 'graduated', label: 'GRADUATED', stages: ['graduated'],         color: '#22c55e' },
  { key: 'failed',    label: 'FAILED',    stages: ['failed', 'expired'], color: '#ef4444' },
];

/* ──────────────────────────────────────────
   Helpers
────────────────────────────────────────── */
function fmtPct(v: number | null | undefined): string {
  if (v == null) return '—';
  const s = v >= 0 ? `+${v.toFixed(1)}` : v.toFixed(1);
  return `${s}%`;
}



function getCurrentPrice(pick: Pick): number | null {
  if (!pick.daily_checks || pick.daily_checks.length === 0) return null;
  return pick.daily_checks[pick.daily_checks.length - 1].close_price ?? null;
}

function getChangePct(pick: Pick): number | null {
  const cur = getCurrentPrice(pick);
  if (cur == null || !pick.entry_price) return null;
  return Math.round((cur - pick.entry_price) / pick.entry_price * 10000) / 100;
}

/* ──────────────────────────────────────────
   Component
────────────────────────────────────────── */
export default function MonitorV2({ selectedScreener: propSelectedScreener }: { selectedScreener?: string }) {
  const [picks, setPicks]             = useState<Pick[]>([]);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState<string | null>(null);
  const [activeTab, setActiveTab]     = useState<TabKey>('newbie');
  const [selectedId, setSelectedId]   = useState<number | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const [localSelectedScreener, setLocalSelectedScreener] = useState<string>('');
  const [screeners, setScreeners]     = useState<{ name: string; display_name: string }[]>([]);

  // Use local state, but sync with prop
  const selectedScreener = localSelectedScreener || propSelectedScreener || '';

  /* ── Fetch picks ── */
  const fetchPicks = useCallback(async (currentScreener?: string) => {
    try {
      const screenerToFetch = currentScreener !== undefined ? currentScreener : selectedScreener;

      // Step 1: get screener list
      const sRes = await fetch('/api/monitor/screeners');
      if (!sRes.ok) throw new Error(`screeners HTTP ${sRes.status}`);
      const sData = await sRes.json();
      const fetchedScreeners: { name: string; display_name: string }[] = sData.screeners || [];
      setScreeners(fetchedScreeners);
      if (fetchedScreeners.length === 0) { setLoading(false); return; }

      // Step 2: aggregate picks from all screeners (or just selected one)
      const allPicks: Pick[] = [];
      const screenersToFetch = screenerToFetch
        ? fetchedScreeners.filter(s => s.name === screenerToFetch)
        : fetchedScreeners;

      for (const s of screenersToFetch) {
        const r = await fetch(`/api/monitor/pipeline?screener_id=${encodeURIComponent(s.name)}`);
        if (!r.ok) continue;
        const d = await r.json();
        allPicks.push(...(d.picks || []));
      }
      setPicks(allPicks);
      setLastUpdated(new Date().toLocaleTimeString('zh-CN'));
    } catch (e) {
      setError(e instanceof Error ? e.message : '获取失败');
    } finally {
      setLoading(false);
    }
  }, [selectedScreener]); // Include selectedScreener in deps

  // Fetch on mount and when screener changes
  useEffect(() => {
    setLoading(true);
    fetchPicks(selectedScreener);
  }, [selectedScreener, fetchPicks]);

  // Auto-refresh every 60 seconds
  useEffect(() => {
    const t = setInterval(() => fetchPicks(selectedScreener), 60_000);
    return () => clearInterval(t);
  }, [selectedScreener, fetchPicks]);

  /* ── Fetch expired picks ── */
  const handleFetchExpired = async () => {
    try {
      const res = await fetch('/api/monitor/expired', { method: 'GET' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await fetchPicks();
    } catch (e) {
      alert(e instanceof Error ? e.message : '操作失败');
    }
  };

  /* ── Grouping ── */
  const grouped = TAB_CONFIG.reduce<Record<TabKey, Pick[]>>((acc, tab) => {
    acc[tab.key] = picks.filter((p) => tab.stages.includes(p.status));
    return acc;
  }, { newbie: [], watching: [], graduated: [], failed: [] } as Record<TabKey, Pick[]>);

  const visiblePicks = grouped[activeTab];
  const selectedPick = visiblePicks.find((p) => p.id === selectedId) ?? null;

  /* ── Colors ── */
  const BG      = '#0a0f1e';
  const PANEL   = '#111827';
  const BORDER  = '#1e2d3d';
  const GOLD    = '#FFCB05';
  const DIM     = '#6b7280';
  const WHITE   = '#e5e7eb';
  const GREEN   = '#22c55e';
  const RED     = '#ef4444';

  /* ── Loading / Error ── */
  if (loading) return (
    <div style={{ color: DIM, padding: 24, background: BG, height: '100%' }}>加载中…</div>
  );
  if (error) return (
    <div style={{ color: RED, padding: 24, background: BG, height: '100%' }}>错误：{error}</div>
  );

  /* ── Render ── */
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: BG, overflow: 'hidden' }}>

      {/* ─── Header ─── */}
      <div style={{
        padding: '0 16px',
        borderBottom: `1px solid ${BORDER}`,
        background: BG,
        flexShrink: 0,
      }}>
        <div style={{
          fontSize: 11,
          color: '#FFCB05',
          letterSpacing: 2,
          fontWeight: 700,
          lineHeight: '40px',
          height: 40,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <span>MONITORING</span>
          <select
            value={selectedScreener}
            onChange={(e) => setLocalSelectedScreener(e.target.value)}
            style={{
              background: '#1e2d3d',
              color: '#e5e7eb',
              border: `1px solid ${BORDER}`,
              borderRadius: 4,
              padding: '4px 8px',
              fontSize: 11,
              outline: 'none',
              cursor: 'pointer',
            }}
          >
            <option value="">全部筛选器</option>
            {screeners.map(s => (
              <option key={s.name} value={s.name}>{s.display_name}</option>
            ))}
          </select>
        </div>

        {/* Tab bar */}
        <div style={{ display: 'flex', gap: 0 }}>
          {TAB_CONFIG.map((tab) => {
            const count = grouped[tab.key].length;
            const active = tab.key === activeTab;
            return (
              <button
                key={tab.key}
                onClick={() => { setActiveTab(tab.key); setSelectedId(null); }}
                style={{
                  flex: 1,
                  padding: '6px 4px',
                  background: 'none',
                  border: 'none',
                  borderBottom: active ? `2px solid ${tab.color}` : '2px solid transparent',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 5,
                  transition: 'all 0.15s ease',
                  outline: 'none',
                  borderRadius: '4px 4px 0 0',
                }}
                onMouseEnter={(e) => {
                  if (!active) {
                    e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!active) {
                    e.currentTarget.style.background = 'transparent';
                  }
                }}
                onMouseDown={(e) => {
                  if (!active) {
                    e.currentTarget.style.transform = 'translateY(1px)';
                  }
                }}
                onMouseUp={(e) => {
                  e.currentTarget.style.transform = 'none';
                }}
              >
                <span style={{
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: 1,
                  color: active ? tab.color : DIM,
                }}>
                  {tab.label}
                </span>
                <span style={{
                  fontSize: 10,
                  fontWeight: 700,
                  color: active ? '#fff' : DIM,
                  background: active ? tab.color : '#1e2d3d',
                  borderRadius: 10,
                  padding: '1px 6px',
                  lineHeight: 1.4,
                }}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ─── Table header ─── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 60px 60px 38px 50px 62px',
        padding: '6px 16px',
        borderBottom: `1px solid ${BORDER}`,
        flexShrink: 0,
      }}>
        {['STOCK', '行业', '市值', 'PE', '今日', 'P&L'].map((h) => (
          <div key={h} style={{ fontSize: 10, color: DIM, fontWeight: 600, letterSpacing: 1,
            textAlign: h === 'STOCK' ? 'left' : 'right' }}>
            {h}
          </div>
        ))}
      </div>

      {/* ─── Table rows ─── */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {visiblePicks.length === 0 ? (
          <div style={{ color: DIM, fontSize: 12, padding: 20, textAlign: 'center' }}>
            暂无数据
          </div>
        ) : (
          visiblePicks.map((pick) => {
            const isSelected = pick.id === selectedId;
            const pnlColor   = (getChangePct(pick) ?? 0) >= 0 ? GREEN : RED;
            const rowColor   = isSelected ? GOLD : WHITE;
            const rowBg      = isSelected ? 'rgba(255,203,5,0.07)' : 'transparent';

            return (
              <div
                key={pick.id}
                onClick={() => setSelectedId(isSelected ? null : pick.id)}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 60px 60px 38px 50px 62px',
                  padding: '8px 16px',
                  borderBottom: `1px solid ${BORDER}`,
                  background: rowBg,
                  cursor: 'pointer',
                  borderLeft: isSelected ? `3px solid ${GOLD}` : '3px solid transparent',
                  transition: 'background 0.12s',
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) e.currentTarget.style.background = 'transparent';
                }}
              >
                {/* Stock */}
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: isSelected ? GOLD : '#60a5fa' }}>
                    {pick.stock_code}
                  </div>
                  <div style={{ fontSize: 11, color: isSelected ? 'rgba(255,203,5,0.7)' : DIM, marginTop: 1 }}>
                    {pick.stock_name}
                  </div>
                </div>
                {/* Entry price + date */}
                <div style={{ textAlign: 'right', fontSize: 12, color: rowColor, paddingTop: 2 }}>
                  {pick.entry_price ? `¥${pick.entry_price.toFixed(2)}` : '—'}
                  <div style={{ fontSize: 10, color: DIM }}>{pick.entry_date?.slice(5)}</div>
                </div>
                {/* 行业 */}
                <div style={{ textAlign: 'right', fontSize: 10, color: 'rgba(255,203,5,0.6)',
                  paddingTop: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {pick.industry && pick.industry !== '-' ? pick.industry.substring(0,6) : '–'}
                </div>
                {/* 市值 */}
                <div style={{ textAlign: 'right', fontSize: 11, color: rowColor, paddingTop: 3 }}>
                  {pick.market_cap != null
                    ? pick.market_cap >= 1e8 ? (pick.market_cap/1e8).toFixed(0)+'亿'
                    : (pick.market_cap/1e4).toFixed(0)+'万'
                    : '–'}
                </div>
                {/* PE */}
                <div style={{ textAlign: 'right', fontSize: 11, color: rowColor, paddingTop: 3 }}>
                  {pick.pe != null ? Number(pick.pe).toFixed(1) : '–'}
                </div>
                {/* 今日涨幅 */}
                <div style={{ textAlign: 'right', fontSize: 11, fontWeight: 600, paddingTop: 3,
                  color: pick.pct_change == null ? DIM
                    : pick.pct_change > 0 ? GREEN
                    : pick.pct_change < 0 ? RED : DIM }}>
                  {pick.pct_change != null
                    ? (pick.pct_change > 0 ? '+' : '') + pick.pct_change.toFixed(2) + '%'
                    : '–'}
                </div>
                {/* P&L */}
                <div style={{ textAlign: 'right', fontSize: 13, fontWeight: 700,
                  color: isSelected ? GOLD : pnlColor, paddingTop: 2 }}>
                  {fmtPct(getChangePct(pick))}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* ─── Inline Detail Panel (selected pick) ─── */}
      {selectedPick && (
        <div style={{
          flexShrink: 0,
          borderTop: `1px solid ${BORDER}`,
          background: PANEL,
          padding: '12px 16px',
          fontSize: 12,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ color: GOLD, fontWeight: 700, fontSize: 13 }}>
              {selectedPick.stock_code} {selectedPick.stock_name}
            </span>
            <button
              onClick={() => setSelectedId(null)}
              style={{
                background: 'none',
                border: 'none',
                color: DIM,
                cursor: 'pointer',
                fontSize: 14,
                padding: '4px 8px',
                borderRadius: '4px',
                transition: 'all 0.15s ease',
                outline: 'none',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(255,255,255,0.05)';
                e.currentTarget.style.color = '#fff';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'none';
                e.currentTarget.style.color = DIM;
              }}
              onMouseDown={(e) => {
                e.currentTarget.style.transform = 'scale(0.95)';
              }}
              onMouseUp={(e) => {
                e.currentTarget.style.transform = 'scale(1)';
              }}
            >✕</button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px 12px' }}>
            {[
              ['入场价',   `¥${selectedPick.entry_price.toFixed(2)}`],
              ['现价',     getCurrentPrice(selectedPick) != null ? `¥${getCurrentPrice(selectedPick)!.toFixed(2)}` : '—'],
              ['涨跌幅',   fmtPct(getChangePct(selectedPick))],
              ['最高价',   selectedPick.max_price_seen != null ? `¥${selectedPick.max_price_seen.toFixed(2)}` : '—'],
              ['杯沿价',   selectedPick.cup_rim_price != null ? `¥${selectedPick.cup_rim_price.toFixed(2)}` : '—'],
              ['入场日期', selectedPick.entry_date],
              ['预计退出', selectedPick.expected_exit_date],
              ['跟踪天数', String(selectedPick.daily_checks.length)],
              ['筛选器',   selectedPick.screener_id],
            ].map(([k, v]) => (
              <div key={k}>
                <div style={{ color: DIM, fontSize: 10, marginBottom: 2 }}>{k}</div>
                <div style={{ color: WHITE, fontWeight: 600 }}>{v}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ─── Footer: Fetch Expired banner ─── */}
      <div style={{ flexShrink: 0, padding: '8px 12px', borderTop: `1px solid ${BORDER}` }}>
        <button
          onClick={handleFetchExpired}
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '8px 12px',
            background: '#1a1f2e',
            border: `1px solid ${BORDER}`,
            borderRadius: 6,
            cursor: 'pointer',
            color: '#f59e0b',
            fontSize: 12,
            fontWeight: 600,
            transition: 'all 0.15s ease',
            outline: 'none',
            position: 'relative',
            overflow: 'hidden',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = '#f59e0b';
            e.currentTarget.style.background = 'rgba(245,158,11,0.1)';
            e.currentTarget.style.transform = 'translateY(-1px)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = BORDER;
            e.currentTarget.style.background = '#1a1f2e';
            e.currentTarget.style.transform = 'none';
          }}
          onMouseDown={(e) => {
            e.currentTarget.style.transform = 'translateY(0)';
          }}
          onMouseUp={(e) => {
            e.currentTarget.style.transform = 'translateY(-1px)';
          }}
        >
          <span style={{ fontSize: 16 }}>📦</span>
          <span>Fetch Expired (Last 30 TD)</span>
          <span style={{ marginLeft: 'auto', color: DIM, fontSize: 10 }}>
            更新：{lastUpdated}
          </span>
        </button>
      </div>
    </div>
  );
}
