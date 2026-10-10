# Requires PowerShell 7.5+ and Python. Run with the KBA clone as workdir.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$HtmlPath,
    [Parameter(Mandatory = $true)][string]$JsonPath,
    [Parameter(Mandatory = $true)][string]$PublishedHtmlName,
    [string]$RepositoryPath = (Split-Path -Parent $PSScriptRoot),
    [switch]$PrepareOnly
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path -LiteralPath $RepositoryPath).Path
$sourceHtml = (Resolve-Path -LiteralPath $HtmlPath).Path
$sourceJson = (Resolve-Path -LiteralPath $JsonPath).Path
if ($PublishedHtmlName -notmatch '^report_(?<date>\d{8})_(?<authority>jra|nar)_[a-z0-9_]+_v(?<version>\d+)\.html$') {
    throw '公開名はreport_YYYYMMDD_jra_predictions_vN.htmlまたはreport_YYYYMMDD_nar_..._vN.htmlを指定してください。'
}
$filenameDate = $Matches.date
$authority = $Matches.authority.ToLowerInvariant()
$reportVersion = 'v' + $Matches.version
$publishedJsonName = [IO.Path]::ChangeExtension($PublishedHtmlName, '.json')
$predictionFolder = Join-Path $repositoryRoot 'predictions'
$htmlTarget = Join-Path $predictionFolder $PublishedHtmlName
$jsonTarget = Join-Path $predictionFolder $publishedJsonName
$utf8NoBom = [Text.UTF8Encoding]::new($false)
$htmlContent = [IO.File]::ReadAllText($sourceHtml, [Text.Encoding]::UTF8)
$jsonDocument = [IO.File]::ReadAllText($sourceJson, [Text.Encoding]::UTF8) | ConvertFrom-Json -Depth 100 -DateKind String

# Preserve original JRA/NAR fields. Publication metadata holds their common labels.
$forecastVersion = $jsonDocument.forecast_version
if (-not $forecastVersion) { $forecastVersion = $jsonDocument.version }
if (-not $forecastVersion -and $jsonDocument.model_version) { $forecastVersion = $reportVersion }
$fixedAt = $jsonDocument.fixed_at
if (-not $fixedAt) { $fixedAt = $jsonDocument.generated_at }
$predictionDate = $jsonDocument.date_jst
if (-not $predictionDate) { $predictionDate = $jsonDocument.target_date }
if (-not $forecastVersion -or -not $fixedAt -or -not $predictionDate -or -not $jsonDocument.races) {
    throw 'JSONに予想版・固定時刻・開催日・対象レースが必要です（共通仕様または旧JRA/地方形式）。'
}
if ($predictionDate -notmatch '^\d{4}-\d{2}-\d{2}$' -or $predictionDate.Replace('-', '') -ne $filenameDate) {
    throw 'JSONの開催日と公開ファイル名の日付が一致しません。'
}
if ($fixedAt -notmatch '(Z|[+-]\d{2}:\d{2})$') {
    throw '固定時刻にはタイムゾーン付きISO 8601を指定してください。'
}
if ($jsonDocument.document_type -and $jsonDocument.document_type -ne 'prediction') {
    throw 'このコマンドは固定予想を公開するものです。振り返りや購入記録は別の公開手順で扱ってください。'
}
if ($jsonDocument.authority -and $jsonDocument.authority -ne $authority) {
    throw 'JSONの区分と公開ファイル名の区分が一致しません。'
}
if ($authority -eq 'jra' -and $jsonDocument.baba_code) {
    throw '地方競馬のJSONをJRAとして公開できません。'
}
if (-not $jsonDocument.authority -and $jsonDocument.target_date -and $jsonDocument.generated_at -and $jsonDocument.model_version -and $authority -ne 'jra') {
    throw '旧JRA形式のJSONにはJRAの公開ファイル名を指定してください。'
}
# New JRA days must preserve explicit rival/unknown-condition and ticket reviews.
# Historical frozen forecasts and NAR publication stay under their existing contracts.
if ($authority -eq 'jra' -and $predictionDate -ge '2026-10-11') {
    & python -X utf8 (Join-Path $repositoryRoot 'scripts/check_jra_forecast.py') $sourceJson --strict
    if ($LASTEXITCODE -ne 0) { throw 'JRAの公開前比較・根拠照合が未完了です。指摘を直すか本線を見送ってください。' }
}
$venueNames = @($jsonDocument.venues | ForEach-Object { $_.label } | Where-Object { $_ })
if (-not $venueNames.Count -and $jsonDocument.venue) { $venueNames = @($jsonDocument.venue) }
if (-not $venueNames.Count) { $venueNames = @($jsonDocument.races | ForEach-Object { $_.venue } | Where-Object { $_ } | Select-Object -Unique) }
$sourceJsonLink = 'href="' + [IO.Path]::GetFileName($sourceJson) + '"'
if (-not $htmlContent.Contains($sourceJsonLink)) { throw 'HTMLに対応するJSONへの相対リンクがありません。' }
$htmlContent = $htmlContent.Replace($sourceJsonLink, 'href="' + $publishedJsonName + '"')

function Invoke-RepositoryGit {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $gitResult = & git -C $repositoryRoot @Arguments
    if ($LASTEXITCODE -ne 0) { throw "git $($Arguments[0]) が失敗しました。" }
    return $gitResult
}

$env:GIT_TERMINAL_PROMPT = '0'
$env:GCM_INTERACTIVE = 'Never'
if ((Invoke-RepositoryGit branch --show-current) -ne 'main') { throw 'mainブランチで実行してください。' }
if ((Invoke-RepositoryGit remote get-url origin) -notin @('https://github.com/ZunchiLab/KBA.git', 'git@github.com:ZunchiLab/KBA.git')) {
    throw 'originが指定のKBAリポジトリではありません。'
}
if (Invoke-RepositoryGit status --porcelain) { throw '作業ツリーに既存の変更があります。対象を確認してから公開してください。' }
Invoke-RepositoryGit fetch origin main
Invoke-RepositoryGit merge --ff-only origin/main
if ((Invoke-RepositoryGit rev-parse HEAD) -ne (Invoke-RepositoryGit rev-parse origin/main)) {
    throw '未公開の既存コミットがあります。混在を避けるため停止しました。'
}
if ((Test-Path -LiteralPath $htmlTarget) -or (Test-Path -LiteralPath $jsonTarget)) {
    throw '公開済み版は上書きできません。新しい版名を指定してください。'
}
$publicationInfo = [ordered]@{
    repository = 'https://github.com/ZunchiLab/KBA'
    branch = 'main'
    html_file = "predictions/$PublishedHtmlName"
    json_file = "predictions/$publishedJsonName"
    authority = $authority
    date_jst = $predictionDate
    report_version = $reportVersion
    forecast_version = $forecastVersion
    model_version = $jsonDocument.model_version
    fixed_at = $fixedAt
    venues = $venueNames
    original_html_sha256 = (Get-FileHash -LiteralPath $sourceHtml -Algorithm SHA256).Hash.ToLowerInvariant()
    original_json_sha256 = (Get-FileHash -LiteralPath $sourceJson -Algorithm SHA256).Hash.ToLowerInvariant()
    source_snapshots_published = $false
    source_snapshot_note = 'このコマンドの公開対象はHTML・JSON・一覧・カタログ。取得原文、結果取得対象、workflowは別途登録する。'
}
$jsonDocument | Add-Member -NotePropertyName publication -NotePropertyValue $publicationInfo -Force
[IO.File]::WriteAllText($htmlTarget, $htmlContent, $utf8NoBom)
[IO.File]::WriteAllText($jsonTarget, ($jsonDocument | ConvertTo-Json -Depth 100), $utf8NoBom)
& python -X utf8 (Join-Path $repositoryRoot 'scripts/build_catalog.py')
if ($LASTEXITCODE -ne 0) { throw '一覧ページの生成に失敗しました。' }
Invoke-RepositoryGit add -- "predictions/$PublishedHtmlName" "predictions/$publishedJsonName" index.html data/catalog.json
Invoke-RepositoryGit diff --cached --stat
if ($PrepareOnly) {
    Write-Output '公開ファイルを準備しました。差分確認後にgit commitとgit push origin mainを実行してください。'
    return
}
Invoke-RepositoryGit commit -m "Add $predictionDate $authority prediction $reportVersion"
Invoke-RepositoryGit push origin main
$localHead = Invoke-RepositoryGit rev-parse HEAD
$remoteLine = Invoke-RepositoryGit ls-remote origin refs/heads/main
if ($remoteLine.Split()[0] -ne $localHead) { throw 'リモートmainがローカルコミットと一致しません。' }
Write-Output "プッシュ完了: $localHead"
