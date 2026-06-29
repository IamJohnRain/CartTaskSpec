#!/bin/bash

curl --location 'http://127.0.0.1:4000/v1/chat/completions' \
--header 'Content-Type: application/json' \
--data-binary @- <<EOF
{
    "model": "glm-5.2",
    "messages": [
        {
            "role": "user",
            "content": "你是什么模型？"
        }
    ]
}
EOF