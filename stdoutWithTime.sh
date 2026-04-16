#!/bin/bash

# 標準入力からのストリームを1行ずつ処理
while IFS= read -r line; do
  # タイムスタンプ部分とJSON部分に分割
  timestamp=$(echo "$line" | cut -d' ' -f1 | date +"%Y-%m-%dT%H:%M:%S%z")
  json=$(echo "$line" | cut -d' ' -f2-)
  
  # jqでJSON部分を処理して、その結果の前にタイムスタンプを追加して表示
    jq_output=$(echo "$json" | jq '.' 2>/dev/null)
  
  if [ $? -ne 0 ]; then
    # JSONでない場合はそのまま出力
    echo "$timestamp $json"
  else
    # JSONの場合は処理した結果を出力
    jq_output=$(echo "$json" | jq -r -c --unbuffered '"\(.ecs_task_arn):\(.log)"' | sed -r -u 's@(.*/KPS-cluster/)(\w{6})([^:]*)@\2@')
    echo "$timestamp $jq_output" 
  fi
done
