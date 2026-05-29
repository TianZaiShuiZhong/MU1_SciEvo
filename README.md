# MU1_SciEvo（赛道一）

GitHub: `https://github.com/TianZaiShuiZhong/MU1_SciEvo`

这个仓库做一件事：把科研文献整理成可训练/可评测的 `Sci-Evo` 数据。  
流程是两段：先解析文献（MinerU / Sciverse），再结构化成统一 `jsonl`。

## 当前状态（2026-05-29）

- 多论文数据：`data/processed/scievo_multi_paper_draft.jsonl`
- 规模：`524` 条记录，`131` 个独立来源
- 数据域：`scientific-ml / plasma-physics / protein-engineering / materials-science / earth-science / drug-discovery / computational-chemistry / computational-biology`
- 切分：`train=367, valid=79, test=78`

## 先跑起来（最短路径）

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 配置环境变量

```bash
cp .env.example .env
# 必填：MU_API_TOKEN
# 建议填：SCIVERSE_API_TOKEN（要扩源时用）
```

3. 跑最小样例（用于确认环境）

```bash
python scripts/build_demo_dataset.py --min-count 12
python scripts/validate_dataset.py --dataset data/processed/scievo_demo.jsonl
```

## 常用流程

### 1) 本地 PDF -> MinerU -> Sci-Evo

```bash
python scripts/run_mineru_parse.py --input-csv configs/paper_files.scievo.csv --mode agent_file --page-range 1-20
python scripts/build_multi_paper_dataset.py --records-per-paper 4
python scripts/validate_dataset.py --dataset data/processed/scievo_multi_paper_draft.jsonl
python scripts/split_dataset.py
```

### 2) Sciverse 扩源 -> Sci-Evo

```bash
python scripts/import_sciverse_sources.py --queries-csv configs/sciverse_queries_longtail.csv --max-docs 45 --max-per-query 3
python scripts/build_multi_paper_dataset.py --records-per-paper 4
python scripts/validate_dataset.py --dataset data/processed/scievo_multi_paper_draft.jsonl
python scripts/split_dataset.py
```

可选查询文件：

- `configs/sciverse_queries.csv`
- `configs/sciverse_queries_balanced.csv`
- `configs/sciverse_queries_longtail.csv`
- `configs/sciverse_queries_balance_psml.csv`

## 你可能会用到的脚本

- `scripts/run_mineru_parse.py`：MinerU 解析（URL / 本地上传）
- `scripts/import_sciverse_sources.py`：Sciverse 检索 + 全文抓取
- `scripts/build_multi_paper_dataset.py`：把 `full.md` 统一转成 Sci-Evo `jsonl`
- `scripts/validate_dataset.py`：按 `schemas/scievo.schema.json` 校验
- `scripts/split_dataset.py`：切分 train/valid/test

## 目录说明（只列关键）

- `data/interim/markdown/`：每篇文献的中间产物（`full.md` + `meta.json`）
- `data/processed/`：最终 `jsonl` 数据和切分数据
- `reports/source_inventory.csv`：来源清单
- `docs/技术报告_参赛终稿版.md`：提交用报告
- `schemas/scievo.schema.json`：数据格式约束

## 实操提醒

- 网络不稳时，重跑同一命令即可；脚本里有去重和重试。

