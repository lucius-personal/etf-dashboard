'use client';

import { useState, useEffect, useRef } from 'react';
import { supabase } from '@/lib/supabase';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, CartesianGrid, ComposedChart, Line,
  PieChart, Pie, Cell,
} from 'recharts';

/* ═══════ Theme ═══════ */
const C = {
  bg: '#0c0e14', s1: '#141720', s2: '#1a1e2a', s3: '#222738',
  border: 'rgba(255,255,255,0.06)', bh: 'rgba(255,255,255,0.1)',
  gold: '#e2b84a', goldDim: 'rgba(226,184,74,0.12)', goldGlow: 'rgba(226,184,74,0.3)',
  up: '#34d399', upDim: 'rgba(52,211,153,0.12)',
  dn: '#f87171', dnDim: 'rgba(248,113,113,0.12)',
  blue: '#60a5fa', blueDim: 'rgba(96,165,250,0.12)',
  tx: '#eae8e3', t2: '#9a978e', t3: '#5e5c56',
};

/* ═══════ Tiny UI Pieces ═══════ */

function Card({ children, style }) {
  return <div style={{ background: C.s1, border: `1px solid ${C.border}`, borderRadius: 14, ...style }}>{children}</div>;
}

function Stat({ label, value, unit, color, alert }) {
  return (
    <Card style={{ padding: '14px 16px', position: 'relative', overflow: 'hidden' }}>
      {alert && <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: C.dn }} />}
      <div style={{ fontSize: 10, color: C.t3, letterSpacing: 0.8, marginBottom: 6, textTransform: 'uppercase' }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: color || C.tx, letterSpacing: -0.5 }}>{value}</div>
      {unit && <div style={{ fontSize: 11, color: alert ? C.dn : C.t2, marginTop: 3, fontWeight: alert ? 600 : 400 }}>{unit}</div>}
    </Card>
  );
}

function StarIcon({ filled, size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={filled ? C.gold : 'none'}
      stroke={filled ? C.gold : C.t3} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

function TabBar({ tabs, active, onChange }) {
  return (
    <div style={{ display: 'flex', gap: 2, background: C.s1, borderRadius: 12, padding: 3, border: `1px solid ${C.border}`, overflowX: 'auto' }}>
      {tabs.map(t => (
        <button key={t.key} onClick={() => onChange(t.key)} style={{
          padding: '8px 12px', fontSize: 11, fontFamily: 'inherit',
          fontWeight: active === t.key ? 600 : 400, borderRadius: 10,
          border: 'none', background: active === t.key ? C.s2 : 'transparent',
          color: active === t.key ? C.tx : C.t2,
          cursor: 'pointer', transition: 'all .2s', whiteSpace: 'nowrap', flexShrink: 0,
        }}>{t.label}</button>
      ))}
    </div>
  );
}

function TT({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: C.s2, border: `1px solid ${C.bh}`, borderRadius: 10, padding: '8px 12px', boxShadow: '0 8px 24px rgba(0,0,0,.6)' }}>
      <div style={{ fontSize: 10, color: C.t2, marginBottom: 3 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ fontSize: 13, fontWeight: 600, color: p.color || C.tx }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toLocaleString() : p.value}
        </div>
      ))}
    </div>
  );
}

function LoadingBox({ text }) {
  return (
    <Card style={{ padding: 40, textAlign: 'center' }}>
      <div className="loading-pulse" style={{ fontSize: 14, color: C.t2 }}>{text || '載入中...'}</div>
    </Card>
  );
}

function EmptyBox({ text, action, onAction }) {
  return (
    <Card style={{ padding: 40, textAlign: 'center' }}>
      <div style={{ fontSize: 14, color: C.t2, marginBottom: action ? 12 : 0 }}>{text}</div>
      {action && (
        <button onClick={onAction} style={{
          padding: '8px 20px', fontSize: 12, fontFamily: 'inherit', fontWeight: 600,
          background: C.gold, color: C.bg, border: 'none', borderRadius: 10, cursor: 'pointer',
        }}>{action}</button>
      )}
    </Card>
  );
}

/* ═══════ Dropdown ═══════ */

function ETFDropdown({ categories, selectedId, onSelect, pinned, onTogglePin }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const ref = useRef(null);
  const allEtfs = categories.flatMap(c => c.items);
  const selected = allEtfs.find(e => e.id === selectedId);

  useEffect(() => {
    const h = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  const filtered = search.trim()
    ? categories.map(cat => ({ ...cat, items: cat.items.filter(e => e.id.includes(search) || e.name.includes(search)) })).filter(c => c.items.length > 0)
    : categories;

  const up = selected && (selected.spread || 0) >= 0;

  return (
    <div ref={ref} style={{ position: 'relative', marginBottom: 16 }}>
      <button onClick={() => { setOpen(!open); setSearch(''); }} style={{
        width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 14px', background: C.s1, border: `1px solid ${open ? C.gold : C.border}`,
        borderRadius: 14, cursor: 'pointer', fontFamily: 'inherit',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 34, height: 34, borderRadius: 9, background: C.goldDim, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, color: C.gold }}>
            {selected?.id?.slice(0, 4) || '----'}
          </div>
          <div style={{ textAlign: 'left' }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: C.tx }}>{selected?.id || '選擇 ETF'} <span style={{ fontWeight: 400, color: C.t2, fontSize: 12 }}>{selected?.name}</span></div>
          </div>
        </div>
        <div style={{ width: 26, height: 26, borderRadius: 7, background: C.s2, display: 'flex', alignItems: 'center', justifyContent: 'center', transform: open ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform .2s', fontSize: 11, color: C.t2 }}>▾</div>
      </button>
      {open && (
        <div style={{ position: 'absolute', top: 'calc(100% + 6px)', left: 0, right: 0, background: C.s1, border: `1px solid ${C.bh}`, borderRadius: 14, overflow: 'hidden', boxShadow: '0 16px 48px rgba(0,0,0,.6)', zIndex: 100, maxHeight: 420, overflowY: 'auto' }}>
          <div style={{ padding: '10px 12px', borderBottom: `1px solid ${C.border}` }}>
            <input type="text" placeholder="搜尋代碼或名稱…" value={search} onChange={e => setSearch(e.target.value)} autoFocus
              style={{ width: '100%', padding: '9px 12px', background: C.s2, border: `1px solid ${C.border}`, borderRadius: 10, color: C.tx, fontSize: 13, fontFamily: 'inherit', outline: 'none', boxSizing: 'border-box' }} />
          </div>
          {filtered.map(cat => (
            <div key={cat.label}>
              <div style={{ padding: '10px 14px 5px', fontSize: 10, fontWeight: 600, letterSpacing: 1.5, color: C.t3, textTransform: 'uppercase', background: C.bg }}>{cat.label}</div>
              {cat.items.map(etf => (
                <div key={etf.id} style={{ display: 'flex', alignItems: 'center', background: etf.id === selectedId ? C.s2 : 'transparent', borderLeft: etf.id === selectedId ? `3px solid ${C.gold}` : '3px solid transparent' }}>
                  <button onClick={e => { e.stopPropagation(); onTogglePin(etf.id); }} style={{ padding: '12px 4px 12px 10px', background: 'none', border: 'none', cursor: 'pointer', display: 'flex' }}>
                    <StarIcon filled={pinned.includes(etf.id)} size={13} />
                  </button>
                  <button onClick={() => { onSelect(etf.id); setOpen(false); }} style={{ flex: 1, display: 'flex', justifyContent: 'space-between', padding: '12px 14px 12px 6px', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit' }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: etf.id === selectedId ? C.gold : C.tx }}>{etf.id} <span style={{ fontSize: 11, color: C.t2, fontWeight: 400 }}>{etf.name}</span></span>
                    <span style={{ fontSize: 12, color: C.tx, fontWeight: 600 }}>{etf.close ? `$${etf.close}` : ''}</span>
                  </button>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ═══════ Watchlist Table ═══════ */

function WatchlistTable({ pinned, etfMap, selectedId, onSelect }) {
  if (pinned.length === 0) return null;
  return (
    <Card style={{ overflow: 'hidden', marginBottom: 16 }}>
      <div style={{ padding: '12px 16px 8px', borderBottom: `1px solid ${C.border}`, display: 'flex', alignItems: 'center', gap: 6 }}>
        <StarIcon filled size={12} />
        <span style={{ fontSize: 12, fontWeight: 600, color: C.tx }}>追蹤清單總覽</span>
      </div>
      <div className="table-scroll">
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, minWidth: 420 }}>
          <thead>
            <tr>{['ETF', '收盤', '漲跌', '殖利率', '成交量'].map(h => (
              <th key={h} style={{ padding: '8px 10px', textAlign: h === 'ETF' ? 'left' : 'right', fontWeight: 500, color: C.t3, fontSize: 10, borderBottom: `1px solid ${C.border}` }}>{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {pinned.map(id => {
              const e = etfMap[id];
              if (!e) return null;
              const up = (e.spread || 0) >= 0;
              return (
                <tr key={id} onClick={() => onSelect(id)} style={{ borderBottom: `1px solid ${C.border}`, cursor: 'pointer', background: id === selectedId ? C.s2 : 'transparent' }}>
                  <td style={{ padding: '10px', fontWeight: 600, color: id === selectedId ? C.gold : C.tx, whiteSpace: 'nowrap' }}>{id} <span style={{ fontWeight: 400, color: C.t2, fontSize: 10 }}>{e.name?.slice(0, 5)}</span></td>
                  <td style={{ padding: '10px', textAlign: 'right', fontWeight: 600, color: C.tx }}>{e.close ? `$${e.close}` : '—'}</td>
                  <td style={{ padding: '10px', textAlign: 'right', color: up ? C.up : C.dn, fontWeight: 600 }}>{e.spread ? `${up ? '+' : ''}${e.spread}` : '—'}</td>
                  <td style={{ padding: '10px', textAlign: 'right', color: e.yield ? C.gold : C.t3 }}>{e.yield ? `${e.yield}%` : '—'}</td>
                  <td style={{ padding: '10px', textAlign: 'right', color: C.t2 }}>{e.volume ? `${Math.round(e.volume / 1000)}K` : '—'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/* ═══════ Panels ═══════ */

function ChartPanel({ prices }) {
  if (!prices.length) return <EmptyBox text="尚無股價資料，請先同步資料" />;
  const last = prices[prices.length - 1];
  const first = prices[0];
  const color = last?.close >= first?.close ? C.up : C.dn;
  return (
    <Card style={{ padding: '20px 8px 12px 0' }}>
      <div style={{ paddingLeft: 20, marginBottom: 12 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: C.tx }}>近期走勢</span>
        <span style={{ fontSize: 10, color: C.t3, marginLeft: 8 }}>{prices.length} 個交易日</span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={prices.map(p => ({ date: p.date.slice(5), price: p.close }))} margin={{ top: 4, right: 12, left: 4, bottom: 4 }}>
          <defs><linearGradient id="pg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={color} stopOpacity={0.25} /><stop offset="100%" stopColor={color} stopOpacity={0} /></linearGradient></defs>
          <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fontSize: 9, fill: C.t3 }} interval={Math.floor(prices.length / 5)} />
          <YAxis domain={['auto', 'auto']} axisLine={false} tickLine={false} tick={{ fontSize: 9, fill: C.t3 }} width={44} />
          <Tooltip content={<TT />} />
          <Area type="monotone" dataKey="price" name="收盤" stroke={color} strokeWidth={2} fill="url(#pg)" dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </Card>
  );
}

function InvestorPanel({ data }) {
  if (!data.length) return <EmptyBox text="尚無法人資料" />;
  // Group by date
  const byDate = {};
  data.forEach(d => {
    if (!byDate[d.date]) byDate[d.date] = { date: d.date.slice(5) };
    const net = (d.buy || 0) - (d.sell || 0);
    if (d.investor_type === 'Foreign_Investor') byDate[d.date]['外資'] = (byDate[d.date]['外資'] || 0) + net;
    else if (d.investor_type === 'Foreign_Dealer_Self') byDate[d.date]['外資'] = (byDate[d.date]['外資'] || 0) + net;
    else if (d.investor_type === 'Investment_Trust') byDate[d.date]['投信'] = (byDate[d.date]['投信'] || 0) + net;
    else if (d.investor_type === 'Dealer_self' || d.investor_type === 'Dealer_Hedging') byDate[d.date]['自營商'] = (byDate[d.date]['自營商'] || 0) + net;
  });
  const chartData = Object.values(byDate).slice(-15);

  return (
    <Card style={{ padding: '20px 8px 12px 0' }}>
      <div style={{ paddingLeft: 20, marginBottom: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: C.tx }}>三大法人買賣超</span>
        <span style={{ fontSize: 10, color: C.t3, marginLeft: 8 }}>張</span>
      </div>
      <div style={{ display: 'flex', gap: 10, paddingLeft: 20, marginBottom: 12, fontSize: 10 }}>
        {[{ n: '外資', c: C.blue }, { n: '投信', c: C.gold }, { n: '自營商', c: C.t2 }].map(l => (
          <span key={l.n} style={{ color: l.c }}>● {l.n}</span>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={chartData} margin={{ top: 4, right: 12, left: 4, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
          <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fontSize: 9, fill: C.t3 }} />
          <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 9, fill: C.t3 }} width={44} />
          <Tooltip contentStyle={{ background: C.s2, border: `1px solid ${C.bh}`, borderRadius: 10, fontSize: 11, color: C.tx }} />
          <Bar dataKey="外資" fill={C.blue} radius={[3, 3, 0, 0]} maxBarSize={10} />
          <Bar dataKey="投信" fill={C.gold} radius={[3, 3, 0, 0]} maxBarSize={10} />
          <Bar dataKey="自營商" fill={C.t2} radius={[3, 3, 0, 0]} maxBarSize={10} />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

function ValuationPanel({ etfInfo, valuations }) {
  const isBond = etfInfo?.category === '債券型';
  const isNoDist = etfInfo?.is_distributing === false;
  const latest = valuations[valuations.length - 1];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {!isNoDist && !isBond && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Stat label="本益比 PER" value={latest?.per || '—'} />
          <Stat label="殖利率" value={latest?.dividend_yield ? `${latest.dividend_yield}%` : '—'} color={C.gold} />
        </div>
      )}
      {isBond && <Stat label="殖利率" value={latest?.dividend_yield ? `${latest.dividend_yield}%` : '—'} unit="年化" color={C.gold} />}
      {isNoDist && <Stat label="收益分配" value="不配息" unit="股利自動再投入，複利成長" color={C.gold} />}

      {/* 費用率 */}
      <Card style={{ padding: 16 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: C.tx, marginBottom: 12 }}>費用率</div>
        <div style={{ fontSize: 28, fontWeight: 700, color: C.gold }}>{etfInfo?.expense_ratio || '—'}%</div>
        <div style={{ fontSize: 11, color: C.t2, marginTop: 4 }}>年度總費用率（經理費 + 保管費 + 其他）</div>
      </Card>

      {/* 估值歷史 */}
      {valuations.length > 3 && (
        <Card style={{ padding: '16px 8px 12px 0' }}>
          <div style={{ paddingLeft: 16, marginBottom: 10, fontSize: 12, fontWeight: 600, color: C.tx }}>殖利率趨勢</div>
          <ResponsiveContainer width="100%" height={100}>
            <AreaChart data={valuations.slice(-30).map(v => ({ date: v.date?.slice(5), yld: v.dividend_yield }))}>
              <Area type="monotone" dataKey="yld" stroke={C.gold} strokeWidth={1.5} fill={C.goldDim} dot={false} />
              <XAxis dataKey="date" hide />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  );
}

function DividendPanel({ dividends, etfInfo }) {
  const isNoDist = etfInfo?.is_distributing === false;
  if (isNoDist) return <EmptyBox text="此 ETF 不配息，股利自動再投入以複利成長" />;
  if (!dividends.length) return <EmptyBox text="尚無配息資料" />;

  let cum = 0;
  return (
    <Card style={{ overflow: 'hidden' }}>
      <div style={{ padding: '14px 16px 8px', borderBottom: `1px solid ${C.border}` }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: C.tx }}>歷次配息紀錄</span>
      </div>
      <div className="table-scroll">
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, minWidth: 340 }}>
          <thead><tr>{['年度', '現金股利', '除息日', '累計'].map(h => (
            <th key={h} style={{ padding: '10px 12px', textAlign: h === '年度' ? 'left' : 'right', fontWeight: 500, color: C.t3, fontSize: 10, borderBottom: `1px solid ${C.border}` }}>{h}</th>
          ))}</tr></thead>
          <tbody>
            {dividends.slice(0, 12).map((d, i) => {
              cum += d.cash_dividend || 0;
              return (
                <tr key={i} style={{ borderBottom: `1px solid ${C.border}` }}>
                  <td style={{ padding: '11px 12px', color: C.tx, fontWeight: 500 }}>{d.year || d.ex_date}</td>
                  <td style={{ padding: '11px 12px', textAlign: 'right', color: C.gold, fontWeight: 600 }}>${d.cash_dividend?.toFixed(2) || '—'}</td>
                  <td style={{ padding: '11px 12px', textAlign: 'right', color: C.t2 }}>{d.ex_date || '—'}</td>
                  <td style={{ padding: '11px 12px', textAlign: 'right', color: C.t2, fontSize: 11 }}>${cum.toFixed(2)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/* ═══════ Portfolio (local state for now) ═══════ */

function PortfolioPanel({ etfMap }) {
  const [holdings, setHoldings] = useState([
    { id: '0050', shares: 5000, cost: 182.30 },
    { id: '0056', shares: 10000, cost: 36.50 },
    { id: '009816', shares: 20000, cost: 10.00 },
  ]);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ id: '0050', shares: '', cost: '' });

  const totalCost = holdings.reduce((s, h) => s + h.shares * h.cost, 0);
  const totalValue = holdings.reduce((s, h) => {
    const e = etfMap[h.id];
    return s + (e?.close ? h.shares * e.close : 0);
  }, 0);
  const pl = totalValue - totalCost;
  const plPct = totalCost > 0 ? ((pl / totalCost) * 100).toFixed(2) : '0';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Card style={{ padding: 16 }}>
          <div style={{ fontSize: 10, color: C.t3, marginBottom: 6 }}>持倉市值</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: C.tx }}>${Math.round(totalValue).toLocaleString()}</div>
          <div style={{ fontSize: 11, color: C.t2, marginTop: 3 }}>成本 ${Math.round(totalCost).toLocaleString()}</div>
        </Card>
        <Card style={{ padding: 16 }}>
          <div style={{ fontSize: 10, color: C.t3, marginBottom: 6 }}>未實現損益</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: pl >= 0 ? C.up : C.dn }}>{pl >= 0 ? '+' : ''}{Math.round(pl).toLocaleString()}</div>
          <div style={{ fontSize: 11, color: pl >= 0 ? C.up : C.dn, fontWeight: 600, marginTop: 3 }}>{pl >= 0 ? '+' : ''}{plPct}%</div>
        </Card>
      </div>

      <Card style={{ overflow: 'hidden' }}>
        <div style={{ padding: '14px 16px 8px', borderBottom: `1px solid ${C.border}`, display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: C.tx }}>持倉明細</span>
          <button onClick={() => setAdding(true)} style={{ fontSize: 11, color: C.gold, background: C.goldDim, border: 'none', padding: '4px 12px', borderRadius: 8, cursor: 'pointer', fontFamily: 'inherit' }}>+ 新增</button>
        </div>
        <div className="table-scroll">
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, minWidth: 380 }}>
            <thead><tr>{['ETF', '股數', '成本', '現價', '損益', ''].map(h => (
              <th key={h} style={{ padding: '10px', textAlign: h === 'ETF' ? 'left' : 'right', fontWeight: 500, color: C.t3, fontSize: 10, borderBottom: `1px solid ${C.border}` }}>{h}</th>
            ))}</tr></thead>
            <tbody>
              {holdings.map((h, idx) => {
                const e = etfMap[h.id];
                const val = e?.close ? h.shares * e.close : 0;
                const cst = h.shares * h.cost;
                const hpl = val - cst;
                return (
                  <tr key={idx} style={{ borderBottom: `1px solid ${C.border}` }}>
                    <td style={{ padding: '11px 10px', fontWeight: 600, color: C.tx }}>{h.id}</td>
                    <td style={{ padding: '11px 10px', textAlign: 'right', color: C.tx }}>{h.shares.toLocaleString()}</td>
                    <td style={{ padding: '11px 10px', textAlign: 'right', color: C.t2 }}>${h.cost}</td>
                    <td style={{ padding: '11px 10px', textAlign: 'right', color: C.tx, fontWeight: 500 }}>{e?.close ? `$${e.close}` : '—'}</td>
                    <td style={{ padding: '11px 10px', textAlign: 'right', color: hpl >= 0 ? C.up : C.dn, fontWeight: 600 }}>{hpl ? `${hpl >= 0 ? '+' : ''}${Math.round(hpl).toLocaleString()}` : '—'}</td>
                    <td style={{ padding: '11px 6px', textAlign: 'right' }}>
                      <button onClick={() => setHoldings(p => p.filter((_, i) => i !== idx))} style={{ background: 'none', border: 'none', color: C.t3, cursor: 'pointer', fontSize: 14 }}>✕</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {adding && (
          <div style={{ padding: '12px 16px', borderTop: `1px solid ${C.border}`, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <input type="text" placeholder="代碼" value={form.id} onChange={e => setForm(p => ({ ...p, id: e.target.value }))} style={{ width: 70, padding: '8px 10px', background: C.s2, border: `1px solid ${C.border}`, borderRadius: 8, color: C.tx, fontSize: 12, fontFamily: 'inherit' }} />
            <input type="number" placeholder="股數" value={form.shares} onChange={e => setForm(p => ({ ...p, shares: e.target.value }))} style={{ width: 70, padding: '8px 10px', background: C.s2, border: `1px solid ${C.border}`, borderRadius: 8, color: C.tx, fontSize: 12, fontFamily: 'inherit' }} />
            <input type="number" placeholder="成本價" value={form.cost} onChange={e => setForm(p => ({ ...p, cost: e.target.value }))} style={{ width: 80, padding: '8px 10px', background: C.s2, border: `1px solid ${C.border}`, borderRadius: 8, color: C.tx, fontSize: 12, fontFamily: 'inherit' }} />
            <button onClick={() => { if (form.shares && form.cost) { setHoldings(p => [...p, { id: form.id, shares: Number(form.shares), cost: Number(form.cost) }]); setAdding(false); setForm({ id: '0050', shares: '', cost: '' }); } }} style={{ padding: '8px 16px', background: C.gold, border: 'none', borderRadius: 8, color: C.bg, fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>確認</button>
            <button onClick={() => setAdding(false)} style={{ padding: '8px 12px', background: 'none', border: `1px solid ${C.border}`, borderRadius: 8, color: C.t2, fontSize: 12, cursor: 'pointer', fontFamily: 'inherit' }}>取消</button>
          </div>
        )}
      </Card>
    </div>
  );
}

/* ═══════ MAIN DASHBOARD ═══════ */

export default function Dashboard() {
  const [etfList, setEtfList] = useState([]);
  const [selectedId, setSelectedId] = useState('0050');
  const [pinned, setPinned] = useState(['0050', '009816', '0056', '00878', '00919']);
  const [tab, setTab] = useState('chart');
  const [prices, setPrices] = useState([]);
  const [valuations, setValuations] = useState([]);
  const [institutional, setInstitutional] = useState([]);
  const [dividends, setDividends] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [user, setUser] = useState(null);

  // Build etfMap: { '0050': { id, name, close, spread, yield, volume, ... } }
  const [etfMap, setEtfMap] = useState({});

  // Auth: listen for login/logout
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user || null);
    });
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user || null);
    });
    return () => subscription.unsubscribe();
  }, []);

  async function handleLogin() {
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin },
    });
  }

  async function handleLogout() {
    await supabase.auth.signOut();
    setUser(null);
  }

  // Load ETF list from Supabase
  useEffect(() => {
    async function load() {
      const { data } = await supabase.from('etf_info').select('*').order('id');
      if (data) {
        setEtfList(data);
        // For each ETF, get latest price and valuation
        const map = {};
        for (const etf of data) {
          map[etf.id] = { ...etf, close: null, spread: null, volume: null, yield: null };
        }
        // Get latest prices for all ETFs
        const { data: latestPrices } = await supabase
          .from('etf_daily_price')
          .select('etf_id, date, close, spread, volume')
          .order('date', { ascending: false });

        if (latestPrices) {
          const seen = {};
          latestPrices.forEach(p => {
            if (!seen[p.etf_id] && map[p.etf_id]) {
              map[p.etf_id].close = p.close;
              map[p.etf_id].spread = p.spread;
              map[p.etf_id].volume = p.volume;
              seen[p.etf_id] = true;
            }
          });
        }

        // Get latest yields
        const { data: latestVals } = await supabase
          .from('etf_valuation')
          .select('etf_id, dividend_yield')
          .order('date', { ascending: false });

        if (latestVals) {
          const seen = {};
          latestVals.forEach(v => {
            if (!seen[v.etf_id] && map[v.etf_id]) {
              map[v.etf_id].yield = v.dividend_yield;
              seen[v.etf_id] = true;
            }
          });
        }

        setEtfMap(map);
      }
      setLoading(false);
    }
    load();
  }, [syncing]); // reload after sync

  // Load detail data for selected ETF
  useEffect(() => {
    async function loadDetail() {
      if (!selectedId) return;

      const [priceRes, valRes, instRes, divRes] = await Promise.all([
        supabase.from('etf_daily_price').select('*').eq('etf_id', selectedId).order('date', { ascending: true }).limit(60),
        supabase.from('etf_valuation').select('*').eq('etf_id', selectedId).order('date', { ascending: true }).limit(60),
        supabase.from('etf_institutional').select('*').eq('etf_id', selectedId).order('date', { ascending: true }).limit(60),
        supabase.from('etf_dividend').select('*').eq('etf_id', selectedId).order('ex_date', { ascending: false }).limit(12),
      ]);

      setPrices(priceRes.data || []);
      setValuations(valRes.data || []);
      setInstitutional(instRes.data || []);
      setDividends(divRes.data || []);
    }
    loadDetail();
  }, [selectedId, syncing]);

  // Group ETFs by category for dropdown
  const categories = [];
  const catMap = {};
  etfList.forEach(e => {
    const cat = e.category || '其他';
    if (!catMap[cat]) { catMap[cat] = { label: cat, items: [] }; categories.push(catMap[cat]); }
    catMap[cat].items.push({ ...e, ...etfMap[e.id] });
  });

  const togglePin = id => setPinned(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id]);

  const currentEtf = etfMap[selectedId] || {};
  const up = (currentEtf.spread || 0) >= 0;
  const hasData = prices.length > 0;

  // Sync data from FinMind
  async function handleSync() {
    setSyncing(true);
    try {
      const res = await fetch('/api/sync');
      const json = await res.json();
      alert(`同步完成！\n股價: ${json.results?.price || 0} 筆\n估值: ${json.results?.valuation || 0} 筆\n法人: ${json.results?.institutional || 0} 筆${json.results?.errors?.length ? '\n\n錯誤: ' + json.results.errors.join('\n') : ''}`);
    } catch (e) {
      alert('同步失敗: ' + e.message);
    }
    setSyncing(false);
  }

  const tabs = [
    { key: 'chart', label: '走勢' },
    { key: 'investors', label: '法人' },
    { key: 'valuation', label: '估值' },
    { key: 'dividend', label: '配息' },
    { key: 'portfolio', label: '持倉' },
  ];

  if (loading) return (
    <div style={{ minHeight: '100vh', background: C.bg, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="loading-pulse" style={{ color: C.t2, fontSize: 16 }}>載入中...</div>
    </div>
  );

  return (
    <div style={{ minHeight: '100vh', background: C.bg, color: C.tx }}>
      {/* Ambient glow */}
      <div style={{ position: 'fixed', inset: 0, pointerEvents: 'none', background: 'radial-gradient(ellipse at 30% 0%, rgba(226,184,74,0.04) 0%, transparent 55%), radial-gradient(ellipse at 80% 100%, rgba(96,165,250,0.03) 0%, transparent 50%)' }} />

      <div style={{ position: 'relative', zIndex: 1, maxWidth: 520, margin: '0 auto', padding: '0 16px 60px' }}>

        {/* Header */}
        <div style={{ paddingTop: 28, marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: C.up, boxShadow: `0 0 10px ${C.up}` }} />
              <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: 2.5, color: C.gold, textTransform: 'uppercase' }}>台股 ETF 儀表板</span>
            </div>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <button onClick={handleSync} disabled={syncing} style={{
                padding: '6px 14px', fontSize: 11, fontFamily: 'inherit', fontWeight: 600,
                background: syncing ? C.s2 : C.goldDim, color: syncing ? C.t3 : C.gold,
                border: `1px solid ${C.goldGlow}`, borderRadius: 10, cursor: syncing ? 'wait' : 'pointer',
              }}>
                {syncing ? '同步中...' : '⟳ 同步'}
              </button>
              {user ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: '50%', overflow: 'hidden',
                    border: `1.5px solid ${C.gold}`, flexShrink: 0,
                  }}>
                    {user.user_metadata?.avatar_url ? (
                      <img src={user.user_metadata.avatar_url} alt="" width={28} height={28} style={{ borderRadius: '50%' }} />
                    ) : (
                      <div style={{ width: 28, height: 28, background: C.goldDim, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 600, color: C.gold }}>
                        {(user.email || '?')[0].toUpperCase()}
                      </div>
                    )}
                  </div>
                  <button onClick={handleLogout} style={{
                    padding: '6px 10px', fontSize: 10, fontFamily: 'inherit',
                    background: 'none', color: C.t3, border: `1px solid ${C.border}`,
                    borderRadius: 8, cursor: 'pointer',
                  }}>
                    登出
                  </button>
                </div>
              ) : (
                <button onClick={handleLogin} style={{
                  padding: '6px 14px', fontSize: 11, fontFamily: 'inherit', fontWeight: 600,
                  background: C.s2, color: C.tx, border: `1px solid ${C.border}`,
                  borderRadius: 10, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5,
                }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg>
                  登入
                </button>
              )}
            </div>
          </div>

          {/* Watchlist */}
          <WatchlistTable pinned={pinned} etfMap={etfMap} selectedId={selectedId} onSelect={setSelectedId} />

          {/* Dropdown */}
          <ETFDropdown categories={categories} selectedId={selectedId} onSelect={setSelectedId} pinned={pinned} onTogglePin={togglePin} />

          {/* Hero Price */}
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 40, fontWeight: 800, letterSpacing: -1.5, lineHeight: 1 }}>
              {currentEtf.close ? `$${currentEtf.close}` : '—'}
            </span>
            {currentEtf.spread != null && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: up ? C.upDim : C.dnDim, padding: '5px 12px', borderRadius: 20, fontSize: 14, fontWeight: 700, color: up ? C.up : C.dn }}>
                {up ? '▲' : '▼'} {Math.abs(currentEtf.spread)}
              </span>
            )}
            <button onClick={() => togglePin(selectedId)} style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '5px 10px', borderRadius: 20, background: pinned.includes(selectedId) ? C.goldDim : C.s2, border: `1px solid ${pinned.includes(selectedId) ? C.goldGlow : C.border}`, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11, color: pinned.includes(selectedId) ? C.gold : C.t2 }}>
              <StarIcon filled={pinned.includes(selectedId)} size={11} />{pinned.includes(selectedId) ? '已追蹤' : '追蹤'}
            </button>
          </div>

          {!hasData && (
            <div style={{ marginTop: 12, padding: '12px 16px', background: C.goldDim, borderRadius: 10, fontSize: 12, color: C.gold }}>
              資料庫目前是空的。請點右上角「⟳ 同步資料」從 FinMind 撈取第一批資料！
            </div>
          )}
        </div>

        {/* Stats */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 20 }}>
          <Stat label="殖利率"
            value={currentEtf.is_distributing === false ? '不配息' : currentEtf.yield ? `${currentEtf.yield}%` : '—'}
            unit={currentEtf.is_distributing === false ? '複利再投入' : '年化'}
            color={C.gold} />
          <Stat label="成交量" value={currentEtf.volume ? `${Math.round(currentEtf.volume / 1000).toLocaleString()}K` : '—'} unit="張" />
        </div>

        {/* Tabs */}
        <div style={{ marginBottom: 16 }}><TabBar tabs={tabs} active={tab} onChange={setTab} /></div>

        {/* Panels */}
        {tab === 'chart' && <ChartPanel prices={prices} />}
        {tab === 'investors' && <InvestorPanel data={institutional} />}
        {tab === 'valuation' && <ValuationPanel etfInfo={etfMap[selectedId]} valuations={valuations} />}
        {tab === 'dividend' && <DividendPanel dividends={dividends} etfInfo={etfMap[selectedId]} />}
        {tab === 'portfolio' && (user ? <PortfolioPanel etfMap={etfMap} /> : (
          <Card style={{ padding: 40, textAlign: 'center' }}>
            <div style={{ fontSize: 14, color: C.t2, marginBottom: 16 }}>登入後即可使用持倉記帳功能</div>
            <button onClick={handleLogin} style={{
              padding: '10px 24px', fontSize: 13, fontFamily: 'inherit', fontWeight: 600,
              background: C.gold, color: C.bg, border: 'none', borderRadius: 10, cursor: 'pointer',
              display: 'inline-flex', alignItems: 'center', gap: 8,
            }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg>
              用 Google 帳號登入
            </button>
          </Card>
        ))}

        {/* Footer */}
        <div style={{ marginTop: 24, padding: '14px 16px', background: C.s1, borderRadius: 14, border: `1px solid ${C.border}`, fontSize: 11, color: C.t3, display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <span>FinMind + TWSE API</span>
          <span>Supabase → Next.js → Vercel</span>
        </div>
      </div>
    </div>
  );
}
