#!/usr/bin/env bash
# Build the .mkp from the sources in this repository.
#
# Must run as the site user on a Checkmk 2.5 site: the packager reads the
# files from the site's local/ tree, so the sources are copied there first.
#
#   ./scripts/build.sh            # deploy sources + build n8n-<VERSION>.mkp
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d '[:space:]' < "$REPO/VERSION")"

if [ -z "${OMD_ROOT:-}" ]; then
    echo "error: run this as the Checkmk site user (OMD_ROOT is unset)" >&2
    exit 1
fi

PLUGINS="$OMD_ROOT/local/lib/python3/cmk_addons/plugins"
MANIFEST="$OMD_ROOT/tmp/n8n_manifest"

echo "==> deploying sources to $PLUGINS/n8n_cmk"
find "$PLUGINS/n8n_cmk" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
mkdir -p "$PLUGINS"
cp -r "$REPO/n8n_cmk" "$PLUGINS/"
chmod +x "$PLUGINS/n8n_cmk/libexec/agent_n8n_monitor"

echo "==> compiling"
python3 -m compileall -q "$PLUGINS/n8n_cmk"

echo "==> writing manifest for version $VERSION"
sed "s/'version': '[^']*'/'version': '$VERSION'/" \
    "$REPO/packaging/manifest.template" > "$MANIFEST"

echo "==> packaging"
mkp package "$MANIFEST"
rm -f "$MANIFEST"

echo "==> installed packages"
mkp list | grep -E '^n8n\b' || true

cat <<MSG

Built and enabled n8n $VERSION.
The MKP is at: $OMD_ROOT/var/check_mk/packages_local/n8n-$VERSION.mkp

Remaining steps:
  mkp disable n8n <old-version> && mkp remove n8n <old-version>
  cmk -II <host> && cmk -R
MSG
