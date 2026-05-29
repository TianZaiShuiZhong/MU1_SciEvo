# MU1 Sci-Evo 项目（赛道一）

这个仓库是一个可运行的 `Sci-Evo` 数据构建工程，目标是把科研文献转换为可训练/可评测的科学演化数据，并满足赛题要求中“必须使用至少一项 MinerU 工具链”。

## 目录说明

- `scripts/run_mineru_parse.py`: 调 MinerU API 解析文献（精准 API / Agent API）
- `scripts/build_demo_dataset.py`: 基于官方 `Sci-Evo_tool_case.json` 生成标准化 `jsonl` 样例集（默认 12 条）
- `scripts/build_multi_paper_dataset.py`: 从 MinerU 解析得到的多论文 markdown 自动生成多论文草稿数据集
- `scripts/validate_dataset.py`: 按 `schemas/scievo.schema.json` 校验数据格式
- `scripts/split_dataset.py`: 将数据切分为 `train/valid/test`
- `src/scievo/mineru_client.py`: MinerU API 客户端（提交任务、轮询、下载）
- `src/scievo/dataset_builder.py`: 官方样例转换与样例集生成
- `schemas/scievo.schema.json`: Sci-Evo 数据结构约束
- `docs/技术报告模板.md`: 可直接改写为提交材料的技术报告模板

## 快速开始

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 配置 Token（精准 API 需要）

```bash
cp .env.example .env
# 编辑 .env，填入 MU_API_TOKEN
```

3. 解析文献（示例）

```bash
python scripts/run_mineru_parse.py --input-csv configs/paper_urls.example.csv --mode precise
```

4. 生成样例数据集（不少于 10 条）

```bash
python scripts/build_demo_dataset.py --min-count 12
```

5. 校验数据

```bash
python scripts/validate_dataset.py
```

6. 多论文草稿集（对应“继续做 1”）

```bash
python scripts/run_mineru_parse.py --input-csv configs/paper_files.scievo.csv --mode agent_file --page-range 1-20
python scripts/build_multi_paper_dataset.py --records-per-paper 4
python scripts/validate_dataset.py --dataset data/processed/scievo_multi_paper_draft.jsonl
python scripts/split_dataset.py
```

## 输出物

- 解析中间产物：`data/interim/markdown/<paper_id>/`
- 样例数据集：`data/processed/scievo_demo.jsonl`
- 多论文草稿集：`data/processed/scievo_multi_paper_draft.jsonl`
- 切分数据：`data/processed/scievo_train.jsonl`、`scievo_valid.jsonl`、`scievo_test.jsonl`
- 技术报告模板：`docs/技术报告模板.md`
- 已填充草稿：`docs/技术报告_草稿_已填充.md`

## 注意事项

- 当前样例集用于“工程跑通 + schema 校验 + 报告示例”；正式参赛需扩展到更多独立论文来源。
- 赛题文档里写的提交截止时间是 `2026-05-24`，当前日期为 `2026-05-29`，如果你们要继续参赛，请先确认是否有补录/延期通知。
