import { useMemo, useState } from 'react';
import {
  api,
  AssistantFiveFlagsParameterOverridesResponse,
  AssistantLaoYaTouBaselineEvalResponse,
  AssistantLaoYaTouDailyCompareResponse,
  AssistantLaoYaTouLabelSummaryResponse,
  AssistantPoolCommonalitiesResponse,
  AssistantRulesAnalyzeResponse,
  AssistantRulesVerifyResponse,
} from '../api';

type ChatItem =
  | { role: 'user'; text: string }
  | { role: 'assistant'; text: string; data?: any };

function formatPoolSummary(d: AssistantPoolCommonalitiesResponse): string {
  const pool = d.pool;
  const perf = d.price_performance?.return_pct;
  const lines = [
    `池子行数: ${pool.rows.toLocaleString()} | 去重股票: ${pool.unique_stocks.toLocaleString()} | 未处理: ${pool.unprocessed_rows.toLocaleString()}`,
    `覆盖区间: ${pool.min_start_date ?? '–'} → ${pool.max_end_date ?? '–'} | 平均窗口(天): ${pool.avg_window_days == null ? '–' : pool.avg_window_days.toFixed(1)}`,
    `样本收益(%)  mean=${perf?.mean == null ? '–' : perf.mean.toFixed(2)}  p50=${perf?.p50 == null ? '–' : perf.p50.toFixed(2)}  p25=${perf?.p25 == null ? '–' : perf.p25.toFixed(2)}  p75=${perf?.p75 == null ? '–' : perf.p75.toFixed(2)}`,
    `Top文件: ${(d.top_files || []).slice(0, 5).map(x => `${x.file_name}(${x.count})`).join(' | ') || '–'}`,
    `Top行业: ${(d.sector_lv1_top || []).slice(0, 5).map(x => `${x.sector_lv1}(${x.stock_count})`).join(' | ') || '–'}`,
  ];
  return lines.join('\n');
}

function formatParamSummary(d: AssistantFiveFlagsParameterOverridesResponse): string {
  const lines: string[] = [];
  for (const s of d.screeners || []) {
    if (s.error) {
      lines.push(`${s.screener}: 读取失败: ${s.error}`);
      continue;
    }
    const title = `${s.display_name || s.screener}（${s.screener}）: ${s.override_count} / ${s.schema_param_count} 参数与默认值不同`;
    lines.push(title);
    for (const o of (s.overrides || []).slice(0, 8)) {
      lines.push(`- ${o.param}: default=${JSON.stringify(o.default)} -> current=${JSON.stringify(o.current)}`);
    }
    if ((s.overrides || []).length > 8) lines.push(`- … 另有 ${(s.overrides || []).length - 8} 项`);
  }
  return lines.join('\n');
}

function formatLabelSummary(d: AssistantLaoYaTouLabelSummaryResponse): string {
  const lines = [
    `标签总行数: ${d.labels.rows.toLocaleString()} | 去重股票: ${d.labels.unique_stocks.toLocaleString()} | 标签日期数: ${d.labels.unique_label_dates.toLocaleString()}`,
    `标签日期范围: ${d.labels.min_label_date ?? '–'} → ${d.labels.max_label_date ?? '–'}`,
    `最近标签日期Top: ${(d.by_label_date || []).slice(0, 10).map(x => `${x.label_date}(${x.stocks})`).join(' | ') || '–'}`,
  ];
  return lines.join('\n');
}

function formatBaselineSummary(d: AssistantLaoYaTouBaselineEvalResponse): string {
  const b = d.baseline;
  const lines = [
    `样本数: ${b.samples.toLocaleString()} | Stage1命中: ${b.stage1_hits.toLocaleString()} | Stage2命中: ${b.stage2_hits.toLocaleString()}`,
    `Stage1召回: ${b.stage1_recall == null ? '–' : (b.stage1_recall * 100).toFixed(1) + '%'} | Stage2召回: ${b.stage2_recall == null ? '–' : (b.stage2_recall * 100).toFixed(1) + '%'}`,
    `缺数据: ${b.data_missing.toLocaleString()} | 运行异常: ${b.errors.toLocaleString()}`,
    `信号分布: signal_1=${b.by_signal?.signal_1 ?? 0} | signal_2=${b.by_signal?.signal_2 ?? 0} | signal_3=${b.by_signal?.signal_3 ?? 0}`,
    `覆盖标签日: ${(b.label_dates || []).slice(0, 10).join(' | ') || '–'}`,
  ];
  return lines.join('\n');
}

function formatDailyCompare(d: AssistantLaoYaTouDailyCompareResponse): string {
  const p = d.compare;
  const ours = d.our_screener;
  const tdx = d.tdx_upload;
  const pct = (x: number | null) => (x == null ? '–' : (x * 100).toFixed(1) + '%');
  const lines = [
    `交易日: ${d.trade_date}（请求: ${d.requested_date}${d.non_trading_day ? '，非交易日已自动回退' : ''}）`,
    `我方筛选: ${ours.count.toLocaleString()} | 已处理: ${ours.processed_stocks.toLocaleString()} / ${ours.max_stocks.toLocaleString()} | 错误: ${ours.errors.toLocaleString()} | signal_1=${ours.by_signal?.signal_1 ?? 0} signal_2=${ours.by_signal?.signal_2 ?? 0} signal_3=${ours.by_signal?.signal_3 ?? 0}`,
    `通达信上传: ${tdx.count.toLocaleString()} | 文件: ${(tdx.by_file || []).slice(0, 3).map(x => `${x.file_name}(${x.count})`).join(' | ') || '–'}`,
    `交集: ${p.intersection_count.toLocaleString()} | 我方独有: ${p.ours_only_count.toLocaleString()} | 通达信独有: ${p.tdx_only_count.toLocaleString()}`,
    `Precision(我方命中率): ${pct(p.precision)} | Recall(覆盖率): ${pct(p.recall)} | Jaccard: ${pct(p.jaccard)}`,
  ].filter(Boolean);
  return lines.join('\n');
}

export default function Assistant({ theme }: { theme: 'dark' | 'light' }) {
  const isLight = theme === 'light';
  const [mode, setMode] = useState<'rules' | 'tools'>('rules');

  const [codesInput, setCodesInput] = useState('300666,001339,000938,603220');
  const [horizon, setHorizon] = useState<'short' | 'medium' | 'long'>('short');
  const [useTripleScreen, setUseTripleScreen] = useState(true);
  const [useTurtle, setUseTurtle] = useState(true);
  const [asofDate, setAsofDate] = useState('');
  const [rulesBusy, setRulesBusy] = useState(false);
  const [rulesError, setRulesError] = useState<string | null>(null);
  const [rulesData, setRulesData] = useState<AssistantRulesAnalyzeResponse | null>(null);
  const [verifyDays, setVerifyDays] = useState(20);
  const [verifyBusy, setVerifyBusy] = useState(false);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const [verifyData, setVerifyData] = useState<AssistantRulesVerifyResponse | null>(null);
  const [fbDrafts, setFbDrafts] = useState<Record<string, { rating: number; usefulness: boolean | null; issue_type: string; comment: string; busy: boolean; ok: boolean; error: string | null }>>({});

  const [items, setItems] = useState<ChatItem[]>([
    {
      role: 'assistant',
      text: '可用指令：\n- “老鸭头股票池共同点”\n- “老鸭头标签汇总”\n- “老鸭头基线评估”\n- “老鸭头每日对比”\n- “五旗参数有哪些调整过”\n也可以直接点下面按钮。',
    },
  ]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);

  const containerStyle = useMemo(() => ({
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 12,
    height: 'calc(100vh - 40px - 16px)',
    padding: 12,
    background: isLight ? '#ffffff' : '#0a1628',
    color: isLight ? '#0f172a' : '#e5e7eb',
    colorScheme: isLight ? 'light' : 'dark',
  }), [isLight]);
  const compactField = useMemo(() => ({
    padding: '6px 8px',
    borderRadius: 10,
    border: `1px solid ${isLight ? 'rgba(15,23,42,0.16)' : 'rgba(255,255,255,0.18)'}`,
    background: isLight ? '#ffffff' : 'rgba(0,0,0,0.25)',
    color: isLight ? '#0f172a' : '#e5e7eb',
    outline: 'none',
  }), [isLight]);
  const compactSelect = useMemo(() => ({
    ...compactField,
    height: 30,
    cursor: 'pointer',
  }), [compactField]);

  const bubbleStyle = (role: 'user' | 'assistant') => ({
    maxWidth: 900,
    alignSelf: role === 'user' ? 'flex-end' : 'flex-start',
    background: role === 'user'
      ? (isLight ? 'rgba(30,64,175,0.10)' : 'rgba(255,203,5,0.10)')
      : (isLight ? 'rgba(15,23,42,0.04)' : 'rgba(255,255,255,0.07)'),
    border: `1px solid ${role === 'user'
      ? (isLight ? 'rgba(30,64,175,0.25)' : 'rgba(255,203,5,0.25)')
      : (isLight ? 'rgba(15,23,42,0.10)' : 'rgba(255,255,255,0.15)')}`,
    borderRadius: 10,
    padding: '10px 12px',
    whiteSpace: 'pre-wrap' as const,
    lineHeight: 1.5,
    fontSize: 13,
  });

  const parseCodes = (raw: string): string[] => {
    const parts = raw.replace(/\n/g, ',').replace(/\s+/g, ',').split(',').map(s => s.trim()).filter(Boolean);
    const out: string[] = [];
    const seen = new Set<string>();
    for (const p of parts) {
      if (!/^\d{6}$/.test(p)) continue;
      if (seen.has(p)) continue;
      out.push(p);
      seen.add(p);
    }
    return out;
  };

  const formatScalar = (v: any): string => {
    if (v === null || v === undefined) return '缺失';
    if (typeof v === 'string') return v.trim() ? v : '缺失';
    if (typeof v === 'number') {
      if (!Number.isFinite(v)) return '缺失';
      return String(v);
    }
    if (typeof v === 'boolean') return v ? '是' : '否';
    return String(v);
  };

  const formatEvidence = (e: any): string => {
    if (e === null || e === undefined) return '缺失';
    if (typeof e !== 'object') return formatScalar(e);
    if (Array.isArray(e)) {
      if (e.length === 0) return '[]';
      if (e.length <= 6) return e.map(x => formatScalar(x)).join('，');
      return `数组(${e.length})`;
    }
    const keys = Object.keys(e);
    if (keys.length === 0) return '{}';
    const showKeys = keys.slice(0, 8);
    const parts = showKeys.map(k => `${k}=${formatScalar((e as any)[k])}`);
    const suffix = keys.length > showKeys.length ? ` …(共${keys.length}项)` : '';
    return parts.join('，') + suffix;
  };

  const formatPlanText = (plan: any): string => {
    if (!plan || typeof plan !== 'object') return '缺失';
    const lines: string[] = [];
    const direction = plan.direction ? formatScalar(plan.direction) : '缺失';
    lines.push(`方向：${direction}`);
    if (plan.entry) {
      const entry = plan.entry;
      const trigger = entry.trigger ? formatScalar(entry.trigger) : '缺失';
      lines.push(`入场：${trigger}`);
      if (entry.note) lines.push(`入场备注：${formatScalar(entry.note)}`);
    } else {
      lines.push('入场：缺失');
    }
    if (plan.risk) {
      const risk = plan.risk;
      lines.push(`止损/失效：${risk.stop_loss ? formatScalar(risk.stop_loss) : '缺失'}`);
      lines.push(`仓位/风控：${risk.position_sizing ? formatScalar(risk.position_sizing) : '缺失'}`);
    } else {
      lines.push('止损/失效：缺失');
      lines.push('仓位/风控：缺失');
    }
    if (plan.notes) lines.push(`备注：${formatScalar(plan.notes)}`);
    return lines.join('\n');
  };

  const formatTraceText = (trace: any): string => {
    if (!Array.isArray(trace) || trace.length === 0) return '缺失';
    const lines: string[] = [];
    trace.forEach((t, idx) => {
      if (!t || typeof t !== 'object') return;
      const src = t.source || {};
      const srcTxt = src.ref || src.title || '—';
      const ok = t.result === true ? '通过' : t.result === false ? '不通过' : '未知';
      lines.push(`${idx + 1}. ${t.rule_name || t.rule_id || '规则'}：${ok}`);
      if (t.predicate) lines.push(`   条件：${formatScalar(t.predicate)}`);
      if (t.evidence !== undefined) lines.push(`   证据：${formatEvidence(t.evidence)}`);
      if (t.conclusion) lines.push(`   结论：${formatScalar(t.conclusion)}`);
      lines.push(`   出处：${formatScalar(srcTxt)}`);
    });
    return lines.join('\n');
  };

  const formatFactsText = (facts: any): string => {
    if (!facts || typeof facts !== 'object') return '缺失';
    const f = facts as any;
    const lines: string[] = [];
    lines.push(`交易日：${formatScalar(f.trade_date)}`);
    lines.push(`收盘：${formatScalar(f.close)}  涨跌幅：${formatScalar(f.pct_change)}`);
    lines.push(`均线：MA5=${formatScalar(f.ma5)}  MA10=${formatScalar(f.ma10)}  MA20=${formatScalar(f.ma20)}  MA60=${formatScalar(f.ma60)}  MA120=${formatScalar(f.ma120)}`);
    lines.push(`通道：20日最高=${formatScalar(f.hi20)}  55日最高=${formatScalar(f.hi55)}  10日最低=${formatScalar(f.lo10)}  20日最低=${formatScalar(f.lo20)}`);
    lines.push(`波动：ATR14=${formatScalar(f.atr14)}  ATR14%=${formatScalar(f.atr14_pct)}  RSI14=${formatScalar(f.rsi14)}`);
    lines.push(`量能：量比(5/20)=${formatScalar(f.vol_ratio_5_20)}`);
    lines.push(`周线趋势：趋势向上=${formatScalar(f.weekly_trend_up)}  MACD柱=${formatScalar(f.weekly_macd_hist)}  DIF=${formatScalar(f.weekly_macd)}  DEA=${formatScalar(f.weekly_signal)}`);
    const fund = f.fundamentals || {};
    lines.push(`基本面：PE=${formatScalar(fund.pe_ratio)}  PB=${formatScalar(fund.pb_ratio)}  ROE=${formatScalar(fund.roe)}  负债率=${formatScalar(fund.debt_ratio)}`);
    lines.push(`盈利/营收：profit=${formatScalar(fund.profit)}  revenue=${formatScalar(fund.revenue)}`);
    const flags = Array.isArray(fund.flags) ? fund.flags.filter(Boolean) : [];
    lines.push(`基本面标记：${flags.length ? flags.join('，') : '无'}  适配周期=${formatScalar(fund.ok_for_horizon)}`);
    return lines.join('\n');
  };

  const buildReadableText = (payload: AssistantRulesAnalyzeResponse): string => {
    const lines: string[] = [];
    lines.push(`交易法则分析`);
    lines.push(`horizon=${payload.request.horizon}  models=${(payload.request.models || []).join(',') || '—'}  trade_date=${payload.request.trade_date}${payload.request.requested_date ? `  requested_date=${payload.request.requested_date}` : ''}`);
    if (payload.run_id) lines.push(`run_id=${payload.run_id}`);
    lines.push('');
    for (const r of payload.results || []) {
      lines.push(`${r.code}${r.name ? ` ${r.name}` : ''}  trade_date=${r.trade_date}`);
      if (r.error) {
        lines.push(`错误：${r.error}`);
        lines.push('');
        continue;
      }
      if (r.explanation_text) lines.push(r.explanation_text);
      const selected = (r.models || []).find(m => m.model_id === r.selected_model_id) || (r.models || [])[0];
      if (selected?.plan) {
        lines.push('');
        lines.push('方案：');
        lines.push(formatPlanText(selected.plan));
      }
      if (r.facts) {
        lines.push('');
        lines.push('Facts（本地数据）：');
        lines.push(formatFactsText(r.facts));
      }
      if (r.trace) {
        lines.push('');
        lines.push('Trace（规则出处/证据）：');
        lines.push(formatTraceText(r.trace));
      }
      lines.push('');
      lines.push('----');
      lines.push('');
    }
    return lines.join('\n');
  };

  const downloadText = (filename: string, text: string) => {
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const defaultFbDraft = { rating: 5, usefulness: true as boolean | null, issue_type: '建议/偏好', comment: '', busy: false, ok: false, error: null as string | null };
  const getFbDraftFrom = (drafts: typeof fbDrafts, code: string) => drafts[code] || defaultFbDraft;

  async function runRulesAnalyze() {
    const codes = parseCodes(codesInput);
    if (!codes.length) {
      setRulesError('请输入股票代码（6位数字，支持逗号/空格/换行分隔）');
      setRulesData(null);
      setVerifyData(null);
      setVerifyError(null);
      return;
    }
    const enabledModels: string[] = [];
    if (useTripleScreen) enabledModels.push('triple_screen');
    if (useTurtle) enabledModels.push('turtle');
    if (!enabledModels.length) {
      setRulesError('请至少勾选一个策略模型（例如：三重滤网 或 海龟交易）');
      setRulesData(null);
      setVerifyData(null);
      setVerifyError(null);
      return;
    }
    setRulesBusy(true);
    setRulesError(null);
    setVerifyData(null);
    setVerifyError(null);
    try {
      const data = await api.assistantRulesAnalyze({
        codes: codes.join(','),
        horizon,
        date: asofDate || undefined,
        models: enabledModels,
      });
      setRulesData(data);
    } catch (e: any) {
      setRulesData(null);
      setRulesError(e?.message || String(e));
    } finally {
      setRulesBusy(false);
    }
  }

  async function runVerify() {
    const runId = rulesData?.run_id;
    if (!runId) {
      setVerifyError('当前结果没有 run_id（可能是落库失败），无法做自我验证。');
      setVerifyData(null);
      return;
    }
    setVerifyBusy(true);
    setVerifyError(null);
    try {
      const data = await api.assistantRulesVerify({ run_id: runId, forward_days: verifyDays });
      setVerifyData(data);
    } catch (e: any) {
      setVerifyData(null);
      setVerifyError(e?.message || String(e));
    } finally {
      setVerifyBusy(false);
    }
  }

  async function runMessage(text: string) {
    const msg = text.trim();
    if (!msg) return;
    setItems(prev => [...prev, { role: 'user', text: msg }]);
    setInput('');
    setBusy(true);
    try {
      const needPool = /共同点|股票池|老鸭头池|池子/.test(msg);
      const needParams = /参数|阈值|配置|默认|调整/.test(msg);
      const needLabels = /标签|label|加入日|筛选日/.test(msg);
      const needBaseline = /基线|baseline|命中|召回|评估/.test(msg);
      const needDailyCompare = /每日对比|对比|比对|通达信/.test(msg);

      if (!needPool && !needParams && !needLabels && !needBaseline && !needDailyCompare) {
        setItems(prev => [...prev, { role: 'assistant', text: '我目前只支持：老鸭头股票池共同点、老鸭头标签汇总、老鸭头基线评估、老鸭头每日对比、五旗筛选器参数与默认值差异。' }]);
        return;
      }

      if (needPool) {
        const data = await api.assistantPoolCommonalities();
        setItems(prev => [...prev, { role: 'assistant', text: formatPoolSummary(data), data }]);
      }
      if (needLabels) {
        const data = await api.assistantLaoYaTouLabelSummary();
        setItems(prev => [...prev, { role: 'assistant', text: formatLabelSummary(data), data }]);
      }
      if (needBaseline) {
        const data = await api.assistantLaoYaTouBaselineEval();
        setItems(prev => [...prev, { role: 'assistant', text: formatBaselineSummary(data), data }]);
      }
      if (needDailyCompare) {
        const data = await api.assistantLaoYaTouDailyCompare({ auto_run: true, include_codes: true, max_codes: 200 });
        setItems(prev => [...prev, { role: 'assistant', text: formatDailyCompare(data), data }]);
      }
      if (needParams) {
        const data = await api.assistantFiveFlagsParameterOverrides();
        setItems(prev => [...prev, { role: 'assistant', text: formatParamSummary(data), data }]);
      }
    } catch (e: any) {
      setItems(prev => [...prev, { role: 'assistant', text: `请求失败：${e?.message || String(e)}` }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={containerStyle}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' as const, alignItems: 'center' }}>
        <button
          onClick={() => setMode('rules')}
          disabled={rulesBusy}
          style={{
            padding: '8px 10px',
            borderRadius: 10,
            cursor: rulesBusy ? 'not-allowed' : 'pointer',
            border: `1px solid ${mode === 'rules' ? (isLight ? 'rgba(30,64,175,0.45)' : 'rgba(255,203,5,0.6)') : (isLight ? 'rgba(15,23,42,0.14)' : 'rgba(255,255,255,0.18)')}`,
            background: mode === 'rules' ? (isLight ? 'rgba(30,64,175,0.10)' : 'rgba(255,203,5,0.12)') : (isLight ? 'rgba(15,23,42,0.03)' : 'rgba(255,255,255,0.06)'),
            color: mode === 'rules' ? (isLight ? '#1e40af' : '#FFCB05') : (isLight ? '#0f172a' : '#e5e7eb'),
            fontWeight: 800,
            fontSize: 12,
          }}
        >交易法则</button>
        <button
          onClick={() => setMode('tools')}
          disabled={busy}
          style={{
            padding: '8px 10px',
            borderRadius: 10,
            cursor: busy ? 'not-allowed' : 'pointer',
            border: `1px solid ${mode === 'tools' ? (isLight ? 'rgba(30,64,175,0.45)' : 'rgba(255,203,5,0.6)') : (isLight ? 'rgba(15,23,42,0.14)' : 'rgba(255,255,255,0.18)')}`,
            background: mode === 'tools' ? (isLight ? 'rgba(30,64,175,0.10)' : 'rgba(255,203,5,0.12)') : (isLight ? 'rgba(15,23,42,0.03)' : 'rgba(255,255,255,0.06)'),
            color: mode === 'tools' ? (isLight ? '#1e40af' : '#FFCB05') : (isLight ? '#0f172a' : '#e5e7eb'),
            fontWeight: 800,
            fontSize: 12,
          }}
        >已有工具</button>
      </div>

      {mode === 'rules' ? (
        <>
          <div style={{
            borderRadius: 12,
            border: `1px solid ${isLight ? 'rgba(15,23,42,0.10)' : 'rgba(255,255,255,0.15)'}`,
            padding: 14,
            background: isLight ? 'rgba(15,23,42,0.02)' : 'rgba(0,0,0,0.18)',
          }}>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' as const, alignItems: 'center', justifyContent: 'center' }}>
              <input
                value={codesInput}
                onChange={e => setCodesInput(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') runRulesAnalyze();
                }}
                placeholder="输入股票代码：300666,001339（支持多个，逗号/空格/换行分隔）"
                style={{
                  width: 'min(900px, 100%)',
                  padding: '12px 14px',
                  borderRadius: 999,
                  border: `1px solid ${isLight ? 'rgba(15,23,42,0.16)' : 'rgba(255,255,255,0.18)'}`,
                  background: isLight ? '#ffffff' : 'rgba(0,0,0,0.25)',
                  color: isLight ? '#0f172a' : '#e5e7eb',
                  outline: 'none',
                }}
                disabled={rulesBusy}
              />
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' as const, justifyContent: 'center' }}>
                {(['short', 'medium', 'long'] as const).map(h => (
                  <button
                    key={h}
                    onClick={() => setHorizon(h)}
                    disabled={rulesBusy}
                    style={{
                      padding: '10px 12px',
                      borderRadius: 12,
                      cursor: rulesBusy ? 'not-allowed' : 'pointer',
                      border: `1px solid ${horizon === h ? (isLight ? 'rgba(30,64,175,0.45)' : 'rgba(255,203,5,0.6)') : (isLight ? 'rgba(15,23,42,0.14)' : 'rgba(255,255,255,0.18)')}`,
                      background: horizon === h ? (isLight ? 'rgba(30,64,175,0.10)' : 'rgba(255,203,5,0.12)') : (isLight ? 'rgba(15,23,42,0.03)' : 'rgba(255,255,255,0.06)'),
                      color: horizon === h ? (isLight ? '#1e40af' : '#FFCB05') : (isLight ? '#0f172a' : '#e5e7eb'),
                      fontWeight: 800,
                      fontSize: 12,
                    }}
                  >{h === 'short' ? '短线' : h === 'medium' ? '中线' : '长线'}</button>
                ))}
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' as const, justifyContent: 'center' }}>
                <button
                  onClick={() => setUseTripleScreen(v => !v)}
                  disabled={rulesBusy}
                  title="三重滤网：长周期趋势过滤 + 中周期择时 + 短周期触发"
                  style={{
                    padding: '10px 12px',
                    borderRadius: 12,
                    cursor: rulesBusy ? 'not-allowed' : 'pointer',
                    border: `1px solid ${useTripleScreen ? (isLight ? 'rgba(30,64,175,0.45)' : 'rgba(255,203,5,0.6)') : (isLight ? 'rgba(15,23,42,0.14)' : 'rgba(255,255,255,0.18)')}`,
                    background: useTripleScreen ? (isLight ? 'rgba(30,64,175,0.10)' : 'rgba(255,203,5,0.12)') : (isLight ? 'rgba(15,23,42,0.03)' : 'rgba(255,255,255,0.06)'),
                    color: useTripleScreen ? (isLight ? '#1e40af' : '#FFCB05') : (isLight ? '#0f172a' : '#e5e7eb'),
                    fontWeight: 800,
                    fontSize: 12,
                  }}
                >三重滤网</button>
                <button
                  onClick={() => setUseTurtle(v => !v)}
                  disabled={rulesBusy}
                  title="海龟：通道突破入场 + 通道退出"
                  style={{
                    padding: '10px 12px',
                    borderRadius: 12,
                    cursor: rulesBusy ? 'not-allowed' : 'pointer',
                    border: `1px solid ${useTurtle ? (isLight ? 'rgba(30,64,175,0.45)' : 'rgba(255,203,5,0.6)') : (isLight ? 'rgba(15,23,42,0.14)' : 'rgba(255,255,255,0.18)')}`,
                    background: useTurtle ? (isLight ? 'rgba(30,64,175,0.10)' : 'rgba(255,203,5,0.12)') : (isLight ? 'rgba(15,23,42,0.03)' : 'rgba(255,255,255,0.06)'),
                    color: useTurtle ? (isLight ? '#1e40af' : '#FFCB05') : (isLight ? '#0f172a' : '#e5e7eb'),
                    fontWeight: 800,
                    fontSize: 12,
                  }}
                >海龟交易</button>
              </div>
              <input
                type="date"
                value={asofDate}
                onChange={e => setAsofDate(e.target.value)}
                style={{
                  padding: '10px 12px',
                  borderRadius: 12,
                  border: `1px solid ${isLight ? 'rgba(15,23,42,0.16)' : 'rgba(255,255,255,0.18)'}`,
                  background: isLight ? '#ffffff' : 'rgba(0,0,0,0.25)',
                  color: isLight ? '#0f172a' : '#e5e7eb',
                  colorScheme: isLight ? 'light' : 'dark',
                }}
                disabled={rulesBusy}
              />
              <button
                onClick={() => runRulesAnalyze()}
                disabled={rulesBusy}
                style={{
                  padding: '10px 14px',
                  borderRadius: 12,
                  cursor: rulesBusy ? 'not-allowed' : 'pointer',
                  border: `1px solid ${isLight ? 'rgba(30,64,175,0.28)' : 'rgba(255,203,5,0.3)'}`,
                  background: isLight ? 'rgba(30,64,175,0.08)' : 'rgba(255,203,5,0.1)',
                  color: isLight ? '#1e40af' : '#FFCB05',
                  fontWeight: 900,
                }}
              >{rulesBusy ? '...' : '分析'}</button>
            </div>
            {rulesError && (
              <div style={{ marginTop: 10, color: isLight ? '#b91c1c' : '#ff6b6b', fontSize: 13, whiteSpace: 'pre-wrap' }}>
                {rulesError}
              </div>
            )}
            {rulesData && (
              <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' as const, justifyContent: 'center', fontSize: 12, opacity: 0.9 }}>
                  <div>trade_date={rulesData.request.trade_date}</div>
                  {rulesData.run_id && (
                    <div title="run_id=本次分析的唯一编号，用于绑定反馈/自我验证/复现同一次结果">
                      analysis_id={rulesData.run_id}
                    </div>
                  )}
                </div>
                {rulesData.run_id && (
                  <details style={{ textAlign: 'center' }}>
                    <summary style={{ cursor: 'pointer', fontWeight: 800, fontSize: 12, opacity: 0.9 }}>analysis_id（run_id）是什么？</summary>
                    <div style={{ marginTop: 8, fontSize: 12, lineHeight: 1.55, opacity: 0.9 }}>
                      它是这次分析的唯一编号：用于把你的反馈精确绑定到这次结果、用于后续“自我验证（forward_days）”、也用于在规则更新后复现同一次输出做对比。
                    </div>
                  </details>
                )}
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' as const, justifyContent: 'center' }}>
                <button
                  onClick={() => downloadText(`assistant_rules_${rulesData.request.trade_date}.json`, JSON.stringify(rulesData, null, 2))}
                  style={{
                    padding: '8px 10px',
                    borderRadius: 10,
                    cursor: 'pointer',
                    border: `1px solid ${isLight ? 'rgba(15,23,42,0.14)' : 'rgba(255,255,255,0.18)'}`,
                    background: isLight ? '#ffffff' : 'rgba(255,255,255,0.06)',
                    color: isLight ? '#0f172a' : '#e5e7eb',
                    fontWeight: 800,
                    fontSize: 12,
                  }}
                >下载 JSON</button>
                <button
                  onClick={() => downloadText(`assistant_rules_${rulesData.request.trade_date}.txt`, buildReadableText(rulesData))}
                  style={{
                    padding: '8px 10px',
                    borderRadius: 10,
                    cursor: 'pointer',
                    border: `1px solid ${isLight ? 'rgba(15,23,42,0.14)' : 'rgba(255,255,255,0.18)'}`,
                    background: isLight ? '#ffffff' : 'rgba(255,255,255,0.06)',
                    color: isLight ? '#0f172a' : '#e5e7eb',
                    fontWeight: 800,
                    fontSize: 12,
                  }}
                >下载文本</button>
                <button
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(buildReadableText(rulesData));
                    } catch {}
                  }}
                  style={{
                    padding: '8px 10px',
                    borderRadius: 10,
                    cursor: 'pointer',
                    border: `1px solid ${isLight ? 'rgba(15,23,42,0.14)' : 'rgba(255,255,255,0.18)'}`,
                    background: isLight ? '#ffffff' : 'rgba(255,255,255,0.06)',
                    color: isLight ? '#0f172a' : '#e5e7eb',
                    fontWeight: 800,
                    fontSize: 12,
                  }}
                >复制文本</button>
                {rulesData.run_id && (
                  <button
                    onClick={async () => {
                      try {
                        await navigator.clipboard.writeText(rulesData.run_id || '');
                      } catch {}
                    }}
                    title="复制分析编号（analysis_id/run_id），用于反馈/验证/复现"
                    style={{
                      padding: '8px 10px',
                      borderRadius: 10,
                      cursor: 'pointer',
                      border: `1px solid ${isLight ? 'rgba(15,23,42,0.14)' : 'rgba(255,255,255,0.18)'}`,
                      background: isLight ? '#ffffff' : 'rgba(255,255,255,0.06)',
                      color: isLight ? '#0f172a' : '#e5e7eb',
                      fontWeight: 800,
                      fontSize: 12,
                    }}
                  >复制 run_id</button>
                )}
                </div>

                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' as const, justifyContent: 'center', alignItems: 'center' }}>
                  <input
                    type="number"
                    value={verifyDays}
                    min={1}
                    max={252}
                    onChange={e => setVerifyDays(Number(e.target.value || 0))}
                    style={{
                      width: 120,
                      padding: '8px 10px',
                      borderRadius: 10,
                      border: `1px solid ${isLight ? 'rgba(15,23,42,0.16)' : 'rgba(255,255,255,0.18)'}`,
                      background: isLight ? '#ffffff' : 'rgba(0,0,0,0.25)',
                      color: isLight ? '#0f172a' : '#e5e7eb',
                    }}
                    disabled={verifyBusy}
                  />
                  <button
                    onClick={() => runVerify()}
                    disabled={verifyBusy}
                    style={{
                      padding: '8px 10px',
                      borderRadius: 10,
                      cursor: verifyBusy ? 'not-allowed' : 'pointer',
                      border: `1px solid ${isLight ? 'rgba(15,23,42,0.14)' : 'rgba(255,255,255,0.18)'}`,
                      background: isLight ? '#ffffff' : 'rgba(255,255,255,0.06)',
                      color: isLight ? '#0f172a' : '#e5e7eb',
                      fontWeight: 800,
                      fontSize: 12,
                    }}
                  >{verifyBusy ? '...' : '自我验证（forward_days）'}</button>
                </div>
                {verifyError && (
                  <div style={{ color: isLight ? '#b91c1c' : '#ff6b6b', fontSize: 13, whiteSpace: 'pre-wrap', textAlign: 'center' }}>
                    {verifyError}
                  </div>
                )}
                {verifyData && (
                  <details style={{ textAlign: 'left' }}>
                    <summary style={{ cursor: 'pointer', fontWeight: 900, fontSize: 12, textAlign: 'center' }}>验证结果</summary>
                    <pre style={{
                      marginTop: 8,
                      padding: 10,
                      overflowX: 'auto',
                      borderRadius: 10,
                      border: `1px solid ${isLight ? 'rgba(15,23,42,0.10)' : 'rgba(255,255,255,0.12)'}`,
                      background: isLight ? '#ffffff' : 'rgba(0,0,0,0.35)',
                      color: isLight ? '#0f172a' : '#e5e7eb',
                      fontSize: 12,
                      lineHeight: 1.45,
                      whiteSpace: 'pre-wrap',
                    }}>{JSON.stringify(verifyData, null, 2)}</pre>
                  </details>
                )}
              </div>
            )}
          </div>

          <div style={{
            flex: 1,
            overflowY: 'auto',
            borderRadius: 12,
            border: `1px solid ${isLight ? 'rgba(15,23,42,0.10)' : 'rgba(255,255,255,0.15)'}`,
            padding: 12,
            background: isLight ? 'rgba(15,23,42,0.02)' : 'rgba(0,0,0,0.18)',
          }}>
            {!rulesData ? (
              <div style={{ color: isLight ? 'rgba(15,23,42,0.65)' : 'rgba(229,231,235,0.65)', fontSize: 13, lineHeight: 1.6 }}>
                输入股票代码后点击“分析”。输出包含：facts（本地数据库计算）、模型候选（海龟/三重滤网）、可追溯 trace（每条规则的出处引用与证据）。
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {(rulesData.results || []).map((r) => {
                  const selected = (r.models || []).find(m => m.model_id === r.selected_model_id) || (r.models || [])[0];
                  return (
                    <div key={r.code} style={{
                      borderRadius: 12,
                      border: `1px solid ${isLight ? 'rgba(15,23,42,0.12)' : 'rgba(255,255,255,0.14)'}`,
                      background: isLight ? '#ffffff' : 'rgba(0,0,0,0.25)',
                      padding: 12,
                    }}>
                      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' as const, alignItems: 'baseline' }}>
                        <div style={{ fontWeight: 900, fontSize: 14 }}>
                          {r.code}{r.name ? ` ${r.name}` : ''}
                        </div>
                        <div style={{ fontSize: 12, opacity: 0.8 }}>
                          trade_date={r.trade_date} horizon={r.horizon}
                        </div>
                        {r.selected_model_id && (
                          <div style={{ fontSize: 12, opacity: 0.9 }}>
                            selected={r.selected_model_id}
                          </div>
                        )}
                      </div>
                      {r.error ? (
                        <div style={{ marginTop: 8, color: isLight ? '#b91c1c' : '#ff6b6b', fontSize: 13 }}>
                          {r.error}
                        </div>
                      ) : (
                        <>
                          {r.explanation_text && (
                            <pre style={{
                              marginTop: 10,
                              padding: 10,
                              overflowX: 'auto',
                              borderRadius: 10,
                              border: `1px solid ${isLight ? 'rgba(15,23,42,0.10)' : 'rgba(255,255,255,0.12)'}`,
                              background: isLight ? 'rgba(15,23,42,0.02)' : 'rgba(255,255,255,0.06)',
                              color: isLight ? '#0f172a' : '#e5e7eb',
                              fontSize: 12,
                              lineHeight: 1.45,
                              whiteSpace: 'pre-wrap',
                            }}>{r.explanation_text}</pre>
                          )}
                          {selected?.plan && (
                            <details style={{ marginTop: 10 }}>
                              <summary style={{ cursor: 'pointer', fontWeight: 800, fontSize: 12 }}>可操作方案</summary>
                              <pre style={{
                                marginTop: 8,
                                padding: 10,
                                overflowX: 'auto',
                                borderRadius: 10,
                                border: `1px solid ${isLight ? 'rgba(15,23,42,0.10)' : 'rgba(255,255,255,0.12)'}`,
                                background: isLight ? 'rgba(15,23,42,0.02)' : 'rgba(255,255,255,0.06)',
                                color: isLight ? '#0f172a' : '#e5e7eb',
                                fontSize: 12,
                                lineHeight: 1.45,
                                whiteSpace: 'pre-wrap',
                              }}>{formatPlanText(selected.plan)}</pre>
                            </details>
                          )}
                          {r.trace && (
                            <details style={{ marginTop: 10 }}>
                              <summary style={{ cursor: 'pointer', fontWeight: 800, fontSize: 12 }}>Trace（规则出处/证据）</summary>
                              <pre style={{
                                marginTop: 8,
                                padding: 10,
                                overflowX: 'auto',
                                borderRadius: 10,
                                border: `1px solid ${isLight ? 'rgba(15,23,42,0.10)' : 'rgba(255,255,255,0.12)'}`,
                                background: isLight ? 'rgba(15,23,42,0.02)' : 'rgba(255,255,255,0.06)',
                                color: isLight ? '#0f172a' : '#e5e7eb',
                                fontSize: 12,
                                lineHeight: 1.45,
                                whiteSpace: 'pre-wrap',
                              }}>{formatTraceText(r.trace)}</pre>
                            </details>
                          )}
                          {r.facts && (
                            <details style={{ marginTop: 10 }}>
                              <summary style={{ cursor: 'pointer', fontWeight: 800, fontSize: 12 }}>Facts（本地数据计算）</summary>
                              <pre style={{
                                marginTop: 8,
                                padding: 10,
                                overflowX: 'auto',
                                borderRadius: 10,
                                border: `1px solid ${isLight ? 'rgba(15,23,42,0.10)' : 'rgba(255,255,255,0.12)'}`,
                                background: isLight ? 'rgba(15,23,42,0.02)' : 'rgba(255,255,255,0.06)',
                                color: isLight ? '#0f172a' : '#e5e7eb',
                                fontSize: 12,
                                lineHeight: 1.45,
                                whiteSpace: 'pre-wrap',
                              }}>{formatFactsText(r.facts)}</pre>
                            </details>
                          )}
                          <details style={{ marginTop: 10 }}>
                            <summary style={{ cursor: 'pointer', fontWeight: 800, fontSize: 12 }}>反馈（用于迭代/修正规则）</summary>
                            <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
                              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' as const, alignItems: 'center' }}>
                                <label style={{ fontSize: 12, opacity: 0.9 }}>
                                  评分
                                  <select
                                    value={getFbDraftFrom(fbDrafts, r.code).rating}
                                    onChange={e => {
                                      const v = Number(e.target.value);
                                      setFbDrafts(prev => {
                                        const cur = getFbDraftFrom(prev, r.code);
                                        return { ...prev, [r.code]: { ...cur, rating: v, ok: false, error: null } };
                                      });
                                    }}
                                    style={{ ...compactSelect, marginLeft: 6 }}
                                  >
                                    {[5, 4, 3, 2, 1].map(x => <option key={x} value={x}>{x}</option>)}
                                  </select>
                                </label>
                                <label style={{ fontSize: 12, opacity: 0.9 }}>
                                  有用
                                  <select
                                    value={String(getFbDraftFrom(fbDrafts, r.code).usefulness)}
                                    onChange={e => {
                                      const v = e.target.value === 'true' ? true : e.target.value === 'false' ? false : null;
                                      setFbDrafts(prev => {
                                        const cur = getFbDraftFrom(prev, r.code);
                                        return { ...prev, [r.code]: { ...cur, usefulness: v, ok: false, error: null } };
                                      });
                                    }}
                                    style={{ ...compactSelect, marginLeft: 6 }}
                                  >
                                    <option value="true">是</option>
                                    <option value="false">否</option>
                                    <option value="null">不确定</option>
                                  </select>
                                </label>
                                <label style={{ fontSize: 12, opacity: 0.9 }}>
                                  问题类型
                                  <select
                                    value={getFbDraftFrom(fbDrafts, r.code).issue_type}
                                    onChange={e => {
                                      const v = e.target.value;
                                      setFbDrafts(prev => {
                                        const cur = getFbDraftFrom(prev, r.code);
                                        return { ...prev, [r.code]: { ...cur, issue_type: v, ok: false, error: null } };
                                      });
                                    }}
                                    style={{ ...compactSelect, marginLeft: 6 }}
                                  >
                                    {['数据缺失', '规则不合理', '阈值不合适', '解释不清晰', '风险控制不合理', '建议/偏好', '其他'].map(x => (
                                      <option key={x} value={x}>{x}</option>
                                    ))}
                                  </select>
                                </label>
                              </div>
                              <textarea
                                value={getFbDraftFrom(fbDrafts, r.code).comment}
                                onChange={e => {
                                  const v = e.target.value;
                                  setFbDrafts(prev => {
                                    const cur = getFbDraftFrom(prev, r.code);
                                    return { ...prev, [r.code]: { ...cur, comment: v, ok: false, error: null } };
                                  });
                                }}
                                placeholder="补充说明：哪里有用/没用？哪些条件应该调整？缺了哪些本地数据？"
                                rows={3}
                                style={{
                                  width: '100%',
                                  padding: '10px 12px',
                                  borderRadius: 10,
                                  border: `1px solid ${isLight ? 'rgba(15,23,42,0.16)' : 'rgba(255,255,255,0.18)'}`,
                                  background: isLight ? '#ffffff' : 'rgba(0,0,0,0.25)',
                                  color: isLight ? '#0f172a' : '#e5e7eb',
                                  resize: 'vertical',
                                }}
                              />
                              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' as const, alignItems: 'center' }}>
                                <button
                                  onClick={async () => {
                                    const draft = getFbDraftFrom(fbDrafts, r.code);
                                    setFbDrafts(prev => {
                                      const cur = getFbDraftFrom(prev, r.code);
                                      return { ...prev, [r.code]: { ...cur, busy: true, ok: false, error: null } };
                                    });
                                    try {
                                      await api.assistantSubmitFeedback({
                                        run_id: rulesData?.run_id,
                                        code: r.code,
                                        rating: draft.rating,
                                        usefulness: draft.usefulness === null ? undefined : draft.usefulness,
                                        issue_type: draft.issue_type,
                                        comment: draft.comment,
                                        extra: {
                                          selected_model_id: r.selected_model_id,
                                          horizon: r.horizon,
                                          trade_date: r.trade_date,
                                        },
                                      });
                                      setFbDrafts(prev => {
                                        const cur = getFbDraftFrom(prev, r.code);
                                        return { ...prev, [r.code]: { ...cur, busy: false, ok: true, error: null } };
                                      });
                                    } catch (e: any) {
                                      setFbDrafts(prev => {
                                        const cur = getFbDraftFrom(prev, r.code);
                                        return { ...prev, [r.code]: { ...cur, busy: false, ok: false, error: e?.message || String(e) } };
                                      });
                                    }
                                  }}
                                  disabled={getFbDraftFrom(fbDrafts, r.code).busy}
                                  style={{
                                    padding: '8px 10px',
                                    borderRadius: 10,
                                    cursor: getFbDraftFrom(fbDrafts, r.code).busy ? 'not-allowed' : 'pointer',
                                    border: `1px solid ${isLight ? 'rgba(30,64,175,0.28)' : 'rgba(255,203,5,0.3)'}`,
                                    background: isLight ? 'rgba(30,64,175,0.08)' : 'rgba(255,203,5,0.1)',
                                    color: isLight ? '#1e40af' : '#FFCB05',
                                    fontWeight: 800,
                                    fontSize: 12,
                                  }}
                                >{getFbDraftFrom(fbDrafts, r.code).busy ? '...' : '提交反馈'}</button>
                                {getFbDraftFrom(fbDrafts, r.code).ok && (
                                  <div style={{ fontSize: 12, opacity: 0.85 }}>已提交</div>
                                )}
                                {getFbDraftFrom(fbDrafts, r.code).error && (
                                  <div style={{ fontSize: 12, color: isLight ? '#b91c1c' : '#ff6b6b', whiteSpace: 'pre-wrap' }}>
                                    {getFbDraftFrom(fbDrafts, r.code).error}
                                  </div>
                                )}
                              </div>
                            </div>
                          </details>
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </>
      ) : (
        <>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' as const }}>
            <button
              onClick={() => runMessage('老鸭头股票池共同点')}
              disabled={busy}
              style={{
                padding: '8px 10px',
                borderRadius: 10,
                cursor: busy ? 'not-allowed' : 'pointer',
                border: `1px solid ${isLight ? 'rgba(30,64,175,0.28)' : 'rgba(255,203,5,0.3)'}`,
                background: isLight ? 'rgba(30,64,175,0.08)' : 'rgba(255,203,5,0.1)',
                color: isLight ? '#1e40af' : '#FFCB05',
                fontWeight: 700,
                fontSize: 12,
              }}
            >分析老鸭头池</button>
            <button
              onClick={() => runMessage('老鸭头标签汇总')}
              disabled={busy}
              style={{
                padding: '8px 10px',
                borderRadius: 10,
                cursor: busy ? 'not-allowed' : 'pointer',
                border: `1px solid ${isLight ? 'rgba(30,64,175,0.28)' : 'rgba(255,203,5,0.3)'}`,
                background: isLight ? 'rgba(30,64,175,0.08)' : 'rgba(255,203,5,0.1)',
                color: isLight ? '#1e40af' : '#FFCB05',
                fontWeight: 700,
                fontSize: 12,
              }}
            >标签汇总</button>
            <button
              onClick={() => runMessage('老鸭头基线评估')}
              disabled={busy}
              style={{
                padding: '8px 10px',
                borderRadius: 10,
                cursor: busy ? 'not-allowed' : 'pointer',
                border: `1px solid ${isLight ? 'rgba(30,64,175,0.28)' : 'rgba(255,203,5,0.3)'}`,
                background: isLight ? 'rgba(30,64,175,0.08)' : 'rgba(255,203,5,0.1)',
                color: isLight ? '#1e40af' : '#FFCB05',
                fontWeight: 700,
                fontSize: 12,
              }}
            >基线评估</button>
            <button
              onClick={() => runMessage('老鸭头每日对比')}
              disabled={busy}
              style={{
                padding: '8px 10px',
                borderRadius: 10,
                cursor: busy ? 'not-allowed' : 'pointer',
                border: `1px solid ${isLight ? 'rgba(30,64,175,0.28)' : 'rgba(255,203,5,0.3)'}`,
                background: isLight ? 'rgba(30,64,175,0.08)' : 'rgba(255,203,5,0.1)',
                color: isLight ? '#1e40af' : '#FFCB05',
                fontWeight: 700,
                fontSize: 12,
              }}
            >每日对比</button>
            <button
              onClick={() => runMessage('五旗参数有哪些调整过')}
              disabled={busy}
              style={{
                padding: '8px 10px',
                borderRadius: 10,
                cursor: busy ? 'not-allowed' : 'pointer',
                border: `1px solid ${isLight ? 'rgba(30,64,175,0.28)' : 'rgba(255,203,5,0.3)'}`,
                background: isLight ? 'rgba(30,64,175,0.08)' : 'rgba(255,203,5,0.1)',
                color: isLight ? '#1e40af' : '#FFCB05',
                fontWeight: 700,
                fontSize: 12,
              }}
            >查看五旗参数差异</button>
          </div>

          <div style={{
            flex: 1,
            overflowY: 'auto',
            borderRadius: 12,
            border: `1px solid ${isLight ? 'rgba(15,23,42,0.10)' : 'rgba(255,255,255,0.15)'}`,
            padding: 12,
            background: isLight ? 'rgba(15,23,42,0.02)' : 'rgba(0,0,0,0.18)',
          }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {items.map((it, idx) => (
                <div key={idx} style={bubbleStyle(it.role)}>
                  <div>{it.text}</div>
                  {'data' in it && it.data && (
                    <pre style={{
                      marginTop: 10,
                      padding: 10,
                      overflowX: 'auto',
                      borderRadius: 10,
                      border: `1px solid ${isLight ? 'rgba(15,23,42,0.10)' : 'rgba(255,255,255,0.12)'}`,
                      background: isLight ? '#ffffff' : 'rgba(0,0,0,0.35)',
                      color: isLight ? '#0f172a' : '#e5e7eb',
                      fontSize: 12,
                      lineHeight: 1.45,
                      whiteSpace: 'pre-wrap',
                    }}>{JSON.stringify(it.data, null, 2)}</pre>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') runMessage(input);
              }}
              placeholder="输入：老鸭头股票池共同点 / 老鸭头标签汇总 / 老鸭头基线评估 / 老鸭头每日对比 / 五旗参数有哪些调整过"
              style={{
                flex: 1,
                padding: '10px 12px',
                borderRadius: 10,
                border: `1px solid ${isLight ? 'rgba(15,23,42,0.16)' : 'rgba(255,255,255,0.18)'}`,
                background: isLight ? '#ffffff' : 'rgba(0,0,0,0.25)',
                color: isLight ? '#0f172a' : '#e5e7eb',
              }}
              disabled={busy}
            />
            <button
              onClick={() => runMessage(input)}
              disabled={busy}
              style={{
                padding: '10px 14px',
                borderRadius: 10,
                cursor: busy ? 'not-allowed' : 'pointer',
                border: `1px solid ${isLight ? 'rgba(30,64,175,0.28)' : 'rgba(255,203,5,0.3)'}`,
                background: isLight ? 'rgba(30,64,175,0.08)' : 'rgba(255,203,5,0.1)',
                color: isLight ? '#1e40af' : '#FFCB05',
                fontWeight: 700,
              }}
            >{busy ? '...' : '发送'}</button>
          </div>
        </>
      )}
    </div>
  );
}
