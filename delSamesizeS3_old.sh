#!/bin/bash

BACKFILENM=$1
S3BUCKETNM=$2
PREFIX=$3
SUFIX=$4
#既存のものが同じサイズだったらそれを消す
sizeLo=$(ls -l $BACKFILENM |  awk '{print $5}')
/usr/bin/s3cmd ls $S3BUCKETNM | while read line
do
    nmS3=$(echo $line | awk '{print $4}')
    #[[ $nmS3 =~ ^$S3BUCKETNM$PREFIX.+\.$SUFIX ]] && echo "Matched" || echo "Not Matched"
    if [[ $nmS3 =~ ^$S3BUCKETNM$PREFIX.+\.$SUFIX ]]; then
        sizeS3=$(echo $line | awk '{print $3}')
        if [ $sizeS3 = $sizeLo ]; then
            echo del $nmS3
            /usr/bin/s3cmd del $nmS3
        fi
    fi
done
