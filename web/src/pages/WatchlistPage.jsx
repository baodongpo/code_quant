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
import { C } from '../utils/colors.js'

function fmt(v, d = 2) {
  if (v == null) return '-'
  return typeof v === 'number' ? v.toFixed(d) : String(v)
}

const colStyle = {
  padding:      '9px 14px',
  fontSize:     12,
  fontFamily:   C.fontData,
  borderBottom: `1px solid ${C.border}`,
  textAlign:    'center',
  color:        C.text,
}
const headStyle = {
  ...colStyle,
  background:    C.panelBg,
  color:         C.textDim,
  fontSize:      9,
  fontFamily:    C.fontUI,
  letterSpacing: '0.10em',
  textTransform: 'uppercase',
  fontWeight:    600,
  position:      'sticky',
  top:           0,
  zIndex:        1,
}
const marketGroupStyle = {
  padding:       '6px 14px',
  fontSize:      9,
  fontFamily:    C.fontUI,
  fontWeight:    700,
  letterSpacing: '0.12em',
  textTransform: 'uppercase',
  background:    C.panelBg,
  color:         C.textDim,
  textAlign:     'left',
  borderBottom:  `1px solid ${C.border}`,
  borderTop:     `1px solid ${C.border}`,
}

/** 市场分组顺序 */
const MARKET_GROUPS = [
  { key: 'A',  label: 'A股' },
  { key: 'HK', label: '港股' },
  { key: 'US', label: '美股' },
]

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
    <div style={{ minHeight: '100vh', background: C.chartBg, color: C.text }}>
      {/* 顶部栏 */}
      <div style={{
        display:      'flex',
        alignItems:   'center',
        gap:          12,
        padding:      '8px 20px',
        background:   C.panelBg,
        borderBottom: `1px solid ${C.border}`,
        position:     'sticky',
        top:          0,
        zIndex:       100,
      }}>
        {/* 系统标识 */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <span style={{
            fontSize:      11,
            fontFamily:    C.fontUI,
            fontWeight:    800,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            color:         C.accent,
          }}>QT</span>
          <span style={{
            fontSize:      9,
            fontFamily:    C.fontUI,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            color:         C.textDim,
          }}>WATCHLIST</span>
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          {loading && (
            <span style={{
              fontSize:      10,
              fontFamily:    C.fontData,
              letterSpacing: '0.06em',
              color:         C.accent,
            }}>LOADING...</span>
          )}
          {lastUpdate && !loading && (
            <span style={{
              fontSize:   10,
              fontFamily: C.fontData,
              color:      C.textDim,
            }}>{lastUpdate}</span>
          )}
          <button
            onClick={load}
            style={{
              fontSize:      10,
              fontFamily:    C.fontData,
              letterSpacing: '0.06em',
              color:         C.textMuted,
              background:    'transparent',
              border:        `1px solid ${C.border2}`,
              borderRadius:  2,
              padding:       '4px 10px',
              cursor:        'pointer',
            }}
          >
            REFRESH
          </button>
          <Link to="/" style={{
            fontSize:       10,
            fontFamily:     C.fontData,
            letterSpacing:  '0.06em',
            color:          C.accentText,
            textDecoration: 'none',
            border:         `1px solid ${C.border2}`,
            borderRadius:   2,
            padding:        '4px 10px',
          }}>
            ← TERMINAL
          </Link>
        </div>
      </div>

      {error && (
        <div style={{
          padding:      '8px 20px',
          background:   C.buyBg,
          color:        C.buyText,
          fontSize:     11,
          fontFamily:   C.fontData,
          borderBottom: `1px solid ${C.buyBorder}`,
        }}>
          {error}
        </div>
      )}

      {/* 表格 */}
      <div style={{ padding: '16px 20px', overflowX: 'auto' }}>
        <table style={{
          width:           '100%',
          borderCollapse:  'collapse',
          background:      C.chartBg,
          borderRadius:    3,
          overflow:        'hidden',
          border:          `1px solid ${C.border}`,
        }}>
          <thead>
            <tr>
              <th style={{ ...headStyle, textAlign: 'left' }}>Stock</th>
              <th style={{ ...headStyle, textAlign: 'right' }}>Close</th>
              <th style={{ ...headStyle, textAlign: 'right' }}>Chg%</th>
              <th style={headStyle}>RSI</th>
              <th style={headStyle}>MACD</th>
              <th style={headStyle}>KDJ</th>
              <th style={headStyle}>Signal</th>
            </tr>
          </thead>
          <tbody>
            {summary.length === 0 && !loading && (
              <tr>
                <td colSpan={7} style={{
                  ...colStyle,
                  textAlign: 'center',
                  color:     C.textDim,
                  padding:   '48px',
                  fontSize:  11,
                  fontFamily: C.fontData,
                  letterSpacing: '0.08em',
                }}>
                  NO DATA — watchlist empty or sync pending
                </td>
              </tr>
            )}
            {MARKET_GROUPS.map(group => {
              const items = summary.filter(item => item.market === group.key)
              if (items.length === 0) return null
              return (
                <React.Fragment key={group.key}>
                  {/* 市场分组标题行 */}
                  <tr>
                    <td colSpan={7} style={marketGroupStyle}>
                      {group.label} · {items.length}
                    </td>
                  </tr>
                  {items.map(item => {
                    const sig   = item.signals || {}
                    const rsi   = sig.RSI || 'neutral'
                    const macd  = sig.MACD || 'neutral'
                    const kdj   = sig.KDJ || 'neutral'
                    const comp  = sig.composite || 'neutral'
                    const changePct = item.change_pct
                    const changeColor = changePct == null ? C.textMuted
                      : changePct >= 0 ? C.buyText : C.sellText
                    const rsiVal = sig.RSI_value

                    return (
                      <tr
                        key={item.stock_code}
                        onClick={() => navigate(`/?code=${item.stock_code}`)}
                        style={{ cursor: 'pointer', transition: 'background 0.1s' }}
                        onMouseEnter={e => e.currentTarget.style.background = C.panelBg}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                      >
                        {/* 股票名称 + 代码 */}
                        <td style={{ ...colStyle, textAlign: 'left' }}>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                            {item.name && (
                              <span style={{
                                fontWeight: 600,
                                fontSize:   12,
                                fontFamily: C.fontData,
                                color:      C.text,
                              }}>
                                {item.name}
                              </span>
                            )}
                            <span style={{
                              fontSize:   10,
                              fontFamily: C.fontData,
                              color:      C.accentText,
                              letterSpacing: '0.04em',
                            }}>
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
                              <span style={{
                                fontFamily: C.fontData,
                                fontWeight: 600,
                                fontSize:   11,
                                color:      C.textMuted,
                              }}>{rsiVal.toFixed(1)}</span>
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
                </React.Fragment>
              )
            })}
          </tbody>
        </table>

        {/* 免责声明 */}
        <p style={{
          marginTop:     12,
          fontSize:      10,
          fontFamily:    C.fontData,
          letterSpacing: '0.04em',
          color:         C.textDim,
          textAlign:     'center',
        }}>
          综合信号为技术指标机械汇总，仅供参考，不构成投资建议。
        </p>
      </div>
    </div>
  )
}
