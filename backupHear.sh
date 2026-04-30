#!/bin/bash

PREFIX=scon2_src_
LOCLADIR=/mnt/c/Users/K00013/git/scon2/src/
/home/taira/tools/backupHearSub.sh $PREFIX $LOCLADIR

PREFIX=platform2_src_
LOCLADIR=/mnt/c/Users/K00013/git/platform2/src/
/home/taira/tools/backupHearSub.sh $PREFIX $LOCLADIR

PREFIX=kokyakuroku_src_
LOCLADIR=/mnt/c/Users/K00013/git/kokyakuroku/src/
/home/taira/tools/backupHearSub.sh $PREFIX $LOCLADIR

PREFIX=Documents_
LOCLADIR=/mnt/c/Users/K00013/Documents/
SUFIX=zip
DATE=`date "+%Y%m%d"`
BAKDIR=/tmp
FILENM=$PREFIX${DATE}.$SUFIX
BACKFILENM=${BAKDIR}/$FILENM
EVALCMD="zip $BACKFILENM -y -r $LOCLADIR -x '*My Kindle Content/*' '*Reflector/*' '*sql/backup*'"
/home/taira/tools/backupHearSub.sh $PREFIX $LOCLADIR "$EVALCMD"

PREFIX=home_
LOCLADIR=/home/taira/
FILENM=$PREFIX${DATE}.$SUFIX
BACKFILENM=${BAKDIR}/$FILENM
EVALCMD="zip $BACKFILENM -y -r $LOCLADIR -x '*.pyenv/*' '*mypy/*' '*.local/*' '*.cache/*' '*.vscode/*' '*.dotnet/*' '*aws/*' '*.vscode-server/*' '*.vscode-remote-containers/*' '*.windsurf-server/*' '*.cursor-server/*' '*.codeium/*' '*.npm*' '*.deb' '*.zip' '*node_modules/*' '*go/pkg/*' '*go/bin/*' '*go/src/*' '*go/cache/*' '*go/mod/*' '*go/sumdb/*'"
/home/taira/tools/backupHearSub.sh $PREFIX $LOCLADIR "$EVALCMD"


