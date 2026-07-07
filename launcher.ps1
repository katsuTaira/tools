# launcher.ps1

$propFile = Join-Path $PSScriptRoot "scripts.properties"
$historyDir = Join-Path $HOME ".tools"
$historyFile = Join-Path $historyDir "history.json"

if (-Not (Test-Path $historyDir)) {
    New-Item -ItemType Directory -Path $historyDir | Out-Null
}

# ---- Load properties file ----------------------------------------------------

$props = [ordered]@{}
Get-Content $propFile | ForEach-Object {
    if ($_ -match "^\s*([^=]+)\s*=\s*(.+)$") {
        $key = $matches[1].Trim()
        $val = $matches[2].Trim()
        $props[$key] = $val
    }
}

# ---- Load history ------------------------------------------------------------

$history = @{}
if (Test-Path $historyFile) {
    $json = Get-Content $historyFile -Raw
    $obj = $json | ConvertFrom-Json
    foreach ($p in $obj.PSObject.Properties) {
        $history[$p.Name] = @($p.Value)
    }
}

# ---- Script list -------------------------------------------------------------

$scriptList = $props.Keys | Where-Object { $_ -notmatch "\." }

Write-Host "===== スクリプト一覧 ====="
$i = 1
$keys = @()
foreach ($k in $scriptList) {
    Write-Host "$i) $k : $($props[$k])"
    $keys += $k
    $i++
}

while ($true) {
    $sel = Read-Host "起動したい番号を入力"
    if ($sel -match '^\d+$' -and [int]$sel -ge 1 -and [int]$sel -le $keys.Count) {
        break
    }
}

$scriptName = $keys[$sel - 1]
$execCommand = ""

# 1. properties に .cmd 指定があるか確認
if ($props.Contains("$scriptName.cmd")) {
    $execCommand = $props["$scriptName.cmd"]
} else {
    # 2. なければ従来通り tools 配下の .ps1 とみなす
    $execCommand = Join-Path $PSScriptRoot "$scriptName.ps1"
}

# クォート除去してパス形式（/ または \ を含む）なら存在確認
$cleanCommand = $execCommand -replace '^"|"$', ''
if ($cleanCommand -match '[\\/]' -and -Not (Test-Path $cleanCommand)) {
    Write-Host "実行対象が見つかりません: $cleanCommand"
    exit 1
}

# ---- Argument Definitions ----------------------------------------------------

$argNames = @()
$defaults = @()

if ($props.Contains("$scriptName.args")) {
    $argNames = @($props["$scriptName.args"].Split(",") | ForEach-Object { $_.Trim() })
}

if ($props.Contains("$scriptName.defaults")) {
    $defaults = @($props["$scriptName.defaults"].Split(",") | ForEach-Object { $_.Trim() })
}

# ---- Show history ------------------------------------------------------------

$scriptHistory = @()
if ($history.ContainsKey($scriptName)) {
    $scriptHistory = $history[$scriptName]
}

if ($scriptHistory.Count -gt 0) {
    Write-Host ""
    Write-Host "===== 過去の引数セット ====="
    $i = 1
    foreach ($h in $scriptHistory) {
        Write-Host "$i) $($h -join ', ')"
        $i++
    }
    Write-Host "0) 履歴を使わない（新しく入力）"
}

$useHistory = -1
if ($scriptHistory.Count -gt 0) {
    while ($true) {
        $in = Read-Host "履歴番号を選択（0 で新規入力）"
        if ($in -match "^\d+$" -and [int]$in -ge 0 -and [int]$in -le $scriptHistory.Count) {
            $useHistory = [int]$in
            break
        }
    }
}

if ($useHistory -gt 0) {
    # ---- Use history as baseline and allow modification ---------------------
    Write-Host ""
    Write-Host "===== 引数の確認・修正（空 Enter = 現在の値を使用） ====="
    $baseArgs = $scriptHistory[$useHistory - 1]
    $argsList = @()
    
    # 定義された引数名がある場合はその数を優先し、履歴は値としてのみ使う
    $count = if ($argNames.Count -gt 0) { $argNames.Count } else { $baseArgs.Count }
    
    for ($i = 0; $i -lt $count; $i++) {
        $name = if ($i -lt $argNames.Count) { $argNames[$i] } else { "Arg $($i + 1)" }
        $currentVal = if ($i -lt $baseArgs.Count) { $baseArgs[$i] } else { "" }

        # 表示される値からクォートを除去して見やすくする
        $displayVal = $currentVal -replace '^"|"$', ''
        $val = Read-Host "$name (current: $displayVal)"
        
        if ([string]::IsNullOrWhiteSpace($val)) {
            $val = $displayVal
        } else {
            $val = $val.Trim()
        }

        # クォートで囲み、内部のクォートをエスケープする
        if ($val -ne "") {
            if ($val -match '^"(.*)"$') { $val = $matches[1] }
            $val = '"' + ($val -replace '"', '`"') + '"'
        }
        $argsList += $val
    }
} else {
    # ---- Interactive argument input -----------------------------------------
    Write-Host ""
    Write-Host "===== 引数入力（空 Enter = デフォルト値使用） ====="

    $argsList = @()
    for ($i = 0; $i -lt $argNames.Count; $i++) {
        $name = $argNames[$i]
        $def = if ($i -lt $defaults.Count) { $defaults[$i] } else { "" }

        $msg = if ($def -ne "") { "$name (default: $def)" } else { $name }
        $val = Read-Host $msg

        if ([string]::IsNullOrWhiteSpace($val)) {
            $val = $def
        } else {
            $val = $val.Trim()
        }

        # クォートで囲み、内部のクォートをエスケープする
        if ($val -ne "") {
            if ($val -match '^"(.*)"$') { $val = $matches[1] }
            $val = '"' + ($val -replace '"', '`"') + '"'
        }
        $argsList += $val
    }
}

# ---- Save history ------------------------------------------------------------

if (-Not $history.ContainsKey($scriptName)) {
    $history[$scriptName] = @()
}

# 既存履歴と重複していない時だけ追加
if ($argsList.Count -gt 0 -and 
    -not ($history[$scriptName] | Where-Object { ($_ -join ",") -eq ($argsList -join ",") })) {

    $history[$scriptName] += , $argsList

    # 履歴は最大 5 件にする（古いものから削除）
    if ($history[$scriptName].Count -gt 5) {
        $history[$scriptName] = $history[$scriptName][-5..-1]
    }

    $history | ConvertTo-Json -Depth 5 | Set-Content $historyFile
}

# ---- Execute -----------------------------------------------------------------

Write-Host ""
Write-Host "実行コマンド:"
Write-Host "  $execCommand $($argsList -join ' ')"
Read-Host "[Enter] で実行 / Ctrl+C で中止" | Out-Null

if ($execCommand.EndsWith(".ps1")) {
    & $execCommand @argsList
} else {
    # .sh や一般コマンドの場合
    $argString = $argsList -join ' '
    iex "$execCommand $argString"
}
