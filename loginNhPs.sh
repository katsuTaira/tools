#!/usr/bin/expect
set timeout 5
spawn ssh -p 2221 taira@swtaira.com@media.swtaira.com
expect "password";
send "medoedo97\n"
expect "PS"
send "pwsh -NoProfile -ExecutionPolicy Bypass -File \"C:\\Users\\taira\\Box\\lib\\ps\\tailLogs.ps1\"\r\n"
interact
