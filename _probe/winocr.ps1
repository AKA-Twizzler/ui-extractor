# The third reader: Windows' own OCR (Windows.Media.Ocr), no package, no admin.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File winocr.ps1 <list.json>
# where list.json holds a JSON array of image paths. Prints one JSON array:
# per image {path, w, h, ms, lines:[{text, words:[{t,x,y,w,h}]}]}; boxes in
# the image's own pixels. Every image in the list is read by one engine in
# one process, so the process start is paid once per batch.
param([string]$ListPath)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.StorageFile, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, $t) { $m = $asTaskGeneric.MakeGenericMethod($t); $task = $m.Invoke($null, @($op)); $task.Wait(-1) | Out-Null; $task.Result }
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
$paths = Get-Content -Raw -Encoding UTF8 $ListPath | ConvertFrom-Json
$all = New-Object System.Collections.ArrayList
foreach ($p in $paths) {
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($p)) ([Windows.Storage.StorageFile])
  $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
  $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
  $sw.Stop()
  $lines = New-Object System.Collections.ArrayList
  foreach ($line in $result.Lines) {
    $words = New-Object System.Collections.ArrayList
    foreach ($w in $line.Words) {
      [void]$words.Add(@{ t = $w.Text; x = [double]$w.BoundingRect.X; y = [double]$w.BoundingRect.Y; w = [double]$w.BoundingRect.Width; h = [double]$w.BoundingRect.Height })
    }
    [void]$lines.Add(@{ text = $line.Text; words = $words.ToArray() })
  }
  [void]$all.Add(@{ path = $p; w = $bitmap.PixelWidth; h = $bitmap.PixelHeight; ms = $sw.ElapsedMilliseconds; lines = $lines.ToArray() })
  $stream.Dispose(); $bitmap.Dispose()
}
ConvertTo-Json -Depth 8 -Compress -InputObject $all.ToArray()
