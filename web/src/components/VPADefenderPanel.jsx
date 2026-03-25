/**
 * components/VPADefenderPanel.jsx — VPA-Defender 量价共振副图（迭代7）
 *
 * 独立副图面板，与 MACD / RSI / KDJ 平级。
 * 双 Y 轴：左轴 Stop_Line（价格量纲），右轴 OBV/OBV_MA20。
 * 顶部信号标签展示最新一日的四象限状态。
 * [?] 新手解释浮层（默认隐藏，点击展开）。
 *
 * 迭代8变更：
 *   - BUG-emoji: 折叠/展开按钮字符统一为直接 Unicode 字符（∨/∧）
 *   - BUG-vpa-color: 破位警示配色改为绿色（#2ea043）
 *   - BUG-align: yAxis axisLabel 加 width:52, overflow:'truncate'
 *   - FEAT-guide-icon: HELP_ITEMS 加 iconType，浮层图标与图例形状一致
 *   - FEAT-collapse-btn: PanelInner 标题行移除折叠按钮（改由 ChartSidebar 统一渲染）
 *
 * 规格（遵循迭代裁定规范）：
 *   - 面板高度 200px（与其他副图统一）
 *   - 独立 ECharts 实例
 *   - forwardRef 暴露实例给 useChartSync
 *   - 禁止滚轮缩放，仅保留底部 slider dataZoom
 *   - 配色引用 utils/colors.js
 */
import React, { useState, useMemo, forwardRef } from 'react'
import ReactECharts from 'echarts-for-react'
import SignalTag from './SignalTag.jsx'
import { LegendMark } from './ChartSidebar.jsx'
import { C } from '../utils/colors.js'

// 四象限信号配置
const SIGNAL_CONFIG = {
  1: { emoji: '🟢', label: '共振主升浪', color: '#26a69a' },
  2: { emoji: '🟡', label: '顶背离预警', color: '#ffd54f' },
  3: { emoji: '🟢', label: '破位警示',   color: '#2ea043' },  // 迭代8 BUG-vpa-color: 改为绿色
  4: { emoji: '⚪', label: '底部观察',   color: '#b0bec5' },
}

// 新手解释浮层内容（迭代4+ 裁定规范：不含任何买卖指令）
// 迭代8 FEAT-guide-icon: 各条目加 iconType，与右侧图例形状保持一致
const HELP_ITEMS = [
  { iconType: 'line',   color: '#ef5350', text: '<b>防守线（红色实线）</b>：基于价格波动幅度计算的动态参考线。它会随着价格创新高而自动上移，但绝不会下降。当价格跌破这条线时，意味着波动幅度已经超出了正常范围。' },
  { iconType: 'line',   color: '#ff7043', text: '<b>橙红（空仓阻力线）</b>：追踪历史最低价上方 ATR 倍数距离，只降不升。价格长期在线下方运行，说明上方压力持续；价格有效突破阻力线，可关注趋势反转信号。' },
  { iconType: 'line',   color: '#42a5f5', text: '<b>OBV 能量潮（蓝色线）</b>：通过成交量的累计变化，观察资金的流入流出方向。当它持续上升时，说明伴随上涨的成交量大于伴随下跌的成交量。' },
  { iconType: 'dashed', color: '#ffa726', text: '<b>OBV 均线（橙色虚线）</b>：OBV 的 20 日平均值，用来过滤单日波动噪音，判断资金流向的中期趋势。' },
  { iconType: 'dot',    color: '#26a69a', text: '<b>绿色（共振主升浪）</b>：价格在防守线上方，且资金持续流入——量价配合良好' },
  { iconType: 'dot',    color: '#ffd54f', text: '<b>黄色（顶背离预警）</b>：价格仍在防守线上方，但资金已开始流出——量价出现分歧' },
  { iconType: 'dot',    color: '#2ea043', text: '<b>绿色（破位警示）</b>：价格跌破防守线——趋势可能发生变化' },  // 迭代8 BUG-vpa-color: 改为绿色
  { iconType: 'dot',    color: '#b0bec5', text: '<b>灰色（底部观察）</b>：价格在防守线下方，但资金开始流入——可能正在酝酿变化' },
]

const VPADefenderPanel = forwardRef(function VPADefenderPanel({ dates, closes, vpaDefender, signal, collapsed, onToggle }, ref) {
  const { stop_line = [], resistance_line = [], obv = [], obv_ma20 = [], signal: signalSeries = [] } = vpaDefender || {}

  // 最新有效信号
  let latestSignal = null
  for (let i = signalSeries.length - 1; i >= 0; i--) {
    if (signalSeries[i] != null) { latestSignal = signalSeries[i]; break }
  }
  const sigCfg = SIGNAL_CONFIG[latestSignal] || null

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
        <span style={{ fontSize: 12, fontWeight: 600, color: C.textMuted }}>VPA-Defender</span>
        {sigCfg && (
          <span style={{
            fontSize:     11,
            fontWeight:   600,
            color:        sigCfg.color,
            padding:      '2px 8px',
            borderRadius: 10,
            background:   `${sigCfg.color}18`,
          }}>
            {sigCfg.emoji} {sigCfg.label}
          </span>
        )}
        <SignalTag indicator="VPA_DEFENDER" signal={signal || 'neutral'} />
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
          title="展开 VPA-Defender"
        >∨</button>
      </div>
    )
  }

  return (
    <VPADefenderPanelInner
      ref={ref}
      dates={dates}
      closes={closes}
      stop_line={stop_line}
      resistance_line={resistance_line}
      obv={obv}
      obv_ma20={obv_ma20}
      signalSeries={signalSeries}
      signal={signal}
      latestSignal={latestSignal}
      sigCfg={sigCfg}
      onToggle={onToggle}
    />
  )
})

const VPADefenderPanelInner = forwardRef(function VPADefenderPanelInner({
  dates, closes, stop_line, resistance_line, obv, obv_ma20, signalSeries, signal, latestSignal, sigCfg, onToggle,
}, ref) {
  const [showHelp, setShowHelp] = useState(false)
  const option = useMemo(() => {
    if (!dates || dates.length === 0) return {}
    const zoomStart = Math.max(0, 100 - Math.round(120 / dates.length * 100))
    const signalMarkAreas = []
    let areaStart = null
    let areaSignal = null
    for (let i = 0; i < signalSeries.length; i++) {
      const s = signalSeries[i]
      if (s !== areaSignal) {
        if (areaStart !== null && areaSignal != null) {
          const cfg = SIGNAL_CONFIG[areaSignal]
          signalMarkAreas.push([
            { xAxis: dates[areaStart], itemStyle: { color: `${cfg.color}30` } },
            { xAxis: dates[i - 1] },
          ])
        }
        areaStart = s != null ? i : null
        areaSignal = s
      }
    }
    // 最后一段
    if (areaStart !== null && areaSignal != null) {
      const cfg = SIGNAL_CONFIG[areaSignal]
      signalMarkAreas.push([
        { xAxis: dates[areaStart], itemStyle: { color: `${cfg.color}30` } },
        { xAxis: dates[dates.length - 1] },
      ])
    }

    return {
      backgroundColor: C.chartBg,
      animation: false,
      legend: { show: false, data: ['收盘价', '防守线', '阻力线', 'OBV', 'OBV均线'] },
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
          if (closes && closes[idx] != null) lines.push(`收盘价: ${closes[idx]?.toFixed(2)}`)
          if (stop_line[idx] != null) lines.push(`防守线: ${stop_line[idx]?.toFixed(2)}`)
          if (resistance_line[idx] != null) lines.push(`阻力线: ${resistance_line[idx]?.toFixed(2)}`)
          if (obv[idx] != null) lines.push(`OBV: ${Number(obv[idx]).toLocaleString()}`)
          if (obv_ma20[idx] != null) lines.push(`OBV均线: ${Number(obv_ma20[idx]).toLocaleString()}`)
          const sig = signalSeries[idx]
          if (sig != null && SIGNAL_CONFIG[sig]) {
            lines.push(`信号: ${SIGNAL_CONFIG[sig].emoji} ${SIGNAL_CONFIG[sig].label}`)
          }
          return lines.join('<br/>')
        },
      },
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
      grid: [{ left: 60, right: 60, top: 20, bottom: 28 }],
      xAxis: [{
        type: 'category', data: dates,
        axisLine:  { lineStyle: { color: C.axisLine } },
        axisLabel: { color: C.textMuted, fontSize: 10 },
        axisTick:  { lineStyle: { color: C.axisLine } },
        splitLine: { show: false },
      }],
      yAxis: [
        // 左 Y 轴：价格（Stop_Line）
        {
          scale:     true,
          splitLine: { lineStyle: { color: C.gridLine, type: 'dashed' } },
          axisLabel: { color: C.textMuted, fontSize: 10, width: 52, overflow: 'truncate' },
          axisLine:  { lineStyle: { color: C.axisLine } },
        },
        // 右 Y 轴：OBV
        {
          scale:     true,
          splitLine: { show: false },
          axisLabel: {
            color:    C.textMuted,
            fontSize: 10,
            width:    52,
            overflow: 'truncate',
            formatter: (val) => {
              if (Math.abs(val) >= 1e8) return (val / 1e8).toFixed(1) + '\u4EBF'
              if (Math.abs(val) >= 1e4) return (val / 1e4).toFixed(0) + '\u4E07'
              return val
            },
          },
          axisLine: { lineStyle: { color: C.axisLine } },
        },
      ],
      series: [
        // 收盘价（左 Y 轴，灰色细线，辅助参考）
        {
          name:       '收盘价',
          type:       'line',
          yAxisIndex: 0,
          data:       closes || [],
          symbol:     'none',
          smooth:     false,
          lineStyle:  { color: '#8b949e', width: 1, type: 'solid', opacity: 0.6 },
          z:          1,
        },
        // Stop_Line（左 Y 轴，红色实线）
        {
          name:       '防守线',
          type:       'line',
          yAxisIndex: 0,
          data:       stop_line,
          symbol:     'none',
          smooth:     false,
          lineStyle:  { color: '#ef5350', width: 2 },
          z:          3,
          markArea: signalMarkAreas.length > 0 ? {
            silent: true,
            data:   signalMarkAreas,
          } : undefined,
        },
        // 阻力线（左 Y 轴，橙黄色实线，只降不升）（迭代8.1-patch）
        {
          name:       '阻力线',
          type:       'line',
          yAxisIndex: 0,
          data:       resistance_line,
          symbol:     'none',
          smooth:     false,
          lineStyle:  { color: '#ff7043', width: 1.5 },
          z:          2,
        },
        // OBV（右 Y 轴，蓝色实线 + 半透明面积）
        {
          name:       'OBV',
          type:       'line',
          yAxisIndex: 1,
          data:       obv,
          symbol:     'none',
          smooth:     false,
          lineStyle:  { color: '#42a5f5', width: 1 },
          areaStyle:  { color: 'rgba(66,165,245,0.08)' },
          z:          2,
        },
        // OBV_MA20（右 Y 轴，橙色虚线）
        {
          name:       'OBV均线',
          type:       'line',
          yAxisIndex: 1,
          data:       obv_ma20,
          symbol:     'none',
          smooth:     false,
          lineStyle:  { color: '#ffa726', width: 1, type: 'dashed' },
          z:          2,
        },
      ],
    }
  }, [dates, closes, stop_line, resistance_line, obv, obv_ma20, signalSeries])

  return (
    <div style={{ flex: 1, minWidth: 0, background: C.chartBg, position: 'relative', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
      {/* 面板标题行 + [?] 新手解释浮层 */}
      {/* 迭代8 FEAT-collapse-btn: 折叠按钮已移至 ChartSidebar，此处仅保留标题/信号/[?] */}
      <div style={{
        padding:    '8px 12px 0',
        display:    'flex',
        alignItems: 'center',
        gap:        6,
      }}>
        <span style={{ fontSize: 11, color: C.textMuted, fontWeight: 600 }}>VPA-Defender(22,3.0,20)</span>
        {sigCfg && (
          <span style={{
            fontSize:     11,
            fontWeight:   600,
            color:        sigCfg.color,
            padding:      '1px 8px',
            borderRadius: 10,
            background:   `${sigCfg.color}18`,
          }}>
            {sigCfg.emoji} {sigCfg.label}
          </span>
        )}
        {/* [?] 新手解释浮层按钮（迭代4+ 裁定规范强制） */}
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
      {/* [?] 新手解释浮层内容（默认隐藏，点击展开） */}
      {/* 迭代8 FEAT-guide-icon: 图标按 iconType 渲染，与右侧图例形状一致 */}
      {showHelp && (
        <div style={{
          margin:       '6px 12px 0',
          padding:      10,
          background:   C.panelBg,
          borderRadius: 8,
          border:       `1px solid ${C.border}`,
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: C.accentText, marginBottom: 6 }}>
            📖 VPA-Defender 量价共振防守指标
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

export default VPADefenderPanel
