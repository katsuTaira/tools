#!/bin/bash -x

upFile="/efs/ecs/Docker/"
dirnm=${upFile%/}
dirnm=/${dirnm##*/}
echo $dirnm

