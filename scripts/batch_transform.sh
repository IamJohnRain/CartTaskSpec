#!/bin/bash
# 批量把 case 目录中的 task.taskSpec.json 转换为 A2UI 模型的
# chat-completions 请求体,写入同目录 task.request.json。
set -u

DEFAULT_BASE_DIR="datasets/case-600-newSkill-gpt5.5"
DEFAULT_REJECTED_DSL_NAME="card.MiniMax-M3.dsl.jsonl"
BASE_DIR_ARG=""
HFRL_MODE=false
REJECTED_DSL_NAME=""

usage() {
  cat <<EOF
Usage:
  scripts/batch_transform.sh [BASE_DIR]
  scripts/batch_transform.sh -b BASE_DIR
  scripts/batch_transform.sh -b BASE_DIR --hfrl [--rejected-dsl-name NAME]

Options:
  -b, --base-dir DIR        指定待批量转换的 case 根目录。
                            脚本会遍历 DIR/*/ 下的 task.taskSpec.json。
  --hfrl                    生成 HFRL 格式的请求体 (task.request.hfrl.json)，
                            在顶层增加 rejected_response 字段。
  --rejected-dsl-name NAME  rejected DSL 文件名（按 case 目录解析）。
                            仅 --hfrl 模式下生效。
                            默认: ${DEFAULT_REJECTED_DSL_NAME}
  -h, --help                显示本帮助文档。

传参参考:
  scripts/batch_transform.sh
  scripts/batch_transform.sh datasets/case-600-newSkill-gpt5.5
  scripts/batch_transform.sh -b datasets/case-600-newSkill-gpt5.5

  # HFRL 模式（默认 rejected = card.MiniMax-M3.dsl.jsonl）
  scripts/batch_transform.sh -b datasets/case-600-newSkill-gpt5.5 --hfrl

  # HFRL 模式，指定 rejected DSL 文件名
  scripts/batch_transform.sh -b datasets/case-600-newSkill-gpt5.5 --hfrl \\
      --rejected-dsl-name card.glm-5.2.dsl.jsonl

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
    --hfrl)
      HFRL_MODE=true
      shift
      ;;
    --rejected-dsl-name)
      if [ "$#" -lt 2 ]; then
        echo "error: $1 需要一个文件名参数" >&2
        usage >&2
        exit 2
      fi
      REJECTED_DSL_NAME="$2"
      shift 2
      ;;
    --rejected-dsl-name=*)
      REJECTED_DSL_NAME="${1#*=}"
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
REJECTED_DSL_NAME="${REJECTED_DSL_NAME:-${DEFAULT_REJECTED_DSL_NAME}}"
echo "使用 BASE_DIR: ${BASE_DIR}"
if [ "${HFRL_MODE}" = true ]; then
  echo "HFRL 模式: ON | rejected DSL: ${REJECTED_DSL_NAME}"
fi

total=0
ok=0
fail=0
skip=0

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

  # HFRL 模式：检查 rejected DSL 文件是否存在，不存在则跳过
  if [ "${HFRL_MODE}" = true ]; then
    REJECTED_DSL_PATH="${CASE_DIR}/${REJECTED_DSL_NAME}"
    if [ ! -f "${REJECTED_DSL_PATH}" ]; then
      echo "skip: ${BASE_DIR}/${CASE_NAME} (no ${REJECTED_DSL_NAME})"
      skip=$((skip + 1))
      continue
    fi
  fi

  total=$((total + 1))
  echo ">>> [${total}] ${BASE_DIR}/${CASE_NAME}"

  if [ "${HFRL_MODE}" = true ]; then
    REJECTED_DSL_PATH="${CASE_DIR}/${REJECTED_DSL_NAME}"
    OUTPUT_FILE="${CASE_DIR}/task.request.hfrl.json"
    $PY scripts/taskspec_to_chat_completions.py \
        "${CASE_DIR}/task.taskSpec.json" \
        -q "${CASE_DIR}/query.txt" \
        --genui_dsl "${CASE_DIR}/card.dsl.jsonl" \
        --hfrl \
        --rejected-dsl "${REJECTED_DSL_PATH}" \
        -o "${OUTPUT_FILE}" \
      && ok=$((ok + 1)) \
      || {
        fail=$((fail + 1))
        echo "!!! Failed: ${BASE_DIR}/${CASE_NAME}" >&2
      }
  else
    $PY scripts/taskspec_to_chat_completions.py \
        "${CASE_DIR}/task.taskSpec.json" \
        -q "${CASE_DIR}/query.txt" \
        --genui_dsl "${CASE_DIR}/card.dsl.jsonl" \
        -o "${CASE_DIR}/task.request.json" \
      && ok=$((ok + 1)) \
      || {
        fail=$((fail + 1))
        echo "!!! Failed: ${BASE_DIR}/${CASE_NAME}" >&2
      }
  fi
done

echo "─────────────"
echo "Done. total=${total} ok=${ok} fail=${fail} skip=${skip}"
exit 0
