#!/bin/bash 

CLUSTER_NAME="KPS-cluster"
tgArn=$1

# Get a list of tasks in the cluster
TASKS=$(aws ecs list-tasks --cluster "$CLUSTER_NAME" --query "taskArns" --output text)

# Loop through each task to get the container instance ARN
ipv4s=()
for TASK_ARN in $TASKS
do
  # Get a human readable ARN.
  TASK_ID=$(basename $TASK_ARN)
  #service ipv4 入手
  SERVICE_IPV4=$(aws ecs describe-tasks --cluster $CLUSTER_NAME --tasks $TASK_ARN --output text --query 'tasks[0].containers[0].networkInterfaces[0].privateIpv4Address')
  ipv4s+=($SERVICE_IPV4)    
done
# ターゲットのヘルス情報を取得
TARGET_HEALTH=$(aws elbv2 describe-target-health --target-group-arn $tgArn --output json)

# ターゲットのIDとヘルスステータスを抽出し、IDがインスタンスIDの場合はIPアドレスを取得
echo "$TARGET_HEALTH" | jq -r '.TargetHealthDescriptions[] | "\(.Target.Id) \(.TargetHealth.State)"' | while read TARGET_ID STATE; do
  if printf '%s\n' "${ipv4s[@]}" | grep -qx $TARGET_ID; then
    :
  else
    echo $TARGET_ID $STATE
    if [ $STATE = "unhealthy" ]; then
      echo $TARGET_ID was dead!
      aws elbv2 deregister-targets  --target-group-arn $tgArn --targets Id=$TARGET_ID
    fi  
  fi
done