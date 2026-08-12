[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$vendor = Join-Path $root 'static/vendor'
$operationId = [guid]::NewGuid().ToString('N')
$staging = Join-Path $root ".viewer-assets-staging-$operationId"
$backup = Join-Path $root ".viewer-assets-backup-$operationId"
$stagingCreated = $false
$backupCreated = $false
$utf8StrictNoBom = [Text.UTF8Encoding]::new($false, $true)
$assets = @(
    @{ RelativePath = 'pdfjs/pdf.mjs'; Url = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@6.2.108/build/pdf.mjs'; Sha256 = '487BDE1BCF89E041F791173D0509A1DC18D0FEB6655D78395E1611F9DA0DE17D'; Kind = 'JavaScript' }
    @{ RelativePath = 'pdfjs/pdf.worker.mjs'; Url = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@6.2.108/build/pdf.worker.mjs'; Sha256 = '1A7607F28CFBC63F0E4E0A41927C89F991E353E4F3FB4565ECFD621AC5975089'; Kind = 'JavaScript' }
    @{ RelativePath = 'docx-preview/docx-preview.min.js'; Url = 'https://cdn.jsdelivr.net/npm/docx-preview@0.4.0/dist/docx-preview.min.js'; Sha256 = '051EF503F2677D53159A388B7384E950EDA41EA4E47A103E5E36F124D7FAEA40'; Kind = 'JavaScript' }
    @{ RelativePath = 'jszip/jszip.min.js'; Url = 'https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js'; Sha256 = 'ACC7E41455A80765B5FD9C7EE1B8078A6D160BBBCA455AEAE854DE65C947D59E'; Kind = 'JavaScript' }
    @{ RelativePath = 'three/three.module.min.js'; Url = 'https://cdn.jsdelivr.net/npm/three@0.185.1/build/three.module.min.js'; Sha256 = '86BCEE248B64F44BCFC23C331AE74619061957D59CAB040171DCB6FB5900BEB6'; Kind = 'JavaScript' }
    @{ RelativePath = 'three/three.core.min.js'; Url = 'https://cdn.jsdelivr.net/npm/three@0.185.1/build/three.core.min.js'; Sha256 = '05B2609338C76CD65DAF74F3AC515BC9A5045E1B3B33EDC07D8C9BD55250FA90'; Kind = 'JavaScript' }
    @{ RelativePath = 'three/examples/jsm/controls/OrbitControls.js'; Url = 'https://cdn.jsdelivr.net/npm/three@0.185.1/examples/jsm/controls/OrbitControls.js'; Sha256 = 'FAABB4E8DFD9235EE4A9FD7C9A3D75F90F1689DBD4944BD6FD32117DACEC5F93'; PublishedSha256 = '2555534AAF439B68A30851133DC168AAAC18AA301D450419FB29BC1DEFAD4E61'; Kind = 'JavaScript'; RewriteImport = $true }
    @{ RelativePath = 'occt-import-js/occt-import-js.js'; Url = 'https://cdn.jsdelivr.net/npm/occt-import-js@0.0.23/dist/occt-import-js.js'; Sha256 = '3FB44CE11D00611F9B3F3C5775D520EBAB48930C1F08279B7B1316F05F0D3379'; Kind = 'JavaScript' }
    @{ RelativePath = 'occt-import-js/occt-import-js.wasm'; Url = 'https://cdn.jsdelivr.net/npm/occt-import-js@0.0.23/dist/occt-import-js.wasm'; Sha256 = '33391FC9D94EA5C869A6718488BF0A9A464222BAC9BDC764DFE1690CEF281952'; Kind = 'Wasm' }
)
$replacedFiles = [System.Collections.Generic.List[object]]::new()
$recoverySucceeded = $false

function Remove-OwnDirectory($path, $label) {
    if (Test-Path -LiteralPath $path) {
        try { Remove-Item -LiteralPath $path -Recurse -Force }
        catch { Write-Warning "Could not clean $label '$path': $($_.Exception.Message)" }
    }
}

try {
    New-Item -ItemType Directory -Force -Path $staging | Out-Null
    $stagingCreated = $true
    foreach ($asset in $assets) {
        $destination = Join-Path $staging $asset.RelativePath
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
        Invoke-WebRequest -Uri $asset.Url -OutFile $destination -UseBasicParsing
        $item = Get-Item -LiteralPath $destination
        if ($item.Length -le 0) { throw "Downloaded asset is empty: $($asset.Url)" }
        $hash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
        if ($hash -ne $asset.Sha256) { throw "SHA-256 mismatch for $($asset.RelativePath): $hash" }
        $bytes = [IO.File]::ReadAllBytes($destination)
        if ($asset.Kind -eq 'Wasm') {
            if ($bytes.Length -lt 4 -or $bytes[0] -ne 0 -or $bytes[1] -ne 97 -or $bytes[2] -ne 115 -or $bytes[3] -ne 109) { throw "Invalid WASM header: $($asset.RelativePath)" }
        } else {
            $source = $utf8StrictNoBom.GetString($bytes)
            if ($source -match '<!DOCTYPE html|<html|<body') { throw "HTML error page downloaded: $($asset.RelativePath)" }
            if ($source -notmatch '^\s*(?:/\*|//|import\b|var\b|!function|\(function)') { throw "Invalid JavaScript header: $($asset.RelativePath)" }
            if ($asset.RewriteImport) {
                $source = $source.Replace("from 'three';", "from '../../../three.core.min.js';")
                [IO.File]::WriteAllText($destination, $source, $utf8StrictNoBom)
                if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -ne $asset.PublishedSha256) { throw "Published SHA-256 mismatch for $($asset.RelativePath)" }
                if ($source -match 'from ["'']three["'']') { throw 'OrbitControls.js still has a bare three import' }
            }
        }
    }
    Set-Content -LiteralPath (Join-Path $staging '.install-ready') -Value $operationId -NoNewline -Encoding ascii
    New-Item -ItemType Directory -Force -Path $backup | Out-Null
    $backupCreated = $true
    foreach ($asset in $assets) {
        $relative = $asset.RelativePath
        $target = Join-Path $vendor $relative
        $backupTarget = Join-Path $backup $relative
        $state = [pscustomobject]@{ RelativePath = $relative; Target = $target; Backup = $backupTarget; HadOriginal = (Test-Path -LiteralPath $target); BackedUp = $false; Installed = $false }
        $replacedFiles.Add($state)
        if ($state.HadOriginal) {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backupTarget) | Out-Null
            Move-Item -LiteralPath $target -Destination $backupTarget
            $state.BackedUp = $true
        }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Move-Item -LiteralPath (Join-Path $staging $relative) -Destination $target
        $state.Installed = $true
        Set-Content -LiteralPath (Join-Path $staging ".installed-$($relative.Replace('/', '-'))") -Value $operationId -NoNewline -Encoding ascii
    }
    $recoverySucceeded = $true
}
catch {
    $originalError = $_
    $recoverySucceeded = $true
    for ($index = $replacedFiles.Count - 1; $index -ge 0; $index--) {
        $state = $replacedFiles[$index]
        try {
            if ($state.Installed -and (Test-Path -LiteralPath $state.Target)) { Remove-Item -LiteralPath $state.Target -Force }
            if ($state.BackedUp -and (Test-Path -LiteralPath $state.Backup)) {
                New-Item -ItemType Directory -Force -Path (Split-Path -Parent $state.Target) | Out-Null
                Move-Item -LiteralPath $state.Backup -Destination $state.Target
            }
        } catch { Write-Warning "Could not restore $($state.RelativePath): $($_.Exception.Message)"; $recoverySucceeded = $false }
    }
    Write-Error -ErrorRecord $originalError -ErrorAction Continue
    exit 1
}
finally {
    if ($stagingCreated) { Remove-OwnDirectory $staging 'staging directory' }
    if ($backupCreated -and $recoverySucceeded) { Remove-OwnDirectory $backup 'backup directory' }
}
