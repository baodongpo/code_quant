/**
 * components/BottomBar.jsx — 底部信息条（双层）
 *
 * Midnight Amber 主题：等宽数值、方角按钮
 *
 * 第一层（始终可见）：收盘价 / 涨跌幅 / PE / PB
 * 第二层（可折叠，默认展开）：指标信号标签（RSI/MACD/KDJ/BOLL/MA）
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
      margin:     '0 0',
      background: C.panelBg,
      borderTop:  `1px solid ${C.border}`,
      fontSize:   13,
      color:      C.text,
    }}>
      {/* 第一层：基础行情（始终可见） */}
      <div style={{
        display:    'flex',
        alignItems: 'center',
        flexWrap:   'wrap',
        gap:        16,
        padding:    '8px 16px',
      }}>
        {/* 最新价 */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <span style={{
            fontSize:      9,
            fontFamily:    C.fontUI,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            color:         C.textDim,
          }}>CLOSE</span>
          <span style={{
            fontSize:   20,
            fontFamily: C.fontData,
            fontWeight: 600,
            color:      C.text,
            letterSpacing: '-0.01em',
          }}>{fmt(latestBar.close)}</span>
          {changePct != null && (
            <span style={{
              color:      changeColor,
              fontFamily: C.fontData,
              fontWeight: 600,
              fontSize:   12,
              letterSpacing: '0.02em',
            }}>
              {parseFloat(changePct) >= 0 ? '▲' : '▼'} {parseFloat(changePct) >= 0 ? '+' : ''}{changePct}%
            </span>
          )}
        </div>

        {/* 分隔线 */}
        <div style={{ width: 1, height: 20, background: C.border2 }} />

        {/* 估值 */}
        {latestBar.pe_ratio != null && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <span style={{
              fontSize:      9,
              fontFamily:    C.fontUI,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color:         C.textDim,
            }}>PE (TTM)</span>
            <span style={{
              fontFamily: C.fontData,
              fontWeight: 600,
              color:      C.text,
              fontSize:   13,
            }}>{fmt(latestBar.pe_ratio)}</span>
          </div>
        )}
        {latestBar.pb_ratio != null && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <span style={{
              fontSize:      9,
              fontFamily:    C.fontUI,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color:         C.textDim,
            }}>PB</span>
            <span style={{
              fontFamily: C.fontData,
              fontWeight: 600,
              color:      C.text,
              fontSize:   13,
            }}>{fmt(latestBar.pb_ratio)}</span>
          </div>
        )}

        {/* 右侧：折叠指标层按钮 */}
        <div style={{ marginLeft: 'auto' }}>
          <button
            onClick={() => setSignalsExpanded(v => !v)}
            style={{
              background:    'none',
              border:        `1px solid ${C.border2}`,
              borderRadius:  2,
              color:         C.textDim,
              fontSize:      10,
              fontFamily:    C.fontData,
              letterSpacing: '0.06em',
              cursor:        'pointer',
              padding:       '3px 10px',
            }}
          >
            {signalsExpanded ? 'SIGNALS ∧' : 'SIGNALS ∨'}
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
          gap:        10,
          padding:    '7px 16px 9px',
        }}>
          {/* RSI */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{
              fontSize:      9,
              fontFamily:    C.fontUI,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color:         C.textDim,
            }}>RSI</span>
            {rsiValue != null && (
              <span style={{
                fontFamily: C.fontData,
                fontWeight: 600,
                fontSize:   11,
                color:      C.textMuted,
              }}>{rsiValue.toFixed(1)}</span>
            )}
            <SignalTag indicator="RSI" signal={signals?.RSI || 'neutral'} />
          </div>

          {/* MACD */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{
              fontSize:      9,
              fontFamily:    C.fontUI,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color:         C.textDim,
            }}>MACD</span>
            <SignalTag indicator="MACD" signal={signals?.MACD || 'neutral'} />
          </div>

          {/* KDJ */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{
              fontSize:      9,
              fontFamily:    C.fontUI,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color:         C.textDim,
            }}>KDJ</span>
            <SignalTag indicator="KDJ" signal={signals?.KDJ || 'neutral'} />
          </div>

          {/* BOLL */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{
              fontSize:      9,
              fontFamily:    C.fontUI,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color:         C.textDim,
            }}>BOLL</span>
            <SignalTag indicator="BOLL" signal={signals?.BOLL || 'neutral'} />
          </div>

          {/* MA */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{
              fontSize:      9,
              fontFamily:    C.fontUI,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color:         C.textDim,
            }}>MA</span>
            <SignalTag indicator="MA" signal={signals?.MA || 'neutral'} />
          </div>
        </div>
      )}
    </div>
  )
}
