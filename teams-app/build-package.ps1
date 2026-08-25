$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$packageDirectory = Join-Path $PSScriptRoot "build"
$archivePath = Join-Path $PSScriptRoot "Scribe-Teams.zip"
New-Item -ItemType Directory -Path $packageDirectory -Force | Out-Null
Copy-Item (Join-Path $PSScriptRoot "manifest.json") $packageDirectory -Force

function New-ScribeIcon {
    param(
        [int]$Size,
        [string]$Path,
        [bool]$Color
    )
    $bitmap = New-Object System.Drawing.Bitmap($Size, $Size)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.Clear([System.Drawing.Color]::Transparent)
    if ($Color) {
        $margin = [int]($Size * 0.08)
        $brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(23, 62, 53))
        $graphics.FillEllipse($brush, $margin, $margin, $Size - 2 * $margin, $Size - 2 * $margin)
        $brush.Dispose()
    }
    $fontSize = if ($Color) { [single]($Size * 0.48) } else { [single]($Size * 0.72) }
    $font = New-Object System.Drawing.Font("Segoe UI", $fontSize, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
    $textBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
    $format = New-Object System.Drawing.StringFormat
    $format.Alignment = [System.Drawing.StringAlignment]::Center
    $format.LineAlignment = [System.Drawing.StringAlignment]::Center
    $graphics.DrawString("S", $font, $textBrush, [System.Drawing.RectangleF]::new(0, 0, $Size, $Size), $format)
    $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $format.Dispose(); $textBrush.Dispose(); $font.Dispose(); $graphics.Dispose(); $bitmap.Dispose()
}

New-ScribeIcon -Size 192 -Path (Join-Path $packageDirectory "color.png") -Color $true
New-ScribeIcon -Size 32 -Path (Join-Path $packageDirectory "outline.png") -Color $false
if (Test-Path $archivePath) { Remove-Item -LiteralPath $archivePath }
Compress-Archive -Path (Join-Path $packageDirectory "manifest.json"), (Join-Path $packageDirectory "color.png"), (Join-Path $packageDirectory "outline.png") -DestinationPath $archivePath
Write-Host "Paquet créé : $archivePath"
