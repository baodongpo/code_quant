/**
 * components/ChartSidebar.jsx — 图表右侧固定说明栏（200px）
 *
 * Midnight Amber 主题：方角、等宽数值、细边框
 *
 * 每个图表（主图 + MACD + RSI + KDJ）右侧紧贴的固定 200px 说明栏，
 * 始终可见，包含：当前指标值/信号标签 + HTML图例
 *
 * Props:
 *   title        - 面板标题（如 "MACD 趋势动能"）
 *   signal       - 信号值（bullish/bearish/neutral）
 *   signalLabel  - 信号文案（可选）
 *   valueItems   - Array<{ label, value, type? }>  指标当前值
 *   legendItems  - Array<{ color, type, label }>   HTML图例
 *   guideItems   - Array<{ dotType?, dotColor?, text }> (保留接口，不再渲染)
 *   onToggle     - 折叠回调（可选），传入时在右上角渲染折叠按钮（∧）
 *
 * 强制规范（CLAUDE.md 裁定）：
 *   guideItems 文案严禁包含任何买卖操作指令，只允许描述现象/机制。
 */
import React, { useState } from 'react'
import { C } from '../utils/colors.js'

const SIGNAL_STYLE = {
  bullish: { bg: C.buyBg,     border: C.buyBorder,     text: C.buyText  },
  bearish: { bg: C.sellBg,    border: C.sellBorder,    text: C.sellText },
  neutral: { bg: C.neutralBg, border: C.neutralBorder, text: C.neutralText },
}

export default function ChartSidebar({
  title,
  signal,
  signalLabel,
  valueItems = [],
  legendItems = [],
  guideItems  = [],  // deprecated：保留 prop 接口，不再渲染
  onToggle,
  onLegendToggle,
}) {
  const sigStyle = SIGNAL_STYLE[signal] || SIGNAL_STYLE.neutral
  const [activeMap, setActiveMap] = useState({})

  return (
    <div style={{
      width:          '14%',
      minWidth:       190,
      maxWidth:       260,
      background:     C.panelBg,
      borderLeft:     `1px solid ${C.border}`,
      padding:        '12px 12px',
      display:        'flex',
      flexDirection:  'column',
      justifyContent: 'center',
      gap:            10,
      overflowY:      'auto',
      position:       'relative',
    }}>
      {/* 折叠按钮（右上角，当 onToggle 存在时显示） */}
      {onToggle && (
        <button
          onClick={onToggle}
          style={{
            position:     'absolute',
            top:          8,
            right:        8,
            background:   'none',
            border:       `1px solid ${C.border2}`,
            borderRadius: 2,
            color:        C.textDim,
            fontSize:     10,
            fontFamily:   C.fontData,
            cursor:       'pointer',
            padding:      '1px 6px',
            letterSpacing: '0.05em',
          }}
          title="折叠"
        >∧</button>
      )}

      {/* 标题 */}
      {title && (
        <div style={{
          fontSize:      11,
          fontFamily:    C.fontUI,
          fontWeight:    700,
          letterSpacing: '0.06em',
          color:         C.textMuted,
          textTransform: 'uppercase',
          paddingBottom: 8,
          borderBottom:  `1px solid ${C.border}`,
        }}>
          {title}
        </div>
      )}

      {/* 当前指标值 */}
      {valueItems.map((item, i) => {
        const valColor = item.type === 'bull' ? C.buyText
          : item.type === 'bear' ? C.sellText
          : C.text
        return (
          <div key={i}>
            <div style={{
              fontSize:      9,
              fontFamily:    C.fontUI,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color:         C.textDim,
              marginBottom:  3,
            }}>{item.label}</div>
            <div style={{
              fontSize:   18,
              fontFamily: C.fontData,
              fontWeight: 600,
              color:      valColor,
              letterSpacing: '-0.01em',
            }}>{item.value}</div>
          </div>
        )
      })}

      {/* 信号标签 */}
      {signal && (
        <span style={{
          display:       'inline-flex',
          alignItems:    'center',
          padding:       '3px 8px',
          borderRadius:  2,
          fontSize:      10,
          fontFamily:    C.fontData,
          fontWeight:    500,
          letterSpacing: '0.04em',
          background:    sigStyle.bg,
          border:        `1px solid ${sigStyle.border}`,
          color:         sigStyle.text,
          width:         'fit-content',
        }}>
          {signalLabel || signal}
        </span>
      )}

      {/* 分割线 */}
      {legendItems.length > 0 && (
        <hr style={{ border: 'none', borderTop: `1px solid ${C.border}`, margin: '0' }} />
      )}

      {/* HTML 图例 */}
      {legendItems.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px 8px', padding: '2px 0' }}>
          {legendItems.map((item, i) => {
            if (item.seriesName) {
              const isActive = activeMap[item.seriesName] !== false
              return (
                <button
                  key={i}
                  onClick={() => {
                    setActiveMap(prev => ({ ...prev, [item.seriesName]: prev[item.seriesName] === false ? true : false }))
                    onLegendToggle?.(item.seriesName)
                  }}
                  style={{
                    display:    'inline-flex',
                    alignItems: 'center',
                    gap:        5,
                    fontSize:   10,
                    fontFamily: C.fontData,
                    whiteSpace: 'nowrap',
                    cursor:     'pointer',
                    background: 'none',
                    border:     'none',
                    padding:    0,
                    color:      isActive ? C.textMuted : C.textDim,
                  }}
                  title={isActive ? `隐藏 ${item.label}` : `显示 ${item.label}`}
                >
                  <span style={{ opacity: isActive ? 1 : 0.3 }}>
                    <LegendMark type={item.type} color={item.color} />
                  </span>
                  <span style={{
                    textDecoration: isActive ? 'none' : 'line-through',
                    opacity:        isActive ? 1 : 0.3,
                  }}>{item.label}</span>
                </button>
              )
            }
            return (
              <div key={i} style={{
                display:    'inline-flex',
                alignItems: 'center',
                gap:        5,
                fontSize:   10,
                fontFamily: C.fontData,
                color:      C.textMuted,
                whiteSpace: 'nowrap',
              }}>
                <LegendMark type={item.type} color={item.color} />
                <span>{item.label}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

/**
 * 图例色块渲染（named export，供各面板说明浮层 HELP_ITEMS 复用）
 * 支持 type: 'line' | 'dashed' | 'circle' | 'bar' | 'dot'
 */
export function LegendMark({ type, color }) {
  if (type === 'line') {
    return <span style={{ width: 16, height: 2, background: color, borderRadius: 0, flexShrink: 0, display: 'inline-block' }} />
  }
  if (type === 'dashed') {
    return (
      <span style={{
        width:      16,
        height:     0,
        borderTop:  `2px dashed ${color}`,
        flexShrink: 0,
        display:    'inline-block',
      }} />
    )
  }
  if (type === 'circle') {
    return (
      <span style={{
        width:        7,
        height:       7,
        borderRadius: '50%',
        background:   color,
        flexShrink:   0,
        display:      'inline-block',
      }} />
    )
  }
  if (type === 'dot') {
    return (
      <span style={{
        width:        6,
        height:       6,
        borderRadius: '50%',
        background:   color,
        flexShrink:   0,
        display:      'inline-block',
      }} />
    )
  }
  if (type === 'bar') {
    return (
      <span style={{
        width:        5,
        height:       11,
        borderRadius: 0,
        background:   color,
        flexShrink:   0,
        display:      'inline-block',
      }} />
    )
  }
  // default fallback
  return (
    <span style={{
      width:        9,
      height:       9,
      borderRadius: 1,
      background:   color,
      flexShrink:   0,
      display:      'inline-block',
    }} />
  )
}
