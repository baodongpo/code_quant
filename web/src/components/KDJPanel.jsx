/**
 * components/KDJPanel.jsx — KDJ 副图
 *
 * 包含：
 *   - K线（蓝）/ D线（黄）/ J线（紫虚线）
 *   - 80~120 浅绿背景（超买=卖出信号=绿底）
 *   - -20~20 浅红背景（超卖=买入信号=红底）
 *   - 20/80 参考线（水平虚线）
 *   - K/D 金叉/死叉圆形标记点（symbolSize=10，「金叉」/「死叉」16px加粗）
 *   - 右侧侧边说明栏（由父组件 ChartSidebar 提供）
 *
 * v3.5 变更：
 *   - 高度 140 → 200px
 *   - 移除 inside dataZoom，保留 slider
 *   - 移除 ECharts 内置 legend
 *   - 标记点改为圆形：金叉红圈/死叉绿圈（遵循红买绿卖）
 *   - 标记文字「金叉」/「死叉」，16px加粗
 *   - 区域背景色修正：超买=绿底，超卖=红底
 *   - 支持折叠（collapsed prop）
 *   - 改为 forwardRef
 *   - 配色统一引用 colors.js
 */
import React, { useMemo, forwardRef } from 'react'
import ReactECharts from 'echarts-for-react'
import SignalTag from './SignalTag.jsx'
import { C } from '../utils/colors.js'

const KDJPanel = forwardRef(function KDJPanel({ dates, kdj, signal, collapsed, onToggle }, ref) {
  const K = kdj?.K || []
  const D = kdj?.D || []
  const J = kdj?.J || []

  // 折叠状态：仅显示标题行
  if (collapsed) {
    const latestK = K.slice().reverse().find(v => v != null)
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
        <span style={{ fontSize: 12, fontWeight: 600, color: C.textMuted }}>KDJ(9)</span>
        {latestK != null && (
          <span style={{ fontSize: 12, color: C.text, fontWeight: 600 }}>K={latestK.toFixed(1)}</span>
        )}
        <SignalTag indicator="KDJ" signal={signal || 'neutral'} />
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
          title="展开 KDJ"
        >∨</button>
      </div>
    )
  }

  return (
    <KDJPanelInner
      ref={ref}
      dates={dates}
      K={K}
      D={D}
      J={J}
      signal={signal}
      onToggle={onToggle}
    />
  )
})

const KDJPanelInner = forwardRef(function KDJPanelInner({ dates, K, D, J, signal, onToggle }, ref) {
  const option = useMemo(() => {
    if (!dates || dates.length === 0) return {}

    // 标记 K/D 交叉点：圆形，金叉=红圈/死叉=绿圈（遵循红买绿卖）
    const crossPoints = []
    for (let i = 1; i < K.length; i++) {
      if (K[i] == null || D[i] == null || K[i - 1] == null || D[i - 1] == null) continue
      if (K[i - 1] <= D[i - 1] && K[i] > D[i]) {
        // 金叉：买入信号=红圈，标记在交叉点下方
        crossPoints.push({
          xAxis:       dates[i],
          yAxis:       K[i],
          value:       K[i],
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
      } else if (K[i - 1] >= D[i - 1] && K[i] < D[i]) {
        // 死叉：卖出信号=绿圈，标记在交叉点上方
        crossPoints.push({
          xAxis:       dates[i],
          yAxis:       K[i],
          value:       K[i],
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
          if (K[idx] != null) lines.push(`K: ${K[idx]?.toFixed(2)}`)
          if (D[idx] != null) lines.push(`D: ${D[idx]?.toFixed(2)}`)
          if (J[idx] != null) lines.push(`J: ${J[idx]?.toFixed(2)}`)
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
        min: -10, max: 110,
        splitLine: { lineStyle: { color: C.gridLine, type: 'dashed' } },
        axisLabel: { color: C.textMuted, fontSize: 10 },
        axisLine:  { lineStyle: { color: C.axisLine } },
      }],
      series: [
        // K 线（含金叉/死叉标记 + 超买超卖区域背景）
        {
          name: 'K', type: 'line', data: K,
          symbol: 'none', smooth: false,
          lineStyle: { color: C.kLine, width: 1.5 },
          markPoint: { data: crossPoints, animation: false },
          markArea: {
            silent: true,
            data: [
              // 超买区（80~120）= 卖出信号 = 绿底
              [{
                yAxis: 80,
                itemStyle: { color: C.overbought },
              }, { yAxis: 120 }],
              // 超卖区（-20~20）= 买入信号 = 红底
              [{
                yAxis: -20,
                itemStyle: { color: C.oversold },
              }, { yAxis: 20 }],
            ],
          },
          markLine: {
            silent: true,
            symbol: 'none',
            data: [
              // 超买参考线 = 绿（卖出信号色）
              { yAxis: 80, lineStyle: { color: C.overboughtLine, width: 1, type: 'dashed' } },
              // 超卖参考线 = 红（买入信号色）
              { yAxis: 20, lineStyle: { color: C.oversoldLine,   width: 1, type: 'dashed' } },
            ],
            label: { show: true, color: C.textMuted, fontSize: 10,
                     formatter: params => params.value === 80 ? '80' : '20' },
          },
        },
        // D 线
        {
          name: 'D', type: 'line', data: D,
          symbol: 'none', smooth: false,
          lineStyle: { color: C.dLine, width: 1.5 },
        },
        // J 线（紫虚线）
        {
          name: 'J', type: 'line', data: J,
          symbol: 'none', smooth: false,
          lineStyle: { color: C.jLine, width: 1, type: 'dashed' },
        },
      ],
    }
  }, [dates, K, D, J])

  return (
    <div style={{ flex: 1, minWidth: 0, background: C.chartBg, position: 'relative', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
      {/* 面板标题行（外部 HTML 标题，避免与图表内容重叠） */}
      <div style={{
        padding:    '8px 12px 0',
        display:    'flex',
        alignItems: 'center',
        gap:        6,
      }}>
        <span style={{ fontSize: 11, color: C.textMuted, fontWeight: 600 }}>KDJ(9)</span>
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
            title="折叠 KDJ"
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

export default KDJPanel
