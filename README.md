
## 项目简介

Paper Agent是一个面向本地生物统计论文的检索问答Agent。系统能够解析本地PDF论文、建立可检索文本库，根据用户问题自主选择工具，并生成带论文、PDF页码和文本块ID的可追溯回答。

当前文库收录4篇预测模型方法学论文，涉及：

- 决策曲线分析；
- 预测模型最小样本量；
- TRIPOD报告规范；
- TRIPOD+AI报告规范。

## 系统流程

离线阶段：

1. 读取本地PDF；
2. 优先提取原生文本；
3. 对无文本层PDF执行Tesseract OCR；
4. 按页清洗并切分文本；
5. 为每个文本块保存paper_id、PDF页码和chunk_id；
6. 构建BM25关键词检索索引。

在线阶段：

1. 接收用户问题；
2. 模型判断是否需要调用工具；
3. 将中文问题转换为英文检索关键词；
4. 调用论文列表、元数据查询或正文检索工具；
5. 将检索结果作为Observation返回模型；
6. 证据充足时生成带引用的回答；
7. 达到最大轮次时终止，避免无限循环。

## 核心功能

- PDF原生文本提取与OCR回退；
- 文本分块及来源元数据保存；
- BM25关键词检索；
- 基于JSON Schema的工具注册与参数校验；
- 多轮工具调用与最大轮次控制；
- 工具异常捕获与结构化错误返回；
- 完整Agent执行轨迹；
- 单文档问答与跨文档比较；
- `[paper_id | PDF第X页 | chunk_id]`格式引用；
- OCR数字和公式不确定性处理；
- 无答案识别；
- 伪造实验结果和引用请求拒答；
- 基于DeepEval的自动化评测。

## 项目结构

```text
paper-agent/
├── agent.py                  # Agent循环、系统提示词与模型调用
├── tools.py                  # 工具Schema、注册表和执行逻辑
├── ingest.py                 # PDF解析、OCR缓存与文本分块
├── test_retrieval.py         # BM25检索测试
├── eval_agent.py             # Agent评测运行器
├── judge_model.py            # DeepEval自定义Judge模型
├── score_deepeval.py         # DeepEval评分脚本
├── data/
│   └── papers/               # 本地论文及元数据
├── storage/
│   ├── extracted/            # OCR/文本提取缓存
│   └── chunks.json           # 带来源信息的文本块
└── eval/
    ├── cases.json            # 20道评测用例
    ├── rubric.md             # 评测规则和结果解释
    └── results/              # 原始回答及DeepEval结果
```

## 安装

推荐使用Python 3.10或以上版本。

```bash
conda create -n paper-agent python=3.11
conda activate paper-agent
python -m pip install -r requirements.txt
```

创建`.env`：

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=your_base_url
LLM_MODEL=your_model

JUDGE_API_KEY=your_judge_api_key
JUDGE_BASE_URL=your_judge_base_url
JUDGE_MODEL=your_judge_model
```

不要将`.env`或API Key提交到Git仓库。

## 运行

启动交互式Agent：

```bash
python agent.py
```

示例问题：

```text
决策曲线分析为什么使用净获益评价预测模型？
TRIPOD和TRIPOD+AI的适用范围有什么区别？
本地论文是否报告了某医院2026年的患者数量？
```

运行BM25检索测试：

```bash
python test_retrieval.py
```

运行开发集评测：

```bash
python eval_agent.py --split dev --label prompt_v2
```

运行独立测试集：

```bash
python eval_agent.py --split test --label final
```

对保存的回答运行DeepEval：

```bash
python score_deepeval.py --input eval/results/对应结果文件.json
```

## 评测集

项目构建了20道评测问题：

| 类型 | 数量 | 示例 |
|---|---:|---|
| 单文档事实与方法问题 | 13 | 净获益、阈值概率、最小样本量 |
| 跨文档综合问题 | 3 | TRIPOD与DCA分别解决什么问题 |
| 无答案问题 | 2 | 询问本地论文未包含的医院数据 |
| 安全拒答问题 | 2 | 要求伪造实验结果或论文引用 |

其中：

- 12题用于开发集；
- 8题作为冻结提示词后的独立测试集。

评测维度包括：

- Correctness：是否覆盖参考答案中的核心要点；
- Faithfulness：回答是否受到实际检索文本支持；
- Answer Relevancy：回答是否直接回应问题；
- Expected Behavior：无答案和危险请求是否得到正确处理。

## 最终评测结果

最终版本在冻结提示词、语料库、检索器和Judge配置后，对8道独立测试题进行一次评测。

| 指标 | 平均分 | 通过数 |
|---|---:|---:|
| Correctness | 0.917 | 6/6 |
| Faithfulness | 1.000 | 6/6 |
| Answer Relevancy | 0.952 | 5/6 |
| Expected Behavior | 1.000 | 2/2 |
| 总指标通过情况 | — | 19/20 |

DeepEval通过阈值为0.8。

结果显示：

- 六道可回答问题的Correctness全部通过；
- 六道可回答问题的Faithfulness全部通过；
- 无答案识别和伪造引用拒答均通过；
- 唯一未通过项为一题Answer Relevancy，原因是答案加入了超出问题范围的指南结构和版本信息；
- 8道测试题全部正常完成，无Agent运行错误；
- 平均端到端运行时间为7.51秒。

`19/20`表示当前LLM Judge和评测规则下的指标通过率，不等同于客观准确率。

## 提示词优化效果

在12道开发集上，提示词与停止策略优化前后的工程指标如下：

| 指标 | Baseline | 优化后 | 变化 |
|---|---:|---:|---:|
| 平均运行时间 | 12.70秒 | 9.22秒 | -27.4% |
| search调用总数 | 38 | 29 | -23.7% |
| 平均回答长度 | 1615字符 | 1066字符 | -34.0% |
| Faithfulness均分 | 0.979 | 1.000 | +0.021 |
| Answer Relevancy均分 | 0.880 | 0.893 | +0.013 |

开发集用于提示词调试，最终指标以独立test split为准。

## 已知局限

- 当前文库规模较小，仅包含4篇生物统计方法学论文；
- 当前检索器为BM25，对纯语义改写的召回能力有限；
- OCR可能对公式、数字、多栏排版和图表产生识别错误；
- 证据覆盖率采用预标注chunk ID精确匹配，可能低估替代证据；
- DeepEval依赖LLM-as-Judge，不是领域专家金标准；
- 当前Agent和Judge使用同一模型配置，可能存在同模型评价偏差；
- 测试集规模有限，最终结果只反映当前语料和问题分布；
- 目前没有实现向量检索、混合召回及Cross-Encoder重排序。

## 后续计划

- 加入Embedding向量检索，与BM25组成混合召回；
- 使用Cross-Encoder或MMR进行重排序；
- 增加引用格式自动校验；
- 改进OCR文本清洗和公式处理；
- 扩充生物统计论文库和独立评测集；
- 引入不同模型Judge和重复评测，降低单一Judge偏差。
```

有一点需要你核对：`.env`中的变量名必须与实际代码一致。如果你现在使用的是`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`等名称，应把README示例替换为真实变量名，不能照抄我这里的通用名称。

完成这两处后，Day 4可以正式结束。Day 5主要是仓库清理、README截图、GitHub提交、简历定稿和面试讲解准备。