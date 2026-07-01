#!/bin/bash

BASE_DIR=datasets/Scenario/codex-gpt-5.5

for CASE_DIR in "${BASE_DIR}"/Case-*; do
  [ -d "${CASE_DIR}" ] || continue
  [ -f "${CASE_DIR}/task.taskSpec.json" ] || continue

  echo ">>> Processing ${CASE_DIR}"
  python taskspec_to_chat_completions.py \
    "${CASE_DIR}/task.taskSpec.json" \
    -q "${CASE_DIR}/query.txt" \
    --genui_dsl "${CASE_DIR}/card.dsl.jsonl" \
    -o "${CASE_DIR}/task.request.json" || echo "!!! Failed: ${CASE_DIR}"
done

echo "Done."
