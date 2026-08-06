$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$sdkRoot = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { Join-Path $root ".android-sdk" }
$javaHome = if ($env:JAVA_HOME) { $env:JAVA_HOME } else { Join-Path $root ".jdk" }
$buildTools = Join-Path $sdkRoot "build-tools\35.0.0"
$platformJar = Join-Path $sdkRoot "platforms\android-35\android.jar"
$out = Join-Path $root "build"
$app = Join-Path $root "app\src\main"
$pkg = "com.xinggui.app"
$versionFile = Join-Path $root "..\VERSION"
$manifestFile = Join-Path $app "AndroidManifest.xml"

$javac = Join-Path $javaHome "bin\javac.exe"
$aapt2 = Join-Path $buildTools "aapt2.exe"
$d8 = Join-Path $buildTools "d8.bat"
$zipalign = Join-Path $buildTools "zipalign.exe"
$apksigner = Join-Path $buildTools "apksigner.bat"
$keytool = Join-Path $javaHome "bin\keytool.exe"

function Assert-LastExit($step) {
  if ($LASTEXITCODE -ne 0) {
    throw "$step failed with exit code $LASTEXITCODE"
  }
}

foreach ($tool in @($javac, $aapt2, $d8, $zipalign, $apksigner, $keytool, $platformJar)) {
  if (-not (Test-Path -LiteralPath $tool)) {
    throw "Missing build dependency: $tool"
  }
}

$appVersion = (Get-Content -LiteralPath $versionFile -Raw).Trim()
$manifestText = Get-Content -LiteralPath $manifestFile -Raw
if ($manifestText -notmatch 'android:versionName="([^"]+)"') {
  throw "AndroidManifest.xml is missing android:versionName"
}
$manifestVersion = $Matches[1]
if ($manifestVersion -ne $appVersion) {
  throw "Android versionName $manifestVersion does not match VERSION $appVersion"
}

New-Item -ItemType Directory -Force -Path $out | Out-Null
Remove-Item -LiteralPath (Join-Path $out "compiled") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $out "classes") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $out "dex") -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path (Join-Path $out "compiled"), (Join-Path $out "classes"), (Join-Path $out "dex"), (Join-Path $out "gen") | Out-Null

& $aapt2 compile --dir (Join-Path $app "res") -o (Join-Path $out "compiled\res.zip")
Assert-LastExit "aapt2 compile"
& $aapt2 link -o (Join-Path $out "xinggui-unsigned.apk") -I $platformJar --manifest $manifestFile -R (Join-Path $out "compiled\res.zip") --java (Join-Path $out "gen") --auto-add-overlay
Assert-LastExit "aapt2 link"

$javaFiles = @(
  (Join-Path $out "gen\$($pkg.Replace('.', '\'))\R.java"),
  (Join-Path $app "java\com\xinggui\app\MainActivity.java")
)
& $javac -encoding UTF-8 -source 8 -target 8 -bootclasspath $platformJar -d (Join-Path $out "classes") $javaFiles
Assert-LastExit "javac"
$classFiles = Get-ChildItem -LiteralPath (Join-Path $out "classes") -Recurse -Filter "*.class" | ForEach-Object { $_.FullName }
& $d8 --release --min-api 23 --lib $platformJar --output (Join-Path $out "dex") $classFiles
Assert-LastExit "d8"

Copy-Item -LiteralPath (Join-Path $out "xinggui-unsigned.apk") -Destination (Join-Path $out "xinggui-with-dex.apk") -Force
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$apk = [System.IO.Compression.ZipFile]::Open((Join-Path $out "xinggui-with-dex.apk"), [System.IO.Compression.ZipArchiveMode]::Update)
try {
  [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($apk, (Join-Path $out "dex\classes.dex"), "classes.dex") | Out-Null
} finally {
  $apk.Dispose()
}

& $zipalign -f 4 (Join-Path $out "xinggui-with-dex.apk") (Join-Path $out "xinggui-aligned.apk")
Assert-LastExit "zipalign"

$keystore = Join-Path $out "xinggui-release.jks"
if (-not (Test-Path -LiteralPath $keystore)) {
  & $keytool -genkeypair -v -keystore $keystore -storepass "xinggui123" -keypass "xinggui123" -alias "xinggui" -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Xinggui,O=MimoClaw,C=CN"
  Assert-LastExit "keytool"
}

& $apksigner sign --ks $keystore --ks-key-alias "xinggui" --ks-pass "pass:xinggui123" --key-pass "pass:xinggui123" --out (Join-Path $out "xinggui.apk") (Join-Path $out "xinggui-aligned.apk")
Assert-LastExit "apksigner sign"
& $apksigner verify --verbose (Join-Path $out "xinggui.apk")
Assert-LastExit "apksigner verify"

Write-Host "APK created at: $(Join-Path $out "xinggui.apk")"
