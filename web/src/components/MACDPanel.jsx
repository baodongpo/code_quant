/**
 * components/MACDPanel.jsx — MACD 副图
 *
 * 包含：
 *   - DIF 线（蓝）/ DEA 线（黄）
 *   - MACD 柱（正值红 / 负值绿）
 *   - 金叉/死叉圆形标记（symbolSize=10，「金叉」/「死叉」16px加粗）
 *   - 右侧侧边说明栏（由父组件 ChartSidebar 提供）
 *
 * v3.5 变更：
 *   - 高度 140 → 200px
 *   - 移除 inside dataZoom，保留 slider
 *   - 移除 ECharts 内置 legend
 *   - 标记点改为圆形（circle）：金叉红圈/死叉绿圈（遵循红买绿卖）
 *   - 标记文字「金叉」/「死叉」，16px加粗
 *   - 支持折叠（collapsed prop）
 *   - 改为 forwardRef，暴露 ECharts 实例
 *   - 配色统一引用 colors.js
 */
import React, { useMemo, forwardRef } from 'react'
import ReactECharts from 'echarts-for-react'
import SignalTag from './SignalTag.jsx'
import { C } from '../utils/colors.js'

const MACDPanel = forwardRef(function MACDPanel({ dates, macd, signal, collapsed, onToggle }, ref) {
  const { dif = [], dea = [], macd: macdBar = [] } = macd || {}

  // 折叠状态：仅显示标题行
  if (collapsed) {
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
        <span style={{ fontSize: 12, fontWeight: 600, color: C.textMuted }}>MACD(12,26,9)</span>
        <SignalTag indicator="MACD" signal={signal || 'neutral'} />
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
          title="展开 MACD"
        >∨</button>
      </div>
    )
  }

  return (
    <MACDPanelInner
      ref={ref}
      dates={dates}
      dif={dif}
      dea={dea}
      macdBar={macdBar}
      signal={signal}
      onToggle={onToggle}
    />
  )
})

const MACDPanelInner = forwardRef(function MACDPanelInner({ dates, dif, dea, macdBar, signal, onToggle }, ref) {
  const option = useMemo(() => {
    if (!dates || dates.length === 0) return {}

    // 标记金叉/死叉：圆形标记，金叉=红圈，死叉=绿圈（遵循红买绿卖）
    const crossPoints = []
    for (let i = 1; i < dif.length; i++) {
      if (dif[i] == null || dea[i] == null || dif[i - 1] == null || dea[i - 1] == null) continue
      const wasBelow = dif[i - 1] <= dea[i - 1]
      const isAbove  = dif[i] > dea[i]
      const wasAbove = dif[i - 1] >= dea[i - 1]
      const isBelow  = dif[i] < dea[i]

      if (wasBelow && isAbove) {
        // 金叉：买入信号=红圈，标记在交叉点下方
        crossPoints.push({
          xAxis:       dates[i],
          yAxis:       dif[i],
          value:       dif[i],
          symbol:      'circle',
          symbolSize:  10,
          itemStyle:   { color: C.buy },
          label: {
            show:       true,
            formatter:  '金叉',
            color:      C.buyText,
            fontSize:   16,
            fontWeight: 700,
            position:   'bottom',
            distance:   4,
          },
        })
      } else if (wasAbove && isBelow) {
        // 死叉：卖出信号=绿圈，标记在交叉点上方
        crossPoints.push({
          xAxis:       dates[i],
          yAxis:       dif[i],
          value:       dif[i],
          symbol:      'circle',
          symbolSize:  10,
          itemStyle:   { color: C.sell },
          label: {
            show:       true,
            formatter:  '死叉',
            color:      C.sellText,
            fontSize:   16,
            fontWeight: 700,
            position:   'top',
            distance:   4,
          },
        })
      }
    }

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
          const lines = [`<b>${dates[idx]}</b>`]
          if (dif[idx]     != null) lines.push(`DIF: ${dif[idx]?.toFixed(4)}`)
          if (dea[idx]     != null) lines.push(`DEA: ${dea[idx]?.toFixed(4)}`)
          if (macdBar[idx] != null) lines.push(`MACD柱: ${macdBar[idx]?.toFixed(4)}`)
          return lines.join('<br/>')
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
        scale: true,
        splitLine: { lineStyle: { color: C.gridLine, type: 'dashed' } },
        axisLabel: { color: C.textMuted, fontSize: 10 },
        axisLine:  { lineStyle: { color: C.axisLine } },
      }],
      series: [
        // MACD 柱
        {
          name: 'MACD柱',
          type: 'bar',
          data: macdBar.map(v => ({
            value:     v,
            itemStyle: { color: v == null ? 'transparent' : v >= 0 ? C.macdBarPos : C.macdBarNeg },
          })),
          barMaxWidth: 6,
        },
        // DIF 线（含标记点）
        {
          name: 'DIF', type: 'line', data: dif,
          symbol: 'none', smooth: false,
          lineStyle: { color: C.dif, width: 1.5 },
          markPoint: { data: crossPoints, animation: false },
        },
        // DEA 线
        {
          name: 'DEA', type: 'line', data: dea,
          symbol: 'none', smooth: false,
          lineStyle: { color: C.dea, width: 1.5 },
        },
      ],
    }
  }, [dates, dif, dea, macdBar])

  return (
    <div style={{ flex: 1, minWidth: 0, background: C.chartBg, position: 'relative', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
      {/* 面板标题行（外部 HTML 标题，避免与图表内容重叠） */}
      <div style={{
        padding:    '8px 12px 0',
        display:    'flex',
        alignItems: 'center',
        gap:        6,
      }}>
        <span style={{ fontSize: 11, color: C.textMuted, fontWeight: 600 }}>MACD(12,26,9)</span>
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
            title="折叠 MACD"
          >∧</button>
        )}
      </div>
      <ReactECharts
        ref={ref}
        option={option}
        style={{ height: 280 }}
        notMerge={true}
        lazyUpdate={false}
      />
    </div>
  )
})

export default MACDPanel
