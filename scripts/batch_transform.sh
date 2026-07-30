#!/bin/bash
# 批量把 case 目录中的 task.taskSpec.json 转换为 A2UI 模型的
# chat-completions 请求体,写入同目录 task.request.json。
set -u

DEFAULT_BASE_DIR="datasets/case-600-newSkill-gpt5.5"
DEFAULT_ACCEPTED_DSL_NAME="card.dsl.jsonl"
DEFAULT_REJECTED_DSL_NAME="card.MiniMax-M3.dsl.jsonl"
DEFAULT_ACCEPTED_ALT_NAME="card.alt.txt"
DEFAULT_ACCEPTED_ASC_NAME="card.asc.txt"
DEFAULT_REJECTED_ALT_NAME="card.MiniMax-M3.alt.txt"
DEFAULT_REJECTED_ASC_NAME="card.MiniMax-M3.asc.txt"
BASE_DIR_ARG=""
HFRL_MODE=false
ALT_MODE=false
ACCEPTED_DSL_NAME=""
REJECTED_DSL_NAME=""
ACCEPTED_ALT_NAME=""
ACCEPTED_ASC_NAME=""
REJECTED_ALT_NAME=""
REJECTED_ASC_NAME=""

usage() {
  cat <<EOF
Usage:
  scripts/batch_transform.sh [BASE_DIR]
  scripts/batch_transform.sh -b BASE_DIR
  scripts/batch_transform.sh -b BASE_DIR --hfrl [--accepted-dsl-name NAME] [--rejected-dsl-name NAME]
  scripts/batch_transform.sh -b BASE_DIR --alt [--hfrl]

Options:
  --alt                     Enable ALT+ASC request generation with
                            scripts/taskspec_to_alt_chat_completions.py.
                            Without it, the legacy DSL request workflow is unchanged.
  --accepted-alt-name NAME  Accepted ALT filename in --alt mode.
                            Default: ${DEFAULT_ACCEPTED_ALT_NAME}
  --accepted-asc-name NAME  Accepted ASC filename in --alt mode.
                            Default: ${DEFAULT_ACCEPTED_ASC_NAME}
  --rejected-alt-name NAME  Rejected ALT filename in --alt --hfrl mode.
                            Default: ${DEFAULT_REJECTED_ALT_NAME}
  --rejected-asc-name NAME  Rejected ASC filename in --alt --hfrl mode.
                            Default: ${DEFAULT_REJECTED_ASC_NAME}
  -b, --base-dir DIR        指定待批量转换的 case 根目录。
                            脚本会遍历 DIR/*/ 下的 task.taskSpec.json。
  --hfrl                    生成 HFRL 格式的请求体 (task.request.hfrl.json)，
                            在顶层增加 rejected_response 字段。
  --accepted-dsl-name NAME  accepted DSL 文件名（按 case 目录解析）。
                            仅 --hfrl 模式下生效。
                            默认: ${DEFAULT_ACCEPTED_DSL_NAME}
  --rejected-dsl-name NAME  rejected DSL 文件名（按 case 目录解析）。
                            仅 --hfrl 模式下生效。
                            默认: ${DEFAULT_REJECTED_DSL_NAME}
  -h, --help                显示本帮助文档。

传参参考:
  scripts/batch_transform.sh
  scripts/batch_transform.sh datasets/case-600-newSkill-gpt5.5
  scripts/batch_transform.sh -b datasets/case-600-newSkill-gpt5.5

  # HFRL 模式（默认 accepted = card.dsl.jsonl，rejected = card.MiniMax-M3.dsl.jsonl）
  scripts/batch_transform.sh -b datasets/case-600-newSkill-gpt5.5 --hfrl

  # HFRL 模式，指定 accepted/rejected DSL 文件名
  scripts/batch_transform.sh -b datasets/case-600-newSkill-gpt5.5 --hfrl \\
      --accepted-dsl-name fix.card.dsl.jsonl \\
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
    --alt)
      ALT_MODE=true
      shift
      ;;
    --accepted-dsl-name)
      if [ "$#" -lt 2 ]; then
        echo "error: $1 需要一个文件名参数" >&2
        usage >&2
        exit 2
      fi
      ACCEPTED_DSL_NAME="$2"
      shift 2
      ;;
    --accepted-dsl-name=*)
      ACCEPTED_DSL_NAME="${1#*=}"
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
    --accepted-alt-name)
      if [ "$#" -lt 2 ]; then
        echo "error: $1 requires a filename" >&2
        usage >&2
        exit 2
      fi
      ACCEPTED_ALT_NAME="$2"
      shift 2
      ;;
    --accepted-alt-name=*)
      ACCEPTED_ALT_NAME="${1#*=}"
      shift
      ;;
    --accepted-asc-name)
      if [ "$#" -lt 2 ]; then
        echo "error: $1 requires a filename" >&2
        usage >&2
        exit 2
      fi
      ACCEPTED_ASC_NAME="$2"
      shift 2
      ;;
    --accepted-asc-name=*)
      ACCEPTED_ASC_NAME="${1#*=}"
      shift
      ;;
    --rejected-alt-name)
      if [ "$#" -lt 2 ]; then
        echo "error: $1 requires a filename" >&2
        usage >&2
        exit 2
      fi
      REJECTED_ALT_NAME="$2"
      shift 2
      ;;
    --rejected-alt-name=*)
      REJECTED_ALT_NAME="${1#*=}"
      shift
      ;;
    --rejected-asc-name)
      if [ "$#" -lt 2 ]; then
        echo "error: $1 requires a filename" >&2
        usage >&2
        exit 2
      fi
      REJECTED_ASC_NAME="$2"
      shift 2
      ;;
    --rejected-asc-name=*)
      REJECTED_ASC_NAME="${1#*=}"
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
ACCEPTED_DSL_NAME="${ACCEPTED_DSL_NAME:-${DEFAULT_ACCEPTED_DSL_NAME}}"
REJECTED_DSL_NAME="${REJECTED_DSL_NAME:-${DEFAULT_REJECTED_DSL_NAME}}"
ACCEPTED_ALT_NAME="${ACCEPTED_ALT_NAME:-${DEFAULT_ACCEPTED_ALT_NAME}}"
ACCEPTED_ASC_NAME="${ACCEPTED_ASC_NAME:-${DEFAULT_ACCEPTED_ASC_NAME}}"
REJECTED_ALT_NAME="${REJECTED_ALT_NAME:-${DEFAULT_REJECTED_ALT_NAME}}"
REJECTED_ASC_NAME="${REJECTED_ASC_NAME:-${DEFAULT_REJECTED_ASC_NAME}}"
echo "使用 BASE_DIR: ${BASE_DIR}"
if [ "${ALT_MODE}" = true ]; then
  echo "ALT+ASC mode: ON | alt: ${ACCEPTED_ALT_NAME} | asc: ${ACCEPTED_ASC_NAME}"
fi
if [ "${HFRL_MODE}" = true ]; then
  echo "HFRL 模式: ON | accepted DSL: ${ACCEPTED_DSL_NAME} | rejected DSL: ${REJECTED_DSL_NAME}"
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

  # HFRL 模式：仅在 accepted 和 rejected DSL 都存在时处理。
  if [ "${ALT_MODE}" = true ]; then
    ACCEPTED_ALT_PATH="${CASE_DIR}/${ACCEPTED_ALT_NAME}"
    ACCEPTED_ASC_PATH="${CASE_DIR}/${ACCEPTED_ASC_NAME}"
    if [ ! -f "${ACCEPTED_ALT_PATH}" ] || [ ! -f "${ACCEPTED_ASC_PATH}" ]; then
      echo "skip: ${BASE_DIR}/${CASE_NAME} (missing ${ACCEPTED_ALT_NAME} or ${ACCEPTED_ASC_NAME})"
      skip=$((skip + 1))
      continue
    fi
    if [ "${HFRL_MODE}" = true ]; then
      REJECTED_ALT_PATH="${CASE_DIR}/${REJECTED_ALT_NAME}"
      REJECTED_ASC_PATH="${CASE_DIR}/${REJECTED_ASC_NAME}"
      if [ ! -f "${REJECTED_ALT_PATH}" ] || [ ! -f "${REJECTED_ASC_PATH}" ]; then
        echo "skip: ${BASE_DIR}/${CASE_NAME} (missing ${REJECTED_ALT_NAME} or ${REJECTED_ASC_NAME})"
        skip=$((skip + 1))
        continue
      fi
    fi

    total=$((total + 1))
    echo ">>> [${total}] ${BASE_DIR}/${CASE_NAME} (ALT+ASC)"
    if [ "${HFRL_MODE}" = true ]; then
      $PY scripts/taskspec_to_alt_chat_completions.py \
          "${CASE_DIR}/task.taskSpec.json" \
          -q "${CASE_DIR}/query.txt" \
          -a "${ACCEPTED_ALT_PATH}" \
          -s "${ACCEPTED_ASC_PATH}" \
          --hfrl \
          --rejected-alt "${REJECTED_ALT_PATH}" \
          --rejected-asc "${REJECTED_ASC_PATH}" \
          -o "${CASE_DIR}/task.request.hfrl.json" \
        && ok=$((ok + 1)) \
        || {
          fail=$((fail + 1))
          echo "!!! Failed: ${BASE_DIR}/${CASE_NAME}" >&2
        }
    else
      $PY scripts/taskspec_to_alt_chat_completions.py \
          "${CASE_DIR}/task.taskSpec.json" \
          -q "${CASE_DIR}/query.txt" \
          -a "${ACCEPTED_ALT_PATH}" \
          -s "${ACCEPTED_ASC_PATH}" \
          -o "${CASE_DIR}/task.request.json" \
        && ok=$((ok + 1)) \
        || {
          fail=$((fail + 1))
          echo "!!! Failed: ${BASE_DIR}/${CASE_NAME}" >&2
        }
    fi
    continue
  fi

  if [ "${HFRL_MODE}" = true ]; then
    ACCEPTED_DSL_PATH="${CASE_DIR}/${ACCEPTED_DSL_NAME}"
    REJECTED_DSL_PATH="${CASE_DIR}/${REJECTED_DSL_NAME}"
    if [ ! -f "${ACCEPTED_DSL_PATH}" ]; then
      echo "skip: ${BASE_DIR}/${CASE_NAME} (no ${ACCEPTED_DSL_NAME})"
      skip=$((skip + 1))
      continue
    fi
    if [ ! -f "${REJECTED_DSL_PATH}" ]; then
      echo "skip: ${BASE_DIR}/${CASE_NAME} (no ${REJECTED_DSL_NAME})"
      skip=$((skip + 1))
      continue
    fi
  fi

  total=$((total + 1))
  echo ">>> [${total}] ${BASE_DIR}/${CASE_NAME}"

  if [ "${HFRL_MODE}" = true ]; then
    ACCEPTED_DSL_PATH="${CASE_DIR}/${ACCEPTED_DSL_NAME}"
    REJECTED_DSL_PATH="${CASE_DIR}/${REJECTED_DSL_NAME}"
    OUTPUT_FILE="${CASE_DIR}/task.request.hfrl.json"
    $PY scripts/taskspec_to_chat_completions.py \
        "${CASE_DIR}/task.taskSpec.json" \
        -q "${CASE_DIR}/query.txt" \
        --genui_dsl "${ACCEPTED_DSL_PATH}" \
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
