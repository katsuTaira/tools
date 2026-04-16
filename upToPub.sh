#!/bin/bash
S3BUCKETNM=s3://kps-pub/shells
upFiles=(
    "/efs/ecs/cwlogtail.sh"
    "/efs/ecs/list-ecs-tasks.sh"
    "/efs/ecs/stdoutWithTime.sh"
    "/efs/ecs/Docker/"
)
for upFile in "${upFiles[@]}"
do
    if [[ "$upFile" == */ ]]; then
        /usr/bin/s3cmd put --recursive "$upFile" ${S3BUCKETNM}"$upFile"
    else
        /usr/bin/s3cmd put "$upFile" ${S3BUCKETNM}"$upFile"
    fi
done
