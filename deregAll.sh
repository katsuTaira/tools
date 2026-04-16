#!/bin/bash -x

tgArn=$1
# 既存ターゲット全削除
TARGETS=$(aws elbv2 describe-target-health \
  --target-group-arn "$tgArn" \
  --query 'TargetHealthDescriptions[].Target.Id' \
  --output text)

for IP in $TARGETS; do
  aws elbv2 deregister-targets \
     --target-group-arn "$tgArn" \
    --targets Id="$IP"
done