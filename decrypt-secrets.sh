#!/usr/bin/env bash
# Decrypt committed .enc secrets back into their raw files.
# A native macOS password popup will appear — type the passphrase there.
set -euo pipefail
cd "$(dirname "$0")"

FILES=(
  ".env.enc"
  "frontend/.env.enc"
  "frontend/.env.local.enc"
)

EXISTING=()
for f in "${FILES[@]}"; do
  [[ -f "$f" ]] && EXISTING+=("$f")
done

if [[ ${#EXISTING[@]} -eq 0 ]]; then
  echo "No encrypted files found. Nothing to decrypt."
  exit 0
fi

echo "Will decrypt these files:"
printf '  %s\n' "${EXISTING[@]}"
echo ""
echo "A macOS password dialog should pop up. Type your passphrase there."

PASS=$(osascript <<'OSA' 2>/dev/null
display dialog "Enter decryption passphrase:" default answer "" with hidden answer with title "Decrypt secrets" buttons {"Cancel","OK"} default button "OK"
text returned of result
OSA
)

if [[ -z "${PASS:-}" ]]; then
  echo "Cancelled."
  exit 1
fi

PASSFILE=$(mktemp)
chmod 600 "$PASSFILE"
trap 'rm -f "$PASSFILE"' EXIT INT TERM
printf '%s' "$PASS" > "$PASSFILE"

for f in "${EXISTING[@]}"; do
  out="${f%.enc}"
  echo ">> Decrypting: $f  ->  $out"
  if ! openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 \
       -pass file:"$PASSFILE" \
       -in "$f" -out "$out" 2>/dev/null; then
    echo "  FAILED — wrong passphrase or corrupted file"
    rm -f "$out"
    exit 1
  fi
done

echo ""
echo "Done. Your raw secret files are restored locally (and remain gitignored)."
