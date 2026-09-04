# -*- coding: utf-8 -*-
# 向 zh.js/en.js 追加 stats/compare/unit/search 键与作品标题值键（幂等：已存在则跳过）
import io, re

TITLES = {
    '书画合装卷': 'Calligraphy and Painting, Combined Handscroll',
    '书画图立轴': 'Calligraphy and Painting, Hanging Scroll',
    '兰石灵芝图': 'Orchid, Rock and Lingzhi',
    '北冥有鱼': 'A Fish in the Northern Sea',
    '十二墨花图': 'Twelve Ink Flowers',
    '孔雀图': 'Peacocks',
    '寒梅图': 'Winter Plum',
    '忠孝图': 'Loyalty and Filial Piety',
    '折枝写生册之七': 'Flower Sketches from Life, Album Leaf No. 7',
    '折枝写生册之六': 'Flower Sketches from Life, Album Leaf No. 6',
    '杂画册五开之五': 'Miscellaneous Paintings, Album of Five Leaves No. 5',
    '杂画册五开之四': 'Miscellaneous Paintings, Album of Five Leaves No. 4',
    '杂画册十开之十': 'Miscellaneous Paintings, Album of Ten Leaves No. 10',
    '杂花图': 'Miscellaneous Flowers',
    '水仙双鱼图': 'Narcissus and Two Fish',
    '牡丹图': 'Peonies',
    '花卉册之菊花': 'Flowers Album: Chrysanthemum',
    '花卉册八开之一': 'Flowers, Album of Eight Leaves No. 1',
    '花卉四开之四': 'Flowers, Album of Four Leaves No. 4',
    '花鸟册十开之四': 'Birds and Flowers, Album of Ten Leaves No. 4',
    '花鸟草虫诗画册之三': 'Birds, Flowers and Insects, Poetry-Painting Album No. 3',
    '茉莉图': 'Jasmine',
    '荔枝2': 'Lychee 2',
    '虹鱼图': 'Rainbow Fish',
}
NUMS = '一二三四五六七八九十'
def cnum(n):
    if n <= 10: return NUMS[n-1]
    if n == 11: return '十一'
    if n == 12: return '十二'
    raise ValueError(n)
for i in range(1, 13):
    TITLES[f'花卉册十二开之{cnum(i)}'] = f'Flowers, Album of Twelve Leaves No. {i}'

UI_KEYS = {
    'stats.overview_title': ('{name}题跋数据概览', '{name} — Inscription Data Overview'),
    'stats.all_artists': ('全部作者', 'All Artists'),
    'stats.all': ('全部', 'All'),
    'stats.no_data': ('暂无分析数据', 'No analysis data yet'),
    'stats.upload_tip': ('上传画作后将自动生成统计数据', 'Statistics will be generated automatically after artworks are uploaded'),
    'stats.early': ('早', 'Early'),
    'stats.mid': ('中', 'Mid'),
    'stats.late': ('晚', 'Late'),
    'stats.unknown': ('未分', 'Unsorted'),
    'stats.char_count': ('字数', 'Word Count'),
    'stats.min': ('最低', 'Min'),
    'stats.avg': ('平均', 'Avg'),
    'stats.max': ('最高', 'Max'),
    'stats.chart_theme': ('主题 × 题跋面积', 'Theme × Inscription Area'),
    'stats.chart_period': ('分期 × 题跋面积', 'Period × Inscription Area'),
    'stats.theme_share': ('主题占比', 'Theme Share'),
    'stats.marker_1': ('壹', 'I'),
    'stats.marker_2': ('贰', 'II'),
    'stats.area_pct': ('面积(%)', 'Area (%)'),
    'stats.avg_area': ('平均面积', 'Avg Area'),
    'stats.avg_words': ('平均词数', 'Avg Words'),
    'stats.tooltip_sample': ('样本: {n}幅', 'Sample: {n} works'),
    'stats.unknown_artist': ('未知作者', 'Unknown Artist'),
    'stats.click_detail': ('点击查看详情', 'Click for details'),
    'compare.title': ('名家对比', 'Master Comparison'),
    'compare.count': ('画作数量', 'Artwork Count'),
    'compare.avg_inscription': ('平均题跋占比', 'Avg Inscription Ratio'),
    'compare.avg_painting': ('平均绘画占比', 'Avg Painting Ratio'),
    'compare.avg_blank': ('平均留白占比', 'Avg Blank Ratio'),
    'compare.richness': ('形式丰富度', 'Format Richness'),
    'compare.richness_unit': ('种/幅', 'types/work'),
    'compare.dominant_form': ('主导形式占比', 'Dominant Format'),
    'compare.invasion': ('题跋侵入度', 'Inscription Intrusion'),
    'unit.works': ('幅', 'works'),
    'unit.works_count': ('{n}件', '{n} works'),
    'unit.artists_count': ('{n} 位', '{n} artists'),
    'search.f_inscription': ('题跋', 'Inscription'),
    'search.f_inscription_modern': ('题跋(白话)', 'Inscription (modern)'),
    'search.f_seal': ('印章', 'Seal'),
    'search.f_notes': ('备注', 'Notes'),
    'search.f_analysis': ('AI分析', 'AI Analysis'),
    'search.f_year': ('年代', 'Year'),
}

def add_block(path, lines, anchor):
    s = io.open(path, encoding='utf-8').read()
    new = [l for l in lines if re.match(r"^  '([^']*)':", l) and not re.search(r"^  '" + re.escape(re.match(r"^  '([^']*)':", l).group(1)) + r"':", s + '\n', re.M)]
    new = [l for l in lines]
    # 逐条幂等
    out = []
    for l in lines:
        m = re.match(r"^  '([^']*)':", l)
        if m and re.search("^  '" + re.escape(m.group(1)) + r"':", s, re.M):
            continue
        out.append(l)
    if not out:
        print(path, 'nothing to add')
        return
    s = s.replace(anchor, ''.join(out) + '\n' + anchor, 1)
    io.open(path, 'w', encoding='utf-8', newline='\n').write(s)
    print(path, 'added', len(out))

zh_ui = ["  '%s': %s,\n" % (k, repr(v[0]).replace("'", "'", 1) if False else "'" + v[0].replace("\\", "\\\\").replace("'", "\\'") + "'") for k, v in UI_KEYS.items()]
en_ui = ["  '%s': '%s',\n" % (k, v[1].replace('\\', '\\\\').replace("'", "\\'")) for k, v in UI_KEYS.items()]
en_titles = ["  '%s': '%s',\n" % (k, v.replace("'", "\\'")) for k, v in TITLES.items()]

add_block('src/locales/zh.js', zh_ui, "  'gallery.search_placeholder': '搜索画作...',\n")
add_block('src/locales/en.js', en_ui, "  'gallery.search_placeholder': 'Search artworks...',\n")
add_block('src/locales/en.js', en_titles, "  // Dynasties & eras\n")
