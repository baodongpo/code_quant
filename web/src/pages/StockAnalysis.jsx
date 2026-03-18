/**
 * pages/StockAnalysis.jsx — 个股分析页（主页面 /）
 *
 * 布局：
 *   - 顶部导航栏（股票选择 / 周期切换 / 时间范围 / 跳转 Watchlist）
 *   - 主图（K线 + MA + BOLL + 成交量）
 *   - 副图（MACD / RSI / KDJ）
 *   - 底部信息条
 *   - 60 秒自动刷新
 */
import React, { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { fetchStocks, fetchKline } from '../api/client.js'
import StockSelector     from '../components/StockSelector.jsx'
import PeriodSelector    from '../components/PeriodSelector.jsx'
import TimeRangeSelector from '../components/TimeRangeSelector.jsx'
import MainChart         from '../components/MainChart.jsx'
import MACDPanel         from '../components/MACDPanel.jsx'
import RSIPanel          from '../components/RSIPanel.jsx'
import KDJPanel          from '../components/KDJPanel.jsx'
import BottomBar         from '../components/BottomBar.jsx'

function daysAgo(n) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

const today = () => new Date().toISOString().slice(0, 10)

export default function StockAnalysis() {
  const [stocks,    setStocks]    = useState([])
  const [code,      setCode]      = useState(null)
  const [period,    setPeriod]    = useState('1D')
  const [startDate, setStartDate] = useState(daysAgo(365))
  const [endDate,   setEndDate]   = useState(today())
  const [data,      setData]      = useState(null)   // API 返回的完整数据
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState(null)
  const [lastUpdate,setLastUpdate]= useState(null)
  const timerRef = useRef(null)

  // 加载股票列表
  useEffect(() => {
    fetchStocks()
      .then(list => {
        setStocks(list)
        if (list.length > 0 && !code) setCode(list[0].stock_code)
      })
      .catch(e => setError(e.message))
  }, [])

  // 加载 K线+指标数据
  const loadData = useCallback(async () => {
    if (!code) return
    setLoading(true)
    setError(null)
    try {
      const result = await fetchKline(code, period, startDate, endDate)
      setData(result)
      setLastUpdate(new Date().toLocaleTimeString('zh-CN'))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [code, period, startDate, endDate])

  // 切换参数时重新拉取
  useEffect(() => {
    loadData()
  }, [loadData])

  // 60 秒自动刷新
  useEffect(() => {
    timerRef.current = setInterval(loadData, 60_000)
    return () => clearInterval(timerRef.current)
  }, [loadData])

  const bars      = data?.bars        || []
  const indicators= data?.indicators  || {}
  const signals   = data?.signals     || {}
  const dates     = bars.map(b => b.date)
  const latestBar = bars[bars.length - 1] || null

  // RSI 最新值
  const rsiList = indicators?.RSI?.RSI14 || []
  const rsiValue = rsiList.slice().reverse().find(v => v != null) ?? null

  return (
    <div style={{ minHeight: '100vh', background: '#0d1117', color: '#e6edf3' }}>
      {/* 顶部导航栏 */}
      <div style={{
        display:     'flex',
        alignItems:  'center',
        flexWrap:    'wrap',
        gap:         12,
        padding:     '10px 16px',
        background:  '#161b22',
        borderBottom:'1px solid #21262d',
      }}>
        {/* Logo / 标题 */}
        <span style={{ fontWeight: 700, fontSize: 15, color: '#e6edf3', marginRight: 8, whiteSpace: 'nowrap' }}>
          📈 AI 量化决策
        </span>

        <StockSelector stocks={stocks} value={code} onChange={setCode} />
        <PeriodSelector value={period} onChange={setPeriod} />
        <TimeRangeSelector
          start={startDate} end={endDate}
          onChange={(s, e) => { setStartDate(s); setEndDate(e) }}
        />

        {/* 右侧信息 */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
          {loading && <span style={{ fontSize: 12, color: '#f0c040' }}>⏳ 加载中...</span>}
          {lastUpdate && !loading && (
            <span style={{ fontSize: 11, color: '#8b949e' }}>更新: {lastUpdate}</span>
          )}
          <Link
            to="/watchlist"
            style={{
              fontSize: 13, color: '#79c0ff', textDecoration: 'none',
              border: '1px solid #30363d', borderRadius: 6,
              padding: '4px 10px',
            }}
          >
            Watchlist总览 →
          </Link>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div style={{ padding: '8px 16px', background: '#3a1a1a', color: '#ff7b72',
                      fontSize: 13, borderBottom: '1px solid #f85149' }}>
          ⚠️ {error}
        </div>
      )}

      {/* 图表区域 */}
      <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {bars.length > 0 ? (
          <>
            <MainChart bars={bars} indicators={indicators} />
            <MACDPanel dates={dates} macd={indicators.MACD} signal={signals.MACD} />
            <RSIPanel  dates={dates} rsi={indicators.RSI}   signal={signals.RSI}  />
            <KDJPanel  dates={dates} kdj={indicators.KDJ}   signal={signals.KDJ}  />
          </>
        ) : (
          !loading && (
            <div style={{ textAlign: 'center', padding: '80px 0', color: '#8b949e', fontSize: 14 }}>
              {code ? '暂无数据（请确认 OpenD 已运行且数据已同步）' : '请选择股票'}
            </div>
          )
        )}
      </div>

      {/* 底部信息条 */}
      {latestBar && (
        <BottomBar latestBar={latestBar} signals={signals} rsiValue={rsiValue} />
      )}
    </div>
  )
}
