#!/usr/bin/expect
set timeout 5
spawn ssh swt@media.swtaira.com
expect "password";
send "swttaira\n"
expect "~"
send "cd docker/compose\n"
expect "compose"
send "docker-compose exec bottles bash\n"
expect "swt"
send "tmux a\n"
interact
