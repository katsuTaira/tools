#!/bin/bash
/home/taira/tools/cwlogtail.sh /ecs/tomcat-task-definition 10 | grep -E -v ".*(GET|POST)"