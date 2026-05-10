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
    periods: ['early'],
    yearRanges: [[1686, 1711]],
    description:
      '李鱓出生于江苏扬州府兴化县（今泰州兴化市），为明朝首辅李春芳六世孙。少年时期在此读书学画，师从陆震学书法、魏凌苍学画、族嫂王媛学花卉，打下扎实基础。',
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
      '康熙五十年（1711年），26岁的李鱓赴南京参加乡试，中举人。这是科举道路上的重要节点，为其后入京供奉内廷奠定了基础。',
  },
  {
    id: 'chengde',
    name: '承德（热河）',
    province: '河北',
    lat: 40.99,
    lng: 117.93,
    periods: ['exam-court'],
    yearRanges: [[1714, 1714]],
    description:
      '康熙五十三年（1714年），随驾至热河，在挹翠山房作画。热河行宫时期得以观摩大量内府珍藏，眼界大开。',
  },

  // ── 游历与艺术成熟期（1719–1737）──
  {
    id: 'yangzhou',
    name: '扬州',
    province: '江苏',
    lat: 32.39,
    lng: 119.42,
    periods: ['wandering', 'late'],
    yearRanges: [
      [1719, 1737],
      [1740, 1756],
    ],
    description:
      '离京后长期寓居扬州，与郑板桥、黄慎、金农等"扬州八怪"交往密切，鬻画为生。1725年与郑板桥、黄慎同寓天宁寺。此阶段画风转向破笔泼墨，受高其佩、石涛影响显著。\n\n罢官后重返扬州，筑"浮沤馆"，以卖画为业直至去世。',
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
      '雍正五年（1727年），游历湖州，作《花鸟图》等作品，这一时期画风逐渐成熟，破笔泼墨技法日益精进。',
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
    yearRanges: [[1737, 1737]],
    description:
      '乾隆二年（1737年），赴山东临淄任职，开启仕途最后一站。在任期间清廉刚直，体恤民情。',
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
      '乾隆三年（1738年）署任滕县知县，四年（1739年）正式任职。为官清廉刚直，因得罪权贵，于乾隆五年（1740年）被罢官。罢官后曾暂居滕县北门里黄兰森家，并往来济南（历山）。',
  },

  {
    id: 'beijing',
    name: '北京',
    province: '北京',
    lat: 39.9,
    lng: 116.41,
    periods: ['exam-court', 'shandong'],
    yearRanges: [
      [1713, 1718],
      [1738, 1738],
    ],
    description:
      '康熙五十二年（1713年）客居京城，献诗行在，获康熙赏识，被召入南书房供奉内廷。期间随蒋廷锡学工笔花鸟，研习恽寿平没骨法。后因"画风放逸"被宫廷排斥，于1718年乞归离开。\n\n乾隆三年（1738年），赴京暂住卧佛寺，作《杏花春燕图》。',
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
      '乾隆二十一年（1756年），寓居南通，作《梅石水山图》等。是年卒于南通，享年约七十岁。',
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

