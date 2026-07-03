#!/bin/bash
# 把 datasets/Scenario/cases-10k-gpt-5.5/<scenario>/Case-NNN/task.taskSpec.json
# 转换为 A2UI 模型的 chat-completions 请求体,写入 task.request.json
# 新结构:两层级联(<scenario>/<case>)
set -u

# 自动检测 Python 命令
PY=""
for cand in python python3 py; do
  if command -v "$cand" >/dev/null 2>&1; then
    PY="$cand"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "error: 未找到 python/python3/py,请安装 Python 或加入 PATH" >&2
  exit 2
fi
echo "使用 Python: $PY"

BASE_DIR="${BASE_DIR:-datasets/Scenario/cases-10k-gpt-5.5}"

if [ ! -d "${BASE_DIR}" ]; then
  echo "error: BASE_DIR 不存在: ${BASE_DIR}" >&2
  exit 2
fi

total=0
ok=0
fail=0

for SCEN_DIR in "${BASE_DIR}"/*/; do
  [ -d "${SCEN_DIR}" ] || continue
  SCEN_NAME=$(basename "${SCEN_DIR}")
  for CASE_DIR in "${SCEN_DIR}"/Case-*; do
    [ -d "${CASE_DIR}" ] || continue
    CASE_NAME=$(basename "${CASE_DIR}")
    [ -f "${CASE_DIR}/task.taskSpec.json" ] || {
      echo "skip: ${SCEN_NAME}/${CASE_NAME} (no task.taskSpec.json)"
      continue
    }
    [ -f "${CASE_DIR}/query.txt" ] || {
      echo "skip: ${SCEN_NAME}/${CASE_NAME} (no query.txt)"
      continue
    }
    total=$((total + 1))
    echo ">>> [${total}] ${SCEN_NAME}/${CASE_NAME}"
    if $PY taskspec_to_chat_completions.py \
        "${CASE_DIR}/task.taskSpec.json" \
        -q "${CASE_DIR}/query.txt" \
        --genui_dsl "${CASE_DIR}/card.dsl.jsonl" \
        -o "${CASE_DIR}/task.request.json"; then
      ok=$((ok + 1))
    else
      fail=$((fail + 1))
      echo "!!! Failed: ${SCEN_NAME}/${CASE_NAME}" >&2
    fi
  done
done

echo "─────────────"
echo "Done. total=${total} ok=${ok} fail=${fail}"
exit 0
