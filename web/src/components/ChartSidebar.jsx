/**
 * components/ChartSidebar.jsx — 图表右侧固定说明栏（200px）
 *
 * 每个图表（主图 + MACD + RSI + KDJ）右侧紧贴的固定 200px 说明栏，
 * 始终可见，包含：当前指标值/信号标签 + HTML图例 + 3条通俗解读
 *
 * Props:
 *   title        - 面板标题（如 "📶 MACD 趋势动能"）
 *   signal       - 信号值（bullish/bearish/neutral）
 *   signalLabel  - 信号文案（可选）
 *   valueItems   - Array<{ label, value, type? }>  指标当前值
 *   legendItems  - Array<{ color, type, label }>   HTML图例
 *   guideItems   - Array<{ dotType?, dotColor?, text }>  解读文案
 */
import React from 'react'
import { C } from '../utils/colors.js'

const SIGNAL_STYLE = {
  bullish: { bg: '#3a1a1a', border: C.buy,           text: C.buyText  },
  bearish: { bg: '#1a3a2a', border: C.sell,          text: C.sellText },
  neutral: { bg: C.neutralBg, border: C.neutralBorder, text: C.neutralText },
}

const DOT_COLOR = {
  bull: C.buyText,
  bear: C.sellText,
  neut: C.neutralText,
}

export default function ChartSidebar({
  title,
  signal,
  signalLabel,
  valueItems = [],
  legendItems = [],
  guideItems  = [],
}) {
  const sigStyle = SIGNAL_STYLE[signal] || SIGNAL_STYLE.neutral

  return (
    <div style={{
      width:          '14%',
      minWidth:       200,
      maxWidth:       280,
      background:     C.panelBg,
      borderLeft:     `1px solid ${C.border}`,
      padding:        14,
      display:        'flex',
      flexDirection:  'column',
      justifyContent: 'center',
      gap:            10,
      overflowY:      'auto',
    }}>
      {/* 标题 */}
      {title && (
        <div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>
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
            <div style={{ fontSize: 10, color: C.textMuted, marginBottom: 2 }}>{item.label}</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: valColor }}>{item.value}</div>
          </div>
        )
      })}

      {/* 信号标签 */}
      {signal && (
        <span style={{
          display:      'inline-flex',
          alignItems:   'center',
          padding:      '4px 10px',
          borderRadius: 12,
          fontSize:     11,
          fontWeight:   600,
          background:   sigStyle.bg,
          border:       `1px solid ${sigStyle.border}`,
          color:        sigStyle.text,
          width:        'fit-content',
        }}>
          {signalLabel || signal}
        </span>
      )}

      {/* 分割线 */}
      {legendItems.length > 0 && (
        <hr style={{ border: 'none', borderTop: `1px solid ${C.border}`, margin: '2px 0' }} />
      )}

      {/* HTML 图例 */}
      {legendItems.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 10px', padding: '4px 0 2px' }}>
          {legendItems.map((item, i) => (
            <div key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 10, color: C.textMuted, whiteSpace: 'nowrap' }}>
              <LegendMark type={item.type} color={item.color} />
              <span>{item.label}</span>
            </div>
          ))}
        </div>
      )}

      {/* 分割线 */}
      {guideItems.length > 0 && (
        <hr style={{ border: 'none', borderTop: `1px solid ${C.border}`, margin: '2px 0' }} />
      )}

      {/* 解读文案 */}
      {guideItems.length > 0 && (
        <>
          <div style={{ fontSize: 11, fontWeight: 600, color: C.accentText }}>📖 如何看这张图</div>
          {guideItems.map((item, i) => {
            const dotColor = item.dotColor
              || (item.dotType ? DOT_COLOR[item.dotType] : C.neutralText)
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 6, fontSize: 11, color: C.textMuted, lineHeight: 1.5, padding: '2px 0' }}>
                <span style={{
                  width:        7,
                  height:       7,
                  borderRadius: '50%',
                  background:   dotColor,
                  flexShrink:   0,
                  marginTop:    4,
                  display:      'inline-block',
                }} />
                <span dangerouslySetInnerHTML={{ __html: item.text }} />
              </div>
            )
          })}
        </>
      )}
    </div>
  )
}

/** 图例色块渲染 */
function LegendMark({ type, color }) {
  if (type === 'line') {
    return <span style={{ width: 18, height: 2, background: color, borderRadius: 1, flexShrink: 0 }} />
  }
  if (type === 'dashed') {
    return (
      <span style={{
        width:        18,
        height:       0,
        borderTop:    `2px dashed ${color}`,
        flexShrink:   0,
        display:      'inline-block',
      }} />
    )
  }
  if (type === 'circle') {
    return (
      <span style={{
        width:        8,
        height:       8,
        borderRadius: '50%',
        background:   color,
        flexShrink:   0,
        display:      'inline-block',
      }} />
    )
  }
  // bar / default
  return (
    <span style={{
      width:        10,
      height:       10,
      borderRadius: 2,
      background:   color,
      flexShrink:   0,
      display:      'inline-block',
    }} />
  )
}
