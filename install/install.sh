#!/bin/sh
# UNSUPPORTED PUBLIC INSTALLATION.
# This script is only for an isolated local/CI Stage 1 prerelease fixture.

set -eu

show_usage() {
    cat <<'EOF'
UNSUPPORTED PUBLIC INSTALLATION

This bootstrap is only for an isolated local/CI Stage 1 prerelease fixture.
It requires an explicit absolute bootstrap Python, local wheel, local pinned
uv artifact, fixture root, and toolchain file. It never installs from a public
package channel and does not modify PATH, profiles, projects, or host state.

Usage:
  install.sh --bootstrap-python <absolute-python> install <helper-options>
  install.sh --bootstrap-python <absolute-python> uninstall --fixture-root <root>
  install.sh --bootstrap-python <absolute-python> console-oracle --fixture-root <root>

Run the helper with --help after --bootstrap-python for full bounded options.
EOF
}

if [ "$#" -eq 0 ]; then
    show_usage
    exit 0
fi

for argument in "$@"; do
    if [ "$argument" = "--help" ] || [ "$argument" = "-h" ]; then
        show_usage
        exit 0
    fi
done

if [ "$#" -lt 3 ] || [ "$1" != "--bootstrap-python" ]; then
    printf '%s\n' \
        "--bootstrap-python must be the first option and have one value." >&2
    exit 2
fi
bootstrap_python=$2
shift 2

case "$bootstrap_python" in
    /*) ;;
    *)
        printf '%s\n' \
            "--bootstrap-python must name an explicit absolute existing file." >&2
        exit 2
        ;;
esac
if [ ! -f "$bootstrap_python" ]; then
    printf '%s\n' \
        "--bootstrap-python must name an explicit absolute existing file." >&2
    exit 2
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
helper=$script_dir/../scripts/xc_package_install.py

exec "$bootstrap_python" -I -B "$helper" "$@"
