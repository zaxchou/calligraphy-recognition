export interface LiShanLocation {
  id: string
  name: string
  province: string
  lat: number
  lng: number
  periods: string[]
  yearRanges: [number, number][]
  description: string
}

export interface PeriodConfig {
  id: string
  label: string
  yearRange: [number, number]
  color: string
  order: number
}

export const LI_SHAN_LOCATIONS: LiShanLocation[] = [
  // ── 出生与早年（1686–1711）──
  {
    id: 'xinghua',
    name: '兴化',
    province: '江苏',
    lat: 32.93,
    lng: 119.83,
    periods: ['early', 'late'],
    yearRanges: [[1686, 1713], [1744, 1745]],
    description:
      '李鱓出生于江苏扬州府兴化县（今泰州兴化市），为明朝首辅李春芳六世孙。少年时期在此读书学画，师从陆震学书法、魏凌苍学画、族嫂王媛学花卉。1706年中秀才。1711年南京乡试中举后因科场案暂回。晚年筑浮沤馆于城南，啸咏终老。',
  },

  // ── 仕途与宫廷（1711–1718）──
  {
    id: 'nanjing',
    name: '南京',
    province: '江苏',
    lat: 32.06,
    lng: 118.8,
    periods: ['exam-court'],
    yearRanges: [[1711, 1711]],
    description:
      '康熙五十年（1711年），26岁的李鱓赴江宁（南京）参加乡试，中举人。后因"江南科场案"受牵连，科名暂被革，回乡。',
  },
  {
    id: 'chengde',
    name: '承德（热河）',
    province: '河北',
    lat: 40.99,
    lng: 117.93,
    periods: ['exam-court'],
    yearRanges: [[1713, 1713]],
    description:
      '康熙五十二年（1713年），赴热河行宫（今河北承德）向康熙帝进献诗画，获赏识。奉旨入宫，入南书房行走，是"扬州八怪"中最早得遇圣恩者。',
  },
  {
    id: 'beijing',
    name: '北京',
    province: '北京',
    lat: 39.9,
    lng: 116.41,
    periods: ['exam-court', 'wandering', 'shandong'],
    yearRanges: [[1713, 1718], [1730, 1732], [1736, 1737]],
    description:
      '1713年入宫供奉内廷，师从蒋廷锡学工笔花鸟，研习恽寿平没骨法。1714年作《热河挹翠山房写花卉册》，1715年作《石畔秋英图》。因"画风放逸"被宫廷排斥，于1718年乞归。\n\n1730年二次入京，奉雍正帝旨意在刑部侍郎高其佩门下学指画，试图再入宫廷画苑未果。\n\n1736年再次赴京，以举人资格通过会试"检选"，重谋仕途。',
  },

  // ── 游历卖画（1718–1737）──
  {
    id: 'yangzhou',
    name: '扬州',
    province: '江苏',
    lat: 32.39,
    lng: 119.42,
    periods: ['wandering', 'late'],
    yearRanges: [[1718, 1736], [1745, 1756]],
    description:
      '1718年离京后取道赴扬州，以卖画为生。与郑板桥、黄慎、金农等"扬州八怪"交往密切，结识高翔、华嵒、边寿民等画友。画风转向泼墨写意，受徐渭、陈淳、石涛影响。1725年与郑板桥、黄慎同寓天宁寺。\n\n1732年作《松萱桂兰图》，1734年作《蕉阴鹅梦图》，1735年开始反复画《五松图》。\n\n1745年移居扬州小东门内西雷坛。1749年作《冷艳幽香图》提出"长于水"核心画论。1753年作《花卉十二屏风》。筑"浮沤馆"，以卖画为业直至去世。',
  },
  {
    id: 'huzhou',
    name: '湖州',
    province: '浙江',
    lat: 30.86,
    lng: 120.09,
    periods: ['wandering'],
    yearRanges: [[1727, 1727]],
    description:
      '雍正五年（1727年），游历湖州，作《花鸟图》等作品，画风逐渐成熟，破笔泼墨技法日益精进。',
  },
  {
    id: 'linyi',
    name: '临沂（琅琊）',
    province: '山东',
    lat: 35.1,
    lng: 118.35,
    periods: ['wandering'],
    yearRanges: [[1736, 1736]],
    description:
      '乾隆元年（1736年），游历临沂（古称琅琊、沂州），作画会友，为日后赴山东为官探路。',
  },

  // ── 山东为官（1737–1740）──
  {
    id: 'linzi',
    name: '临淄',
    province: '山东',
    lat: 36.82,
    lng: 118.36,
    periods: ['shandong'],
    yearRanges: [[1737, 1738]],
    description:
      '乾隆二年（1737年），赴任山东青州临淄知县。为政清简，深受百姓爱戴，载入《临淄县志》。',
  },
  {
    id: 'tengxian',
    name: '滕县（枣庄）',
    province: '山东',
    lat: 35.1,
    lng: 117.17,
    periods: ['shandong'],
    yearRanges: [[1738, 1740]],
    description:
      '乾隆三年（1738年）调任滕县知县。为官清廉刚直，因"违例开仓"或"忤大吏"得罪权贵，于乾隆五年（1740年）被罢官。',
  },

  // ── 罢官后滞留山东（1740–1744）──
  {
    id: 'jinan',
    name: '济南',
    province: '山东',
    lat: 36.67,
    lng: 117.0,
    periods: ['late'],
    yearRanges: [[1740, 1744]],
    description:
      '罢官后滞留山东，往返于滕县、历下（济南）、泰安、崮山等地卖画。情绪起伏大，创作高峰期。1744年返回故乡兴化。',
  },

  // ── 罢官定居（1740–1756）──
  {
    id: 'nantong',
    name: '南通',
    province: '江苏',
    lat: 32.0,
    lng: 120.86,
    periods: ['late'],
    yearRanges: [[1756, 1756]],
    description:
      '乾隆二十一年（1756年），寓居南通，作《梅石水山图》等。是年卒于南通，享年约七十一岁。',
  },
]

export const PERIOD_CONFIG: PeriodConfig[] = [
  {
    id: 'early',
    label: '出生与早年',
    yearRange: [1686, 1711],
    color: '#a08060',
    order: 1,
  },
  {
    id: 'exam-court',
    label: '仕途与宫廷',
    yearRange: [1711, 1718],
    color: '#c96442',
    order: 2,
  },
  {
    id: 'wandering',
    label: '游历成熟期',
    yearRange: [1719, 1737],
    color: '#5b7a8c',
    order: 3,
  },
  {
    id: 'shandong',
    label: '山东为官',
    yearRange: [1737, 1740],
    color: '#8b6d4b',
    order: 4,
  },
  {
    id: 'late',
    label: '罢官定居',
    yearRange: [1740, 1756],
    color: '#6b8b5a',
    order: 5,
  },
]

