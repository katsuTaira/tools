#!/bin/bash
upFiles=(
    "/efs/ecs/tools/"
    "/efs/ecs/Docker/"
)

for ((i = 0; i < ${#upFiles[@]}; i++)); do
    /efs/ecs/tools/sync_to_s3.sh "${upFiles[$i]}" $1 "${upFiles[$i]}"
done