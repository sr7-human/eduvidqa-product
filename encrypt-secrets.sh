#!/usr/bin/env bash
# Encrypt local secret files using AES-256-CBC + PBKDF2 (100k iterations).
# A native macOS password popup will appear — type your passphrase there.
# Requires: openssl (preinstalled on macOS / available via Homebrew).
set -euo pipefail
cd "$(dirname "$0")"

FILES=(
  ".env"
  "frontend/.env"
  "frontend/.env.local"
  "SECRETS_STATUS.md"
)

EXISTING=()
for f in "${FILES[@]}"; do
  [[ -f "$f" ]] && EXISTING+=("$f")
done

if [[ ${#EXISTING[@]} -eq 0 ]]; then
  echo "No raw secret files found locally. Nothing to encrypt."
  exit 0
fi

echo "Will encrypt these files:"
printf '  %s\n' "${EXISTING[@]}"
echo ""
echo "A macOS password dialog should pop up. Type your passphrase there."

PASS=$(osascript <<'OSA' 2>/dev/null
display dialog "Enter encryption passphrase:" default answer "" with hidden answer with title "Encrypt secrets" buttons {"Cancel","OK"} default button "OK"
text returned of result
OSA
)

if [[ -z "${PASS:-}" ]]; then
  echo "Cancelled (no passphrase entered)."
  exit 1
fi

CONFIRM=$(osascript <<'OSA' 2>/dev/null
display dialog "Confirm passphrase:" default answer "" with hidden answer with title "Encrypt secrets" buttons {"Cancel","OK"} default button "OK"
text returned of result
OSA
)

if [[ "${PASS}" != "${CONFIRM:-}" ]]; then
  echo "Passphrases do not match. Nothing encrypted."
  exit 1
fi

PASSFILE=$(mktemp)
chmod 600 "$PASSFILE"
trap 'rm -f "$PASSFILE"' EXIT INT TERM
printf '%s' "$PASS" > "$PASSFILE"

for f in "${EXISTING[@]}"; do
  out="$f.enc"
  echo ">> Encrypting: $f  ->  $out"
  openssl enc -aes-256-cbc -salt -pbkdf2 -iter 100000 \
    -pass file:"$PASSFILE" \
    -in "$f" -out "$out"
done

echo ""
echo "Done. Commit the .enc files:"
echo "  git add *.enc frontend/*.enc encrypt-secrets.sh decrypt-secrets.sh"
echo "  git commit -m 'Update encrypted secrets'"
echo "  git push"
