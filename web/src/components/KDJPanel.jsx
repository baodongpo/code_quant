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
const HELP_ITEMS = [
  { iconType: 'line',   color: C.kLine, text: '<b>K 线</b>：随机指标的快线，对价格变化较为敏感，反映短期超买超卖状态。' },
  { iconType: 'line',   color: C.dLine, text: '<b>D 线</b>：K 线的 3 日平均，较平滑，用于确认趋势方向。' },
  { iconType: 'dashed', color: C.jLine, text: '<b>J 线（虚线）</b>：K 与 D 的放大版（3K - 2D），超过 80 或低于 20 时波动往往加剧，可超出 0~100 范围。' },
  { iconType: 'circle', color: C.buy,   text: '<b>红圈●金叉</b>：K 线从下方穿越 D 线，低位出现时反映短期超卖后的动能回升。' },
  { iconType: 'circle', color: C.sell,  text: '<b>绿圈●死叉</b>：K 线从上方穿越 D 线，高位出现时反映短期超买后的动能回落。' },
]

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
  const [showHelp, setShowHelp] = useState(false)

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
      legend: { show: false, data: ['K', 'D', 'J'] },
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
        min: -10, max: 110,
        splitLine: { lineStyle: { color: C.gridLine, type: 'dashed' } },
        axisLabel: { color: C.textMuted, fontSize: 10, width: 52, overflow: 'truncate' },
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
      {/* 面板标题行（迭代8 FEAT-collapse-btn: 折叠按钮已移至 ChartSidebar，仅保留标题/信号/[?]） */}
      <div style={{
        padding:    '8px 12px 0',
        display:    'flex',
        alignItems: 'center',
        gap:        6,
      }}>
        <span style={{ fontSize: 11, color: C.textMuted, fontWeight: 600 }}>KDJ(9)</span>
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
            📖 KDJ 短线时机指标
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
        style={{ height: 240 }}
        notMerge={false}
        lazyUpdate={false}
      />
    </div>
  )
})

export default KDJPanel
