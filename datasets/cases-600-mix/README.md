# cases-600-mix

从两个源文件中,每个场景各取前 10 条混合而成,合计 600 条测试集。

## 来源
- `oral`: `cases-10k-oral\5000Cases.tagged.jsonl`
- `10k`: `cases-10k\10000Cases.tagged.jsonl`

## 文件
- `600Cases.tagged.jsonl` — 合并数据,每条记录新增 `source` 字段(`oral`/`10k`)
- `index.jsonl` — 索引,逐行映射到原文件名与原始行号
- `build_mix.py` — 构建脚本

## 顺序
- 按 scenario 编号(01–30)排序
- 每个场景内: oral 的前 10 条在前, 10k 的前 10 条在后

## 索引字段
| 字段 | 说明 |
|---|---|
| new_line | 新文件中的行号(1-based) |
| source | `oral` 或 `10k` |
| source_file | 原始文件相对路径 |
| original_line | 在原始文件中的行号(1-based) |
| scenario | 场景 ID |
| scenario_name | 场景中文名 |
