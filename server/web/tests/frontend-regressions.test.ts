// @vitest-environment jsdom

import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/utils/api'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/utils/api', () => ({
  API_BASE: 'http://localhost',
  api: vi.fn(),
}))

const readSource = (relativePath: string) =>
  readFileSync(resolve(process.cwd(), relativePath), 'utf8')

describe('safe rich-text rendering', () => {
  it('removes executable markup while preserving ordinary Markdown', async () => {
    const helperPath = resolve(process.cwd(), 'src/utils/safeMarkdown.ts')
    const helperUrl = pathToFileURL(helperPath)
    const helperExists = existsSync(helperPath)

    expect(helperExists, 'a shared Markdown sanitizer must exist').toBe(true)
    if (!helperExists) return

    const { renderSafeMarkdown, renderSandboxedHtml } = await import(
      /* @vite-ignore */ helperUrl.href
    )
    const rendered = renderSafeMarkdown(`
# Safe heading
<script>globalThis.compromised = true</script>
<img src=x onerror="globalThis.compromised = true">
[unsafe link](javascript:alert(1))
<iframe srcdoc="<script>alert(1)</script>"></iframe>
<svg><a xlink:href="javascript:alert(1)"><text>unsafe</text></a></svg>
`)

    expect(rendered).toContain('<h1>Safe heading</h1>')
    expect(rendered).not.toMatch(/<script|onerror\s*=|href\s*=\s*['"]javascript:|<iframe|<svg/i)

    const preview = renderSandboxedHtml(`
      <html><body onload="globalThis.compromised = true">
        <h1>Teaching notes</h1><script>alert(1)</script>
      </body></html>
    `)
    expect(preview).toContain('Teaching notes')
    expect(preview).toContain('Content-Security-Policy')
    expect(preview).not.toMatch(/<script|onload\s*=/i)
  })

  it.each(['src/views/Workbench.vue', 'src/views/Docs.vue'])(
    '%s renders only through the shared sanitizer',
    (componentPath) => {
      const source = readSource(componentPath)

      expect(source).toMatch(
        /import\s+\{[^}]*renderSafeMarkdown[^}]*\}\s+from\s+['"]@\/utils\/safeMarkdown['"]/,
      )
      expect(source).toMatch(/computed\(\(\)\s*=>\s*renderSafeMarkdown\(/)
      expect(source).not.toMatch(
        /import\s+\{\s*marked\s*\}\s+from\s+['"]marked['"]/,
      )
    },
  )

  it('previews teaching HTML in an inert sandbox instead of opening it as same-origin HTML', () => {
    const workbench = readSource('src/views/Workbench.vue')

    expect(workbench).toMatch(/<iframe[^>]*sandbox[^>]*:srcdoc="teachingHtmlPreview"/s)
    expect(workbench).toContain('renderSandboxedHtml')
    expect(workbench).not.toMatch(/window\.open\([^)]*result\.html/)
  })
})

describe('theme contract', () => {
  it('uses one explicit light theme across Naive UI and browser-native controls', () => {
    const app = readSource('src/App.vue')
    const styles = readSource('src/style.css')

    expect(app).toContain(':theme="appTheme"')
    expect(app).toContain("import { lightTheme as appTheme } from 'naive-ui'")
    expect(styles).toMatch(/:root\s*\{[^}]*color-scheme:\s*light;/s)
  })
})

describe('service URL contract', () => {
  it('defaults local development to the loopback backend and derives production from origin', () => {
    const docs = readSource('src/views/Docs.vue')
    const vite = readSource('vite.config.ts')

    // 本地开发回退到本机后端，生产用当前 origin
    expect(docs).toContain("const localServiceUrl = 'http://127.0.0.1:8000'")
    expect(docs).toContain('window.location.origin')
    // 开发代理指向本机后端，且可用环境变量覆盖
    expect(vite).toContain("'http://127.0.0.1:8000'")
    expect(vite).toContain('VITE_API_PROXY')
  })
})

describe('responsive overflow boundaries', () => {
  it('lets the mobile navbar wrap and scroll its links locally', () => {
    const app = readSource('src/App.vue')
    const mobileCss = app.slice(app.indexOf('@media (max-width: 760px)'))

    expect(mobileCss).toMatch(/\.navbar\s*\{[^}]*height:\s*auto;/s)
    expect(mobileCss).toMatch(/\.navbar\s*\{[^}]*flex-wrap:\s*wrap;/s)
    expect(mobileCss).toMatch(/\.navbar-left[^}]*min-width:\s*0;/s)
    expect(mobileCss).toMatch(/\.nav-links\s*\{[^}]*overflow-x:\s*auto;/s)
    expect(app).not.toContain('.server-status,.quota-badge { display:none }')
    expect(mobileCss).toMatch(/\.server-status\s*\{[^}]*font-size:\s*0\.75rem;?/s)
  })

  it('keeps the history table scroll inside its card on narrow screens', () => {
    const history = readSource('src/views/History.vue')

    expect(history).toMatch(/<n-data-table[^>]*:scroll-x="960"/s)
    expect(history).toMatch(/@media\s*\(max-width:\s*640px\)[\s\S]*?\.header-banner\s*\{[^}]*flex-direction:\s*column;/)
  })

  it('contains long documentation tables and code blocks', () => {
    const docs = readSource('src/views/Docs.vue')

    expect(docs).toMatch(/\.markdown-body\s*\{[^}]*overflow-wrap:\s*anywhere;?/s)
    expect(docs).toMatch(/:deep\(table\)\s*\{[^}]*display:\s*block;[^}]*overflow-x:\s*auto;/s)
    expect(docs).toMatch(/@media\s*\(max-width:\s*640px\)[\s\S]*?\.header-section\s*\{[^}]*flex-direction:\s*column;/)
  })
})

describe('document and form metadata', () => {
  it('uses a branded Chinese document title and browser autocomplete hints', () => {
    const html = readSource('index.html')
    const login = readSource('src/views/Login.vue')

    expect(html).toContain('<html lang="zh-CN">')
    expect(html).toContain('<title>VideoMind | AI 视频理解工作台</title>')
    expect(login).toContain("autocomplete:'email'")
    expect(login).toContain("'current-password':'new-password'")
    expect(login).toContain("autocomplete:'one-time-code'")
  })
})

describe('runtime state handling', () => {
  it('stops polling after repeated API failures instead of swallowing errors forever', () => {
    const workbench = readSource('src/views/Workbench.vue')
    const pollingBlock = workbench.slice(
      workbench.indexOf('const checkJobStatus ='),
      workbench.indexOf('const fetchResult ='),
    )

    expect(workbench).toContain('pollFailureCount')
    expect(pollingBlock).toMatch(/const res = await api[\s\S]*?pollFailureCount\.value\s*=\s*0/)
    expect(pollingBlock).toMatch(/catch(?:\s*\([^)]*\))?\s*\{[\s\S]*?pollFailureCount\.value\s*\+=\s*1/)
    expect(pollingBlock).toMatch(/pollFailureCount\.value\s*>=\s*(?:MAX_POLL_FAILURES|3)/)
    expect(pollingBlock).toContain("status.value = 'failed'")
    expect(pollingBlock).toContain('stopPolling()')
    expect(pollingBlock).toContain('pollGeneration')
    expect(pollingBlock).not.toContain('setInterval')
    expect(workbench).toMatch(/const stopPolling\s*=\s*\(\)\s*=>\s*\{[\s\S]*?pollTimer\s*=\s*null[\s\S]*?\n\}/)
  })

  it('clears prior input state when creating a new task', () => {
    const workbench = readSource('src/views/Workbench.vue')
    const resetBlock = workbench.slice(
      workbench.indexOf('const reset ='),
      workbench.indexOf('watch(()=>route.query.jobId'),
    )

    expect(resetBlock).toContain("bilibiliUrl.value=''")
    expect(resetBlock).toContain("fileId.value=''")
    expect(resetBlock).toContain("outputMode.value='study_note'")
    expect(resetBlock).toContain('stopPolling()')
    expect(resetBlock).toContain('pollFailureCount.value=0')
    expect(resetBlock).toContain('htmlPreviewVisible.value=false')
    expect(resetBlock).toContain('htmlPreviewLoading.value=false')
    expect(resetBlock).toContain("teachingHtmlPreview.value=''")
  })

  it('derives the engine badge from the actual health request', () => {
    const app = readSource('src/App.vue')
    const auth = readSource('src/stores/auth.ts')

    expect(auth).toContain('healthStatus')
    expect(auth).toContain("healthStatus.value = 'ready'")
    expect(auth).toContain("healthStatus.value = 'unavailable'")
    expect(auth).toContain('healthRequestId')
    expect(app).toContain('authStore.healthStatus')
    expect(app).not.toContain('<span class="status-text">引擎就绪</span>')
    expect(app).toContain('引擎检测中')
    expect(app).toContain('引擎不可用')
  })
})

describe('auth health state', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.mocked(api).mockReset()
    setActivePinia(createPinia())
  })

  it('recovers from unavailable to ready after a later successful health request', async () => {
    const authStore = useAuthStore()
    expect(authStore.healthStatus).toBe('checking')

    vi.mocked(api).mockRejectedValueOnce(new Error('offline'))
    await authStore.refreshMe()
    expect(authStore.healthStatus).toBe('unavailable')

    vi.mocked(api).mockResolvedValueOnce({
      quota: { tier: 'guest', running: 0, limit: 1, global_running: 0, global_limit: 4 },
      worker_count: 2,
    })
    await authStore.refreshMe()
    expect(authStore.healthStatus).toBe('ready')
  })
})
