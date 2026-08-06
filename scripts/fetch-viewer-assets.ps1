[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$assets = @(
    @{ RelativePath = 'static/vendor/pdfjs/pdf.mjs'; Url = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@6.2.108/build/pdf.mjs' }
    @{ RelativePath = 'static/vendor/pdfjs/pdf.worker.mjs'; Url = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@6.2.108/build/pdf.worker.mjs' }
    @{ RelativePath = 'static/vendor/docx-preview/docx-preview.min.js'; Url = 'https://cdn.jsdelivr.net/npm/docx-preview@0.4.0/dist/docx-preview.min.js' }
    @{ RelativePath = 'static/vendor/three/three.module.min.js'; Url = 'https://cdn.jsdelivr.net/npm/three@0.185.1/build/three.module.min.js' }
    @{ RelativePath = 'static/vendor/three/examples/jsm/controls/OrbitControls.js'; Url = 'https://cdn.jsdelivr.net/npm/three@0.185.1/examples/jsm/controls/OrbitControls.js' }
    @{ RelativePath = 'static/vendor/occt-import-js/occt-import-js.js'; Url = 'https://cdn.jsdelivr.net/npm/occt-import-js@0.0.23/dist/occt-import-js.js' }
    @{ RelativePath = 'static/vendor/occt-import-js/occt-import-js.wasm'; Url = 'https://cdn.jsdelivr.net/npm/occt-import-js@0.0.23/dist/occt-import-js.wasm' }
)

$temporaryFiles = [System.Collections.Generic.List[string]]::new()
try {
    foreach ($asset in $assets) {
        $destination = Join-Path $root $asset.RelativePath
        $directory = Split-Path -Parent $destination
        New-Item -ItemType Directory -Force -Path $directory | Out-Null

        $temporary = "$destination.tmp-$PID"
        $temporaryFiles.Add($temporary)
        Invoke-WebRequest -Uri $asset.Url -OutFile $temporary -UseBasicParsing
        if (-not (Test-Path -LiteralPath $temporary) -or (Get-Item -LiteralPath $temporary).Length -le 0) {
            throw "Downloaded asset is empty: $($asset.Url)"
        }
        Move-Item -Force -LiteralPath $temporary -Destination $destination
        Write-Host "$($asset.RelativePath) $((Get-Item -LiteralPath $destination).Length) bytes"
    }
}
catch {
    Write-Error $_
    exit 1
}
finally {
    foreach ($temporary in $temporaryFiles) {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -Force -LiteralPath $temporary
        }
    }
}
