/**
 * components/MACDPanel.jsx — MACD 副图
 *
 * 包含：
 *   - DIF 线（蓝）/ DEA 线（黄）
 *   - MACD 柱（正值红 / 负值绿）
 *   - 金叉/死叉圆形标记（symbolSize=10，「金叉」/「死叉」16px加粗）
 *   - 右侧侧边说明栏（由父组件 ChartSidebar 提供）
 *
 * 迭代8变更：
 *   - BUG-align: grid 改为 left:60, right:60，去掉 containLabel，yAxis axisLabel 加 width:52
 *   - FEAT-guide-top: 新增 [?] 按钮 + showHelp 状态 + HELP_ITEMS 说明浮层
 *   - FEAT-collapse-btn: PanelInner 标题行移除折叠按钮（改由 ChartSidebar 统一渲染）
 *   - FEAT-guide-icon: HELP_ITEMS 各条目含 iconType，图标与图例形状一致
 */
import React, { useState, useMemo, forwardRef } from 'react'
import ReactECharts from 'echarts-for-react'
import SignalTag from './SignalTag.jsx'
import { LegendMark } from './ChartSidebar.jsx'
import { C } from '../utils/colors.js'

// 说明浮层内容（迭代8 FEAT-guide-top + FEAT-guide-icon）
// iconType: 'line'|'dashed'|'circle'|'bar'|'dot'，与右侧 ChartSidebar 图例形状对应
const HELP_ITEMS = [
  { iconType: 'line',   color: C.dif,        text: '<b>DIF 线</b>：短期（12日）与长期（26日）移动均线之差，反映短期趋势动能。DIF 持续上升说明短期涨势强于长期。' },
  { iconType: 'line',   color: C.dea,        text: '<b>DEA 线</b>：DIF 的 9 日平均，平滑了 DIF 的波动，用于辅助判断趋势方向。' },
  { iconType: 'bar',    color: C.macdBarPos, text: '<b>MACD 柱（正）</b>：DIF 在 DEA 上方时柱为正值（红色），说明短期动能强于长期。柱越高说明多头力量越强。' },
  { iconType: 'bar',    color: C.macdBarNeg, text: '<b>MACD 柱（负）</b>：DIF 在 DEA 下方时柱为负值（绿色），说明短期动能弱于长期。柱越深说明空头力量越强。' },
  { iconType: 'circle', color: C.buy,        text: '<b>红圈●金叉</b>：DIF 从下方穿越 DEA，短期动能由弱转强的信号。出现在低位时意义更大。' },
  { iconType: 'circle', color: C.sell,       text: '<b>绿圈●死叉</b>：DIF 从上方穿越 DEA，短期动能由强转弱的信号。出现在高位时意义更大。' },
]

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
  const [showHelp, setShowHelp] = useState(false)

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
      legend: { show: false, data: ['DIF', 'DEA', 'MACD柱'] },
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
      // 迭代8 BUG-align: 统一 left:60, right:60，去掉 containLabel
      grid: [{ left: 60, right: 60, top: 20, bottom: 28 }],
      xAxis: [{
        type: 'category', data: dates,
        axisLine:  { lineStyle: { color: C.axisLine } },
        axisLabel: { color: C.textMuted, fontSize: 10 },
        axisTick:  { lineStyle: { color: C.axisLine } },
        splitLine: { show: false },
      }],
      // 迭代8 BUG-align: axisLabel 加 width:52, overflow:'truncate'
      yAxis: [{
        scale: true,
        splitLine: { lineStyle: { color: C.gridLine, type: 'dashed' } },
        axisLabel: { color: C.textMuted, fontSize: 10, width: 52, overflow: 'truncate' },
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
      {/* 面板标题行（迭代8 FEAT-collapse-btn: 折叠按钮已移至 ChartSidebar，仅保留标题/信号/[?]） */}
      <div style={{
        padding:    '8px 12px 0',
        display:    'flex',
        alignItems: 'center',
        gap:        6,
      }}>
        <span style={{ fontSize: 11, color: C.textMuted, fontWeight: 600 }}>MACD(12,26,9)</span>
        {/* 迭代8 FEAT-guide-top: 新增 [?] 说明浮层按钮 */}
        <button
          onClick={() => setShowHelp(v => !v)}
          title={showHelp ? '收起说明' : '展开指标说明'}
          style={{
            flexShrink:   0,
            background:   showHelp ? C.accentBg : 'none',
            border:       `1px solid ${showHelp ? C.accent : C.border2}`,
            borderRadius: 4,
            color:        showHelp ? C.accentText : C.textMuted,
            fontSize:     11,
            fontWeight:   600,
            cursor:       'pointer',
            padding:      '1px 6px',
            lineHeight:   '18px',
          }}
        >?</button>
      </div>
      {/* 迭代8 FEAT-guide-top: 说明浮层（默认隐藏，点击 [?] 展开） */}
      {showHelp && (
        <div style={{
          margin:       '6px 12px 0',
          padding:      10,
          background:   C.panelBg,
          borderRadius: 8,
          border:       `1px solid ${C.border}`,
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: C.accentText, marginBottom: 6 }}>
            📖 MACD 趋势动能指标
          </div>
          {HELP_ITEMS.map((item, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 6, fontSize: 11, color: C.textMuted, lineHeight: 1.5, padding: '2px 0' }}>
              <span style={{ flexShrink: 0, marginTop: 4, display: 'inline-flex', alignItems: 'center' }}>
                <LegendMark type={item.iconType || 'dot'} color={item.color} />
              </span>
              <span dangerouslySetInnerHTML={{ __html: item.text }} />
            </div>
          ))}
        </div>
      )}
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
