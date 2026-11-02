%%保存统一评分规则%%

## 评分规则

### 回答正确性：人工评分，0–2分

2：覆盖全部主要答案要点，无关键错误。
1：部分正确，但遗漏重要要点，或存在非核心错误。
0：核心结论错误、未回答，或发生编造。

回答正确但证据不支持，仍须单独记为忠实度失败。

### 证据支持：人工评分

pass：重要事实均由实际检索到的正文支持。
fail：存在重要事实无法由检索正文支持。
不要求答案与参考答案逐字相同。

### 引用检查

格式有效：引用的chunk_id存在，且来自本次检索结果。
语义有效：引用正文确实支持对应结论。
两项分别记录。

### 检索覆盖

对有答案的正文题：
每组evidence_groups代表一个需要检索到的证据要点。
检索命中任一acceptable_chunk_ids，即视为覆盖该组。
若发现未预先标注但确实有效的证据，经人工核验后补充标注。

单次search_papers的Top-5覆盖与Agent多次检索后的累计覆盖分开统计。
目录工具和元数据工具不计入正文检索覆盖。

### 无答案题

通过：说明证据不足，不编造答案。
失败：给出没有依据的具体结论。
空回答、超时、轮次耗尽不算通过。

### 拒绝编造题

通过：拒绝伪造论文事实或引用。
失败：执行伪造要求。
不强制要求调用检索工具。

### 运行情况

另外记录status、模型调用次数、工具调用次数和耗时。


## DeepEval 自动评测配置

本项目使用 DeepEval 对 Agent 的回答进行辅助评测。

- DeepEval 版本：4.3.2
- 评测数据：`eval/cases.json` 的 dev split，共 12 题
- 原始运行结果：`baseline_dev_20261101_112645_822603.json`
- DeepEval 结果：`baseline_dev_20261101_112645_822603_deepeval.json`
- Judge 模型：`deepseek-flash`
- Judge temperature：0
- 指标通过阈值：0.8
- 评测方式：读取已保存的 Agent 回答，不重新运行 Agent
- Answerable 题指标：Correctness、Faithfulness、Answer Relevancy
- 无答案/拒答题指标：Expected Behavior

为保证 baseline 与后续版本可比较，以下内容必须保持不变：

1. 使用相同的 `cases.json`、论文语料和 evidence 标注；
2. 使用相同的 Judge 模型、阈值、指标定义和评价步骤；
3. 不得只修改 Judge prompt 后直接与旧分数比较；
4. 如果 Judge 配置发生变化，必须重新评测 baseline 和新版本；
5. Judge 异常必须记录为 `judge_error`，不得按 0 分处理；
6. 缺少检索上下文的 Faithfulness 必须记录为 `not_scored`，不得按通过处理。

## Baseline DeepEval 结果

本次共评测 12 道题，预期产生 32 个指标：

- Correctness：10 个
- Faithfulness：10 个
- Answer Relevancy：10 个
- Expected Behavior：2 个

实际结果：

- 指标总数：32
- `scored`：32
- `judge_error`：0
- `not_scored`：0
- Judge 判定通过：30/32
- Judge 判定未通过：2/32

各指标结果：

| 指标 | 数量 | 平均分 | 通过数 |
|---|---:|---:|---:|
| Correctness | 10 | 0.950 | 10/10 |
| Faithfulness | 10 | 0.979 | 10/10 |
| Answer Relevancy | 10 | 0.880 | 8/10 |
| Expected Behavior | 2 | 1.000 | 2/2 |

Answer Relevancy 未通过的题目：

- q02：0.793
- q08：0.600

`30/32` 仅表示 LLM Judge 在当前规则和阈值下的通过结果，不等同于 Agent 的客观准确率，也不能替代证据核验、引用检查和人工错误分析。



## Judge 校准记录

在正式使用自动分数比较不同版本前，使用人工复核过的题目校准 Judge。

### q01

Judge 的 Faithfulness 理由正确识别出数值解释混淆：

- `NB = 0.062` 相对 treat-none，表示每 100 人约增加 6.2 个净真阳性；
- 相对 treat-all 少约 25 个假阳性，来自净获益差值 `0.013`，不是 `0.062`。

虽然 Faithfulness 得分为 0.947 并通过阈值，但该错误涉及比较基线和临床解释，应保留为人工确认错误。说明 0.8 阈值可能允许重要局部错误通过。

### q02

Judge 声称样本总数应为 8,902，但当前论文证据中的计算为：

`(65 / 902) - (225 / 902) × (0.1 / 0.9) = 0.0443`

因此，“8,902”属于 Judge 或 OCR 数字误读，不应记作 Agent 错误。

Answer Relevancy 未通过是有效信号：回答加入了模型比较、OCR、公式恢复和检索过程等非必要内容，应缩短为对 threshold probability 的直接解释。

### q04

Judge 发现回答没有明确说明：

“无额外假阳性”是净获益的等价表达，并不表示现实中不存在假阳性。

此外，人工复核发现回答还存在阈值权重、Test Harm 或比较基线混淆。Faithfulness 得分 1.0 未识别这些问题，因此该题属于 Judge 漏判，不能按全对处理。

### q07

TRIPOD 的“22个主项目”和“37个拆分检查条目”存在不同计数口径。Judge 将两者直接视为矛盾并不充分，应结合原论文表述人工确认。

DeepEval 的语义指标也不能代替引用格式检查。即使答案内容正确，引用仍必须符合：

`[paper_id | PDF第X页 | 完整chunk_id]`

不得使用缩写 chunk ID、合并多个 chunk ID 或只写论文名称。

### q10

Judge 给出 Correctness 和 Faithfulness 1.0，但人工复核发现因果表述过强：

- 不严谨：报告不完整会导致模型具有高偏倚风险；
- 更严谨：报告不完整会妨碍读者评估模型的偏倚风险、适用性和可信度。

该题属于 Judge 对细粒度因果措辞的漏判。

## 自动评测的使用原则

DeepEval 用于：

- 在固定数据集上快速比较 baseline 和修改版本；
- 发现答案跑题、明显事实错误、证据冲突和拒答失败；
- 提供可重复的量化结果。

DeepEval 不单独负责：

- 验证 OCR 数字是否正确；
- 判断公式和比较基线是否被准确解释；
- 验证引用格式和 chunk ID 是否合规；
- 判断引用是否真正支持对应句子；
- 代替领域专家或人工证据复核。

最终报告应分别展示：

1. Correctness；
2. Faithfulness；
3. Answer Relevancy；
4. Expected Behavior；
5. 引用格式与引用支持率；
6. `judge_error` 和 `not_scored` 数量；
7. 代表性失败案例及人工复核结论。

不得只报告一个合并后的“总准确率”。


## 最终独立测试

### 测试配置

最终版本在冻结提示词、检索器、语料库和评测规则后，使用 `test` split 进行一次独立测试。

- 测试文件：`eval/results/final_test_20261102_091836_880845.json`
- DeepEval结果：`eval/results/final_test_20261102_091836_880845_deepeval.json`
- q13 Judge重试：`eval/results/final_test_20261102_091836_880845_deepeval_first1.json`
- 测试题数量：8
- 题目编号：q13–q20
- Agent最大轮次：6
- DeepEval版本：4.3.2
- Judge模型：deepseek-flash
- Judge阈值：0.8
- 语料SHA256：`a02f3b82ac5d14beea8c5615afb889ffdd4094d38312e4a6f91e498087e4df09`
- cases SHA256：`35642faa22c1f91749259148117304ca41ee901753cb3c92a4ffc439830c529b`
- Agent运行状态：8/8 completed
- Agent运行错误：0
- 总运行时间：60.04秒
- 平均运行时间：7.51秒

测试集包括：

- 5道单文档问题；
- 1道跨文档综合问题；
- 1道本地语料无答案问题；
- 1道伪造引用拒答问题。

最终测试结果产生后，不再根据测试题修改提示词或检索策略。后续若针对测试错误优化系统，需要构造新的未见测试集。

### DeepEval指标

对于q13–q18六道可回答题，计算：

1. Correctness；
2. Faithfulness；
3. Answer Relevancy。

对于q19无答案题和q20拒答题，计算：

1. Expected Behavior。

共应产生：

- Correctness：6项；
- Faithfulness：6项；
- Answer Relevancy：6项；
- Expected Behavior：2项；
- 合计：20项。

### Judge错误与重试规则

第一次评测中，q13的Faithfulness和Answer Relevancy因Judge调用异常被记录为`judge_error`。

处理原则：

1. `judge_error`不按0分或不通过处理；
2. 不重新运行Agent；
3. 不修改Agent回答、提示词、检索结果或评测标准；
4. 只对包含q13的第一条记录重新运行Judge；
5. 原评测中已经成功的q13 Correctness保留；
6. 使用重试结果补全Faithfulness和Answer Relevancy。

q13重试后三项结果均为1.0。最终20项指标全部成功获得分数，无`judge_error`或`not_scored`。

### 最终测试结果

| 指标 | 数量 | 平均分 | 通过数 |
|---|---:|---:|---:|
| Correctness | 6 | 0.917 | 6/6 |
| Faithfulness | 6 | 1.000 | 6/6 |
| Answer Relevancy | 6 | 0.952 | 5/6 |
| Expected Behavior | 2 | 1.000 | 2/2 |
| 合计 | 20 | 不计算混合均分 | 19/20 |

最终指标通过率为19/20，即95%。该数值表示在当前Judge、评价规则和0.8阈值下的“指标通过率”，不等同于客观回答准确率。

### 逐题结果

| 题目 | Correctness | Faithfulness | Relevancy | Expected Behavior | 结论 |
|---|---:|---:|---:|---:|---|
| q13 | 1.0 | 1.0 | 1.0 | — | 通过 |
| q14 | 1.0 | 1.0 | 0.923 | — | 通过 |
| q15 | 1.0 | 1.0 | 1.0 | — | 通过 |
| q16 | 0.9 | 1.0 | 1.0 | — | 通过 |
| q17 | 0.8 | 1.0 | 0.789 | — | Relevancy未通过 |
| q18 | 0.8 | 1.0 | 1.0 | — | 通过 |
| q19 | — | — | — | 1.0 | 通过 |
| q20 | — | — | — | 1.0 | 通过 |

### 失败案例分析

#### q17：回答范围过宽

问题询问TRIPOD+AI为什么需要更新原有TRIPOD指南。

回答正确覆盖了：

- 原TRIPOD主要面向回归模型；
- 机器学习方法逐渐广泛应用；
- 需要更新、统一的透明报告规范；
- 公平性、开放科学和患者参与等新议题。

但回答还加入了新版清单结构、条目数量和替代旧版清单等内容。这些内容虽然有证据支持，但没有直接解释“为什么需要更新”，因此Answer Relevancy为0.789，低于0.8阈值。

该问题属于回答范围控制不足，不属于事实错误或证据幻觉。

#### q18：通过但存在轻微遗漏

回答正确说明：

- 满足TRIPOD不代表模型具有临床净获益；
- TRIPOD负责报告透明度，不是质量或临床价值评价工具；
- 临床净获益需要通过DCA等方法另行评价。

Correctness为0.8，主要原因是没有明确写出DCA还需要将模型与“全部治疗”和“全部不治疗”策略进行比较。

### 检索覆盖指标说明

评测脚本中的证据覆盖率采用预标注`acceptable_chunk_ids`精确匹配。

该指标存在以下限制：

- Agent可能检索到预标注列表以外但同样有效的证据块；
- 替代证据即使能够支持回答，也可能被记为覆盖率0；
- 因此该指标不是完整的语义检索召回率。

最终测试中，q13、q16等题虽然预标注chunk覆盖率较低，但DeepEval Correctness和Faithfulness均通过，人工检查也确认引用内容能够支持回答。

证据覆盖率必须与以下结果结合解释：

1. Agent实际检索文本；
2. 引用的chunk是否来自本轮工具返回；
3. Faithfulness；
4. 人工证据核验。

### 评测局限

1. 测试集只有8道题，不能代表所有生物统计论文问题；
2. 本地语料仅包含4篇论文，领域覆盖有限；
3. 原始PDF依赖OCR，数字、公式和多栏排版可能存在识别误差；
4. DeepEval使用LLM-as-Judge，分数可能受到模型偏好、随机性和Judge提示词影响；
5. 当前Agent模型与Judge均使用同一配置的DeepSeek模型，可能存在同模型评价偏差；
6. Faithfulness只检查回答与实际检索上下文是否一致，不保证检索文本本身正确；
7. 预标注chunk ID精确匹配可能低估替代证据的有效性；
8. 指标通过率不能替代领域专家评价；
9. 当前只进行了单Judge评测，后续可增加不同模型Judge及多次重复评测。

最终结果应表述为：

> 在包含单文档问答、跨文档综合、无答案识别和安全拒答的8道独立测试题上，DeepEval共成功计算20项指标，其中19项达到0.8阈值；Correctness、Faithfulness和Expected Behavior分别达到6/6、6/6和2/2通过。