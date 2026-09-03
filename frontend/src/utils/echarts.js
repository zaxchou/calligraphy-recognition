// echarts 按需注册（v2.0 构建瘦身：全量 ~1MB → 按需，含项目实际用到的图表与组件）
// 新增图表类型时，在此文件补充注册即可，不要直接 import 'echarts' 全量包
import * as echarts from 'echarts/core'
import {
  BarChart,
  LineChart,
  PieChart,
  ScatterChart,
  EffectScatterChart,
  RadarChart,
  GraphChart,
  LinesChart,
} from 'echarts/charts'
import {
  GeoComponent,
  RadarComponent,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  PolarComponent,
  AxisPointerComponent,
  DatasetComponent,
  TransformComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  ScatterChart,
  EffectScatterChart,
  RadarChart,
  GraphChart,
  LinesChart,
  GeoComponent,
  RadarComponent,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  PolarComponent,
  AxisPointerComponent,
  DatasetComponent,
  TransformComponent,
  CanvasRenderer,
])

export default echarts
export { echarts }
