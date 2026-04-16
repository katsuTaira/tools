#!/bin/bash
S3BUCKETNM=s3://kps-versioning/wars
while IFS= read -r -d '' file
do
    sizeLo=$(ls -l "$file" |  awk '{print $5}')
    sizeS3=$(/usr/bin/s3cmd ls "${S3BUCKETNM}$file"  |  awk '{print $3}')
    #sizeが違う場合のみput
    if  [ -z $sizeS3 ] || [ $sizeS3 -ne $sizeLo ]; then
        /usr/bin/s3cmd  put $file "${S3BUCKETNM}$file"
    else
        echo $file same size exsist!
    fi
  done <   <(find /efs -name '*.war' -print0)