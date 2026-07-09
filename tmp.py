import os

dataset_dir = "datasets/case-600-newSkill-gpt5.5"

train_file = os.path.join(dataset_dir, "train.jsonl")
test_file = os.path.join(dataset_dir, "test.jsonl")

raw_cases =os.listdir(dataset_dir)
cases = [case for case in raw_cases if os.path.isdir(os.path.join(dataset_dir, case))]

train_cases = []
test_cases = []
for i, case in enumerate(cases):
    case_file = os.path.join(dataset_dir, case, "task.request.json")
    if not os.path.exists(case_file):
        print(f"Warning: task.request.json not found for case {case}, skipping.")
        continue
    if i % 5 == 0:
        with open(case_file, "r", encoding="utf-8") as f:
            test_cases.append(f.read().strip())
    else:
        with open(case_file, "r", encoding="utf-8") as f:
            train_cases.append(f.read().strip())

with open(train_file, "w", encoding="utf-8") as f:
    for case in train_cases:
        f.write(case + "\n")

with open(test_file, "w", encoding="utf-8") as f:
    for case in test_cases:
        f.write(case + "\n")
