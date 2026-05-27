/**
 * Lightweight markdown stripper for inline previews (TaskCard descriptions,
 * memory snippets, etc.). Removes the most common syntax markers without
 * pulling in a full parser. The goal is "looks like plain text in a small
 * preview" — not perfect rendering.
 */
const PATTERNS: Array<[RegExp, string]> = [
  // Code fences (multiline) → keep contents on a single line.
  [/```[\s\S]*?```/g, ' '],
  // Inline code: `foo` → foo.
  [/`([^`]*)`/g, '$1'],
  // Images: ![alt](url) → alt.
  [/!\[([^\]]*)\]\([^)]*\)/g, '$1'],
  // Links: [text](url) → text.
  [/\[([^\]]+)\]\([^)]*\)/g, '$1'],
  // Headings, blockquotes, list bullets at line start.
  [/^\s{0,3}#{1,6}\s+/gm, ''],
  [/^\s{0,3}>+\s?/gm, ''],
  [/^\s*[-*+]\s+/gm, ''],
  [/^\s*\d+\.\s+/gm, ''],
  // Horizontal rules.
  [/^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/gm, ''],
  // Bold/italic markers (run twice so **bold _italic_** also collapses).
  [/(\*\*|__)(.*?)\1/g, '$2'],
  [/(\*|_)(.*?)\1/g, '$2'],
  // Strikethrough.
  [/~~(.*?)~~/g, '$1'],
  // Stray HTML tags.
  [/<\/?[^>]+>/g, ' '],
]

export function stripMarkdown(input: string | null | undefined): string {
  if (!input) return ''
  let out = input
  for (const [pattern, replacement] of PATTERNS) {
    out = out.replace(pattern, replacement)
  }
  return out.replace(/\s+/g, ' ').trim()
}
