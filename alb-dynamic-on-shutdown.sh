#!/bin/bash
set -e
set -o pipefail

TG_DYNAMIC_ARN="arn:aws:elasticloadbalancing:us-west-2:778568780562:targetgroup/AI-test/bae5c2c54cacbd8b"
TG_OTHER_ARN="arn:aws:elasticloadbalancing:us-west-2:778568780562:targetgroup/ECSPRO-tomcat/7eb3bf4d07626769"

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

REGION=$(get_metadata placement/region)

echo "Getting IPs from tgOther..."  >> "$LOG"

OTHER_IPS=$(aws elbv2 describe-target-health \
  --region "$REGION" \
  --target-group-arn "$TG_OTHER_ARN" \
  --query 'TargetHealthDescriptions[].Target.Id' \
  --output text)

if [ -z "$OTHER_IPS" ]; then
  echo "No targets found in tgOther"  >> "$LOG"
  exit 1
fi

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
    --targets Id="$IP",Port="$PORT" || true
done

echo "Registering ECSPRO-tomcat targets to tgDynamic: $OTHER_IPS"  >> "$LOG"
echo "$OTHER_IPS"  >> "$LOG"

TARGETS_JSON=$(for ip in $OTHER_IPS; do
  printf "Id=%s,Port=%d " "$ip" "$PORT"
done)

aws elbv2 register-targets \
  --region "$REGION" \
  --target-group-arn "$TG_DYNAMIC_ARN" \
  --targets $TARGETS_JSON

echo "Done."  >> "$LOG"

logger -t alb-dynamic "shutdown triggered by alb-dynamic-on-shutdown via SSM at $(date)"

# 二重 shutdown 防止
if systemctl is-system-running --quiet; then
  echo "calling shutdown" >> "$LOG"
  shutdown -h now
else
  echo "system already stopping" >> "$LOG"
fi
