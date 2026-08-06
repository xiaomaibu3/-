[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$vendor = Join-Path $root 'static/vendor'
$staging = Join-Path $root ".viewer-assets-staging-$PID"
$backup = Join-Path $root ".viewer-assets-backup-$PID"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
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

try {
    New-Item -ItemType Directory -Force -Path $staging | Out-Null
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
            $head = [Text.Encoding]::UTF8.GetString($bytes, 0, [Math]::Min($bytes.Length, 512))
            if ($head -match '<!DOCTYPE html|<html|<body') { throw "HTML error page downloaded: $($asset.RelativePath)" }
            if ($head -notmatch '^\s*(?:/\*|//|import\b|var\b|!function|\(function)') { throw "Invalid JavaScript header: $($asset.RelativePath)" }
        }
        if ($asset.RewriteImport) {
            $source = [IO.File]::ReadAllText($destination, [Text.Encoding]::UTF8)
            $source = $source.Replace("from 'three';", "from '../../../three.core.min.js';")
            [IO.File]::WriteAllText($destination, $source, $utf8NoBom)
            if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -ne $asset.PublishedSha256) { throw "Published SHA-256 mismatch for $($asset.RelativePath)" }
            if ($source -match 'from ["'']three["'']') { throw 'OrbitControls.js still has a bare three import' }
        }
    }
    foreach ($asset in $assets) {
        if (-not (Test-Path -LiteralPath (Join-Path $staging $asset.RelativePath))) { throw "Missing staged asset: $($asset.RelativePath)" }
    }
    if (Test-Path -LiteralPath $vendor) { Move-Item -LiteralPath $vendor -Destination $backup }
    Move-Item -LiteralPath $staging -Destination $vendor
    if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Recurse -Force }
}
catch {
    if ((Test-Path -LiteralPath $backup) -and -not (Test-Path -LiteralPath $vendor)) {
        Move-Item -LiteralPath $backup -Destination $vendor
    }
    Write-Error $_
    exit 1
}
finally {
    if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
    if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Recurse -Force }
}
