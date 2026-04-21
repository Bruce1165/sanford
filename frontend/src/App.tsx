import { useState, useEffect, useRef } from 'react';
import './App.css';
import './cockpit.css';
import * as echarts from 'echarts';
import { createChart, CandlestickSeries, HistogramSeries, LineSeries, ColorType, CrosshairMode } from 'lightweight-charts';
import { formatDate, formatStockCode, isValidDate, isValidStockCode, toISODate } from './utils/format';
import FiveFlagsMonitor from './pages/FiveFlagsMonitor';
import { CalendarWithButton } from './components/Calendar';
import { ScreenerConfig } from './components/ScreenerConfig';

// Backend API configuration
// Use proxy in development, auto-detect in production
const isDev = (import.meta as any).env?.DEV === 'true';
const API_BASE = isDev ? '/api' : `${window.location.origin}/api`;

// Get today's date in YYYY-MM-DD format
const getTodayString = () => {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

interface Screener {
  id: number;
  name: string;
  display_name: string;
  description: string;
  category: string;
}

interface CheckResult {
  match: boolean;
  code: string;
  name: string;
  date: string;
  details: Record<string, any>;
  reasons: string[];
}

function App() {
  const [screeners, setScreeners] = useState<Screener[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentTime, setCurrentTime] = useState(() => new Date().toLocaleTimeString('zh-CN'));
  const [selectedScreener, setSelectedScreener] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('screener') || '';
  });

  // 实时时钟
  useEffect(() => {
    const clockTimer = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString('zh-CN'));
    }, 1000);
    return () => clearInterval(clockTimer);
  }, []);

  // 读取 URL 参数初始化 activeTab
  const getInitialTab = () => {
    const params = new URLSearchParams(window.location.search);
    const tab = params.get('tab');
    return tab || 'screeners';
  };

  const [activeTab, setActiveTab] = useState(getInitialTab());

  // Update URL when tab changes
  const handleTabChange = (tabId: string) => {
    setActiveTab(tabId);
    const url = new URL(window.location.href);
    url.searchParams.set('tab', tabId);
    window.history.replaceState({}, '', url.toString());
  };

  useEffect(() => {
    fetch(`${API_BASE}/screeners`)
      .then(r => r.json())
      .then(data => { setScreeners(data.screeners || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);



  // Data health status for top strip
  const [dhStatus, setDhStatus] = useState<{status:string, time:string, stocks:number}>({status:'unknown', time:'–', stocks:0});
  const [showHealth, setShowHealth] = useState(false);
  useEffect(() => {
    fetch(`${API_BASE}/data-health`)
      .then(r => r.json())
      .then(d => {
        const ts = d?.db_health?.timestamp;
        const time = ts ? (() => {
          const dt = new Date(String(ts).replace(' ','T'));
          return isNaN(dt.getTime()) ? String(ts).slice(11,16) : dt.toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'});
        })() : '–';
        setDhStatus({
          status: d?.db_health?.status ?? 'unknown',
          time,
          stocks: d?.db_health?.checks?.stock_pool?.active_stocks ?? 0,
        });
      }).catch(() => {});
  }, []);

  const dhColor = dhStatus.status === 'healthy' ? '#00e676'
    : dhStatus.status === 'warning' ? '#ff9f43'
    : dhStatus.status === 'critical' ? '#ff4757' : '#555';

  return (
    <div className="neo-app">

      {/* ── Top Bar ── */}
      <header className="neo-topbar">
        <div className="neo-topbar-left">
          <div className="market-ticker">
            <span className="index">上证指数 <span className="up">+0.85%</span></span>
            <span className="index">深证成指 <span className="up">+1.12%</span></span>
            <span className="index">创业板指 <span className="down">-0.23%</span></span>
            <span className="time">{currentTime}</span>
          </div>
        </div>
        <div className="neo-topbar-center">
          <h1 className="logo">NEO TERMINAL</h1>
        </div>
        <div className="neo-topbar-right">
          <div
            onClick={() => setShowHealth(v => !v)}
            className="neo-live-btn"
            style={{
              background: showHealth ? 'rgba(255,203,5,0.15)' : 'rgba(255,255,255,0.07)',
              border: `1px solid ${showHealth ? 'rgba(255,203,5,0.6)' : 'rgba(255,255,255,0.22)'}`,
              transition: 'all 0.15s ease',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => {
              if (!showHealth) {
                e.currentTarget.style.borderColor = 'rgba(255,255,255,0.35)';
                e.currentTarget.style.background = 'rgba(255,255,255,0.12)';
              }
            }}
            onMouseLeave={(e) => {
              if (!showHealth) {
                e.currentTarget.style.borderColor = 'rgba(255,255,255,0.22)';
                e.currentTarget.style.background = 'rgba(255,255,255,0.07)';
              }
            }}
            onMouseDown={(e) => {
              e.currentTarget.style.transform = 'scale(0.98)';
            }}
            onMouseUp={(e) => {
              e.currentTarget.style.transform = 'scale(1)';
            }}
          >
            <span style={{
              width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
              background: dhColor, boxShadow: `0 0 8px ${dhColor}`,
              animation: 'neo-pulse 2s ease-in-out infinite',
              display: 'inline-block',
            }} />
            <span style={{
              color: dhStatus.status === 'warning' ? '#ff9f43'
                   : dhStatus.status === 'healthy'  ? '#00e676'
                   : '#c8c8c8',
              fontWeight: 700, fontSize: 11, letterSpacing: '0.12em',
            }}>
              {dhStatus.status === 'warning' ? 'WARNING'
               : dhStatus.status === 'healthy' ? 'LIVE'
               : 'LIVE'}
            </span>
            <span style={{color: 'rgba(255,255,255,0.5)', fontSize: 11}}>
              {dhStatus.time}
            </span>
            {dhStatus.stocks > 0 && (
              <span style={{color: 'rgba(255,255,255,0.35)', fontSize: 11}}>
                · {dhStatus.stocks.toLocaleString()} stocks
              </span>
            )}
            <span style={{color: '#FFCB05', fontSize: 10, fontWeight: 700}}>
              {showHealth ? '▲' : '▼'}
            </span>
          </div>
        </div>
      </header>

      {/* ── Data Health Drawer ── */}
      {showHealth && (
        <div
          style={{
            position: 'fixed',
            top: 40,
            right: 0,
            width: 750,
            maxHeight: 'calc(100vh - 40px)',
            overflowY: 'auto',
            background: '#0a1628',
            border: '1px solid rgba(255,203,5,0.2)',
            borderTop: 'none',
            borderRadius: '0 0 0 12px',
            boxShadow: '0 20px 60px rgba(0,0,0,0.7)',
            zIndex: 2000,
            padding: '16px',
          }}
          onClick={e => e.stopPropagation()}
        >
          <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12}}>
            <span style={{color:'#FFCB05', fontWeight:700, fontSize:11, letterSpacing:'0.15em'}}>DATA HEALTH</span>
            <button
              onClick={() => setShowHealth(false)}
              style={{background:'rgba(255,203,5,0.1)', border:'1px solid rgba(255,203,5,0.3)',
                color:'#FFCB05', borderRadius:'50%', width:22, height:22, cursor:'pointer',
                fontSize:13, display:'flex', alignItems:'center', justifyContent:'center'}}
            >×</button>
          </div>
          <DataHealthInline />
        </div>
      )}

      {/* ── Three-Column Layout ── */}
      <div className="neo-workspace" onClick={() => setShowHealth(false)}>

        {/* LEFT — Screeners (22%) */}
        <aside className="neo-col-left">
          <ScreenersView screeners={screeners} loading={loading} />
        </aside>

        {/* MIDDLE — Results + Detail (38%) */}
        <section className="neo-col-mid">
          <ResultsView screeners={screeners} selectedScreener={selectedScreener} setSelectedScreener={setSelectedScreener} />
        </section>

        {/* RIGHT — Monitoring (40%) */}
          <section className="neo-col-right">
            <FiveFlagsMonitor />
          </section>

      </div>

      {/* ── Mobile Tab Bar (< 640px) ── */}
      <nav className="neo-mobile-tabs">
        {[
          { id:'screeners', icon:'🔍', label:'Screeners' },
          { id:'results',   icon:'📈', label:'Results'  },
          { id:'monitor',   icon:'👁️', label:'Monitor'  },
          { id:'strategy',  icon:'🧬', label:'Strategy' },
        ].map(item => (
          <div key={item.id}
            className={`neo-mobile-tab ${activeTab === item.id ? 'active' : ''}`}
            onClick={() => handleTabChange(item.id)}>
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </div>
        ))}
      </nav>

    </div>
  );
}

// Dashboard
// @ts-ignore — reserved for future use
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function DashboardView({ screenerCount }: { screenerCount: number }) {
  const [stats, setStats] = useState({ oneil: 5, lastUpdate: 'Loading...' });
  const [accessStats, setAccessStats] = useState<{today: {date: string, unique_visitors: number}, this_month: {start_date: string, end_date: string, unique_visitors: number}} | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/health`).then(r => r.json()).then(d => {
      if (d.data_date) setStats(s => ({ ...s, lastUpdate: d.data_date }));
    }).catch(() => setStats(s => ({ ...s, lastUpdate: 'N/A' })));
    
    // Fetch access statistics
    fetch(`${API_BASE}/stats/access`)
      .then(r => r.json())
      .then(d => {
        if (d.success && d.data) {
          setAccessStats(d.data);
        }
      })
      .catch(() => {});
  }, []);

  const metrics = [
    { label: 'SCREENERS', value: screenerCount, accent: true },
    { label: "O'NEIL", value: stats.oneil, accent: false },
    { label: 'DATA DATE', value: stats.lastUpdate, accent: false },
    ...(accessStats ? [
      { label: 'TODAY', value: accessStats.today.unique_visitors, accent: false },
      { label: 'THIS MONTH', value: accessStats.this_month.unique_visitors, accent: false },
    ] : []),
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

      {/* ── Command Bar ── */}
      <div style={{
        display: 'flex', alignItems: 'center',
        background: '#0a0e1a',
        border: '1px solid #1e2d45',
        borderRadius: 8,
        padding: '0 20px',
        height: 52,
        gap: 0,
      }}>
        {/* Logo */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          paddingRight: 24,
          borderRight: '1px solid #1e2d45',
          marginRight: 24,
          flexShrink: 0,
        }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: '#FFCB05',
            boxShadow: '0 0 6px #FFCB05',
          }} />
          <span style={{
            color: '#FFCB05', fontWeight: 700, fontSize: 14,
            letterSpacing: '0.15em', fontFamily: 'monospace',
          }}>NEO TERMINAL</span>
        </div>

        {/* Metrics */}
        <div style={{ display: 'flex', gap: 0, flex: 1 }}>
          {metrics.map(({ label, value, accent }, i) => (
            <div key={label} style={{
              display: 'flex', flexDirection: 'column', justifyContent: 'center',
              paddingLeft: i === 0 ? 0 : 20,
              paddingRight: 20,
              borderRight: '1px solid #1e2d45',
            }}>
              <div style={{
                color: accent ? '#FFCB05' : '#e2e8f0',
                fontWeight: 700,
                fontSize: typeof value === 'number' ? 18 : 14,
                lineHeight: 1.1,
                fontFamily: 'monospace',
              }}>{value}</div>
              <div style={{
                color: '#4a6080',
                fontSize: 11,
                letterSpacing: '0.12em',
                marginTop: 2,
                fontFamily: 'monospace',
              }}>{label}</div>
            </div>
          ))}
        </div>

        {/* Visitor dot + build */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
          {accessStats && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{
                width: 6, height: 6, borderRadius: '50%',
                background: '#22c55e',
                boxShadow: '0 0 4px #22c55e',
              }} />
              <span style={{ color: '#22c55e', fontSize: 13, fontFamily: 'monospace' }}>
                {accessStats.today.unique_visitors} online today
              </span>
            </div>
          )}
          <span style={{
            color: '#2a3f5a', fontSize: 12,
            fontFamily: 'monospace', letterSpacing: '0.08em',
          }}>
            v1.0
          </span>
        </div>
      </div>

      {/* Data Health */}
      <DataHealthInline />
    </div>
  );
}

// ── Screeners Left Panel — Mockup strict ──
function ScreenersView({ screeners, loading }: { screeners: Screener[], loading: boolean }) {
  const [activeCategory, setActiveCategory] = useState<string>('内部公式');
  const [showRetired, setShowRetired] = useState(false);
  const [runModal, setRunModal] = useState<{open: boolean, screener: Screener | null}>({ open: false, screener: null });

  // ── CONFIG MANAGEMENT state ──
  const [configMode, setConfigMode] = useState<{open: boolean, screener: Screener | null}>({ open: false, screener: null });

  // Debug: Watch configMode changes
  useEffect(() => {
    // configMode changed - can add logging here if needed
  }, [configMode]);


  // ── CHECK STOCK inline state ──
  const [checkCode, setCheckCode] = useState('');
  const [checkScreener, setCheckScreener] = useState<string>('');
  const [checkDate, setCheckDate] = useState<string>(getTodayString());
  const [showCheckCalendar, setShowCheckCalendar] = useState(false);
  const [checkLoading, setCheckLoading] = useState(false);
  const [checkResult, setCheckResult] = useState<CheckResult | null>(null);
  const [checkError, setCheckError] = useState('');

  // set default screener for check
  useEffect(() => {
    if (screeners.length > 0 && !checkScreener) {
      setCheckScreener(screeners[0].name);
    }
  }, [screeners]);

  // reset check states when screener changes
  useEffect(() => {
    setCheckResult(null);
    setCheckError('');
    setCheckLoading(false);
  }, [checkScreener]);

  const categories = ['内部公式', '经典公式', '其它'];

  // 筛选器分类映射
  const getScreenerCategory = (name: string): string => {
    const internalFormulas = [
      'coffee_cup_v4',
      'daily_hot_cold',
      'yin_feng_huang_screener',
      'jin_feng_huang_screener',
      // 'lao_ya_tou_zhou_xian_screener', // DISABLED
      'er_ban_hui_tiao',
      'shi_pan_xian',
      'zhang_ting_bei_liang_yin',
    ];
    const classicFormulas = [
      'ascending_triangle',
      'ashare_21',
      'breakout_20day',
      'breakout_main',
      'double_bottom',
      'flat_base',
      'high_tight_flag',
    ];

    if (internalFormulas.includes(name)) return '内部公式';
    if (classicFormulas.includes(name)) return '经典公式';
    return '经典公式';
  };

  const filtered = screeners.filter(s => {
    if (activeCategory === '内部公式') {
      return getScreenerCategory(s.name) === '内部公式';
    }
    if (activeCategory === '经典公式') {
      return getScreenerCategory(s.name) === '经典公式';
    }
    return true;
  });

  const handleCheck = async () => {
    if (!checkCode.trim() || !checkScreener) return;
    const formattedCode = formatStockCode(checkCode.trim());
    if (!isValidStockCode(formattedCode)) {
      setCheckError('请输入6位股票代码');
      return;
    }
    setCheckLoading(true);
    setCheckError('');
    setCheckResult(null);
    try {
      const res = await fetch(`${API_BASE}/check-stock`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ screener: checkScreener, code: formattedCode, date: checkDate })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setCheckResult(data);
    } catch (e: any) {
      setCheckError(e.message || '查询失败');
    }
    setCheckLoading(false);
  };

  return (
    <div className="sl-wrap">

      {/* ── Header ── */}
      <div className="sl-header">
        <span className="sl-title">SCREENERS</span>
        <span className="sl-badge">{screeners.length}</span>
      </div>

      {/* ── Category Tabs ── */}
      <div className="sl-tabs">
        {categories.map(c => (
          <button key={c}
            className={`sl-tab ${activeCategory === c ? 'active' : ''}`}
            onClick={() => setActiveCategory(c)}>
            {c}
          </button>
        ))}
      </div>

      {/* ── CHECK STOCK inline ── */}
      <div className="sl-check-section">
        <div className="sl-check-label">
          <span>🔍</span>
          <span>CHECK STOCK</span>
        </div>
        <div className="sl-check-row sl-check-row-with-calendar">
          <input
            className="sl-check-input sl-check-input-with-calendar"
            type="text"
            placeholder="Enter code (e.g. 000001)"
            value={checkCode}
            onChange={e => setCheckCode(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleCheck()}
            autoComplete="off" autoCorrect="off" autoCapitalize="off" spellCheck={false}
          />
          <CalendarWithButton
            value={checkDate}
            onChange={setCheckDate}
            showPicker={showCheckCalendar}
            onTogglePicker={() => setShowCheckCalendar(!showCheckCalendar)}
            onSelectDate={setCheckDate}
          />
        </div>
        <div className="sl-check-row">
          <select
            className="sl-check-select"
            value={checkScreener}
            onChange={e => setCheckScreener(e.target.value)}>
            {screeners.map(s => (
              <option key={s.id} value={s.name}>{s.display_name || s.name}</option>
            ))}
          </select>
          <button className="sl-check-btn" onClick={handleCheck} disabled={checkLoading}>
            {checkLoading ? '...' : 'CHECK'}
          </button>
        </div>

        {/* Check result card */}
        {checkError && (
          <div className="sl-check-error">{checkError}</div>
        )}
        {checkResult && (
          <div className="sl-check-result">
            <div className="sl-check-result-header">
              <span className="sl-check-stock-name">
                {checkResult.code} {checkResult.name}
              </span>
              <span className={`sl-check-badge ${checkResult.match ? 'pass' : 'fail'}`}>
                {checkResult.match ? '✓ PASS' : '✗ FAIL'}
              </span>
            </div>
            <div className="sl-check-rules">
              {checkResult.match
                ? Object.entries(checkResult.details || {}).slice(0, 4).map(([k, v], i) => (
                    <div key={i} className="sl-check-rule">
                      <span className="sl-rule-pass">✓</span>
                      <span>{k}: {String(v)}</span>
                    </div>
                  ))
                : (checkResult.reasons || []).slice(0, 4).map((r, i) => (
                    <div key={i} className="sl-check-rule">
                      <span className="sl-rule-fail">✗</span>
                      <span>{r}</span>
                    </div>
                  ))
              }
            </div>
            <div className="sl-check-footer">Ad-hoc check · Not saved</div>
          </div>
        )}
      </div>

      {/* ── Screener List ── */}
      <div className="sl-list">
        {loading && <div className="sl-loading">Loading...</div>}
        {!loading && filtered.map(s => (
          <div key={s.id} className="sl-card">
            <div className="sl-card-left">
              <div className="sl-card-name">{s.display_name || s.name}</div>
              <div className="sl-card-desc">
                {(s.description || 'Technical analysis screener').substring(0, 48)}...
              </div>
            </div>
            <div className="sl-card-right">
              <button
                className="sl-config-btn"
                onClick={() => {
                  setConfigMode({ open: true, screener: s });
                }}
                title="配置参数"
              >
                ⚙️
              </button>
              <button className="sl-run-btn" onClick={() => setRunModal({ open: true, screener: s })}>
                ▶ RUN
              </button>
            </div>
          </div>
        ))}
        {!loading && filtered.length === 0 && (
          <div className="sl-empty">No screeners in this category</div>
        )}
      </div>

      {/* ── Bottom Actions ── */}
      <div className="sl-footer">
        <button className="sl-footer-btn">＋ New Screener</button>
        <button className="sl-footer-btn" onClick={() => setShowRetired(!showRetired)}>
          ≡ {showRetired ? 'Hide Retired' : 'Retired'}
        </button>
      </div>

      {/* ── Run Modal ── */}
      {runModal.open && runModal.screener && (
        <RunScreenerModal
          screener={runModal.screener}
          onClose={() => setRunModal({ open: false, screener: null })}
        />
      )}

      {/* ── Config Modal ── */}
      {/* Simple Modal Implementation (replacing Ant Design Modal) */}
      {configMode.open && configMode.screener && (
        <div className="config-modal-overlay">
          <div className="config-modal-container">
            <div className="config-modal-header">
              <h3>
                {configMode.screener.display_name || configMode.screener.name} - 参数配置
              </h3>
              <button
                onClick={() => setConfigMode({ open: false, screener: null })}
                className="config-modal-close"
              >
                ×
              </button>
            </div>
            <div className="config-modal-body">
              <ScreenerConfig
                key={configMode.screener.name}
                screenerName={configMode.screener.name}
                onClose={() => setConfigMode({ open: false, screener: null })}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Check Stock Modal - REAL FUNCTIONALITY

// Run Screener Modal - REAL FUNCTIONALITY
function RunScreenerModal({ screener, onClose }: { screener: Screener, onClose: () => void }) {
  // Initialize with today's date
  const [date, setDate] = useState(getTodayString());
  const [showCalendar, setShowCalendar] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [stocks, setStocks] = useState<any[]>([]);
  const [error, setError] = useState('');

  const handleRun = async () => {
    setLoading(true);
    setError('');
    setResult(null);

    try {
      // Final validation and formatting
      const formattedDate = toISODate(date);

      if (!isValidDate(formattedDate)) {
        setError('日期格式无效，请使用 YYYY-MM-DD 格式 (例如: 2026-03-20)');
        setLoading(false);
        return;
      }

      
      const body = JSON.stringify({ date: formattedDate });
      
      const res = await fetch(`${API_BASE}/screeners/${screener.name}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body
      });
      
      
      // Debug: log the raw response
      let data;
      try {
        data = await res.json();
      } catch (parseErr: any) {
        setError('响应解析失败，请重试');
        setLoading(false);
        return;
      }
      
      
      if (data.error) throw new Error(data.message || data.error);
      setResult(data);

      // Fetch results for download
      if (data.status === 'success' && data.run_id && data.run_id.success) {
        try {
          const resultsUrl = `${API_BASE}/results?screener=${encodeURIComponent(screener.name)}&date=${encodeURIComponent(formattedDate)}`;
          const resultsRes = await fetch(resultsUrl);
          
          if (!resultsRes.ok) {
            setError(`获取结果失败: HTTP ${resultsRes.status}`);
            setLoading(false);
            return;
          }
          
          let resultsData;
          try {
            resultsData = await resultsRes.json();
          } catch (parseErr: any) {
            setError('结果解析失败，请重试');
            setLoading(false);
            return;
          }

          // Handle daily_hot_cold_screener which returns {hot: [], cold: []}
          if (screener.name === 'daily_hot_cold_screener' && (resultsData.hot !== undefined || resultsData.cold !== undefined)) {
            // Combine hot and cold with type marker
            const hotStocks = (resultsData.hot || []).map((s: any) => ({ ...s, _type: 'hot', _category: '热股' }));
            const coldStocks = (resultsData.cold || []).map((s: any) => ({ ...s, _type: 'cold', _category: '冷股' }));
            setStocks([...hotStocks, ...coldStocks]);
          } else {
            setStocks(resultsData.results || []);
          }
        } catch (fetchErr: any) {
          setError(`Error fetching results: ${fetchErr.message}`);
        }
      }
    } catch (e: any) {
      setError(e.message || 'Failed to run screener');
    }
    setLoading(false);
  };

  // Download handlers for screener results
  const downloadCSV = () => {
    if (stocks.length === 0) return;

    // Get all columns
    const flatRow = flattenObject(stocks[0]);
    let columns = Object.keys(flatRow).filter(col =>
      !['id', 'run_id', 'created_at', 'updated_at', 'is_deleted'].includes(col)
    );

    // Priority columns first
    const priorityCols = ['stock_code', 'stock_name', 'code', 'name'];
    columns = [
      ...priorityCols.filter(c => columns.includes(c)),
      ...columns.filter(c => !priorityCols.includes(c))
    ];

    // Header translations
    const headerMap: Record<string, string> = {
      'stock_code': '代码', 'code': '代码',
      'stock_name': '名称', 'name': '名称',
      'close_price': '收盘价', 'close': '收盘价',
      'pct_change': '涨幅%', 'change': '涨幅%',
      'turnover': '换手率%',
      'volume': '成交量',
      'amount': '成交额',
      'industry': '行业',
      'category': '类别',
      'type': '类型',
      'board': '板块',
      'reason': '原因',
      'signal': '信号',
      'status': '状态',
      'score': '评分',
      'rank': '排名',
      'note': '备注',
      'total_market_cap': '总市值',
      'circulating_market_cap': '流通市值', 'circulating_cap': '流通市值',
      'pe_ratio': '市盈率', 'pe': '市盈率',
      'pb_ratio': '市净率', 'pb': '市净率',
      'listing_date': '上市日期'
    };

    const headers = columns.map(col => headerMap[col] || col).join(',');
    const rows = stocks.map(row => {
      const flatData = flattenObject(row);
      return columns.map(col => {
        const val = flatData[col];
        if (val === null || val === undefined) return '';
        const str = String(val);
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      }).join(',');
    });

    const csvContent = '\uFEFF' + [headers, ...rows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${screener.name}_${date}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const downloadExcel = () => {
    if (stocks.length === 0) return;

    const flatRow = flattenObject(stocks[0]);
    let columns = Object.keys(flatRow).filter(col =>
      !['id', 'run_id', 'created_at', 'updated_at', 'is_deleted'].includes(col)
    );

    const priorityCols = ['stock_code', 'stock_name', 'code', 'name'];
    columns = [
      ...priorityCols.filter(c => columns.includes(c)),
      ...columns.filter(c => !priorityCols.includes(c))
    ];

    const headerMap: Record<string, string> = {
      'stock_code': '代码', 'code': '代码',
      'stock_name': '名称', 'name': '名称',
      'close_price': '收盘价', 'close': '收盘价',
      'pct_change': '涨幅%', 'change': '涨幅%',
      'turnover': '换手率%',
      'volume': '成交量',
      'amount': '成交额',
      'industry': '行业',
      'category': '类别',
      'type': '类型',
      'board': '板块',
      'reason': '原因',
      'signal': '信号',
      'status': '状态',
      'score': '评分',
      'rank': '排名',
      'note': '备注',
      'total_market_cap': '总市值',
      'circulating_market_cap': '流通市值', 'circulating_cap': '流通市值',
      'pe_ratio': '市盈率', 'pe': '市盈率',
      'pb_ratio': '市净率', 'pb': '市净率',
      'listing_date': '上市日期'
    };

    let html = '<table border="1">';
    html += '<tr>' + columns.map(col => `<th>${headerMap[col] || col}</th>`).join('') + '</tr>';
    stocks.forEach(row => {
      const flatData = flattenObject(row);
      html += '<tr>' + columns.map(col => {
        const val = flatData[col];
        if (val === null || val === undefined) return '<td></td>';
        return `<td>${val}</td>`;
      }).join('') + '</tr>';
    });
    html += '</table>';

    const blob = new Blob([`
      <html xmlns:o="urn:schemas-microsoft-com:office:office"
            xmlns:x="urn:schemas-microsoft-com:office:excel"
            xmlns="http://www.w3.org/TR/REC-html40">
        <head><meta charset="UTF-8"></head>
        <body>${html}</body>
      </html>
    `], { type: 'application/vnd.ms-excel;charset=utf-8' });

    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${screener.name}_${date}.xlsx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>▶ Run Screener</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          <div className="form-row">
            <label>Screener: <strong>{screener.display_name}</strong></label>
            <CalendarWithButton
              value={date}
              onChange={setDate}
              maxDate={new Date().toISOString().split('T')[0]}
              showPicker={showCalendar}
              onTogglePicker={() => setShowCalendar(!showCalendar)}
              onSelectDate={(d) => { setDate(d); setShowCalendar(false); }}
            />
            <button className="btn-primary" onClick={handleRun} disabled={loading}>
              {loading ? 'Running...' : 'Run'}
            </button>
          </div>
          {error && <div className="error-message">{error}</div>}
          {result && (
            <div className={`result-box ${result.run_id?.success ? 'success' : 'fail'}`}>
              <div className="result-header">
                <span className="result-icon">{result.run_id?.success ? '✅' : '❌'}</span>
                <span className="result-text">{result.run_id?.success ? 'SUCCESS' : 'FAILED'}</span>
              </div>
              <div className="result-details">
                <div><strong>Run ID:</strong> {result.run_id?.run_id}</div>
                <div><strong>Stocks Found:</strong> {result.run_id?.stocks_found || 0}</div>
                <div><strong>Message:</strong> {result.run_id?.message || ''}</div>
              </div>
              {result.run_id?.success && (
                <div className="download-actions" style={{
                  marginTop: '16px',
                  paddingTop: '12px',
                  borderTop: '1px solid rgba(255,203,5,0.2)',
                  background: 'rgba(255,203,5,0.05)',
                  padding: '12px',
                  borderRadius: '6px'
                }}>
                  <div style={{ fontSize: '12px', color: 'rgba(255,255,255,0.5)', marginBottom: '10px', letterSpacing: '0.08em' }}>
                    LOADED {stocks.length} STOCKS FOR DOWNLOAD
                  </div>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                    <button 
                      className="btn-csv-primary" 
                      onClick={() => {
                        downloadCSV();
                      }}
                      disabled={stocks.length === 0}
                      title={stocks.length === 0 ? 'No data to download' : 'Download CSV'}
                    >
                      📄 Download CSV {stocks.length > 0 && `(${stocks.length})`}
                    </button>
                    <button 
                      className="btn-excel-secondary" 
                      onClick={() => {
                        downloadExcel();
                      }}
                      disabled={stocks.length === 0}
                      title={stocks.length === 0 ? 'No data to download' : 'Download Excel'}
                    >
                      📊 Excel {stocks.length > 0 && `(${stocks.length})`}
                    </button>
                    <button
                      className="btn-view-results"
                      onClick={() => {
                        window.location.href = `?tab=results&screener=${screener.name}&date=${formatDate(date)}`;
                      }}
                      style={{ backgroundColor: '#3b82f6', color: 'white', padding: '10px 20px', border: 'none', borderRadius: '6px', cursor: 'pointer' }}
                    >
                      👁️ View Results
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


// Helper function to flatten nested objects
function flattenObject(obj: any, prefix = ''): any {
  let result: any = {};
  for (const key in obj) {
    if (obj.hasOwnProperty(key)) {
      const newKey = prefix ? `${prefix}.${key}` : key;
      if (obj[key] !== null && typeof obj[key] === 'object' && !Array.isArray(obj[key])) {
        Object.assign(result, flattenObject(obj[key], newKey));
      } else {
        result[newKey] = obj[key];
      }
    }
  }
  return result;
}




// ── Inline Stock Detail Panel ──
function StockDetailPanel({
  stock, rowData, onClose
}: {
  stock: { code: string; name: string };
  rowData: any;
  onClose: () => void;
}) {
  const chartRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<any>(null);
  const [chartDays, setChartDays] = useState<number | 'ytd'>(20);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState('');

  const flat = flattenObject(rowData || {});
  const pe  = flat['extra_data.pe'] ?? flat['pe_ratio'] ?? flat['pe'] ?? flat['PE'] ?? '–';
  const pb  = flat['extra_data.pb'] ?? flat['pb_ratio'] ?? flat['pb'] ?? flat['PB'] ?? '–';
  const cap = flat['extra_data.market_cap'] ?? flat['total_market_cap'] ?? flat['circulating_market_cap'] ?? flat['circulating_cap'] ?? '–';
  const ind = flat['extra_data.industry'] ?? flat['industry'] ?? flat['行业'] ?? '–';

  const fmtCap = (v: any) => {
    if (v === '–' || v == null) return '–';
    const n = Number(v);
    if (isNaN(n)) return String(v);
    if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿';
    if (n >= 1e4) return (n / 1e4).toFixed(2) + '万';
    return n.toLocaleString();
  };

  const fmtNum = (v: any, dec = 2) => {
    if (v === '–' || v == null) return '–';
    const n = Number(v);
    return isNaN(n) ? String(v) : n.toFixed(dec);
  };

  const getDays = (): number => {
    if (chartDays === 'ytd') {
      const now = new Date();
      const jan1 = new Date(now.getFullYear(), 0, 1);
      return Math.ceil((now.getTime() - jan1.getTime()) / 86400000) + 10;
    }
    return chartDays as number;
  };

  useEffect(() => {
    if (!chartRef.current) return;
    setChartLoading(true);
    setChartError('');
    const days = getDays();
    fetch(`${API_BASE}/stock/${stock.code}/chart?days=${days}`)
      .then(r => r.json())
      .then(data => {
        if (data.error) throw new Error(data.error);
        if (!data.data || data.data.length === 0) throw new Error('无K线数据');
        renderSparkline(data.data);
      })
      .catch(e => { setChartError(e.message); setChartLoading(false); });

    return () => {
      if (chartInstance.current) {
        if ((chartInstance.current as any)._ro) (chartInstance.current as any)._ro.disconnect();
        chartInstance.current.remove();
        chartInstance.current = null;
      }
    };
  }, [stock.code, chartDays]);

  const renderSparkline = (data: any[]) => {
    if (!chartRef.current) return;
    if (chartInstance.current) {
      chartInstance.current.remove();
      chartInstance.current = null;
    }

    const chart = createChart(chartRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: 'rgba(255,255,255,0.45)',
        fontSize: 11,
        fontFamily: "'SF Mono', 'Courier New', monospace",
      },
      grid: {
        vertLines: { color: 'rgba(255,255,255,0.04)' },
        horzLines: { color: 'rgba(255,255,255,0.04)' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: 'rgba(255,203,5,0.4)', labelBackgroundColor: '#0a1628' },
        horzLine: { color: 'rgba(255,203,5,0.4)', labelBackgroundColor: '#0a1628' },
      },
      rightPriceScale: {
        borderColor: 'rgba(255,255,255,0.08)',
        textColor: 'rgba(255,255,255,0.4)',
        scaleMargins: { top: 0.08, bottom: 0.28 },
      },
      timeScale: {
        borderColor: 'rgba(255,255,255,0.08)',
        
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: true,
      handleScale: true,
    });

    chartInstance.current = chart;

    // Candlestick series
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor:          '#00e676',
      downColor:        '#ff4757',
      borderUpColor:    '#00e676',
      borderDownColor:  '#ff4757',
      wickUpColor:      '#00e676',
      wickDownColor:    '#ff4757',
    });

    const candleData = data.map((d: any) => ({
      time: d.date as any,
      open:  d.open,
      high:  d.high,
      low:   d.low,
      close: d.close,
    }));
    candleSeries.setData(candleData);

    // ── MA5 / MA20 均线 ──
    const calcMA = (arr: {close: number}[], period: number) =>
      arr.map((_, i) => {
        if (i < period - 1) return null;
        const avg = arr.slice(i - period + 1, i + 1).reduce((s, d) => s + d.close, 0) / period;
        return avg;
      });

    const ma5vals  = calcMA(candleData, 5);
    const ma20vals = calcMA(candleData, 20);

    const ma5Series = chart.addSeries(LineSeries, {
      color: '#FFD700', lineWidth: 1,
      priceLineVisible: false, lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    ma5Series.setData(
      candleData
        .map((d, i) => ma5vals[i] != null ? { time: d.time, value: ma5vals[i]! } : null)
        .filter(Boolean) as any
    );

    const ma20Series = chart.addSeries(LineSeries, {
      color: '#00b4ff', lineWidth: 1,
      priceLineVisible: false, lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    ma20Series.setData(
      candleData
        .map((d, i) => ma20vals[i] != null ? { time: d.time, value: ma20vals[i]! } : null)
        .filter(Boolean) as any
    );

    // Volume histogram (separate pane via price scale)
    const volSeries = chart.addSeries(HistogramSeries, {
      color: 'rgba(255,203,5,0.35)',
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });
    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.78, bottom: 0.0 },
      visible: false,
    });

    const volData = data.map((d: any) => ({
      time:  d.date as any,
      value: d.volume,
      color: d.close >= d.open ? 'rgba(0,230,118,0.4)' : 'rgba(255,71,87,0.4)',
    }));
    volSeries.setData(volData);

    chart.timeScale().fitContent();

    // ── OHLC Crosshair Tooltip ──
    chart.subscribeCrosshairMove((param) => {
      const tooltip = tooltipRef.current;
      if (!tooltip) return;
      if (!param.time || !param.point || param.point.x < 0 || param.point.y < 0) {
        tooltip.style.display = 'none';
        return;
      }
      const bar = param.seriesData.get(candleSeries) as any;
      if (!bar) { tooltip.style.display = 'none'; return; }

      const { open, high, low, close } = bar;
      const isUp = close >= open;
      const clr  = isUp ? '#00e676' : '#ff4757';
      const fmt  = (v: number) => v.toFixed(2);

      tooltip.innerHTML = `
        <span style="color:${clr};font-weight:700">${isUp ? '▲' : '▼'} ${fmt(close)}</span>
        <span style="color:rgba(255,255,255,0.5);margin-left:8px">O</span><span style="color:${clr}">${fmt(open)}</span>
        <span style="color:rgba(255,255,255,0.5);margin-left:6px">H</span><span style="color:#00e676">${fmt(high)}</span>
        <span style="color:rgba(255,255,255,0.5);margin-left:6px">L</span><span style="color:#ff4757">${fmt(low)}</span>
        <span style="color:rgba(255,255,255,0.5);margin-left:6px">C</span><span style="color:${clr}">${fmt(close)}</span>
      `;

      const container = chartRef.current;
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const tw = tooltip.offsetWidth || 260;
      let left = param.point.x + 12;
      if (left + tw > rect.width) left = param.point.x - tw - 12;
      tooltip.style.left = left + 'px';
      tooltip.style.top  = '6px';
      tooltip.style.display = 'flex';
    });

    // Resize observer
    const ro = new ResizeObserver(() => {
      if (chartRef.current) {
        chart.applyOptions({
          width:  chartRef.current.clientWidth,
          height: chartRef.current.clientHeight,
        });
      }
    });
    if (chartRef.current) ro.observe(chartRef.current);
    (chart as any)._ro = ro;

    requestAnimationFrame(() => setChartLoading(false));
  };

  const ranges: { label: string; val: number | 'ytd' }[] = [
    { label: '5D', val: 5 }, { label: '20D', val: 20 },
    { label: '60D', val: 60 }, { label: 'YTD', val: 'ytd' },
  ];
  const mono: React.CSSProperties = { fontFamily: "'SF Mono','Courier New',monospace" };

  return (
    <div style={{
      background: '#0a1628', borderTop: '1px solid rgba(255,203,5,0.15)',
      padding: '14px 16px 12px', ...mono,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ color: '#FFCB05', fontWeight: 700, fontSize: 11, letterSpacing: '0.12em' }}>DETAIL</span>
          <span style={{ color: '#00d4ff', fontWeight: 700, fontSize: 14 }}>{stock.code}</span>
          <span style={{ color: '#e2e8f0', fontSize: 14 }}>{stock.name}</span>
        </div>
        <button onClick={onClose} style={{
          background: 'none', border: 'none', color: 'rgba(255,255,255,0.4)',
          fontSize: 16, cursor: 'pointer', padding: '0 4px', lineHeight: 1,
        }}>✕</button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
          {[
            { label: '市值', value: fmtCap(cap) },
            { label: 'PE',   value: fmtNum(pe) },
            { label: 'PB',   value: fmtNum(pb) },
            { label: '行业', value: String(ind).substring(0, 8) },
          ].map(({ label, value }) => (
            <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'rgba(255,255,255,0.45)', fontSize: 11, letterSpacing: '0.08em' }}>{label}</span>
              <span style={{ color: '#e2e8f0', fontSize: 12, fontWeight: 600 }}>{value}</span>
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>
            {ranges.map(r => (
              <button key={r.label} onClick={() => setChartDays(r.val)} style={{
                padding: '2px 8px', fontSize: 11, borderRadius: 4, cursor: 'pointer',
                border: '1px solid rgba(255,255,255,0.15)',
                background: chartDays === r.val ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.06)',
                color: chartDays === r.val ? '#050d1a' : 'rgba(255,255,255,0.55)',
                fontWeight: chartDays === r.val ? 700 : 400, ...mono,
              }}>{r.label}</button>
            ))}
          </div>
          <div style={{ position: 'relative', height: 140 }}>
            {chartLoading && (
              <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
                justifyContent: 'center', color: 'rgba(255,255,255,0.35)', fontSize: 12 }}>◌ 加载中...</div>
            )}
            {chartError && !chartLoading && (
              <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
                justifyContent: 'center', color: '#ff4757', fontSize: 12 }}>{chartError}</div>
            )}
            <div ref={chartRef} style={{ width: '100%', height: '100%',
              visibility: chartLoading || chartError ? 'hidden' : 'visible' }} />
            <div ref={tooltipRef} style={{
              display: 'none', position: 'absolute', top: 6, left: 12,
              background: 'rgba(10,22,40,0.92)',
              border: '1px solid rgba(255,203,5,0.25)',
              borderRadius: 5, padding: '3px 10px',
              fontSize: 11, fontFamily: "'SF Mono','Courier New',monospace",
              pointerEvents: 'none', zIndex: 10,
              alignItems: 'center', gap: 2, whiteSpace: 'nowrap',
            }} />
          </div>
        </div>
      </div>
    </div>
  );
}

// Results View — Phase 3 redesign
function ResultsView({ screeners, selectedScreener, setSelectedScreener }: { screeners: Screener[], selectedScreener: string, setSelectedScreener: (s: string) => void }) {
  const [date, setDate] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    const urlDate = params.get('date');
    return (urlDate && isValidDate(urlDate)) ? urlDate : getTodayString();
  });
  const [showCalendar, setShowCalendar] = useState(false);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any[]>([]);
  const [error, setError] = useState('');
  const [selectedStock, setSelectedStock] = useState<{ code: string; name: string; row: any } | null>(null);
  const [autoQueried, setAutoQueried] = useState(false);
  const [autoLoaded, setAutoLoaded] = useState(false);

  useEffect(() => {
    if (!selectedScreener && screeners.length > 0) setSelectedScreener(screeners[0].name);
  }, [screeners]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('tab') === 'results' && params.get('screener') && !autoQueried) {
      setAutoQueried(true);
      handleQuery();
    }
  }, []);

  // Auto-load most recent results on first open (no URL params)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('screener') || params.get('date') || autoLoaded) return;
    setAutoLoaded(true);
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/calendar`);
        const data = await res.json();
        const calendar: { date: string; screeners: { name: string; stocks_found: number }[]; total_stocks: number }[] = data.calendar || [];
        const sorted = calendar.filter(c => c.total_stocks > 0).sort((a, b) => b.date.localeCompare(a.date));
        if (sorted.length === 0) return;
        const latest = sorted[0];
        const best = latest.screeners.filter(s => s.stocks_found > 0).sort((a, b) => b.stocks_found - a.stocks_found)[0];
        if (!best) return;
        // Directly fetch results with resolved date + screener
        setLoading(true); setError(''); setSelectedStock(null);
        const p = new URLSearchParams({ screener: best.name, date: latest.date });
        const r = await fetch(`${API_BASE}/results?${p}`);
        const d = await r.json();
        if (d.error) throw new Error(d.error);
        const rs: any[] = d.results || [];
        setResults(rs);
        setDate(latest.date);
        setSelectedScreener(best.name);
        if (rs.length > 0) setSelectedStock({ code: rs[0].stock_code, name: rs[0].stock_name, row: rs[0] });
      } catch (_) { /* silent */ } finally { setLoading(false); }
    })();
  }, []);

  const handleQuery = async () => {
    if (!selectedScreener) { setError('请选择筛选器'); return; }
    setLoading(true); setError(''); setSelectedStock(null);
    try {
      const formattedDate = formatDate(date);
      if (!isValidDate(formattedDate)) { setError('日期格式无效'); setLoading(false); return; }
      const params = new URLSearchParams({ screener: selectedScreener, date: formattedDate });
      const res = await fetch(`${API_BASE}/results?${params}`);
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      if (selectedScreener === 'daily_hot_cold_screener' && (data.hot !== undefined || data.cold !== undefined)) {
        const hot  = (data.hot  || []).map((s: any) => ({ ...s, _type: 'hot',  _category: '热股' }));
        const cold = (data.cold || []).map((s: any) => ({ ...s, _type: 'cold', _category: '冷股' }));
        setResults([...hot, ...cold]);
      } else {
        setResults(data.results || []);
      }
    } catch (e: any) { setError(e.message || '获取结果失败'); setResults([]); }
    setLoading(false);
  };

  const activeScreener = screeners.find(s => s.name === selectedScreener);
  const displayName = activeScreener?.display_name || selectedScreener || '–';

  const downloadCSV = () => {
    if (!results.length) return;
    const flatRow = flattenObject(results[0]);
    let cols = Object.keys(flatRow).filter(c => !['id','run_id','created_at','updated_at','is_deleted'].includes(c));
    const pri = ['stock_code','stock_name'];
    cols = [...pri.filter(c => cols.includes(c)), ...cols.filter(c => !pri.includes(c))];
    const hdrMap: Record<string,string> = {
      stock_code:'代码', stock_name:'名称', close_price:'收盘价', pct_change:'涨幅%',
      turnover:'换手率%', volume:'成交量', amount:'成交额', industry:'行业',
      total_market_cap:'总市值', circulating_market_cap:'流通市值', pe_ratio:'市盈率', pb_ratio:'市净率',
    };
    const hdr = cols.map(c => hdrMap[c] || c).join(',');
    const rows = results.map(row => {
      const f = flattenObject(row);
      return cols.map(c => {
        const v = f[c]; if (v==null) return '';
        const s = String(v);
        return (s.includes(',')||s.includes('"')||s.includes('\n')) ? `"${s.replace(/"/g,'""')}"` : s;
      }).join(',');
    });
    const blob = new Blob(['\uFEFF' + [hdr,...rows].join('\n')], { type: 'text/csv;charset=utf-8;' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = `${selectedScreener}_${date}.csv`; document.body.appendChild(a); a.click(); document.body.removeChild(a);
  };

  const downloadExcel = () => {
    if (!results.length) return;
    const flatRow = flattenObject(results[0]);
    let cols = Object.keys(flatRow).filter(c => !['id','run_id','created_at','updated_at','is_deleted'].includes(c));
    const pri = ['stock_code','stock_name'];
    cols = [...pri.filter(c => cols.includes(c)), ...cols.filter(c => !pri.includes(c))];
    const hdrMap: Record<string,string> = {
      stock_code:'代码', stock_name:'名称', close_price:'收盘价', pct_change:'涨幅%',
      turnover:'换手率%', volume:'成交量', amount:'成交额', industry:'行业',
      total_market_cap:'总市值', circulating_market_cap:'流通市值', pe_ratio:'市盈率', pb_ratio:'市净率',
    };
    let html = '<table border="1"><tr>' + cols.map(c => `<th>${hdrMap[c]||c}</th>`).join('') + '</tr>';
    results.forEach(row => {
      const f = flattenObject(row);
      html += '<tr>' + cols.map(c => `<td>${f[c]??''}</td>`).join('') + '</tr>';
    });
    html += '</table>';
    const blob = new Blob([`<html xmlns:o="urn:schemas-microsoft-com:office:office"
      xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40">
      <head><meta charset="UTF-8"></head><body>${html}</body></html>`],
      { type: 'application/vnd.ms-excel;charset=utf-8' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = `${selectedScreener}_${date}.xlsx`; document.body.appendChild(a); a.click(); document.body.removeChild(a);
  };

  const mono: React.CSSProperties = { fontFamily: "'SF Mono','Courier New',monospace" };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', ...mono }}>

      {/* ── Header bar ── */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', height: 40, flexShrink: 0,
        borderBottom: '1px solid rgba(255,203,5,0.12)', background: '#0a1628',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: '#FFCB05', fontWeight: 700, fontSize: 12, letterSpacing: '0.15em' }}>RESULTS</span>
          <span style={{ color: 'rgba(255,255,255,0.35)', fontSize: 12 }}>—</span>
          <span style={{ color: '#e2e8f0', fontSize: 12 }}>{displayName}</span>
          <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 12 }}>@ {date}</span>
          {results.length > 0 && (
            <span style={{
              background: 'rgba(255,203,5,0.15)', border: '1px solid rgba(255,203,5,0.3)',
              color: '#FFCB05', fontSize: 11, fontWeight: 700, padding: '1px 7px',
              borderRadius: 10, letterSpacing: '0.05em',
            }}>{results.length}</span>
          )}
        </div>
        {results.length > 0 && (
          <div style={{ display: 'flex', gap: 6 }}>
            <button onClick={downloadCSV} style={{
              background: 'rgba(0,230,118,0.1)', border: '1px solid rgba(0,230,118,0.25)',
              color: '#00e676', padding: '3px 10px', borderRadius: 4, fontSize: 11,
              cursor: 'pointer', ...mono,
            }}>📄 CSV</button>
            <button onClick={downloadExcel} style={{
              background: 'rgba(0,212,255,0.1)', border: '1px solid rgba(0,212,255,0.25)',
              color: '#00d4ff', padding: '3px 10px', borderRadius: 4, fontSize: 11,
              cursor: 'pointer', ...mono,
            }}>📊 XLS</button>
          </div>
        )}
      </div>

      {/* ── Filter bar ── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
        flexShrink: 0, borderBottom: '1px solid rgba(255,255,255,0.06)',
      }}>
        <CalendarWithButton
          value={date} onChange={setDate}
          maxDate={new Date().toISOString().split('T')[0]}
          showPicker={showCalendar}
          onTogglePicker={() => setShowCalendar(!showCalendar)}
          onSelectDate={(d) => { setDate(d); setShowCalendar(false); }}
        />
        <select value={selectedScreener} onChange={e => setSelectedScreener(e.target.value)} style={{
          flex: 1, background: '#0d1f35', border: '1px solid rgba(255,255,255,0.12)',
          color: '#e2e8f0', borderRadius: 5, padding: '5px 8px', fontSize: 12, ...mono,
        }}>
          <option value="" disabled>选择筛选器...</option>
          {screeners.map(s => <option key={s.id} value={s.name}>{s.display_name}</option>)}
        </select>
        <button onClick={handleQuery} disabled={loading || !selectedScreener} style={{
          background: loading ? 'rgba(255,203,5,0.3)' : '#FFCB05',
          color: '#050d1a', border: 'none', borderRadius: 5,
          padding: '5px 16px', fontSize: 12, fontWeight: 700,
          cursor: loading ? 'not-allowed' : 'pointer', flexShrink: 0, ...mono,
        }}>{loading ? '查询中...' : '查看结果'}</button>
      </div>

      {/* ── Error ── */}
      {error && (
        <div style={{ margin: '8px 12px', padding: '8px 12px',
          background: 'rgba(255,71,87,0.1)', border: '1px solid rgba(255,71,87,0.3)',
          borderRadius: 5, color: '#ff4757', fontSize: 12 }}>{error}</div>
      )}

      {/* ── Results list ── */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {!loading && results.length === 0 && !error && (
          <div style={{ padding: '40px 16px', textAlign: 'center',
            color: 'rgba(255,255,255,0.25)', fontSize: 13 }}>
            无结果。选择日期并点击查看结果。
          </div>
        )}

        {results.length > 0 && (
          <>
            <div style={{
              display: 'grid', gridTemplateColumns: '80px 1fr 90px 80px 52px 60px',
              padding: '5px 12px', borderBottom: '1px solid rgba(255,255,255,0.08)',
              color: 'rgba(255,255,255,0.35)', fontSize: 10, letterSpacing: '0.1em',
            }}>
              <span>STOCK</span><span>NAME</span>
              <span>行业</span>
              <span style={{ textAlign: 'right' }}>市值</span>
              <span style={{ textAlign: 'right' }}>PE</span>
              <span style={{ textAlign: 'right' }}>涨幅%</span>
            </div>

            {results.map((row, i) => {
              const f = flattenObject(row);
              const code = f['stock_code'] || f['code'] || '';
              const name = f['stock_name'] || f['name'] || '';
              const cap  = f['total_market_cap'] ?? f['circulating_market_cap'] ?? f['circulating_cap'] ?? null;
              const pe   = f['extra_data.pe'] ?? f['pe_ratio'] ?? f['pe'] ?? null;
              const pct  = f['pct_change'] ?? f['change'] ?? null;
              const isSelected = selectedStock?.code === code;

              const fmtCapShort = (v: any) => {
                if (v == null) return '–';
                const n = Number(v); if (isNaN(n)) return '–';
                if (n >= 1e8) return (n/1e8).toFixed(0) + '亿';
                if (n >= 1e4) return (n/1e4).toFixed(0) + '万';
                return n.toFixed(0);
              };

              return (
                <div key={i}>
                  <div
                    onClick={() => setSelectedStock(isSelected ? null : { code, name, row })}
                    style={{
                      display: 'grid', gridTemplateColumns: '80px 1fr 90px 80px 52px 60px',
                      padding: '7px 12px', cursor: 'pointer',
                      borderBottom: '1px solid rgba(255,255,255,0.05)',
                      borderLeft: isSelected ? '2px solid #00d4ff' : '2px solid transparent',
                      background: isSelected ? 'rgba(0,212,255,0.08)'
                        : i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)',
                      transition: 'background 0.15s',
                    }}
                    onMouseEnter={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.05)'; }}
                    onMouseLeave={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.background = i%2===0 ? 'transparent' : 'rgba(255,255,255,0.02)'; }}
                  >
                    <span style={{ color: '#00d4ff', fontSize: 12, fontWeight: 600, ...mono }}>{code}</span>
                    <span style={{ color: '#e2e8f0', fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</span>
                    <span style={{ color: 'rgba(255,203,5,0.55)', fontSize: 10, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', ...mono }}>
                      {f['extra_data.industry'] ?? f['industry'] ?? '–'}
                    </span>
                    <span style={{ color: 'rgba(255,255,255,0.65)', fontSize: 11, textAlign: 'right', ...mono }}>{fmtCapShort(cap)}</span>
                    <span style={{ color: 'rgba(255,255,255,0.65)', fontSize: 11, textAlign: 'right', ...mono }}>
                      {pe != null && !isNaN(Number(pe)) ? Number(pe).toFixed(1) : '–'}
                    </span>
                    <span style={{
                      fontSize: 11, textAlign: 'right', fontWeight: 600, ...mono,
                      color: pct == null ? 'rgba(255,255,255,0.4)'
                        : Number(pct) > 0 ? '#00e676'
                        : Number(pct) < 0 ? '#ff4757'
                        : 'rgba(255,255,255,0.4)',
                    }}>
                      {pct != null ? (Number(pct) > 0 ? '+' : '') + Number(pct).toFixed(2) + '%' : '–'}
                    </span>
                  </div>

                  {isSelected && selectedStock && (
                    <StockDetailPanel
                      stock={{ code: selectedStock.code, name: selectedStock.name }}
                      rowData={selectedStock.row}
                      onClose={() => setSelectedStock(null)}
                    />
                  )}
                </div>
              );
            })}

            <div style={{ padding: '8px 12px', color: 'rgba(255,255,255,0.25)', fontSize: 11 }}>
              {results.length} stocks matched
            </div>
          </>
        )}
      </div>

      {/* ── Bottom Status Bar ── */}
      <div style={{
        flexShrink: 0,
        height: 28,
        borderTop: '1px solid rgba(255,203,5,0.12)',
        background: '#050d1a',
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        gap: 12,
        fontSize: 10,
        color: 'rgba(255,255,255,0.35)',
        letterSpacing: '0.08em',
        fontFamily: "'SF Mono','Courier New',monospace",
      }}>
        {results.length > 0 ? (
          <>
            <span style={{ color: '#FFCB05', fontWeight: 700 }}>MATCHED</span>
            <span style={{ color: 'rgba(255,255,255,0.7)' }}>{results.length}</span>
            <span style={{ opacity: 0.3 }}>·</span>
            <span style={{ color: '#FFCB05', fontWeight: 700 }}>SCREENER</span>
            <span style={{ color: 'rgba(255,255,255,0.7)', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{displayName}</span>
            <span style={{ opacity: 0.3 }}>·</span>
            <span style={{ color: '#FFCB05', fontWeight: 700 }}>DATE</span>
            <span style={{ color: 'rgba(255,255,255,0.7)' }}>{date}</span>
            {selectedStock && (
              <>
                <span style={{ opacity: 0.3 }}>·</span>
                <span style={{ color: '#FFCB05', fontWeight: 700 }}>SEL</span>
                <span style={{ color: 'rgba(255,255,255,0.7)' }}>{selectedStock.code} {selectedStock.name}</span>
              </>
            )}
          </>
        ) : (
          <span>NO DATA — SELECT SCREENER AND DATE</span>
        )}
      </div>
    </div>
  );
}

// Strategy Evolution View - Lab Dashboard Style
// @ts-ignore — reserved for future use
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function StrategyView() {
  const [backtests, setBacktests] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedBacktest, setSelectedBacktest] = useState<any>(null);
  const [trades, setTrades] = useState<any[]>([]);
  const [tradeSummary, setTradeSummary] = useState<any>(null);
  const [loadingTrades, setLoadingTrades] = useState(false);
  const [activePhase, setActivePhase] = useState<'idle' | 'running' | 'analyzing'>('idle');

  useEffect(() => {
    fetch(`${API_BASE}/strategy/backtests`)
      .then(r => r.json())
      .then(data => {
        setBacktests(data.backtests || []);
        setLoading(false);
        // Check if autoresearch is running
        if ((data.backtests || []).length > 0) {
          const latest = data.backtests[data.backtests.length - 1];
          const latestTime = new Date(latest.created_at).getTime();
          const now = new Date().getTime();
          // If latest result is within last 5 minutes, consider it running
          if (now - latestTime < 5 * 60 * 1000) {
            setActivePhase('running');
          }
        }
      })
      .catch(() => setLoading(false));
    
    // Poll every 30 seconds
    const interval = setInterval(() => {
      fetch(`${API_BASE}/strategy/backtests`)
        .then(r => r.json())
        .then(data => {
          setBacktests(data.backtests || []);
        });
    }, 30000);
    
    return () => clearInterval(interval);
  }, []);

  const loadTrades = (backtestId: number, backtest: any) => {
    setLoadingTrades(true);
    setSelectedBacktest(backtest);
    fetch(`${API_BASE}/strategy/trades/${backtestId}`)
      .then(r => r.json())
      .then(data => {
        setTrades(data.trades || []);
        setTradeSummary(data.summary || null);
        setLoadingTrades(false);
      })
      .catch(() => setLoadingTrades(false));
  };

  // Calculate metrics
  const bestSharpe = backtests.length > 0 ? Math.max(...backtests.map(b => b.sharpe_ratio)) : 0;
  const bestReturn = backtests.length > 0 ? Math.max(...backtests.map(b => b.total_return)) : 0;
  
  // Progress to profitability (from -2 to 0)
  const progressToProfit = Math.min(100, Math.max(0, ((bestSharpe + 2) / 2) * 100));
  
  // Current generation
  const currentGen = backtests.length;
  
  // Phase determination
  const getPhase = () => {
    if (currentGen === 0) return { name: 'INITIALIZING', color: '#6c757d', step: 0 };
    if (bestSharpe > 0) return { name: 'PROFITABLE', color: '#28a745', step: 4 };
    if (bestSharpe > -0.5) return { name: 'OPTIMIZING', color: '#ffc107', step: 3 };
    if (currentGen > 50) return { name: 'ITERATING', color: '#17a2b8', step: 2 };
    return { name: 'BASELINE', color: '#007bff', step: 1 };
  };
  
  const phase = getPhase();

  // Chart data
  const chartData = backtests.map((b, idx) => ({
    generation: b.strategy_version,
    sharpe: b.sharpe_ratio,
    return: b.total_return * 100,
    drawdown: b.max_drawdown * 100,
    trades: b.total_trades,
    idx: idx + 1
  }));

  useEffect(() => {
    if (chartData.length === 0) return;

    const chartDom = document.getElementById('strategy-evolution-chart');
    if (!chartDom) return;

    const chart = echarts.init(chartDom, 'dark');
    const option = {
      backgroundColor: 'transparent',
      title: { 
        text: 'EVOLUTION TRAJECTORY', 
        left: 'center',
        textStyle: { color: '#00274C', fontSize: 16, fontWeight: 'bold' }
      },
      tooltip: { 
        trigger: 'axis',
        backgroundColor: 'rgba(0,39,76,0.9)',
        borderColor: '#FFCB05',
        textStyle: { color: '#fff' }
      },
      legend: { 
        data: ['Sharpe Ratio', 'Return %', 'Max Drawdown %'], 
        bottom: 0,
        textStyle: { color: '#00274C' }
      },
      grid: { left: '10%', right: '10%', bottom: '15%', top: '15%' },
      xAxis: { 
        type: 'category', 
        data: chartData.map(d => d.generation),
        axisLabel: { color: '#666', fontSize: 12, rotate: 45 },
        axisLine: { lineStyle: { color: '#dee2e6' } }
      },
      yAxis: [
        { 
          type: 'value', 
          name: 'Sharpe',
          position: 'left',
          nameTextStyle: { color: '#00274C' },
          axisLabel: { color: '#666' },
          splitLine: { lineStyle: { color: '#f0f0f0' } }
        },
        { 
          type: 'value', 
          name: '%',
          position: 'right',
          nameTextStyle: { color: '#00274C' },
          axisLabel: { color: '#666' },
          splitLine: { show: false }
        }
      ],
      series: [
        {
          name: 'Sharpe Ratio',
          type: 'line',
          data: chartData.map(d => d.sharpe),
          smooth: true,
          itemStyle: { color: '#00274C' },
          lineStyle: { width: 3 },
          markLine: { 
            silent: true,
            data: [{ yAxis: 0, label: { formatter: 'PROFIT LINE', color: '#28a745' }, lineStyle: { type: 'dashed', color: '#28a745', width: 2 } }] 
          }
        },
        {
          name: 'Return %',
          type: 'line',
          yAxisIndex: 1,
          data: chartData.map(d => d.return),
          smooth: true,
          itemStyle: { color: '#28a745' },
          lineStyle: { width: 2 }
        },
        {
          name: 'Max Drawdown %',
          type: 'line',
          yAxisIndex: 1,
          data: chartData.map(d => d.drawdown),
          smooth: true,
          itemStyle: { color: '#dc3545' },
          lineStyle: { width: 2, type: 'dashed' }
        }
      ]
    };
    chart.setOption(option);

    return () => chart.dispose();
  }, [backtests]);

  if (loading) return <div className="placeholder">INITIALIZING LAB...</div>;

  return (
    <div style={{ background: '#f8f9fa', minHeight: '100%' }}>
      {/* Lab Header */}
      <div style={{ 
        background: 'linear-gradient(135deg, #00274C 0%, #1a3a6b 100%)', 
        padding: '24px', 
        color: 'white',
        borderBottom: '4px solid #FFCB05'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '26px', fontWeight: 'bold', letterSpacing: '2px' }}>
              🧬 AUTORESEARCH LAB
            </h2>
            <div style={{ fontSize: '14px', opacity: 0.8, marginTop: '4px' }}>
              AI-DRIVEN STRATEGY EVOLUTION PROTOCOL v1.0
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ 
              display: 'inline-block',
              padding: '8px 16px', 
              background: phase.color, 
              borderRadius: '20px',
              fontSize: '14px',
              fontWeight: 'bold',
              color: phase.step >= 3 ? '#00274C' : 'white'
            }}>
              PHASE: {phase.name}
            </div>
            <div style={{ fontSize: '13px', marginTop: '8px', opacity: 0.7 }}>
              GEN {currentGen} | SHARPE {bestSharpe.toFixed(3)}
            </div>
          </div>
        </div>
      </div>

      <div style={{ padding: '24px' }}>
        {/* Phase Progress */}
        <div style={{ 
          background: 'white', 
          padding: '20px', 
          borderRadius: '12px', 
          marginBottom: '24px',
          boxShadow: '0 2px 8px rgba(0,39,76,0.08)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
            {['BASELINE', 'ITERATING', 'OPTIMIZING', 'PROFITABLE'].map((p, i) => (
              <div key={p} style={{ 
                textAlign: 'center', 
                flex: 1,
                opacity: i <= phase.step ? 1 : 0.3
              }}>
                <div style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '50%',
                  background: i <= phase.step ? phase.color : '#dee2e6',
                  color: i <= phase.step ? 'white' : '#666',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 8px',
                  fontWeight: 'bold',
                  fontSize: '16px'
                }}>
                  {i < phase.step ? '✓' : i + 1}
                </div>
                <div style={{ fontSize: '13px', fontWeight: 'bold', color: '#00274C' }}>{p}</div>
              </div>
            ))}
          </div>
          <div style={{ height: '4px', background: '#e9ecef', borderRadius: '2px' }}>
            <div style={{
              height: '100%',
              width: `${(phase.step / 3) * 100}%`,
              background: `linear-gradient(90deg, ${phase.color} 0%, #28a745 100%)`,
              borderRadius: '2px',
              transition: 'width 0.5s ease'
            }} />
          </div>
        </div>

        {/* Key Metrics Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '24px' }}>
          {/* Sharpe Gauge */}
          <div style={{ background: 'white', padding: '20px', borderRadius: '12px', boxShadow: '0 2px 8px rgba(0,39,76,0.08)' }}>
            <div style={{ fontSize: '13px', color: '#666', marginBottom: '8px', fontWeight: 'bold' }}>SHARPE RATIO</div>
            <div style={{ 
              fontSize: '34px', 
              fontWeight: 'bold', 
              color: bestSharpe > 0 ? '#28a745' : bestSharpe > -1 ? '#ffc107' : '#dc3545',
              fontFamily: 'SF Mono, monospace'
            }}>
              {bestSharpe.toFixed(3)}
            </div>
            <div style={{ marginTop: '8px', height: '6px', background: '#e9ecef', borderRadius: '3px' }}>
              <div style={{
                height: '100%',
                width: `${progressToProfit}%`,
                background: bestSharpe > 0 ? '#28a745' : '#ffc107',
                borderRadius: '3px'
              }} />
            </div>
            <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
              {bestSharpe > 0 ? '✓ PROFITABLE' : `▼ ${(0 - bestSharpe).toFixed(3)} to break-even`}
            </div>
          </div>

          {/* Total Return */}
          <div style={{ background: 'white', padding: '20px', borderRadius: '12px', boxShadow: '0 2px 8px rgba(0,39,76,0.08)' }}>
            <div style={{ fontSize: '13px', color: '#666', marginBottom: '8px', fontWeight: 'bold' }}>BEST RETURN</div>
            <div style={{ 
              fontSize: '34px', 
              fontWeight: 'bold', 
              color: bestReturn > 0 ? '#28a745' : '#dc3545',
              fontFamily: 'SF Mono, monospace'
            }}>
              {(bestReturn * 100).toFixed(2)}%
            </div>
            <div style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
              {bestReturn > 0 ? '↑ ABOVE WATER' : '↓ UNDER WATER'}
            </div>
          </div>

          {/* Generations */}
          <div style={{ background: 'white', padding: '20px', borderRadius: '12px', boxShadow: '0 2px 8px rgba(0,39,76,0.08)' }}>
            <div style={{ fontSize: '13px', color: '#666', marginBottom: '8px', fontWeight: 'bold' }}>GENERATIONS</div>
            <div style={{ fontSize: '34px', fontWeight: 'bold', color: '#00274C', fontFamily: 'SF Mono, monospace' }}>
              {currentGen}
            </div>
            <div style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
              EXPERIMENTS RUN
            </div>
          </div>

          {/* Status */}
          <div style={{ background: 'white', padding: '20px', borderRadius: '12px', boxShadow: '0 2px 8px rgba(0,39,76,0.08)' }}>
            <div style={{ fontSize: '13px', color: '#666', marginBottom: '8px', fontWeight: 'bold' }}>STATUS</div>
            <div style={{ 
              display: 'inline-block',
              padding: '8px 16px',
              background: activePhase === 'running' ? '#28a745' : '#6c757d',
              color: 'white',
              borderRadius: '4px',
              fontSize: '16px',
              fontWeight: 'bold'
            }}>
              {activePhase === 'running' ? '● RUNNING' : '○ IDLE'}
            </div>
            <div style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
              {activePhase === 'running' ? 'Iterating...' : 'Waiting for next run'}
            </div>
          </div>
        </div>

        {/* Research Info Panel */}
        <div style={{ 
          background: 'white', 
          padding: '20px', 
          borderRadius: '12px', 
          marginBottom: '24px',
          boxShadow: '0 2px 8px rgba(0,39,76,0.08)',
          borderLeft: '4px solid #00274C'
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '24px' }}>
            <div>
              <div style={{ fontSize: '12px', color: '#666', fontWeight: 'bold', marginBottom: '8px' }}>TRAINING SET</div>
              <div style={{ fontSize: '16px', color: '#00274C' }}>2024-09-02 → 2025-08-31</div>
              <div style={{ fontSize: '13px', color: '#28a745', marginTop: '4px' }}>✓ 12 months for training</div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#666', fontWeight: 'bold', marginBottom: '8px' }}>VALIDATION SET</div>
              <div style={{ fontSize: '16px', color: '#00274C' }}>2025-09-01 → 2026-02-28</div>
              <div style={{ fontSize: '13px', color: '#dc3545', marginTop: '4px' }}>🔒 LOCKED (no peeking)</div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#666', fontWeight: 'bold', marginBottom: '8px' }}>METHODOLOGY</div>
              <div style={{ fontSize: '16px', color: '#00274C' }}>Single Variable Testing</div>
              <div style={{ fontSize: '13px', color: '#666', marginTop: '4px' }}>Git-based experiment tracking</div>
            </div>
          </div>
        </div>

        {/* Evolution Chart */}
        {chartData.length > 0 && (
          <div style={{ 
            background: 'white', 
            padding: '20px', 
            borderRadius: '12px', 
            marginBottom: '24px',
            boxShadow: '0 2px 8px rgba(0,39,76,0.08)'
          }}>
            <div id="strategy-evolution-chart" style={{ width: '100%', height: '400px' }}></div>
          </div>
        )}

        {/* Experiments Table */}
        <div style={{ 
          background: 'white', 
          padding: '20px', 
          borderRadius: '12px',
          boxShadow: '0 2px 8px rgba(0,39,76,0.08)'
        }}>
          <h4 style={{ marginBottom: '16px', color: '#00274C', fontSize: '16px' }}>
            EXPERIMENT LOG (Click to view trades)
          </h4>
          <div style={{ maxHeight: '400px', overflow: 'auto' }}>
            <table style={{ width: '100%', fontSize: '14px', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f8f9fa', borderBottom: '2px solid #dee2e6' }}>
                  <th style={{ padding: '12px', textAlign: 'left', fontWeight: 'bold', color: '#00274C' }}>GEN</th>
                  <th style={{ padding: '12px', textAlign: 'right', fontWeight: 'bold', color: '#00274C' }}>SHARPE</th>
                  <th style={{ padding: '12px', textAlign: 'right', fontWeight: 'bold', color: '#00274C' }}>RETURN</th>
                  <th style={{ padding: '12px', textAlign: 'right', fontWeight: 'bold', color: '#00274C' }}>DRAWDOWN</th>
                  <th style={{ padding: '12px', textAlign: 'center', fontWeight: 'bold', color: '#00274C' }}>TRADES</th>
                  <th style={{ padding: '12px', textAlign: 'center', fontWeight: 'bold', color: '#00274C' }}>TIMESTAMP</th>
                </tr>
              </thead>
              <tbody>
                {backtests.slice().reverse().map((b, idx) => (
                  <tr 
                    key={idx} 
                    onClick={() => loadTrades(b.id, b)}
                    style={{ 
                      cursor: 'pointer',
                      borderBottom: '1px solid #f0f0f0',
                      background: b.sharpe_ratio === bestSharpe ? '#f0fff4' : 'transparent'
                    }}
                  >
                    <td style={{ padding: '12px', fontWeight: 'bold' }}>{b.strategy_version}</td>
                    <td style={{ padding: '12px', textAlign: 'right', color: b.sharpe_ratio > 0 ? '#28a745' : b.sharpe_ratio > -1 ? '#ffc107' : '#dc3545', fontFamily: 'monospace' }}>
                      {b.sharpe_ratio.toFixed(3)}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right', color: b.total_return > 0 ? '#28a745' : '#dc3545', fontFamily: 'monospace' }}>
                      {(b.total_return * 100).toFixed(2)}%
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right', color: '#dc3545', fontFamily: 'monospace' }}>
                      {(b.max_drawdown * 100).toFixed(2)}%
                    </td>
                    <td style={{ padding: '12px', textAlign: 'center' }}>{b.total_trades}</td>
                    <td style={{ padding: '12px', textAlign: 'center', color: '#666', fontSize: '13px' }}>
                      {new Date(b.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Trade Detail Modal */}
      {selectedBacktest && (
        <div className="modal-overlay" onClick={() => setSelectedBacktest(null)}>
          <div className="modal modal-wide" onClick={e => e.stopPropagation()} style={{ maxWidth: '900px' }}>
            <div className="modal-header" style={{ background: '#00274C', color: 'white' }}>
              <h3>🔬 {selectedBacktest.strategy_version} ANALYSIS</h3>
              <button className="modal-close" onClick={() => setSelectedBacktest(null)} style={{ color: 'white' }}>×</button>
            </div>
            <div className="modal-body">
              {loadingTrades ? (
                <div style={{ padding: '40px', textAlign: 'center' }}>LOADING TRADE DATA...</div>
              ) : (
                <>
                  {tradeSummary && (
                    <div style={{ 
                      display: 'grid', 
                      gridTemplateColumns: 'repeat(4, 1fr)', 
                      gap: '16px', 
                      marginBottom: '20px',
                      padding: '16px',
                      background: '#f8f9fa',
                      borderRadius: '8px'
                    }}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '12px', color: '#666' }}>NET P&L</div>
                        <div style={{ fontSize: '22px', fontWeight: 'bold', color: tradeSummary.net_pnl >= 0 ? '#28a745' : '#dc3545' }}>
                          ¥{tradeSummary.net_pnl?.toFixed(2) || '0.00'}
                        </div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '12px', color: '#666' }}>WINS</div>
                        <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#28a745' }}>
                          {tradeSummary.win_count}
                        </div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '12px', color: '#666' }}>LOSSES</div>
                        <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#dc3545' }}>
                          {tradeSummary.loss_count}
                        </div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '12px', color: '#666' }}>WIN RATE</div>
                        <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#00274C' }}>
                          {tradeSummary.total_trades > 0 ? ((tradeSummary.win_count / tradeSummary.total_trades) * 100).toFixed(1) : 0}%
                        </div>
                      </div>
                    </div>
                  )}

                  {trades.length > 0 ? (
                    <div style={{ maxHeight: '400px', overflow: 'auto' }}>
                      <table style={{ width: '100%', fontSize: '13px', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr style={{ background: '#00274C', color: 'white' }}>
                            <th style={{ padding: '10px', textAlign: 'left' }}>DATE</th>
                            <th style={{ padding: '10px', textAlign: 'left' }}>CODE</th>
                            <th style={{ padding: '10px', textAlign: 'center' }}>ACTION</th>
                            <th style={{ padding: '10px', textAlign: 'right' }}>PRICE</th>
                            <th style={{ padding: '10px', textAlign: 'right' }}>P&L</th>
                            <th style={{ padding: '10px', textAlign: 'right' }}>P&L%</th>
                            <th style={{ padding: '10px', textAlign: 'center' }}>HOLD</th>
                            <th style={{ padding: '10px', textAlign: 'left' }}>EXIT REASON</th>
                          </tr>
                        </thead>
                        <tbody>
                          {trades.map((t, i) => (
                            <tr key={i} style={{ borderBottom: '1px solid #f0f0f0', background: i % 2 === 0 ? '#fafafa' : 'white' }}>
                              <td style={{ padding: '10px' }}>{t.trade_date}</td>
                              <td style={{ padding: '10px', fontWeight: 'bold' }}>{t.code}</td>
                              <td style={{ padding: '10px', textAlign: 'center' }}>
                                <span style={{
                                  display: 'inline-block',
                                  padding: '2px 8px',
                                  borderRadius: '4px',
                                  background: t.action === 'BUY' ? '#d4edda' : '#f8d7da',
                                  color: t.action === 'BUY' ? '#155724' : '#721c24',
                                  fontSize: '12px',
                                  fontWeight: 'bold'
                                }}>
                                  {t.action}
                                </span>
                              </td>
                              <td style={{ padding: '10px', textAlign: 'right', fontFamily: 'monospace' }}>¥{t.price?.toFixed(2)}</td>
                              <td style={{ padding: '10px', textAlign: 'right', fontFamily: 'monospace', color: (t.realized_pnl || 0) > 0 ? '#28a745' : (t.realized_pnl || 0) < 0 ? '#dc3545' : '#666' }}>
                                {t.realized_pnl ? (t.realized_pnl > 0 ? '+' : '') + '¥' + t.realized_pnl.toFixed(2) : '-'}
                              </td>
                              <td style={{ padding: '10px', textAlign: 'right', fontFamily: 'monospace', color: (t.realized_pnl_pct || 0) > 0 ? '#28a745' : (t.realized_pnl_pct || 0) < 0 ? '#dc3545' : '#666' }}>
                                {t.realized_pnl_pct ? (t.realized_pnl_pct > 0 ? '+' : '') + t.realized_pnl_pct.toFixed(2) + '%' : '-'}
                              </td>
                              <td style={{ padding: '10px', textAlign: 'center' }}>{t.hold_days}d</td>
                              <td style={{ padding: '10px', fontSize: '12px', color: '#666' }}>{t.exit_reason || '-'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div style={{ padding: '40px', textAlign: 'center', color: '#666' }}>
                      NO TRADES RECORDED FOR THIS EXPERIMENT
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
// ==================== 数据健康页面 ====================










// ── 数据健康内嵌组件 ──
function DataHealthInline() {
  const [health, setHealth] = useState<any>(null);
  const [uploadMsg, setUploadMsg] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [forceUpdate, setForceUpdate] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/data-health`)
      .then(r => r.json())
      .then(d => { setHealth(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadMsg('⏳ 上传中...');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('force_update', forceUpdate ? 'true' : 'false');

    fetch(`${API_BASE}/data-health/upload`, {
      method: 'POST',
      body: formData,
    })
      .then(r => r.json())
      .then(d => {
        if (d.success) {
          setUploadMsg(`✅ ${d.message}`);
          // Show warnings if any
          if (d.warnings && d.warnings.length > 0) {
            setUploadMsg(prev => `${prev}\n⚠️ ${d.warnings.length} 条记录有警告`);
          }
          // Refresh health data after successful upload
          fetch(`${API_BASE}/data-health`)
            .then(r => r.json())
            .then(d => { setHealth(d); });
        } else {
          setUploadMsg(`❌ ${d.error}`);
        }
      })
      .catch((err) => {
        console.error('Upload failed:', err);
        setUploadMsg('❌ 上传失败');
      })
      .finally(() => {
        setIsUploading(false);
        // Reset file input
        event.target.value = '';
      });
  };

  const closeUploadMsg = () => {
    setUploadMsg('');
  };

  const sp = health?.db_health?.checks?.stock_pool;
  const hd = health?.db_health?.checks?.history_data;
  const td = health?.db_health?.checks?.today_data;
  const md = health?.db_health?.checks?.macro_data;
  const rh: any[] = health?.run_history || [];
  const dbStatus: string = health?.db_health?.status ?? 'unknown';

  // ── Fix: parse timestamp correctly ──
  const lastCheck = (() => {
    const raw = health?.db_health?.timestamp;
    if (!raw) return '–';
    const d = new Date(String(raw).replace(' ', 'T'));
    if (isNaN(d.getTime())) return String(raw).substring(0, 16);
    return d.toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' });
  })();

  const fmt = (v: any) => v == null ? '–' : typeof v === 'number' ? v.toLocaleString() : String(v);
  const pct = (v: any) => v == null ? '–' : `${Number(v).toFixed(1)}%`;

  const sColor = dbStatus === 'healthy' ? '#00e676'
    : dbStatus === 'warning' ? '#ff9f43'
    : dbStatus === 'critical' ? '#ff4757' : '#555';

  const outcomeInfo = (r: any) => {
    const s = (r.outcome || r.status || r.result || '').toLowerCase();
    if (s.includes('success') || s.includes('成功') || s.includes('ok'))
      return { icon: '✓', color: '#00e676', label: '成功' };
    if (s.includes('non') || s.includes('not_trad') || s.includes('no_trad') || s.includes('非交易') || s.includes('skip'))
      return { icon: '◈', color: '#4a6080', label: '非交易日' };
    if (s.includes('fail') || s.includes('err'))
      return { icon: '✗', color: '#ff4757', label: '失败' };
    return { icon: '◌', color: '#4a6080', label: r.outcome || '–' };
  };

  const parseRunId = (r: any): string => {
    const ts = r.ts || r.started_at || r.run_id || '';
    if (!ts) return '–';
    const s = String(ts).replace('T', '_').replace(/[-:]/g, '');
    // format: 20260328_120519 → 03-28 12:05
    if (s.length >= 13) {
      return `${s.slice(4,6)}-${s.slice(6,8)} ${s.slice(9,11)}:${s.slice(11,13)}`;
    }
    return String(ts).substring(0, 16);
  };

  const mono: React.CSSProperties = { fontFamily: "'SF Mono','Courier New',monospace" };

  if (loading && !health) return (
    <div style={{ ...mono, background:'#050d1a', border:'1px solid rgba(255,203,5,0.12)',
      borderRadius:10, padding:'24px', textAlign:'center',
      color:'rgba(255,255,255,0.65)', fontSize:14 }}>
      ◌ LOADING DATA HEALTH...
    </div>
  );

  return (
    <div className="dh-wrap" style={{ ...mono }}>

      {/* ── Header ── */}
      <div className="dh-header">
        <div style={{ display:'flex', alignItems:'center', gap:9 }}>
          <div style={{
            width:9, height:9, borderRadius:'50%',
            background:sColor, boxShadow:`0 0 8px ${sColor}`, flexShrink:0,
          }} />
          <span style={{ color:'#FFCB05', fontWeight:700, fontSize:14, letterSpacing:'0.15em' }}>DATA HEALTH</span>
          <span style={{ color:'rgba(255,255,255,0.70)', fontSize:12 }}>CHECKED {lastCheck}</span>
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          {dbStatus !== 'unknown' && (
            <span style={{
              padding:'2px 10px',
              background:`${sColor}22`, border:`1px solid ${sColor}55`,
              borderRadius:4, color:sColor, fontSize:12, fontWeight:700, letterSpacing:'0.1em',
            }}>
              {dbStatus.toUpperCase()}
            </span>
          )}
          <input
            type="file"
            accept=".xls,.xlsx"
            onChange={handleFileUpload}
            style={{ display: 'none' }}
            id="excel-upload"
            disabled={isUploading}
          />
          <button
            className="dh-btn"
            onClick={() => document.getElementById('excel-upload')?.click()}
            disabled={isUploading}
          >
            {isUploading ? '⏳ 上传中...' : '📤 上传股票信息'}
          </button>
          <label style={{
            display:'flex', alignItems:'center', gap:'6px', fontSize:11,
            color:'#888', cursor:'pointer', userSelect:'none'
          }} title="勾选后，Excel 中的数据将完全覆盖数据库记录（Excel 中没有的字段将被清空）。不勾选则只更新 Excel 中有值的字段，保留数据库中已有数据。">
            <input
              type="checkbox"
              checked={forceUpdate}
              onChange={(e) => setForceUpdate(e.target.checked)}
              disabled={isUploading}
              style={{ cursor:'pointer' }}
            />
            <span>强制覆盖</span>
          </label>
        </div>
      </div>

      {/* ── 4-Panel Responsive Grid ── */}
      <div className="dh-grid">

        {/* Stock Pool */}
        <div className="dh-panel">
          <div className="dh-panel-title">STOCK POOL</div>
          <div className="dh-row"><span className="dh-lbl">活跃股</span>
            <span className="dh-val-maize">{fmt(sp?.active_stocks)}</span></div>
          <div className="dh-row"><span className="dh-lbl">退市</span>
            <span className="dh-val-dim">{fmt(sp?.delisted_stocks)}</span></div>
          <div className="dh-row"><span className="dh-lbl">30日新股</span>
            <span className={(sp?.newly_listed_30d ?? 0) > 0 ? 'dh-val-green' : 'dh-val-dim'}>
              {fmt(sp?.newly_listed_30d)}</span></div>
          <div className="dh-row"><span className="dh-lbl">ST 股</span>
            <span className="dh-val-dim">{fmt(sp?.st_stocks ?? 0)}</span></div>
        </div>

        {/* Today */}
        <div className="dh-panel">
          <div className="dh-panel-title">TODAY</div>
          <div className="dh-row"><span className="dh-lbl">数据日期</span>
            <span className="dh-val-cyan">{fmt(td?.date)}</span></div>
          <div className="dh-row"><span className="dh-lbl">有效股</span>
            <span className="dh-val-maize">{fmt(td?.total_stocks ?? td?.total)}</span></div>
          <div className="dh-row"><span className="dh-lbl">正常交易</span>
            <span className="dh-val-green">{fmt(td?.normal_trading ?? td?.normal_stocks)}</span></div>
          <div className="dh-row"><span className="dh-lbl">停牌</span>
            <span className={(td?.suspended ?? 0) > 0 ? 'dh-val-orange' : 'dh-val-dim'}>
              {fmt(td?.suspended)}</span></div>
        </div>

        {/* History */}
        <div className="dh-panel">
          <div className="dh-panel-title">HISTORY</div>
          <div className="dh-row"><span className="dh-lbl">最早日期</span>
            <span className="dh-val-cyan">{fmt(hd?.earliest_date)}</span></div>
          <div className="dh-row"><span className="dh-lbl">最新日期</span>
            <span className="dh-val-cyan">{fmt(hd?.latest_date)}</span></div>
          <div className="dh-row"><span className="dh-lbl">交易日数</span>
            <span className="dh-val-maize">{fmt(hd?.trading_days)}</span></div>
          <div className="dh-row"><span className="dh-lbl">总记录数</span>
            <span className="dh-val-cyan">{fmt(hd?.total_records)}</span></div>
          <div className="dh-row"><span className="dh-lbl">缺失记录</span>
            <span className={(hd?.missing_price_records ?? 0) > 0 ? 'dh-val-orange' : 'dh-val-dim'}>
              {fmt(hd?.missing_price_records)}</span></div>
        </div>

        {/* Macro */}
        <div className="dh-panel">
          <div className="dh-panel-title">MACRO COVERAGE</div>
          <div className="dh-row"><span className="dh-lbl">总市值</span>
            <span className="dh-val-green">{pct(md?.total_market_cap?.pct)}</span></div>
          <div className="dh-row"><span className="dh-lbl">PE</span>
            <span className="dh-val-green">{pct(md?.pe_ratio?.pct)}</span></div>
          <div className="dh-row"><span className="dh-lbl">PB</span>
            <span className="dh-val-green">{pct(md?.pb_ratio?.pct)}</span></div>
          <div className="dh-row"><span className="dh-lbl">行业分类</span>
            <span className="dh-val-green">{pct(md?.sector?.pct)}</span></div>
          <div className="dh-row"><span className="dh-lbl">iFind 更新</span>
            <span className="dh-val-dim">
              {md?.ifind_updated_at ? String(md.ifind_updated_at).substring(0,10) : '–'}
            </span></div>
        </div>
      </div>

      {/* ── Download History — vertical list ── */}
      <div className="dh-downloads">
        <div className="dh-dl-title">DOWNLOADS</div>
        <div className="dh-dl-list">
          {rh.length === 0 && (
            <span style={{ color:'rgba(255,255,255,0.35)', fontSize:12 }}>暂无记录</span>
          )}
          {rh.slice(0, 6).map((r: any, i: number) => {
            const { icon, color, label } = outcomeInfo(r);
            const elapsed = r.elapsed_seconds ?? r.elapsed ?? null;
            return (
              <div key={i} className="dh-dl-row">
                <span style={{ color, fontSize:13, width:14, textAlign:'center', flexShrink:0 }}>{icon}</span>
                <span className="dh-dl-time">{parseRunId(r)}</span>
                <span style={{ color, fontSize:12, fontWeight:600, minWidth:60 }}>{label}</span>
                {elapsed != null
                  ? <span className="dh-dl-elapsed">{elapsed}s</span>
                  : <span className="dh-dl-elapsed">–</span>}
              </div>
            );
          })}
        </div>
        {uploadMsg && (
          <div style={{
            marginTop:8,
            fontSize:13,
            color:uploadMsg.includes('❌') ? '#f5222d' : uploadMsg.includes('⚠️') ? '#f59e0b' : '#00e676',
            whiteSpace:'pre-line',
            display:'flex',
            justifyContent:'space-between',
            alignItems:'flex-start',
            gap:'12px',
            background:uploadMsg.includes('❌') ? 'rgba(245,34,45,0.1)' : uploadMsg.includes('⚠️') ? 'rgba(245,158,11,0.1)' : 'rgba(0,230,118,0.1)',
            padding:'8px 12px',
            borderRadius:'6px',
            border:uploadMsg.includes('❌') ? '1px solid rgba(245,34,45,0.3)' : uploadMsg.includes('⚠️') ? '1px solid rgba(245,158,11,0.3)' : '1px solid rgba(0,230,118,0.3)'
          }}>
            <span style={{flex:1}}>{uploadMsg}</span>
            <button
              onClick={closeUploadMsg}
              style={{
                background:'transparent',
                border:'none',
                color:'currentColor',
                cursor:'pointer',
                fontSize:16,
                lineHeight:1,
                padding:0,
                minWidth:20,
                opacity:0.7,
                flexShrink:0
              }}
              onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
              onMouseLeave={(e) => e.currentTarget.style.opacity = '0.7'}
            >×</button>
          </div>
        )}
      </div>
    </div>
  );
}


// 下载状态子组件



export default App;
