$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$resultDir = Join-Path (Split-Path -Parent $projectRoot) 'Результат'
$docxPath = Join-Path $resultDir 'Контрольная_Маттиев_МиСАКСИИ.docx'
$pdfPath = Join-Path $resultDir 'Контрольная_Маттиев_МиСАКСИИ.pdf'
$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($docxPath, $false, $false)
    $document.Fields.Update() | Out-Null
    foreach ($toc in $document.TablesOfContents) { $toc.Update() }
    $document.Repaginate()
    foreach ($toc in $document.TablesOfContents) { $toc.UpdatePageNumbers() }
    $document.Save()
    $document.ExportAsFixedFormat($pdfPath, 17)
    Write-Output ('Report exported. Pages: ' + $document.ComputeStatistics(2))
} finally {
    if ($null -ne $document) { $document.Close($false) }
    if ($null -ne $word) { $word.Quit() }
}
