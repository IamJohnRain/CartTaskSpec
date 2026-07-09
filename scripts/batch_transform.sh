#!/bin/bash
# 批量把 case 目录中的 task.taskSpec.json 转换为 A2UI 模型的
# chat-completions 请求体,写入同目录 task.request.json。
set -u

DEFAULT_BASE_DIR="datasets/case-600-newSkill-gpt5.5"
BASE_DIR_ARG=""

usage() {
  cat <<EOF
Usage:
  scripts/batch_transform.sh [BASE_DIR]
  scripts/batch_transform.sh -b BASE_DIR

Options:
  -b, --base-dir DIR   指定待批量转换的 case 根目录。
                       脚本会遍历 DIR/*/ 下的 task.taskSpec.json。
  -h, --help           显示本帮助文档。

传参参考:
  scripts/batch_transform.sh
  scripts/batch_transform.sh datasets/case-600-newSkill-gpt5.5
  scripts/batch_transform.sh -b datasets/case-600-newSkill-gpt5.5
  BASE_DIR=datasets/case-600-newSkill-gpt5.5 scripts/batch_transform.sh

优先级:
  命令行参数 > BASE_DIR 环境变量 > 默认值 ${DEFAULT_BASE_DIR}
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    -b|--base-dir)
      if [ "$#" -lt 2 ]; then
        echo "error: $1 需要一个目录参数" >&2
        usage >&2
        exit 2
      fi
      BASE_DIR_ARG="$2"
      shift 2
      ;;
    --base-dir=*)
      BASE_DIR_ARG="${1#*=}"
      shift
      ;;
    -*)
      echo "error: 未知参数: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [ -n "${BASE_DIR_ARG}" ]; then
        echo "error: 只能指定一个 BASE_DIR" >&2
        usage >&2
        exit 2
      fi
      BASE_DIR_ARG="$1"
      shift
      ;;
  esac
done

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

BASE_DIR="${BASE_DIR_ARG:-${BASE_DIR:-${DEFAULT_BASE_DIR}}}"

if [ ! -d "${BASE_DIR}" ]; then
  echo "error: BASE_DIR 不存在: ${BASE_DIR}" >&2
  echo "hint: 使用 -h 查看传参示例" >&2
  exit 2
fi
echo "使用 BASE_DIR: ${BASE_DIR}"

total=0
ok=0
fail=0

for CASE_DIR in "${BASE_DIR}"/*/; do
  echo ">>> Case: ${CASE_DIR}"
  [ -d "${CASE_DIR}" ] || continue
  CASE_NAME=$(basename "${CASE_DIR}")
  [ -f "${CASE_DIR}/task.taskSpec.json" ] || {
    echo "skip: ${BASE_DIR}/${CASE_NAME} (no task.taskSpec.json)"
    continue
  }
  [ -f "${CASE_DIR}/query.txt" ] || {
    echo "skip: ${BASE_DIR}/${CASE_NAME} (no query.txt)"
    continue
  }
  total=$((total + 1))
  echo ">>> [${total}] ${BASE_DIR}/${CASE_NAME}"
  if $PY scripts/taskspec_to_chat_completions.py \
      "${CASE_DIR}/task.taskSpec.json" \
      -q "${CASE_DIR}/query.txt" \
      --genui_dsl "${CASE_DIR}/card.dsl.jsonl" \
      -o "${CASE_DIR}/task.request.json"; then
    ok=$((ok + 1))
  else
    fail=$((fail + 1))
    echo "!!! Failed: ${BASE_DIR}/${CASE_NAME}" >&2
  fi
done

echo "─────────────"
echo "Done. total=${total} ok=${ok} fail=${fail}"
exit 0
