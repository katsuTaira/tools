#!/bin/bash
DATE=`date "+%Y%m%d"`
BAKDIR=/tmp
SUFIX=zip

#/efs/ecs配下backup
PREFIX=efsEcsFiles_
LOCLADIR=/efs/ecs/
S3BUCKETNM=s3://kps-sytem-backup/efs-files/
FILENM=$PREFIX${DATE}.$SUFIX
BACKFILENM=${BAKDIR}/$FILENM
EVALCMD="zip $BACKFILENM -y -r $LOCLADIR -x '*html/*' '*.war' '*upload/*'"
/efs/ecs/tools/backupZipSub.sh $PREFIX $LOCLADIR $S3BUCKETNM "$EVALCMD"

#/efs/ecspro配下backup
PREFIX=efsEcsProFiles_
LOCLADIR=/efs/ecspro/
S3BUCKETNM=s3://kps-sytem-backup/efs-files/
FILENM=$PREFIX${DATE}.$SUFIX
BACKFILENM=${BAKDIR}/$FILENM
EVALCMD="zip $BACKFILENM -y -r $LOCLADIR -x '*html/*' '*.war'"
/efs/ecs/tools/backupZipSub.sh $PREFIX $LOCLADIR $S3BUCKETNM "$EVALCMD"

#/efs/prams配下backup
PREFIX=efsParamsFiles_
LOCLADIR=/efs/parms
S3BUCKETNM=s3://kps-sytem-backup/efs-files/
/efs/ecs/tools/backupZipSub.sh $PREFIX $LOCLADIR $S3BUCKETNM

#/efs/props配下backup
PREFIX=efsPropsFiles_
LOCLADIR=/efs/props
S3BUCKETNM=s3://kps-sytem-backup/efs-files/
/efs/ecs/tools/backupZipSub.sh $PREFIX $LOCLADIR $S3BUCKETNM

#/efs/ecs/Docker配下backup
PREFIX=efsDockerFiles_
LOCLADIR=/efs/ecs/Docker
S3BUCKETNM=s3://kps-sytem-backup/efs-files/
/efs/ecs/tools/backupZipSub.sh $PREFIX $LOCLADIR $S3BUCKETNM
