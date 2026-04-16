#!/bin/bash

DATE=`date "+%Y%m%d"`
BAKDIR=/tmp
SUFIX=zip

PREFIX=$1
LOCLADIR=$2
S3BUCKETNM=$3
FILENM=$PREFIX${DATE}.$SUFIX
LOGFINENM=$PREFIX${DATE}.log
BACKFILENM=${BAKDIR}/$FILENM
rm  $BACKFILENM
if [ $# != 4 ]; then
	zip $BACKFILENM -y -r $LOCLADIR >> $LOGFINENM
else
	EVALCMD=$4
	eval $EVALCMD >> $LOGFINENM
fi
#既存のものが同じサイズだったらそれを消す
/efs/ecs/tools/delSamesizeS3.sh $BACKFILENM $S3BUCKETNM $PREFIX $SUFIX
/usr/bin/s3cmd put $BACKFILENM $S3BUCKETNM
#logの中に読めないものがあった場合アラーム発行
# 変数の設定
sns_topic_arn="arn:aws:sns:us-west-2:778568780562:Taira_Test"

## メッセージを格納する変数
MESSAGE=""

# ログファイルを読み込み、特定のメッセージを抽出
while IFS= read -r line; do
    if [[ "$line" == *"zip warning: could not open for reading"* ]]; then
        MESSAGE+="$line"$'\n'
    fi
done < "$LOGFINENM"

# メッセージが存在する場合、SNSに送信 /ecs/messages errors に書く
if [[ -n "$MESSAGE" ]]; then
    msg="In ${LOGFINENM},"$'\n'" ${MESSAGE}"$'\n'" was found!"
    #msg="test"
     aws sns publish --topic-arn "$sns_topic_arn" --message "$msg"
    /efs/ecs/tools/put-log-events.sh "$msg" errors
fi
if [ -f $LOGFINENM ]; then
	/usr/bin/s3cmd put $LOGFINENM ${S3BUCKETNM}log/
	rm  $LOGFINENM
fi
rm  $BACKFILENM

