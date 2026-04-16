#!/bin/bash

DATE=`date "+%Y%m%d"`
BAKDIR=/tmp

SUFIX=zip
S3BUCKETNM=s3://kps-users/taira/

PREFIX=$1
LOCLADIR=$2
FILENM=$PREFIX${DATE}.$SUFIX
BACKFILENM=${BAKDIR}/$FILENM
LOGFINENM=$PREFIX${DATE}.log
rm  $BACKFILENM
if [ $# != 3 ]; then
	zip $BACKFILENM -y -r $LOCLADIR > $LOGFINENM
else
	EVALCMD=$3
	eval $EVALCMD >> $LOGFINENM
fi
#既存のものが同じサイズだったらそれを消す
/home/taira/tools/delSamesizeS3.sh $BACKFILENM $S3BUCKETNM $PREFIX $SUFIX
#5日以上前のものは月ごと１番古いもの以外消す
/home/taira/tools/delDaybefore.sh $S3BUCKETNM 5
/home/taira/tools/delDaybefore.sh ${S3BUCKETNM}log/ 5 log
/usr/bin/s3cmd put $BACKFILENM $S3BUCKETNM
if [ -f $LOGFINENM ]; then
	/usr/bin/s3cmd put $LOGFINENM ${S3BUCKETNM}log/
	rm  $LOGFINENM
fi
rm  $BACKFILENM

