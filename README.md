# MU1_SciEvo（赛道一）
GitHub：https://github.com/TianZaiShuiZhong/MU1_SciEvo
这个仓库是我们做 `Sci-Evo` 数据集的工程底座。核心思路很简单：  
先把论文转成结构化文本（MinerU / Sciverse），再统一整理成可训练、可评测的 `jsonl`。

如果你只是想先跑通，直接看下面“先跑起来（最短路径）”。

## 先跑起来（最短路径）

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 配置环境变量

```bash
cp .env.example .env
# 填 MU_API_TOKEN（MinerU）
# 填 SCIVERSE_API_TOKEN（可选，不填就不走 Sciverse 扩源）
```

3. 跑一个最小样例（12 条）

```bash
python scripts/build_demo_dataset.py --min-count 12
python scripts/validate_dataset.py --dataset data/processed/scievo_demo.jsonl
```

4. 跑多论文构建（本地 PDF + MinerU）

```bash
python scripts/run_mineru_parse.py --input-csv configs/paper_files.scievo.csv --mode agent_file --page-range 1-20
python scripts/build_multi_paper_dataset.py --records-per-paper 4
python scripts/validate_dataset.py --dataset data/processed/scievo_multi_paper_draft.jsonl
python scripts/split_dataset.py
```

## 想继续扩数据（推荐）

如果要做正式参赛版本，建议用 Sciverse 再拉一批独立来源：

```bash
python scripts/import_sciverse_sources.py --queries-csv configs/sciverse_queries_longtail.csv --max-docs 45 --max-per-query 3
python scripts/build_multi_paper_dataset.py --records-per-paper 4
python scripts/validate_dataset.py --dataset data/processed/scievo_multi_paper_draft.jsonl
python scripts/split_dataset.py
```

可选查询配置：

- `configs/sciverse_queries.csv`
- `configs/sciverse_queries_balanced.csv`
- `configs/sciverse_queries_longtail.csv`
- `configs/sciverse_queries_balance_psml.csv`

## 主要脚本

- `scripts/run_mineru_parse.py`：MinerU 解析（URL / 本地上传）
- `scripts/import_sciverse_sources.py`：Sciverse 检索 + 全文抓取
- `scripts/build_multi_paper_dataset.py`：把 `markdown` 转成 Sci-Evo `jsonl`
- `scripts/validate_dataset.py`：Schema 校验
- `scripts/split_dataset.py`：切分 `train/valid/test`

## 产物在哪

- 中间文本：`data/interim/markdown/<paper_id>/`
- 多论文数据：`data/processed/scievo_multi_paper_draft.jsonl`
- 切分数据：`data/processed/scievo_train.jsonl`、`data/processed/scievo_valid.jsonl`、`data/processed/scievo_test.jsonl`
- 来源清单：`reports/source_inventory.csv`
- 已填充报告：`docs/技术报告_参赛终稿版.md`


