/**
 * components/BottomBar.jsx — 底部信息条（双层）
 *
 * 第一层（始终可见）：收盘价 / 涨跌幅 / PE / PB
 * 第二层（可折叠，默认展开）：指标信号标签（RSI/MACD/KDJ/BOLL/MA）
 *
 * v3.5 变更：
 *   - 双层结构，信息层次更清晰
 *   - 配色遵循红买绿卖（通过 signals.js 全局生效）
 */
import React, { useState } from 'react'
import SignalTag from './SignalTag.jsx'
import { C } from '../utils/colors.js'

function fmt(v, decimals = 2) {
  if (v == null) return '-'
  return typeof v === 'number' ? v.toFixed(decimals) : v
}

export default function BottomBar({ latestBar, signals, rsiValue }) {
  if (!latestBar) return null

  const [signalsExpanded, setSignalsExpanded] = useState(true)

  const changePct = latestBar.last_close && latestBar.last_close !== 0
    ? ((latestBar.close - latestBar.last_close) / latestBar.last_close * 100).toFixed(2)
    : null

  const changeColor = changePct == null
    ? C.textMuted
    : parseFloat(changePct) >= 0 ? C.candleUp : C.candleDown

  return (
    <div style={{
      margin:       '0 0',
      background:   C.panelBg,
      borderTop:    `1px solid ${C.border}`,
      fontSize:     13,
      color:        C.text,
    }}>
      {/* 第一层：基础行情（始终可见） */}
      <div style={{
        display:    'flex',
        alignItems: 'center',
        flexWrap:   'wrap',
        gap:        16,
        padding:    '10px 16px 8px',
      }}>
        {/* 最新价 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ color: C.textMuted, fontSize: 12 }}>收盘</span>
          <b style={{ fontSize: 18 }}>{fmt(latestBar.close)}</b>
          {changePct != null && (
            <span style={{ color: changeColor, fontWeight: 600, fontSize: 13 }}>
              {parseFloat(changePct) >= 0 ? '▲' : '▼'} {parseFloat(changePct) >= 0 ? '+' : ''}{changePct}%
            </span>
          )}
        </div>

        {/* 分隔线 */}
        <div style={{ width: 1, height: 22, background: C.border2 }} />

        {/* 估值 */}
        {latestBar.pe_ratio != null && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <span style={{ color: C.textDim, fontSize: 10 }}>PE (TTM)</span>
            <b style={{ color: C.text, fontSize: 13 }}>{fmt(latestBar.pe_ratio)}</b>
          </div>
        )}
        {latestBar.pb_ratio != null && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <span style={{ color: C.textDim, fontSize: 10 }}>PB</span>
            <b style={{ color: C.text, fontSize: 13 }}>{fmt(latestBar.pb_ratio)}</b>
          </div>
        )}

        {/* 右侧：折叠指标层按钮 */}
        <div style={{ marginLeft: 'auto' }}>
          <button
            onClick={() => setSignalsExpanded(v => !v)}
            style={{
              background:   'none',
              border:       `1px solid ${C.border2}`,
              borderRadius: 6,
              color:        C.textMuted,
              fontSize:     11,
              cursor:       'pointer',
              padding:      '3px 10px',
            }}
          >
            {signalsExpanded ? '折叠指标 ∧' : '展开指标 ∨'}
          </button>
        </div>
      </div>

      {/* 分割线 */}
      {signalsExpanded && (
        <div style={{ borderTop: `1px solid ${C.border}` }} />
      )}

      {/* 第二层：指标快览（可折叠） */}
      {signalsExpanded && (
        <div style={{
          display:    'flex',
          alignItems: 'center',
          flexWrap:   'wrap',
          gap:        12,
          padding:    '8px 16px 10px',
        }}>
          {/* RSI */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ color: C.textMuted, fontSize: 12 }}>RSI</span>
            {rsiValue != null && (
              <span style={{ fontWeight: 600, fontSize: 12 }}>{rsiValue.toFixed(1)}</span>
            )}
            <SignalTag indicator="RSI" signal={signals?.RSI || 'neutral'} />
          </div>

          {/* MACD */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ color: C.textMuted, fontSize: 12 }}>MACD</span>
            <SignalTag indicator="MACD" signal={signals?.MACD || 'neutral'} />
          </div>

          {/* KDJ */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ color: C.textMuted, fontSize: 12 }}>KDJ</span>
            <SignalTag indicator="KDJ" signal={signals?.KDJ || 'neutral'} />
          </div>

          {/* BOLL */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ color: C.textMuted, fontSize: 12 }}>BOLL</span>
            <SignalTag indicator="BOLL" signal={signals?.BOLL || 'neutral'} />
          </div>

          {/* MA */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ color: C.textMuted, fontSize: 12 }}>MA</span>
            <SignalTag indicator="MA" signal={signals?.MA || 'neutral'} />
          </div>
        </div>
      )}
    </div>
  )
}
