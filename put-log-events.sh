#!/bin/bash

# リージョン
export AWS_DEFAULT_REGION=us-west-2

# CloudWatchLogs設定
LogGroupName=$3
LogStreamName=$2

if [ -z "$LogGroupName" ]; then
    LogGroupName=/ecs/messages
fi
# CloudWatchLogsにPUTするメッセージ
Mess=$1

# コーテーションを取り除く
Mess=`echo $Mess | sed -e "s/'//g"`

# put-log-eventに利用するトークン
UploadSequenceToken=$(aws logs describe-log-streams --log-group-name "$LogGroupName" --query 'logStreams[?logStreamName==`'$LogStreamName'`].[uploadSequenceToken]' --output text)

# put-log-eventに利用するタイムスタンプ
TimeStamp=`date "+%s%N" --utc`
TimeStamp=`expr $TimeStamp / 1000000`

# put-log-eventsの実行
if [ "$UploadSequenceToken" != "None" ]
then
  # トークン有りの場合
  aws logs put-log-events --log-group-name "$LogGroupName" --log-stream-name "$LogStreamName" --log-events timestamp=$TimeStamp,message="'$Mess'" --sequence-token $UploadSequenceToken
else
  # トークン無しの場合（初回のput）
  aws logs put-log-events --log-group-name "$LogGroupName" --log-stream-name "$LogStreamName" --log-events timestamp=$TimeStamp,message="'$Mess'"
fi
