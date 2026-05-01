/**
 * Normalize LLM-emitted LaTeX so KaTeX can render it.
 *
 * LLMs (especially Gemini) emit math with several non-standard delimiters:
 *   - `\(...\)` and `\[...\]` (LaTeX-style) → convert to `$...$` and `$$...$$`
 *   - `$...$` already works with remark-math (we keep as-is)
 *   - `\\frac{...}{...}` (escaped backslashes) → strip extra backslash
 *
 * Also fixes the case where the LLM writes `$\sqrt{...}$` correctly but the
 * surrounding markdown swallows the leading `\` (becomes `$sqrt{...}$`).
 */
export function normalizeMath(input: string): string {
  if (!input) return input;
  let s = input;

  // Convert \( ... \) → $ ... $
  s = s.replace(/\\\(/g, '$').replace(/\\\)/g, '$');
  // Convert \[ ... \] → $$ ... $$
  s = s.replace(/\\\[/g, '$$').replace(/\\\]/g, '$$');

  // Some LLM outputs double-escape backslashes inside $...$ blocks (e.g. `$\\frac{a}{b}$`).
  // Collapse `\\` to `\` ONLY inside math delimiters so prose backslashes are untouched.
  s = s.replace(/\$\$([\s\S]*?)\$\$/g, (_m, body) => `$$${body.replace(/\\\\/g, '\\')}$$`);
  s = s.replace(/(?<!\$)\$([^$\n]+?)\$(?!\$)/g, (_m, body) => `$${body.replace(/\\\\/g, '\\')}$`);

  return s;
}
