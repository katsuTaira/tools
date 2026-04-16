#!/bin/bash

# Take the cluster name from the script arguments
CLUSTER_NAME="KPS-cluster"
if [ "login" = "$1" ] || [ "exec" = "$1" ]; then
  # 引数のチェック
  if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <login|exec> <container name> <number|Piece of Task Name>"
    exit 1
  fi
  con=$2
  login="go"
  num=$3
fi
# Get a list of tasks in the cluster
TASKS=$(aws ecs list-tasks --cluster "$CLUSTER_NAME" --query "taskArns" --output text)

# Loop through each task to get the container instance ARN
cnt=0
for TASK_ARN in $TASKS; do
  # Get a human readable ARN.
  TASK_ID=$(basename $TASK_ARN)
  #service ipv4 入手
  SERVICE_IPV4=$(aws ecs describe-tasks --cluster $CLUSTER_NAME --tasks $TASK_ARN --output text --query '[tasks[0].group,tasks[0].containers[0].networkInterfaces[0].privateIpv4Address]')

  # Get the network interface ID for the task
  #NETWORK_INTERFACE_ID=$(aws ecs describe-tasks --cluster $CLUSTER_NAME --tasks $TASK_ARN --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text)

  #Get the public IP of the network interface
  #PUBLIC_IP=$(aws ec2 describe-network-interfaces --network-interface-ids $NETWORK_INTERFACE_ID --query 'NetworkInterfaces[0].Association.PublicIp')

  echo "Task: $TASK_ID -- $SERVICE_IPV4"

  if [ "go" = "$login" ]; then
    if [[ $SERVICE_IPV4 =~ $num ]] && [[ ! "$num" =~ ^[0-9]+$ ]] || [ $cnt = $num ]; then
      if [ "login" = "$1" ]; then
        aws ecs execute-command --region us-west-2 --cluster KPS-cluster --task $TASK_ID --container $con --interactive --command "/bin/bash"
      fi
      if [ "exec" = "$1" ]; then
        aws ecs execute-command --region us-west-2 --cluster KPS-cluster --task $TASK_ID --container $con --interactive --command "$4"
      fi
      break
    fi
  fi
  cnt=$(expr $cnt + 1)
done
