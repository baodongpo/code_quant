/**
 * pages/WatchlistPage.jsx — Watchlist 总览页 /watchlist
 *
 * 显示所有活跃股票的最新指标信号，含综合信号。
 * 点击行跳转到个股分析页。
 */
import React, { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { fetchWatchlistSummary } from '../api/client.js'
import SignalTag from '../components/SignalTag.jsx'
import { getSignalLabel } from '../utils/signals.js'

function fmt(v, d = 2) {
  if (v == null) return '-'
  return typeof v === 'number' ? v.toFixed(d) : String(v)
}

const colStyle = { padding: '10px 14px', fontSize: 13, borderBottom: '1px solid #21262d', textAlign: 'center' }
const headStyle = {
  ...colStyle,
  background: '#161b22', color: '#8b949e', fontWeight: 600,
  position: 'sticky', top: 0, zIndex: 1,
}

export default function WatchlistPage() {
  const [summary,    setSummary]    = useState([])
  const [loading,    setLoading]    = useState(false)
  const [error,      setError]      = useState(null)
  const [lastUpdate, setLastUpdate] = useState(null)
  const navigate = useNavigate()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchWatchlistSummary()
      setSummary(data || [])
      setLastUpdate(new Date().toLocaleTimeString('zh-CN'))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div style={{ minHeight: '100vh', background: '#0d1117', color: '#e6edf3' }}>
      {/* 顶部栏 */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '10px 16px', background: '#161b22',
        borderBottom: '1px solid #21262d',
      }}>
        <span style={{ fontWeight: 700, fontSize: 15 }}>📋 Watchlist 总览</span>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
          {loading && <span style={{ fontSize: 12, color: '#f0c040' }}>⏳ 加载中...</span>}
          {lastUpdate && !loading && (
            <span style={{ fontSize: 11, color: '#8b949e' }}>更新: {lastUpdate}</span>
          )}
          <button
            onClick={load}
            style={{
              fontSize: 12, color: '#79c0ff', background: 'transparent',
              border: '1px solid #30363d', borderRadius: 6, padding: '4px 10px', cursor: 'pointer',
            }}
          >
            刷新
          </button>
          <Link to="/" style={{
            fontSize: 13, color: '#8b949e', textDecoration: 'none',
            border: '1px solid #30363d', borderRadius: 6, padding: '4px 10px',
          }}>
            ← 返回
          </Link>
        </div>
      </div>

      {error && (
        <div style={{ padding: '8px 16px', background: '#3a1a1a', color: '#ff7b72',
                      fontSize: 13, borderBottom: '1px solid #f85149' }}>
          ⚠️ {error}
        </div>
      )}

      {/* 表格 */}
      <div style={{ padding: '16px', overflowX: 'auto' }}>
        <table style={{
          width: '100%', borderCollapse: 'collapse',
          background: '#0d1117', borderRadius: 8, overflow: 'hidden',
          border: '1px solid #21262d',
        }}>
          <thead>
            <tr>
              <th style={{ ...headStyle, textAlign: 'left' }}>股票</th>
              <th style={{ ...headStyle, textAlign: 'right' }}>最新价</th>
              <th style={{ ...headStyle, textAlign: 'right' }}>涨跌幅</th>
              <th style={headStyle}>RSI</th>
              <th style={headStyle}>MACD</th>
              <th style={headStyle}>KDJ</th>
              <th style={headStyle}>综合信号</th>
            </tr>
          </thead>
          <tbody>
            {summary.length === 0 && !loading && (
              <tr>
                <td colSpan={7} style={{ ...colStyle, textAlign: 'center', color: '#8b949e', padding: '40px' }}>
                  暂无数据（请确认 watchlist 中有活跃股票且数据已同步）
                </td>
              </tr>
            )}
            {summary.map(item => {
              const sig   = item.signals || {}
              const rsi   = sig.RSI || 'neutral'
              const macd  = sig.MACD || 'neutral'
              const kdj   = sig.KDJ || 'neutral'
              const comp  = sig.composite || 'neutral'
              const changePct = item.change_pct
              const changeColor = changePct == null ? '#8b949e'
                : changePct >= 0 ? '#ef5350' : '#26a69a'
              const rsiVal = sig.RSI_value

              return (
                <tr
                  key={item.stock_code}
                  onClick={() => navigate(`/?code=${item.stock_code}`)}
                  style={{ cursor: 'pointer', transition: 'background 0.1s' }}
                  onMouseEnter={e => e.currentTarget.style.background = '#161b22'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  {/* 股票名称 + 代码 */}
                  <td style={{ ...colStyle, textAlign: 'left' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      {item.name && (
                        <span style={{ fontWeight: 700, fontSize: 13, color: '#e6edf3' }}>
                          {item.name}
                        </span>
                      )}
                      <span style={{ fontSize: 11, color: '#79c0ff', fontFamily: 'monospace' }}>
                        {item.stock_code}
                      </span>
                    </div>
                  </td>

                  {/* 最新价 */}
                  <td style={{ ...colStyle, textAlign: 'right', fontWeight: 600 }}>
                    {fmt(item.latest_close)}
                  </td>

                  {/* 涨跌幅 */}
                  <td style={{ ...colStyle, textAlign: 'right', color: changeColor, fontWeight: 600 }}>
                    {changePct == null ? '-' : `${changePct >= 0 ? '+' : ''}${changePct}%`}
                  </td>

                  {/* RSI */}
                  <td style={colStyle}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                      {rsiVal != null && (
                        <span style={{ fontWeight: 600, fontSize: 13 }}>{rsiVal.toFixed(1)}</span>
                      )}
                      <SignalTag indicator="RSI" signal={rsi} />
                    </div>
                  </td>

                  {/* MACD */}
                  <td style={colStyle}>
                    <SignalTag indicator="MACD" signal={macd} />
                  </td>

                  {/* KDJ */}
                  <td style={colStyle}>
                    <SignalTag indicator="KDJ" signal={kdj} />
                  </td>

                  {/* 综合信号 */}
                  <td style={colStyle}>
                    <SignalTag indicator="composite" signal={comp} />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {/* 免责声明 */}
        <p style={{ marginTop: 12, fontSize: 11, color: '#484f58', textAlign: 'center' }}>
          ⚠️ 综合信号为技术指标的机械汇总，仅供参考，不构成投资建议。
        </p>
      </div>
    </div>
  )
}
