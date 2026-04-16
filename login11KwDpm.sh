#!/usr/bin/expect
set timeout 5
#対話シェルを起動
spawn bash
expect -re {\$ $}


send "cd dc\n"
expect "dc"
send "docker-compose exec bottles bash\n"
expect "swt"
send "tmux a\n"
interact
