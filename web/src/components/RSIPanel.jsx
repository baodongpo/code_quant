/**
 * components/RSIPanel.jsx — RSI 副图
 *
 * 包含：
 *   - RSI14 曲线
 *   - 70~100 浅绿背景（超买=卖出信号=绿底）
 *   - 0~30 浅红背景（超卖=买入信号=红底）
 *   - 30/70 参考线（水平虚线）
 *   - 右侧侧边说明栏（由父组件 ChartSidebar 提供）
 *
 * v3.5 变更：
 *   - 高度 140 → 200px
 *   - 移除 inside dataZoom，保留 slider
 *   - 移除 ECharts 内置 legend
 *   - 区域背景色修正：超买区=绿底（卖出信号），超卖区=红底（买入信号）
 *   - 参考线颜色：超买参考线绿，超卖参考线红
 *   - 支持折叠（collapsed prop）
 *   - 改为 forwardRef
 *   - 配色统一引用 colors.js
 */
import React, { useMemo, forwardRef } from 'react'
import ReactECharts from 'echarts-for-react'
import SignalTag from './SignalTag.jsx'
import { C } from '../utils/colors.js'

const RSIPanel = forwardRef(function RSIPanel({ dates, rsi, signal, collapsed, onToggle }, ref) {
  const rsi14 = rsi?.RSI14 || []

  // 折叠状态：仅显示标题行
  if (collapsed) {
    const latestRSI = rsi14.slice().reverse().find(v => v != null)
    return (
      <div style={{
        height:       32,
        background:   C.chartBg,
        borderRadius: 8,
        display:      'flex',
        alignItems:   'center',
        padding:      '0 12px',
        gap:          10,
        border:       `1px solid ${C.border}`,
      }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: C.textMuted }}>RSI(14)</span>
        {latestRSI != null && (
          <span style={{ fontSize: 12, color: C.text, fontWeight: 600 }}>{latestRSI.toFixed(1)}</span>
        )}
        <SignalTag indicator="RSI" signal={signal || 'neutral'} />
        <button
          onClick={onToggle}
          style={{
            marginLeft:   'auto',
            background:   'none',
            border:       `1px solid ${C.border2}`,
            borderRadius: 4,
            color:        C.textMuted,
            fontSize:     12,
            cursor:       'pointer',
            padding:      '2px 8px',
          }}
          title="展开 RSI"
        >∨</button>
      </div>
    )
  }

  return (
    <RSIPanelInner
      ref={ref}
      dates={dates}
      rsi14={rsi14}
      signal={signal}
      onToggle={onToggle}
    />
  )
})

const RSIPanelInner = forwardRef(function RSIPanelInner({ dates, rsi14, signal, onToggle }, ref) {
  const option = useMemo(() => {
    if (!dates || dates.length === 0) return {}

    const zoomStart = Math.max(0, 100 - Math.round(120 / dates.length * 100))

    return {
      backgroundColor: C.chartBg,
      animation: false,
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          crossStyle: { color: '#8b949e', width: 0.8, type: 'dashed' },
          label: { backgroundColor: '#1c2128', color: C.text, fontSize: 10 },
        },
        backgroundColor: C.panelBg,
        borderColor:     C.border2,
        textStyle:       { color: C.text, fontSize: 11 },
        formatter(params) {
          if (!params || params.length === 0) return ''
          const idx = params[0].dataIndex
          const v = rsi14[idx]
          // 遵循红买绿卖
          const label = v == null ? '—'
            : v > 70 ? `${v.toFixed(2)} 🟢超买（留意卖出）`
            : v < 30 ? `${v.toFixed(2)} 🔴超卖（关注买入）`
            : `${v.toFixed(2)} ⚖️中性`
          return `<b>${dates[idx]}</b><br/>RSI(14): <b>${label}</b>`
        },
      },
      // 仅保留 slider，不使用 inside（禁止滚轮缩放）
      dataZoom: [
        {
          type:        'slider',
          xAxisIndex:  [0],
          height:      16,
          bottom:      2,
          borderColor: C.border2,
          fillerColor: C.accentBg,
          handleStyle: { color: C.accent },
          textStyle:   { color: C.textMuted, fontSize: 10 },
          start:       zoomStart,
          end:         100,
        },
      ],
      grid: [{ left: 16, right: 16, top: 20, bottom: 28, containLabel: true }],
      xAxis: [{
        type: 'category', data: dates,
        axisLine:  { lineStyle: { color: C.axisLine } },
        axisLabel: { color: C.textMuted, fontSize: 10 },
        axisTick:  { lineStyle: { color: C.axisLine } },
        splitLine: { show: false },
      }],
      yAxis: [{
        min: 0, max: 100,
        splitLine: { lineStyle: { color: C.gridLine, type: 'dashed' } },
        axisLabel: {
          color: C.textMuted, fontSize: 10,
          formatter: v => v === 70 ? '超买70' : v === 30 ? '超卖30' : v,
        },
        axisLine: { lineStyle: { color: C.axisLine } },
      }],
      series: [
        {
          name: 'RSI14', type: 'line', data: rsi14,
          symbol: 'none', smooth: false,
          lineStyle: { color: C.dif, width: 1.5 },
          // 超买超卖区间着色（遵循红买绿卖）
          markArea: {
            silent: true,
            data: [
              // 超买区（70~100）= 卖出信号 = 绿底
              [{
                yAxis: 70,
                itemStyle: { color: C.overbought },
              }, { yAxis: 100 }],
              // 超卖区（0~30）= 买入信号 = 红底
              [{
                yAxis: 0,
                itemStyle: { color: C.oversold },
              }, { yAxis: 30 }],
            ],
          },
          markLine: {
            silent: true,
            symbol: 'none',
            data: [
              // 超买参考线 = 绿（卖出信号色）
              { yAxis: 70, lineStyle: { color: C.overboughtLine, width: 1, type: 'dashed' } },
              // 超卖参考线 = 红（买入信号色）
              { yAxis: 30, lineStyle: { color: C.oversoldLine,   width: 1, type: 'dashed' } },
            ],
            label: { show: true, color: C.textMuted, fontSize: 10,
                     formatter: params => params.value === 70 ? '70' : '30' },
          },
        },
      ],
    }
  }, [dates, rsi14])

  return (
    <div style={{ flex: 1, minWidth: 0, background: C.chartBg, position: 'relative', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
      {/* 面板标题行（外部 HTML 标题，避免与图表内容重叠） */}
      <div style={{
        padding:    '8px 12px 0',
        display:    'flex',
        alignItems: 'center',
        gap:        6,
      }}>
        <span style={{ fontSize: 11, color: C.textMuted, fontWeight: 600 }}>RSI(14)</span>
        {onToggle && (
          <button
            onClick={onToggle}
            style={{
              marginLeft:   'auto',
              background:   'none',
              border:       `1px solid ${C.border2}`,
              borderRadius: 4,
              color:        C.textMuted,
              fontSize:     12,
              cursor:       'pointer',
              padding:      '2px 8px',
            }}
            title="折叠 RSI"
          >∧</button>
        )}
      </div>
      <ReactECharts
        ref={ref}
        option={option}
        style={{ height: 240 }}
        notMerge={true}
        lazyUpdate={false}
      />
    </div>
  )
})

export default RSIPanel
