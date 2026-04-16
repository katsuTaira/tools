#!/bin/bash -x
S3BUCKETNM=s3://kps-pub/shells
LOCALPATH=/home/taira
upFiles=(
    "/efs/ecs/cwlogtail.sh"
    "/efs/ecs/list-ecs-tasks.sh"
    "/efs/ecs/stdoutWithTime.sh"
    "/efs/ecs/Docker/"
)
for upFile in "${upFiles[@]}"; do
    if [[ "$upFile" == */ ]]; then
        dirnm=${upFile%/}
        dirnm=/${dirnm##*/}
        /usr/bin/s3cmd get --recursive ${S3BUCKETNM}"$upFile" ${LOCALPATH}${dirnm}
    else
        /usr/bin/s3cmd get -f ${S3BUCKETNM}"$upFile" $LOCALPATH
        bname=$(basename "$upFile")
        chmod 755 $LOCALPATH/"$bname"
    fi
done
