/**
 * api/client.js — Axios 封装，统一 API 调用
 */
import axios from 'axios'
import { getToken } from '../utils/auth.js'

const BASE_URL = import.meta.env.VITE_API_BASE || ''

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
})

/** 请求拦截器：自动附加 X-Access-Token 请求头（token 为空时不附加）*/
client.interceptors.request.use(config => {
  const token = getToken()
  if (token) config.headers['X-Access-Token'] = token
  return config
})

/** 获取活跃股票列表 */
export async function fetchStocks() {
  const res = await client.get('/api/stocks')
  return res.data.stocks  // [{stock_code, market, ...}]
}

/**
 * 获取 K线 + 指标数据
 * @param {string} code
 * @param {string} period  1D | 1W | 1M
 * @param {string|null} start  YYYY-MM-DD
 * @param {string|null} end    YYYY-MM-DD
 * @param {string} adj  qfq | raw
 */
export async function fetchKline(code, period, start = null, end = null, adj = 'qfq') {
  const params = { code, period, adj }
  if (start) params.start = start
  if (end)   params.end   = end
  const res = await client.get('/api/kline', { params })
  return res.data
}

/** 获取 Watchlist 总览信号 */
export async function fetchWatchlistSummary() {
  const res = await client.get('/api/watchlist/summary')
  return res.data.summary  // [...]
}

/** 获取指标清单 */
export async function fetchIndicators() {
  const res = await client.get('/api/indicators')
  return res.data.indicators
}

/** 获取健康检查状态（含版本号） */
export async function fetchHealth() {
  const res = await client.get('/api/health')
  return res.data  // { status, timestamp, version }
}
