import DOMPurify from 'dompurify'
import { marked } from 'marked'

const executableTags = [
  'base',
  'button',
  'embed',
  'form',
  'iframe',
  'input',
  'object',
  'option',
  'script',
  'select',
  'textarea',
]

export function renderSafeMarkdown(markdown: string): string {
  const rendered = marked.parse(markdown, { async: false }) as string

  return DOMPurify.sanitize(rendered, {
    USE_PROFILES: { html: true },
    FORBID_TAGS: [...executableTags, 'style'],
    FORBID_ATTR: ['srcdoc', 'style'],
    ALLOW_DATA_ATTR: false,
  })
}

export function renderSandboxedHtml(html: string): string {
  const sanitized = DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
    FORBID_TAGS: executableTags,
    FORBID_ATTR: ['srcdoc'],
    ALLOW_DATA_ATTR: false,
  })
  const policy = [
    "default-src 'none'",
    "img-src data: blob: https: http:",
    "media-src data: blob: https: http:",
    "font-src data: https: http:",
    "style-src 'unsafe-inline'",
    "connect-src 'none'",
    "frame-src 'none'",
    "form-action 'none'",
    "base-uri 'none'",
  ].join('; ')

  return `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="${policy}"></head><body>${sanitized}</body></html>`
}
