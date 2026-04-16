#!/usr/bin/expect
set timeout 5
spawn ssh -p 2228 taira@192.168.204.8
expect "password";
send "kpstaira\n"
expect "~"
send "cd dc\n"
expect "dc"
send "docker-compose exec bottles bash\n"
expect "swt"
send "tmux a\n"
interact
