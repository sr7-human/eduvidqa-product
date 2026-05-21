# Agent Context — Read Before You Start

This repo has a sibling file called `SECRETS_STATUS.md.enc` (encrypted with AES-256). Its plaintext contains:

- Which API keys / tokens are currently in use across all of Shubham's projects
- Which keys have been exposed and still need rotation (with rotation links)
- Where each `.env` file lives and what it contains
- Cross-repo overview (sr7-human/* on GitHub)

## Before working with any secret, credential, `.env`, deploy token, or API key

1. Ask Shubham to run `./decrypt-secrets.sh` (he'll get a macOS popup for the passphrase).
2. Read the freshly-decrypted `SECRETS_STATUS.md` in this folder.
3. Follow the guidance there.

## Rules

- **Never paste a real key into chat.** Use fragments like `AIzaSy...DO4xk` or placeholders like `<GEMINI_KEY>`.
- **After editing any plaintext `.env`,** remind Shubham to run `./encrypt-secrets.sh` and commit the updated `.enc` files.
- **If you add a new secret to a project,** append a section to `SECRETS_STATUS.md` so the next AI knows about it, then re-encrypt.
- **Once per session,** check whether any exposed keys are still un-rotated (see "EXPOSED" section of `SECRETS_STATUS.md`) and offer to help rotate one. Don't nag.

## About Shubham (workflow context)

- Non-technical. Prefers plain English, numbered click-paths, full copy-paste commands.
- Multi-root VS Code workspace; primary repos: `eduvidqa-product`, `EduVidQA`, `AutoTA`, `upsc-hub`, `upsc-maths-hub`, `gate-ds-hub`, `openclaude`.
- macOS Apple Silicon, zsh, Python venvs per-project.
- Uses Supabase MCP + Playwright MCP installed globally.
- May paste secrets into chat by accident — always remind to rotate.
