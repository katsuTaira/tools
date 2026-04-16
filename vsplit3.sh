#!/bin/bash

SESSION="vsplit3"

# 新しいセッション作成（上の大きなペインだけ）
tmux new-session -d -s $SESSION

# 上のペイン（0番）から下に向けて高さ3のペインを作る
tmux split-window -v -l 20 -t $SESSION:0.0   # 最下段
tmux split-window -v -l 20 -t $SESSION:0.0   # 下から2番目


# 残った一番上のペインは余りの高さを持つ

# アタッチ
tmux attach -t $SESSION

