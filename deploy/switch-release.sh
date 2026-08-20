#!/bin/sh
set -eu

: "${RELEASE_ROOT:?set RELEASE_ROOT to the absolute releases directory}"
: "${RELEASE_VERSION:?set RELEASE_VERSION}"
case "$RELEASE_ROOT" in /*/releases) ;; *) echo 'RELEASE_ROOT must be an absolute releases directory' >&2; exit 1 ;; esac
case "$RELEASE_VERSION" in *[!A-Za-z0-9._-]*|'') echo 'invalid release version' >&2; exit 1 ;; esac
target="$RELEASE_ROOT/$RELEASE_VERSION"
test -d "$target" || { echo 'release directory does not exist' >&2; exit 1; }
test -f "$target/RELEASE_MANIFEST" || { echo 'release manifest is required' >&2; exit 1; }
parent="$(dirname "$RELEASE_ROOT")"
ln -sfn "$target" "$parent/current"
printf '%s\n' "active release: $RELEASE_VERSION"
