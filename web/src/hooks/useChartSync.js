/**
 * hooks/useChartSync.js — 跨图时间轴联动 Hook
 *
 * 方案说明：
 *   不使用 echarts.connect()，因为主图有两个 grid（K线区 + 成交量区），
 *   echarts.connect() 在成交量区悬停时存在联动失效的已知问题。
 *   改用监听 updateAxisPointer 事件手动同步十字线，监听所有图表的
 *   dataZoom 事件双向同步滑动条（BUG-03 修复）。
 *
 * BUG-03 修复：
 *   原实现仅从主图单向同步 dataZoom 到副图，副图 slider 拖动时无法反向
 *   同步到主图及其他副图。
 *   新实现：对主图 + 所有副图均注册 dataZoom 监听，任意图表 slider 变化时
 *   广播到其余所有图表。使用互斥标志 syncing 防止循环触发。
 *
 * 折叠重建修复：
 *   副图折叠/展开使用条件渲染，展开时产生全新 ECharts 实例。ref 对象引用
 *   不变所以 effect 不重跑。通过额外接收 collapsed 状态对象并加入依赖数组，
 *   折叠状态变化时 effect 重新执行，自动将新实例纳入同步链。
 *
 * @param mainRef   - 主图 ReactECharts 组件 ref
 * @param subRefs   - 副图 ReactECharts 组件 ref 数组 [macdRef, rsiRef, kdjRef]
 * @param collapsed - 折叠状态对象 { MACD, RSI, KDJ }，用于触发 effect 重绑定
 */
import { useEffect } from 'react'

export default function useChartSync(mainRef, subRefs, collapsed) {
  useEffect(() => {
    // 用外部变量持有 cleanup 引用，确保 useEffect 返回函数能正确调用
    // （setTimeout 内部的 return 会被 setTimeout 丢弃，不能直接 return）
    let cleanup = null

    const timer = setTimeout(() => {
      const main = mainRef?.current?.getEchartsInstance?.()
      if (!main) return

      const subs = subRefs
        .map(r => r?.current?.getEchartsInstance?.())
        .filter(Boolean)

      const allCharts = [main, ...subs]

      // 1. 主图十字线移动时，同步到所有副图
      const onAxisPointer = (event) => {
        // axesInfo 包含主图内所有联动轴（xAxisIndex:0 和 xAxisIndex:1 均在此）
        const xInfo = event.axesInfo?.find(a => a.axisDim === 'x')
        if (xInfo == null) return
        const dataIndex = xInfo.value   // category 轴 value 即 dataIndex
        if (dataIndex == null) return
        subs.forEach(c => {
          c.dispatchAction({ type: 'showTip', seriesIndex: 0, dataIndex })
        })
      }
      main.on('updateAxisPointer', onAxisPointer)

      // 2. 鼠标离开主图区域 → 隐藏所有副图浮窗
      const mainDom = main.getDom()
      const onMouseLeave = () => {
        subs.forEach(c => c.dispatchAction({ type: 'hideTip' }))
      }
      mainDom.addEventListener('mouseleave', onMouseLeave)

      // 3. 任意图表 dataZoom 变化时 → 全局广播（双向联动，BUG-03 修复）
      //    互斥标志：防止 dispatchAction 触发目标图表 dataZoom 事件后循环调用
      const syncing = { value: false }
      const zoomHandlers = []

      allCharts.forEach((chart, idx) => {
        const others = allCharts.filter((_, j) => j !== idx)
        const handler = () => {
          if (syncing.value) return
          const option = chart.getOption()
          const zoom = option?.dataZoom?.[0]  // slider 是第0个（已移除 inside）
          if (!zoom) return
          syncing.value = true
          others.forEach(c => {
            c.dispatchAction({ type: 'dataZoom', start: zoom.start, end: zoom.end })
          })
          syncing.value = false
        }
        chart.on('dataZoom', handler)
        zoomHandlers.push({ chart, handler })
      })

      // 注册 cleanup，供 useEffect 返回函数调用
      cleanup = () => {
        main.off('updateAxisPointer', onAxisPointer)
        mainDom.removeEventListener('mouseleave', onMouseLeave)
        zoomHandlers.forEach(({ chart, handler }) => {
          chart.off('dataZoom', handler)
        })
      }
    }, 300)

    // useEffect 返回函数：取消定时器 + 执行监听器清理（cleanup 已通过外部变量持有）
    return () => {
      clearTimeout(timer)
      cleanup?.()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mainRef, ...subRefs, collapsed])
}
