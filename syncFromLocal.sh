#!/bin/bash
upFiles=(
    "/efs/ecs/tools/"
    "/efs/ecs/Docker/"
)
localFiles=(
    "/home/taira/tools/"
    "/home/taira/Docker/"
)

for ((i = 0; i < ${#upFiles[@]}; i++)); do
    /home/taira/tools/sync_to_s3.sh "${localFiles[$i]}" $1 "${upFiles[$i]}"
done
