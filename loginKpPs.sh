#!/usr/bin/expect
set timeout 5
spawn ssh -p 2221 K00013@192.168.204.21
expect "password";
send "kedoedo5x?\n"
expect "K00013"
send "pwsh -NoProfile -ExecutionPolicy Bypass -File \"C:\\Users\\taira\\Box\\lib\\ps\\tailLogs.ps1\"\r\n"
interact
