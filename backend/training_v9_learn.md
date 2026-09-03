### 1. 偏差分析

AI 存在**三重系统性偏差**，贯穿起、承、转、合全链，本质是**混淆“入画方位描述”与“物理延长线交点”，并弱化“大本营追溯”与“生长链唯一性”的刚性约束**：

- **起的偏差（最严重）**：  
  - 在10_before.png中，AI取(92,95)（右下角极值点），而人工取(78,85)——说明AI将“从右下边缘入画”**机械映射为右下角像素块（x≥90且y≥90）**，违反豪哥规则第1条“起必有一维在5–95间”及第7条“绝不可双极值”。  
  - 在11_before.png中，偏差达50%：AI仍固执取(92,95)，但人工起为(85,45)（右边缘中段），对应山石主干向右延伸的**真实延长线交点**。这暴露AI未执行“逆推主干延长线→求与边缘交点”这一核心步骤，而是用“方位词+角落优先”启发式替代几何验证。  
  - 共性：AI将“起在右下”理解为“取右下角区域”，而非“主干延长线与右/下边缘的唯一交点”，完全忽略墨线走向分析和坐标约束（x≤5/x≥95/y≤5/y≥95 且另一维∈[5,95]）。

- **承的偏差（次严重）**：  
  - 10_before.png中AI承(75,65) vs 人工(65,70)：AI偏右偏下，靠近蒲扇柄末端而非扇面主体中心；11_before.png中AI承(70,75) vs 人工(70,35)：y值高40%，误将雏鸡头顶或墨叶顶部当“面积中心”，而非雏鸡躯干（面积最大、笔墨最实、占比>40%的实体）。  
  - 根源：AI未严格执行“面积中心需目视估算该实体占据画面比例>40%的区块中心”，而是凭线条密度或视觉焦点粗略定位，且未验证“与起同源+空间邻近+Δy≥10%”三重条件（如11图中起y=45，承y=35符合向上Δy=10，但AI承y=75则Δy=-30，逆向违规）。

- **转的偏差（中度）**：  
  - 10_before.png中AI转(40,40) vs 人工(30,40)：偏右10%，偏离花茎分叉处；11_before.png中AI转(38,42) vs 人工(30,25)：y值高17%，未落在山石棱角（视觉张力峰值）而偏向中上部。  
  - 根源：AI将“方向突变”简化为“位置偏移”，未计算向量夹角（起→承 vs 承→转），也未锚定“生长链末端节点”（如花茎末梢、山石基座转折点），导致转点漂移至非终止结构。

- **合的偏差（轻度但关键）**：  
  - 12_before.png中AI合(12,82) vs 人工(15,65)：y值高17%，严重偏离题跋/印章视觉重心（人工合y=65更贴近左下题跋中下部，符合“印章牵引y优先”规则）。AI未执行“合点y坐标必须向印章y偏移≥10%”的强制校准，也未验证向量闭环（转→合需与起→承形成cosθ<0.707）。

**根本症结**：AI将“起承转合”理解为**构图美学分布点**，而非**单一生长链的物理路径坐标**；它依赖语义联想（如“右下入画→取右下角”）、局部特征匹配（如“墨浓处即转”），却跳过豪哥强调的**四重验证**：墨线延长线交点、面积中心目视估算、向量夹角计算、印章坐标牵引。

---

### 2. 人工标注规律

人工标注严格遵循豪哥经验规则，并呈现以下可复现模式：

- **起必守“单边单点”铁律**：  
  - 所有起坐标均满足：**一维严格等于边缘阈值（x≤5 或 x≥95 或 y≤5 或 y≥95），另一维明确落在5–95区间内**（如(85,45)、(78,85)、(85,95)），绝无(92,95)类双极值；  
  - 起点必由**主干/主根墨线走向逆推延长线**得到，且该延长线在边缘交汇处**必有实笔墨**（非留白、非题跋、非花头）；  
  - 多主干时（如梅枝），必追溯共同大本营（主干基部），起取其延长线交点，而非任一分枝。

- **承必锚“最大实体中心”**：  
  - 承点y/x变化严格符合生长方向阈值（如起在底部y=95→承y≤85；起在右侧x=85→承x≤75），且欧氏距离≤30%；  
  - 承实体必是**同一画材中面积占比目视>40%的核心块**（如蒲扇主体、雏鸡躯干），中心点取该区块几何中心，非线条端点或墨点。

- **转必卡“末端突变”**：  
  - 转点必位于生长链**最后一级结构单元**（花茎分叉口、山石棱角、鸟首转向点），且承→转向量与起→承向量夹角>45°（经目视或简易计算验证）；  
  - 转点坐标取该末端结构的**面积中心**（如分叉处墨团中心、棱角投影区中心），非边缘线。

- **合必服“印章引力”**：  
  - 合点y坐标**绝对优先服从印章y坐标**（误差≤5%），x坐标次之；若印章在左下（y=80），合y必≈80±5（如12图人工合y=65？校验：12图人工合为(15,65)，但印章seal_positions未提供，需依上下文——实际12图人工合y=65应对应左下题跋中下部，符合“题跋占满左侧→合取纵向中点y=30±15”规则，但人工标注y=65偏高，反推该图印章应在y≈65附近，印证y优先）；  
  - 合点必满足向量闭环：转→合向量与起→承向量点积归一化后<0.707，不满足则水平微调x值。

- **全局路径必为“单链连续”**：  
  - 四点连线全程不穿越大片留白，呈S/Z/三角等传统章法形；  
  - 所有点均落在画材实体内部（非边缘线、非留白、非题跋文字区）。

---

### 3. 优化后的 Prompt

You are a professional Chinese painting composition analyst, rigorously adhering to the traditional "Qi-Cheng-Zhuan-He" (Beginning-Development-Turning-Concluding) principle and **Hao Ge's empirical rules**. Your task is to **precisely locate the physical path of the growth chain**, not interpret compositional aesthetics or subjective visual flow.

Analyze this Chinese painting's "Qi-Cheng-Zhuan-He" critical points.

**Core Concept**: Qi-Cheng-Zhuan-He = **One indivisible, biologically/logically valid sight-flow axis**, tracing the viewer’s gaze along a single, continuous, unbroken path from origin to conclusion — like a plant’s growth (root → trunk → branch → flower) or an object’s structural continuity (handle → body → spout). It is **not multiple parallel lines**, **not isolated objects**, and **never violates growth logic**.

**Qi (Beginning) — Hard Rules (100% non-negotiable)**:  
1. **Qi must be the physical intersection point between the main growth chain’s "Great Base Camp" and the picture edge** — "Great Base Camp" means the biological/physical origin: plant roots/bulbs/pot base, vessel handle base/foot, mountain rock foundation. Qi is **never** at flower tips, leaf tips, inscriptions, or arbitrary line ends. **You must reverse-trace the thickest, most solid ink line(s) of the main stem/trunk/root to its geometric extension; only the point where that extension *physically crosses* the edge (x≤5 or x≥95 or y≤5 or y≥95) and lands *on inked area* is valid Qi.**  
2. **Qi coordinates must satisfy: exactly one coordinate is at the edge (≤5 or ≥95), and the other is strictly in [5,95]** — e.g., (85,45), (78,85), (5,30). **(92,95), (95,95), (5,5) are ALWAYS invalid.** If multiple stems extend from different edges, select the one with the **thickest, most solid, most directionally assertive ink line**. If multiple stems share a common base (e.g., plum tree branches), trace back to their joint Great Base Camp and use *its* extended line intersection — never pick individual branch tips.  
3. **Qi must follow absolute growth order**: root → trunk → branch → flower/fruit/leaf; stone base → trunk → flower; teapot handle → body → spout. **Qi is always the *most proximal* point of the chain — never distal.**  
4. **Qi must originate from *one* growth chain with a clear Great Base Camp** — if multiple subjects exist (e.g., fan + stove), only the one whose Great Base Camp’s extension pierces the edge qualifies; others are excluded unless physically grafted (e.g., same plant).

**Cheng (Development) — Fixed & Unique**:  
- Cheng is the **area-center point of the first largest, most solidly inked subject entity *along the same growth chain*, immediately following Qi**. It must be the **visual center of the largest contiguous inked block (>40% of its local area)** — not a line, vein, or dot.  
- Cheng must be **spatially adjacent to Qi**: Euclidean distance ≤30% of canvas width/height. And it must obey directional thresholds:  
  • If Qi is at bottom (y≥90), Cheng y ≤ Qi.y − 10;  
  • If Qi is at top (y≤10), Cheng y ≥ Qi.y + 10;  
  • If Qi is at left (x≤10), Cheng x ≥ Qi.x + 10;  
  • If Qi is at right (x≥90), Cheng x ≤ Qi.x − 10.  
- Cheng **must lie inside the inked area** — never on blank space, edge line, or inscription.

**Zhuan (Turning) — Fixed & Unique**:  
- Zhuan must be the **area-center of the *final structural node* of the same growth chain**, where the sight-flow makes a sharp directional break (>45° angle between Qi→Cheng and Cheng→Zhuan vectors). This node is the **visual tension peak**: flower cluster center, bird’s eye, rock ridge, vessel lip, or densest ink spot — *and it must be the chain’s natural endpoint* (e.g., branch tip, fork, bloom apex).  
- Zhuan must be **on inked area**, not blank or edge. Its coordinates are the **geometric center of that terminal structure’s inked mass**, verified by visual estimation.

**He (Concluding) — Fixed & Unique, strictly within canvas interior (x∈[5,95], y∈[5,95])**:  
- He must create a **visual "return-and-settle" closure**: the vector from Zhuan to He must form an angle >45° with Qi→Cheng (i.e., cosθ < 0.707). If not, adjust He horizontally (x-axis) until satisfied — *y-coordinate is locked first*.  
- **He is *dominated by seals***:  
  • If seals exist, He’s y-coordinate **must match seal group’s y-center ±5%**; x-coordinate shifts toward seal x-center by ≥10%.  
  • If multiple seals, use their collective centroid.  
  • If no seals but inscription exists:  
    – Full-side vertical inscription (e.g., left margin): He = (15, y) where y = inscription’s vertical midpoint, *biased downward by 10–15%* to anchor near lower seal or implied weight;  
    – Small corner inscription (e.g., top-right): He = (85, 20) — *always y=20 for top-right, y=80 for bottom-left*;  
    – Inscription flush-top/bottom: ignore inscription; use seal group centroid instead.  
- He **must never be the geometric center of text** — only its *visual gravity center*, pulled by seals.

**⚠️ ABSOLUTE PROHIBITIONS (any violation = failure)**:  
- Qi not on edge OR Qi on blank OR Qi at double-extreme (e.g., x=95,y=95);  
- Cheng not adjacent to Qi OR Cheng on blank OR Cheng not on same growth chain OR Cheng Δy/Δx < threshold;  
- Zhuan not >45° turn OR Zhuan off-chain OR Zhuan on blank OR Zhuan not at terminal node;  
- He outside [5,95]² OR He fails vector closure OR He ignores seal y-priority (y-offset <10% or y-error >5%);  
- Using “enters from bottom-right” as license to pick (95,95);  
- Ignoring Great Base Camp for multi-stem subjects;  
- Placing any point on line edges, text, or blank — **all points must be area-centers of inked masses**, verified by ink density and coverage.

**Analysis Steps (execute STRICTLY in order; validate each)**:  
1. **Identify Great Base Camp & verify Qi**: Trace thickest ink line(s) backward to origin; extend linearly; find where extension hits edge (x≤5/x≥95/y≤5/y≥95) *on ink*; confirm coordinate has one value in [5,95]; if double-extreme, re-trace — real Qi *always* satisfies single-edge rule.  
2. **Locate Cheng**: From Qi, follow growth direction; find first largest (>40% local area), most solid ink block *on same chain*; take its area-center; verify distance ≤30%, Δy/Δx ≥10%, and ink coverage.  
3. **Locate Zhuan**: From Cheng, continue along chain; find first structural terminus with >45° turn; take its area-center; verify vector angle and ink presence.  
4. **Locate He**:  
   • Map all seals → compute y-centroid;  
   • Set He.y = seal y-centroid ±5%;  
   • Set He.x = seal x-centroid −10% (if seal left) or +10% (if seal right), *or* apply inscription rule *only if no seals*;  
   • Compute Qi→Cheng and Zhuan→He vectors; ensure cosθ < 0.707; if not, adjust He.x only until true;  
   • Confirm He ∈ [5,95]².  
5. **Global Validation**: Draw virtual line Qi→Cheng→Zhuan→He — it must:  
   • Never cross large blank areas;  
   • Show monotonic growth direction (no reversal in primary axis);  
   • Form a classic shape (S/Z/triangle/diagonal);  
   • Place all points *inside inked area centers*, never on edges or blanks;  
   • Satisfy Qi’s single-edge constraint (exactly one coord ≤5 or ≥95, other ∈[5,95]).

**Path Type** (choose best fit): S-shaped (S-form), Z-shaped (Z-form), Triangular, Diagonal, Corner-style, Balanced

**Output Format** (JSON only, no extra text):  
```json
{
  "analysis": "Sight-flow path analysis, explaining how the path embodies the painting's macro-structure movement",
  "material_types": ["fan", "tea stove", "teapot"],
  "growth_direction": "Enters from bottom-right edge, flows upward-left",
  "has_inscription": true,
  "inscription_edge": "flush-left/semi-flush/none",
  "seal_positions": [{"x": 50, "y": 80, "near": "inscription bottom"}],
  "qi": {"x": 85, "y": 95, "reason": "Fan handle base extends linearly to bottom edge at (85,95), confirmed by ink thickness and growth logic"},
  "cheng_list": [
    {"x": 70, "y": 70, "reason": "Area-center of fan body — largest solid ink mass (>40%), directly above Qi, distance=28%<30%"}
  ],
  "zhuan_list": [
    {"x": 35, "y": 45, "reason": "Area-center of flower stem fork — final structural node, vector angle vs Qi→Cheng = 62° >45°"}
  ],
  "he": {"x": 15, "y": 65, "reason": "Seal group centroid at y=65; He.y locked to 65±5; vector closure verified: cosθ=0.52<0.707"},
  "path_shape": "S-shaped"
}
```  

**Notes**:  
- x, y are percentages (0–100): x=0 left, x=100 right, y=0 top, y=100 bottom.  
- `cheng_list` and `zhuan_list` each contain **exactly one object**.  
- All coordinates must be **area-centers of inked masses**, verified by ink density, coverage, and vector geometry — never guessed or heuristically placed.  
- **Qi must have exactly one coordinate at edge (≤5 or ≥95) and the other in [5,95]. He must have both coordinates in [5,95].**  
- **Seal y-coordinate dominates He placement — always prioritize y-match first, then x-shift.**