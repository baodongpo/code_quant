/**
 * components/BottomBar.jsx — 底部信息条
 *
 * 显示：最新收盘价 | 涨跌幅 | PE | PB | RSI 信号 | MACD 信号 | KDJ 信号
 */
import React from 'react'
import SignalTag from './SignalTag.jsx'

function fmt(v, decimals = 2) {
  if (v == null) return '-'
  return typeof v === 'number' ? v.toFixed(decimals) : v
}

export default function BottomBar({ latestBar, signals, rsiValue }) {
  if (!latestBar) return null

  const changePct = latestBar.last_close && latestBar.last_close !== 0
    ? ((latestBar.close - latestBar.last_close) / latestBar.last_close * 100).toFixed(2)
    : null

  const changeColor = changePct == null
    ? '#8b949e'
    : parseFloat(changePct) >= 0 ? '#ef5350' : '#26a69a'

  return (
    <div style={{
      display:        'flex',
      alignItems:     'center',
      flexWrap:       'wrap',
      gap:            12,
      padding:        '8px 16px',
      background:     '#161b22',
      borderTop:      '1px solid #21262d',
      fontSize:       13,
      color:          '#e6edf3',
      borderRadius:   '0 0 8px 8px',
    }}>
      {/* 最新价 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ color: '#8b949e' }}>收盘</span>
        <b style={{ fontSize: 16 }}>{fmt(latestBar.close)}</b>
        {changePct != null && (
          <span style={{ color: changeColor, fontWeight: 600 }}>
            {parseFloat(changePct) >= 0 ? '+' : ''}{changePct}%
          </span>
        )}
      </div>

      {/* 估值 */}
      {latestBar.pe_ratio != null && (
        <div style={{ color: '#8b949e' }}>
          PE <b style={{ color: '#e6edf3' }}>{fmt(latestBar.pe_ratio)}</b>
        </div>
      )}
      {latestBar.pb_ratio != null && (
        <div style={{ color: '#8b949e' }}>
          PB <b style={{ color: '#e6edf3' }}>{fmt(latestBar.pb_ratio)}</b>
        </div>
      )}

      {/* 分隔线 */}
      <div style={{ width: 1, height: 20, background: '#30363d' }} />

      {/* RSI 信号 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <span style={{ color: '#8b949e' }}>RSI</span>
        {rsiValue != null && <span style={{ fontWeight: 600 }}>{rsiValue.toFixed(1)}</span>}
        <SignalTag indicator="RSI" signal={signals?.RSI || 'neutral'} />
      </div>

      {/* MACD 信号 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <span style={{ color: '#8b949e' }}>MACD</span>
        <SignalTag indicator="MACD" signal={signals?.MACD || 'neutral'} />
      </div>

      {/* KDJ 信号 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <span style={{ color: '#8b949e' }}>KDJ</span>
        <SignalTag indicator="KDJ" signal={signals?.KDJ || 'neutral'} />
      </div>

      {/* BOLL 信号 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <span style={{ color: '#8b949e' }}>BOLL</span>
        <SignalTag indicator="BOLL" signal={signals?.BOLL || 'neutral'} />
      </div>

      {/* MA 信号 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <span style={{ color: '#8b949e' }}>MA</span>
        <SignalTag indicator="MA" signal={signals?.MA || 'neutral'} />
      </div>
    </div>
  )
}
