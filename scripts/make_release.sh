#!/usr/bin/env bash
# Cria a release com os 3 zips. Erros vao para release-debug.log (commitado depois).
TAG="${1:-v1.0-sims-cc}"
export GH_TOKEN="${GITHUB_TOKEN}"
exec 2> release-debug.log
set -x

gh auth status || true
ls -la

gh release delete "$TAG" --yes 2>/dev/null || true

gh release create "$TAG" \
  "Lilith-Cloud-CC-parte1.zip" \
  "Lilith-Cloud-CC-parte2.zip" \
  "Gwen-Cloud-CC-parte1.zip" \
  --title "Lilith Cloud + Gwen - Sims & CC completo (by MizuTS4)" \
  --notes-file RELEASE_NOTES.md

RC=$?
echo "exit=$RC" > release-exit.txt
exit 0
