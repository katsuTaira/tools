#!/bin/bash
case "$0" in
    ./*) SCRIPTNAME="$(pwd)/${0#./}";;
    /*)  SCRIPTNAME="$0";;
    *)   SCRIPTNAME="$(pwd)/$0";;
esac
SCRIPTDIR="${SCRIPTNAME%/*}"

# CloudWatchのロググループ名を取得して配列に格納
log_groups=($(aws logs describe-log-groups --query 'logGroups[*].logGroupName' --output text))

logGroup=$1
if [ -z "$logGroup" ]; then
	# 配列の内容を表示
	for log_group in "${log_groups[@]}"; do
		echo "$log_group"
	done
	echo  select one of above!!
	exit 0
else
	for log_group in "${log_groups[@]}"; do
	 	if [[ $log_group =~ $logGroup ]]; then
			logGroup=$log_group
			echo log group $logGroup is selected!!
			break 
		fi
	done
fi
start=$2
if [ -z "$start" ]; then
	start=60
fi

#log group指定でcloud watchのlogをtailする 最初の６文字にtask idの最初の６文字を表示
source ~/mypy/bin/activate  //python 仮想環境に入る
if [[ "$logGroup" == *apache* ]]; then
	awslogs get $logGroup -w -s ${start}m -G -S --timestamp | sed -r -u 's@(^.+"code":"[0-9]+)(.*/KPS-cluster/)(\w{6})(.*ecs_task_definition[^,]*)@\3:\1"@' | sed -r -u "s/(.*)([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}.[0-9]{3}Z)(.*)/\1$(date +"%Y-%m-%dT%H:%M:%S%z" <<<"\2")\3/"
elif [[ "$logGroup" == *tomcat-task-definition* ]]; then
	awslogs get $logGroup -w -s ${start}m -G -S --timestamp | "$SCRIPTDIR"/stdoutWithTime.sh
else
	awslogs get $logGroup -w -s ${start}m -G -S | jq -cR --unbuffered 'fromjson?' | jq -r -c --unbuffered '"\(.ecs_task_arn):\(.log)"' | sed -r -u 's@(.*/KPS-cluster/)(\w{6})([^:]*)@\2@'
fi
