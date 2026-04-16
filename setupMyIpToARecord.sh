#!/bin/bash
# 稼働環境がaws ecsでない場合はじく
# ECSコンテナメタデータURL
ECS_CONTAINER_METADATA_URL="http://169.254.170.2/v2/metadata"

# メタデータエンドポイントにアクセスしてインスタンスIDを取得
#if curl --silent --fail "$ECS_CONTAINER_METADATA_URL"; then
#    :
#else
#    echo "This script is NOT running on an AWS EC2 instance."
#    exit 1
#fi

# パブリックIPを取得
public_ip=$(curl -s http://checkip.amazonaws.com)

# 変数の設定
hosted_zone_id="Z0924366R6W6OVIZJMB1"
domain_name=$1

# JSONファイルを作成
cat <<EOF > change-batch.json
{
  "Comment": "Update record to reflect new IP address",
  "Changes": [
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "$domain_name",
        "Type": "A",
        "TTL": 300,
        "ResourceRecords": [
          {
            "Value": "$public_ip"
          }
        ]
      }
    }
  ]
}
EOF

# Route 53のAレコードを更新
echo setting ip addr to $public_ip of $domain_name
aws route53 change-resource-record-sets --hosted-zone-id "$hosted_zone_id" --change-batch file://change-batch.json

# JSONファイルを削除
rm change-batch.json

