import { createClient } from '@supabase/supabase-js';

// 用 service role key 才能寫入公開資料表（繞過 RLS）
// 這個 route 跑在 server 端，不會暴露 key
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
);

const FINMIND_BASE = 'https://api.finmindtrade.com/api/v4/data';
const FINMIND_TOKEN = process.env.FINMIND_API_TOKEN;

// 通用 FinMind 請求
async function fetchFM(dataset, params = {}) {
  const query = new URLSearchParams({ dataset, ...params });
  const headers = FINMIND_TOKEN ? { Authorization: `Bearer ${FINMIND_TOKEN}` } : {};
  const res = await fetch(`${FINMIND_BASE}?${query}`, { headers });
  const json = await res.json();
  if (json.msg !== 'success') throw new Error(`FinMind error: ${json.msg}`);
  return json.data || [];
}

// 取得今天日期字串 (台灣時間)
function todayStr() {
  const d = new Date(Date.now() + 8 * 3600 * 1000);
  return d.toISOString().split('T')[0];
}

function daysAgo(n) {
  const d = new Date(Date.now() + 8 * 3600 * 1000);
  d.setDate(d.getDate() - n);
  return d.toISOString().split('T')[0];
}

export async function GET(request) {
  // 簡單的安全檢查（上線後可用更嚴格的 token）
  const { searchParams } = new URL(request.url);
  const secret = searchParams.get('secret');
  if (secret !== process.env.SYNC_SECRET && process.env.SYNC_SECRET) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const today = todayStr();
  const startDate = daysAgo(5); // 撈最近 5 天確保補到假日空缺
  const results = { price: 0, valuation: 0, institutional: 0, errors: [] };

  // 1. 取得所有追蹤的 ETF
  const { data: etfs } = await supabase.from('etf_info').select('id');
  const etfIds = etfs?.map(e => e.id) || [];

  // 2. 撈股價
  for (const etfId of etfIds) {
    try {
      const prices = await fetchFM('TaiwanStockPrice', {
        data_id: etfId,
        start_date: startDate,
      });
      if (prices.length > 0) {
        const rows = prices.map(p => ({
          etf_id: etfId,
          date: p.date,
          open: p.open,
          high: p.max,
          low: p.min,
          close: p.close,
          volume: p.Trading_Volume,
          spread: p.spread,
        }));
        const { error } = await supabase
          .from('etf_daily_price')
          .upsert(rows, { onConflict: 'etf_id,date' });
        if (error) results.errors.push(`price ${etfId}: ${error.message}`);
        else results.price += rows.length;
      }
    } catch (e) {
      results.errors.push(`price ${etfId}: ${e.message}`);
    }
  }

  // 3. 撈估值（PER / PBR / 殖利率）
  for (const etfId of etfIds) {
    try {
      const vals = await fetchFM('TaiwanStockPER', {
        data_id: etfId,
        start_date: startDate,
      });
      if (vals.length > 0) {
        const rows = vals.map(v => ({
          etf_id: etfId,
          date: v.date,
          dividend_yield: v.dividend_yield,
          per: v.PER,
          pbr: v.PBR,
        }));
        const { error } = await supabase
          .from('etf_valuation')
          .upsert(rows, { onConflict: 'etf_id,date' });
        if (error) results.errors.push(`valuation ${etfId}: ${error.message}`);
        else results.valuation += rows.length;
      }
    } catch (e) {
      results.errors.push(`valuation ${etfId}: ${e.message}`);
    }
  }

  // 4. 撈三大法人
  for (const etfId of etfIds) {
    try {
      const invs = await fetchFM('TaiwanStockInstitutionalInvestorsBuySell', {
        data_id: etfId,
        start_date: startDate,
      });
      if (invs.length > 0) {
        const rows = invs.map(i => ({
          etf_id: etfId,
          date: i.date,
          investor_type: i.name,
          buy: i.buy,
          sell: i.sell,
        }));
        const { error } = await supabase
          .from('etf_institutional')
          .upsert(rows, { onConflict: 'etf_id,date,investor_type' });
        if (error) results.errors.push(`institutional ${etfId}: ${error.message}`);
        else results.institutional += rows.length;
      }
    } catch (e) {
      results.errors.push(`institutional ${etfId}: ${e.message}`);
    }
  }

  return Response.json({
    success: true,
    synced_at: new Date().toISOString(),
    etf_count: etfIds.length,
    results,
  });
}
