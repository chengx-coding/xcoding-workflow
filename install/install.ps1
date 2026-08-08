# UNSUPPORTED PUBLIC INSTALLATION.
# This script is only for an isolated local/CI Stage 1 prerelease fixture.

$ErrorActionPreference = "Stop"

function Show-Usage {
    @"
UNSUPPORTED PUBLIC INSTALLATION

This bootstrap is only for an isolated local/CI Stage 1 prerelease fixture.
It requires an explicit absolute bootstrap Python, local wheel, local pinned
uv artifact, fixture root, and toolchain file. It never installs from a public
package channel and does not modify PATH, profiles, projects, or host state.

Usage:
  install.ps1 --bootstrap-python <absolute-python> install <helper-options>
  install.ps1 --bootstrap-python <absolute-python> uninstall --fixture-root <root>
  install.ps1 --bootstrap-python <absolute-python> console-oracle --fixture-root <root>

Run the helper with --help after --bootstrap-python for full bounded options.
"@
}

if ($args.Count -eq 0 -or $args -contains "--help" -or $args -contains "-h") {
    Show-Usage
    exit 0
}

$bootstrapPython = $null
$forward = [System.Collections.Generic.List[string]]::new()
for ($index = 0; $index -lt $args.Count; $index++) {
    if ($args[$index] -eq "--bootstrap-python") {
        if ($null -ne $bootstrapPython -or $index + 1 -ge $args.Count) {
            [Console]::Error.WriteLine(
                "--bootstrap-python must appear exactly once with a value."
            )
            exit 2
        }
        $index++
        $bootstrapPython = $args[$index]
        continue
    }
    $forward.Add($args[$index])
}

if ([string]::IsNullOrWhiteSpace($bootstrapPython) -or
    -not [System.IO.Path]::IsPathRooted($bootstrapPython) -or
    -not [System.IO.File]::Exists($bootstrapPython)) {
    [Console]::Error.WriteLine(
        "--bootstrap-python must name an explicit absolute existing file."
    )
    exit 2
}

$helper = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot "..\scripts\xc_package_install.py")
)
& $bootstrapPython -I -B $helper @forward
exit $LASTEXITCODE
