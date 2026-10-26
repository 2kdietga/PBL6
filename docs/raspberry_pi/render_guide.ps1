$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$docPath = Join-Path $repoRoot 'docs/Raspberry_Pi_Giao_tiep_Server.docx'
$qaDir = Join-Path $repoRoot '.tmp/rasp_docx_qa'
New-Item -ItemType Directory -Path $qaDir -Force | Out-Null
$pdfPath = Join-Path $qaDir 'preview.pdf'
$wordApp = $null
$wordDoc = $null
try {
    $wordApp = New-Object -ComObject Word.Application
    Write-Output 'Word application created'
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $wordApp.AutomationSecurity = 3
    $wordApp.Options.UpdateLinksAtOpen = $false
    Write-Output 'Opening document'
    $wordDoc = $wordApp.Documents.Open($docPath, $false, $true)
    Write-Output 'Document opened'
    $wordDoc.Repaginate()
    $wordDoc.ExportAsFixedFormat($pdfPath, 17)
    Write-Output ('Word pages: ' + $wordDoc.ComputeStatistics(2))
} finally {
    if ($null -ne $wordDoc) { $wordDoc.Close(0) }
    if ($null -ne $wordApp) { $wordApp.Quit() }
}

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType=WindowsRuntime]
$null = [Windows.Data.Pdf.PdfPageRenderOptions, Windows.Data.Pdf, ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType=WindowsRuntime]
$genericAsTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and
    $_.GetGenericArguments().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1
$actionAsTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and -not $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction'
} | Select-Object -First 1
function Wait-Result($operation, $resultType) {
    $task = $genericAsTask.MakeGenericMethod($resultType).Invoke($null, @($operation))
    $task.GetAwaiter().GetResult()
}
$storageFile = Wait-Result ([Windows.Storage.StorageFile]::GetFileFromPathAsync($pdfPath)) ([Windows.Storage.StorageFile])
$pdf = Wait-Result ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($storageFile)) ([Windows.Data.Pdf.PdfDocument])
for ($pageIndex = 0; $pageIndex -lt $pdf.PageCount; $pageIndex++) {
    $pdfPage = $pdf.GetPage($pageIndex)
    $stream = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
    $options = New-Object Windows.Data.Pdf.PdfPageRenderOptions
    $options.DestinationWidth = 1190
    $task = $actionAsTask.Invoke($null, @($pdfPage.RenderToStreamAsync($stream, $options)))
    $task.GetAwaiter().GetResult()
    $reader = [Windows.Storage.Streams.DataReader]::FromStream($stream.GetInputStreamAt(0))
    $null = Wait-Result ($reader.LoadAsync([uint32]$stream.Size)) ([uint32])
    $bytes = New-Object byte[] ([int]$stream.Size)
    $reader.ReadBytes($bytes)
    $imagePath = Join-Path $qaDir ('page-' + ($pageIndex + 1) + '.png')
    [System.IO.File]::WriteAllBytes($imagePath, $bytes)
    Write-Output $imagePath
    $reader.Dispose()
    $stream.Dispose()
    $pdfPage.Dispose()
}
