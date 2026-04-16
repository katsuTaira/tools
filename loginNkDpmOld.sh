#!/usr/bin/expect
set timeout 5
spawn ssh taira@swtaira.com@192.168.204.8
expect "password";
send "medoedo97\n"
expect "PS"
send "cmd\n"
expect "C:"
interact
