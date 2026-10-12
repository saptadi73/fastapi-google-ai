$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskOutput = Join-Path $taskRoot 'docs\presentations'
$taskPptPath = Join-Path $taskOutput 'Panduan_Penggunaan_Google_Sheet_AI.pptx'
$taskPdfPath = Join-Path $taskOutput 'Panduan_Penggunaan_Google_Sheet_AI.pdf'
$taskPreviewPath = Join-Path $taskOutput 'preview'
New-Item -ItemType Directory -Path $taskPreviewPath -Force | Out-Null
$taskPowerPoint = New-Object -ComObject PowerPoint.Application
try {
    # Open without a presentation window; preserve any presentations already open.
    $taskDeck = $taskPowerPoint.Presentations.Open($taskPptPath, -1, 0, 0)
    $taskDeck.SaveAs($taskPdfPath, 32)
    $taskDeck.Export($taskPreviewPath, 'PNG', 1600, 900)
    $taskOverflow = @()
    foreach ($taskSlide in $taskDeck.Slides) {
        foreach ($taskShape in $taskSlide.Shapes) {
            if ($taskShape.HasTable -eq -1) {
                foreach ($taskRow in $taskShape.Table.Rows) {
                    foreach ($taskCell in $taskRow.Cells) {
                        $taskFrame = $taskCell.Shape.TextFrame
                        $taskAvailable = $taskCell.Shape.Height - $taskFrame.MarginTop - $taskFrame.MarginBottom
                        if ($taskFrame.TextRange.BoundHeight -gt ($taskAvailable + 2)) {
                            $taskOverflow += [pscustomobject]@{
                                slide = $taskSlide.SlideIndex
                                kind = 'table'
                                text = $taskFrame.TextRange.Text
                                bound = $taskFrame.TextRange.BoundHeight
                                available = $taskAvailable
                            }
                        }
                    }
                }
            } elseif ($taskShape.HasTextFrame -eq -1 -and $taskShape.TextFrame.HasText -eq -1) {
                $taskFrame = $taskShape.TextFrame
                $taskAvailable = $taskShape.Height - $taskFrame.MarginTop - $taskFrame.MarginBottom
                if ($taskFrame.TextRange.BoundHeight -gt ($taskAvailable + 2)) {
                    $taskOverflow += [pscustomobject]@{
                        slide = $taskSlide.SlideIndex
                        kind = 'textbox'
                        text = $taskFrame.TextRange.Text
                        bound = $taskFrame.TextRange.BoundHeight
                        available = $taskAvailable
                    }
                }
            }
        }
    }
    ConvertTo-Json -InputObject @($taskOverflow) -Depth 3 |
        Set-Content -LiteralPath (Join-Path $taskOutput 'layout_review.json') -Encoding utf8
    Write-Output "SLIDES=$($taskDeck.Slides.Count) OVERFLOW=$($taskOverflow.Count)"
    $taskDeck.Close()
    if ($taskOverflow.Count -gt 0) { throw 'Presentation text overflow requires correction.' }
} finally {
    if ($taskPowerPoint.Presentations.Count -eq 0) { $taskPowerPoint.Quit() }
    [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($taskPowerPoint) | Out-Null
}
