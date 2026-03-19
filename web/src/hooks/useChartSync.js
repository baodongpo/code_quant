/**
 * hooks/useChartSync.js — 跨图时间轴联动 Hook
 *
 * 方案说明：
 *   不使用 echarts.connect()，因为主图有两个 grid（K线区 + 成交量区），
 *   echarts.connect() 在成交量区悬停时存在联动失效的已知问题。
 *   改用监听主图 updateAxisPointer 事件，手动 dispatchAction 到各副图。
 *
 * @param mainRef  - 主图 ReactECharts 组件 ref
 * @param subRefs  - 副图 ReactECharts 组件 ref 数组 [macdRef, rsiRef, kdjRef]
 */
import { useEffect } from 'react'

export default function useChartSync(mainRef, subRefs) {
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

      // 3. 主图 dataZoom 变化时 → 同步副图缩放范围
      const onDataZoom = () => {
        const option = main.getOption()
        const zoom = option?.dataZoom?.[0]  // slider 是第0个（已移除 inside）
        if (!zoom) return
        subs.forEach(c => {
          c.dispatchAction({ type: 'dataZoom', start: zoom.start, end: zoom.end })
        })
      }
      main.on('dataZoom', onDataZoom)

      // 注册 cleanup，供 useEffect 返回函数调用
      cleanup = () => {
        main.off('updateAxisPointer', onAxisPointer)
        main.off('dataZoom', onDataZoom)
        mainDom.removeEventListener('mouseleave', onMouseLeave)
      }
    }, 300)

    // useEffect 返回函数：取消定时器 + 执行监听器清理（cleanup 已通过外部变量持有）
    return () => {
      clearTimeout(timer)
      cleanup?.()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mainRef, ...subRefs])
}
