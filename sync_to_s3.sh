#!/bin/bash

# 引数のチェック
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <local_dir> <up|down> <s3_key>"
    exit 1
fi

# 引数の取得
local_dir="$1"
operation="$2"
s3_key="$3"
s3_bucket="s3://kps-pub"

# 末尾のスラッシュを取り除く
local_dir=$(echo "$local_dir" | sed 's:/*$::')
# 先頭のスラッシュを取り除く
s3_key=$(echo "$s3_key" | sed 's:^/*::')
# .shは 755にする
change_permissions_if_sh() {
    local filepath="$1"

    # ファイルが.shで終了するか確認
    if [[ "$filepath" == *.sh ]]; then
        chmod 755 "$filepath"
        echo "Permissions changed to 755 for $filepath"
    fi
}

# 関数: ローカルファイルをS3にアップロード
upload_to_s3() {
    find "$local_dir" -type f | while read -r local_file; do
        relative_path="${local_file#$local_dir/}"
        s3_object_key="${s3_key}${relative_path}"

        s3_file_info=$(aws s3api head-object --bucket kps-pub --key "$s3_object_key" 2>/dev/null)

        if [ $? -ne 0 ]; then
            echo "Uploading $relative_path (not found in S3)"
            aws s3 cp "$local_file" "$s3_bucket/$s3_key$relative_path"
        else
            local_mod_time=$(stat -c %Y "$local_file")
            local_size=$(stat -c %s "$local_file")
            s3_mod_time=$(date -d "$(echo $s3_file_info | jq -r '.LastModified')" +%s)
            s3_size=$(echo $s3_file_info | jq -r '.ContentLength')

            if [ "$local_size" -ne "$s3_size" ] && [ "$local_mod_time" -gt "$s3_mod_time" ]; then
                echo "Uploading $relative_path (different size and local file is newer)"
                aws s3 cp "$local_file" "$s3_bucket/$s3_key$relative_path"
            else
                echo "$relative_path is up-to-date"
            fi
        fi
    done
}

# 関数: S3ファイルをローカルにダウンロード
download_from_s3() {
    s3_files=$(aws s3api list-objects --bucket kps-pub --prefix "$s3_key" --query "Contents[].Key" --output text)

    for s3_file in $s3_files; do
        relative_path="${s3_file#$s3_key}"
        local_file="$local_dir/$relative_path"
        local_dir_path=$(dirname "$local_file")

        if [ ! -f "$local_file" ]; then
            echo "Downloading $relative_path (not found locally)"
            mkdir -p "$local_dir_path"
            aws s3 cp "s3://kps-pub/$s3_file" "$local_file"
            change_permissions_if_sh "$local_file"
        else
            local_mod_time=$(stat -c %Y "$local_file")
            local_size=$(stat -c %s "$local_file")
            s3_file_info=$(aws s3api head-object --bucket kps-pub --key "$s3_file" 2>/dev/null)
            s3_mod_time=$(date -d "$(echo $s3_file_info | jq -r '.LastModified')" +%s)
            s3_size=$(echo $s3_file_info | jq -r '.ContentLength')

            if [ "$s3_size" -ne "$local_size" ] && [ "$s3_mod_time" -gt "$local_mod_time" ]; then
                echo "Downloading $relative_path (different size and S3 file is newer)"
                aws s3 cp "s3://kps-pub/$s3_file" "$local_file"
                change_permissions_if_sh "$local_file"
            else
                echo "$relative_path is up-to-date"
            fi
        fi
    done
}

# メイン処理
case "$operation" in
up)
    upload_to_s3
    ;;
down)
    download_from_s3
    ;;
*)
    echo "Invalid operation: $operation"
    echo "Usage: $0 <local_dir> <up|down> <s3_key>"
    exit 1
    ;;
esac
