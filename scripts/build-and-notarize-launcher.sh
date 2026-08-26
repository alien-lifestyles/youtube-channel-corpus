#!/usr/bin/env bash
# Build, sign, notarize, and staple Open UI.app
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/Open UI.app"
IDENTITY="Developer ID Application: Michael Reynolds (WFT74BRMPV)"
CONFIG="${CODESIGNING_CONFIG:-$HOME/Archive/2026-08-cursor-workspaces/Alien Lifestyles/shared/.codesigning-config}"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp "$ROOT/launcher/Info.plist" "$APP/Contents/Info.plist"
swiftc -O -framework AppKit -framework Security -o "$APP/Contents/MacOS/Open UI" "$ROOT/launcher/OpenUI.swift"

codesign --force --options runtime --timestamp \
  --entitlements "$ROOT/launcher/OpenUI.entitlements" \
  --sign "$IDENTITY" \
  "$APP"

echo "Signed. Submitting for notarization..."

# Do not print secrets.
set +x
if [[ -f "$CONFIG" ]]; then
  # shellcheck disable=SC1090
  source "$CONFIG"
fi
: "${APPLE_ID:?APPLE_ID missing}"
: "${APP_SPECIFIC_PASSWORD:?APP_SPECIFIC_PASSWORD missing}"
: "${TEAM_ID:?TEAM_ID missing}"

ZIP="$(mktemp -t open-ui).zip"
ditto -c -k --keepParent "$APP" "$ZIP"

xcrun notarytool submit "$ZIP" \
  --apple-id "$APPLE_ID" \
  --password "$APP_SPECIFIC_PASSWORD" \
  --team-id "$TEAM_ID" \
  --wait

rm -f "$ZIP"
xcrun stapler staple "$APP"
spctl --assess --type execute --verbose "$APP" || true
echo "Done: $APP"
