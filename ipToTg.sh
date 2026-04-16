#!/bin/bash

tgArn=$1
dereg=$2
localIp=$(ifconfig eth1 | awk '/inet / {print $2}')

if [ "dereg" = "$dereg" ]; then
        aws elbv2 deregister-targets  --target-group-arn $tgArn --targets Id=$localIp
        echo remove taget ip $localIp to $tgArn
else
        aws elbv2 register-targets  --target-group-arn $tgArn --targets Id=$localIp
        echo added taget ip $localIp to $tgArn
fi

