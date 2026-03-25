/**
 * components/ChartSidebar.jsx — 图表右侧固定说明栏（200px）
 *
 * 每个图表（主图 + MACD + RSI + KDJ）右侧紧贴的固定 200px 说明栏，
 * 始终可见，包含：当前指标值/信号标签 + HTML图例
 *
 * Props:
 *   title        - 面板标题（如 "📶 MACD 趋势动能"）
 *   signal       - 信号值（bullish/bearish/neutral）
 *   signalLabel  - 信号文案（可选）
 *   valueItems   - Array<{ label, value, type? }>  指标当前值
 *   legendItems  - Array<{ color, type, label }>   HTML图例
 *   guideItems   - Array<{ dotType?, dotColor?, text }> (保留接口，不再渲染)
 *   onToggle     - 折叠回调（可选），传入时在右上角渲染折叠按钮（∧）
 *
 * 迭代8变更：
 *   - [?] 按钮 + guideItems 渲染逻辑已移除（统一迁移至各面板顶部）
 *   - 新增 onToggle prop，当传入时在 Sidebar 右上角渲染折叠按钮
 *   - position: relative 支持 absolute 折叠按钮定位
 *
 * 强制规范（CLAUDE.md 裁定）：
 *   guideItems 文案严禁包含任何买卖操作指令，只允许描述现象/机制。
 *   未来新增指标时同样必须补充各面板内部 HELP_ITEMS，且遵守此规范。
 */
import React, { useState } from 'react'
import { C } from '../utils/colors.js'

const SIGNAL_STYLE = {
  bullish: { bg: '#3a1a1a', border: C.buy,           text: C.buyText  },
  bearish: { bg: '#1a3a2a', border: C.sell,          text: C.sellText },
  neutral: { bg: C.neutralBg, border: C.neutralBorder, text: C.neutralText },
}

export default function ChartSidebar({
  title,
  signal,
  signalLabel,
  valueItems = [],
  legendItems = [],
  guideItems  = [],  // deprecated：保留 prop 接口，不再渲染（说明浮层已迁至各面板顶部）
  onToggle,
  onLegendToggle,   // FEAT-legend-toggle：图例点击回调 (seriesName: string) => void
}) {
  const sigStyle = SIGNAL_STYLE[signal] || SIGNAL_STYLE.neutral
  // FEAT-legend-toggle：activeMap 记录各 seriesName 的显示状态，缺省视为 true（active）
  const [activeMap, setActiveMap] = useState({})

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
            borderRadius: 4,
            color:        C.textMuted,
            fontSize:     12,
            cursor:       'pointer',
            padding:      '2px 8px',
          }}
          title="折叠"
        >∧</button>
      )}

      {/* 标题（[?] 按钮已移至各面板顶部，此处仅保留标题文字） */}
      {title && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: C.text, flex: 1 }}>
            {title}
          </span>
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
          {legendItems.map((item, i) => {
            if (item.seriesName) {
              // FEAT-legend-toggle：有 seriesName 的条目渲染为可点击按钮
              const isActive = activeMap[item.seriesName] !== false
              return (
                <button
                  key={i}
                  onClick={() => {
                    // 切换 activeMap 中该 seriesName 的状态
                    setActiveMap(prev => ({ ...prev, [item.seriesName]: prev[item.seriesName] === false ? true : false }))
                    onLegendToggle?.(item.seriesName)
                  }}
                  style={{
                    display:    'inline-flex',
                    alignItems: 'center',
                    gap:        5,
                    fontSize:   10,
                    whiteSpace: 'nowrap',
                    cursor:     'pointer',
                    background: 'none',
                    border:     'none',
                    padding:    0,
                    color:      isActive ? C.textMuted : C.textDim,
                  }}
                  title={isActive ? `隐藏 ${item.label}` : `显示 ${item.label}`}
                >
                  <span style={{ opacity: isActive ? 1 : 0.35 }}>
                    <LegendMark type={item.type} color={item.color} />
                  </span>
                  <span style={{
                    textDecoration: isActive ? 'none' : 'line-through',
                    opacity:        isActive ? 1 : 0.35,
                  }}>{item.label}</span>
                </button>
              )
            }
            // 无 seriesName：保持原有纯展示 div
            return (
              <div key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 10, color: C.textMuted, whiteSpace: 'nowrap' }}>
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
  if (type === 'dot') {
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
