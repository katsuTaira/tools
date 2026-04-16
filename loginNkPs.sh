#!/usr/bin/expect
set timeout 5
spawn ssh taira@swtaira.com@192.168.204.8
expect "password";
send "medoedo97\n"
expect "PS"
send "pwsh -NoProfile -ExecutionPolicy Bypass -File \"C:\\Users\\taira\\Box\\lib\\ps\\tailLogs.ps1\"\r\n"
interact
