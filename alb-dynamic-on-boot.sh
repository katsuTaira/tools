#!/bin/bash
TG_DYNAMIC_ARN="arn:aws:elasticloadbalancing:us-west-2:778568780562:targetgroup/AI-test/bae5c2c54cacbd8b"
PORT=80
LOG=/var/log/alb-dynamic.log

get_metadata() {
  local path=$1
  local token

  token=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")

  curl -s -H "X-aws-ec2-metadata-token: $token" \
    "http://169.254.169.254/latest/meta-data/${path}"
}


PRIVATE_IP=$(get_metadata local-ipv4)
REGION=$(get_metadata placement/region)

echo "[BOOT] $(date) start ($PRIVATE_IP)" >> "$LOG"

# 既存ターゲット全削除
TARGETS=$(aws elbv2 describe-target-health \
  --region "$REGION" \
  --target-group-arn "$TG_DYNAMIC_ARN" \
  --query 'TargetHealthDescriptions[].Target.Id' \
  --output text)

for IP in $TARGETS; do
  aws elbv2 deregister-targets \
    --region "$REGION" \
    --target-group-arn "$TG_DYNAMIC_ARN" \
    --targets Id="$IP",Port="$PORT"
done

# 自分の IP を登録
aws elbv2 register-targets \
  --region "$REGION" \
  --target-group-arn "$TG_DYNAMIC_ARN" \
  --targets Id="$PRIVATE_IP",Port="$PORT"

echo "[BOOT] registered self $PRIVATE_IP" >> "$LOG"