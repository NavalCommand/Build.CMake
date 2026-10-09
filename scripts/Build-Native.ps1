param([Parameter(Mandatory)][string]$Source,[string]$Preset='windows-msvc-release',[string]$CMake='cmake')
$ErrorActionPreference='Stop'
# Run from a compiler developer shell. Compiler/linker selection belongs to
# the configure preset and that shell, never custom workspace env variables.
Push-Location $Source
try {
 & $CMake --build "o/$Preset" --parallel 8
 if($LASTEXITCODE){throw 'Build failed'}
 $tool=Get-Command $CMake
 $ctest=Join-Path (Split-Path $tool.Source) 'ctest.exe'
 if(!$IsWindows){$ctest=Join-Path (Split-Path $tool.Source) 'ctest'}
 & $ctest --test-dir "o/$Preset" --output-on-failure --no-tests=error
 if($LASTEXITCODE){throw 'Tests failed'}
} finally {Pop-Location}
