<template>
  <div class="docs-view">
    <Card3D :max-tilt="1">
      <n-card class="view-card" :bordered="false">
        <div class="header-section">
          <div class="title-box"><h1>开发者 API 文档</h1><p class="muted">了解解码引擎的每一道工序与接口，让知识结晶可被编程调用</p></div>
          <n-button type="success" secondary size="medium" @click="downloadDocs">
            <template #icon><svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg></template>下载 API 文档 (.md)
          </n-button>
        </div>
        <div class="markdown-body" v-html="renderedDocs"></div>
      </n-card>
    </Card3D>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { renderSafeMarkdown } from '@/utils/safeMarkdown'
import { useMessage } from 'naive-ui'
import Card3D from '@/components/Card3D.vue'

const message = useMessage()
// 本地开发时示例指向本机后端；生产环境自动使用当前访问的 origin
const localServiceUrl = 'http://127.0.0.1:8000'
const currentOrigin = typeof window !== 'undefined' ? window.location.origin : localServiceUrl
const serviceUrl = currentOrigin.includes('localhost') || currentOrigin.includes('127.0.0.1') ? localServiceUrl : currentOrigin

const docsContent = `
## 服务基础地址 (Base URL)
* **当前服务根地址**: \`${serviceUrl}\`
* **API 接口前缀**: \`/api/v1\`
* 建议生产环境通过 HTTPS 域名访问；HTTP 入口应重定向到 HTTPS。

---
## 认证机制 (Authentication)
所有受保护的接口需在 HTTP 请求头中携带 Token 凭证：
* **JWT (用户登录凭证)**: \`Authorization: Bearer <access_token>\`
* **API Key (长期开发者凭证)**: \`Authorization: Bearer vw_xxxxxxxx\`

### 当前登录/注册规则
* **密码登录**：已注册用户使用 \`邮箱 + 密码\`
* **验证码登录**：**仅已注册用户** 使用 \`邮箱 + 验证码\`
* **注册账号**：新用户使用 \`邮箱 + 密码 + 验证码\`
* **找回密码**：使用 \`邮箱 + 验证码 + 新密码\`
* **游客访问**：可提交任务，但只有随机 \`job_id\` bearer link 能读取该访客任务；访客不能重渲。

### 任务所有权
* 已登录用户的状态、结果元数据、JSON/Markdown/HTML 产物只对任务所有者开放。
* 其他用户或访客访问已登录用户任务返回 \`403\`。
* \`GET /jobs/{id}\` 的 \`job_id\` 会做格式校验，路径穿越形式返回 \`400\`。

---
## 快速 cURL 集成示例
### 1. 注册账号
\`\`\`bash
curl -X POST "${serviceUrl}/api/v1/auth/request-code" -H "Content-Type: application/json" -d '{"email":"newuser@example.com","purpose":"register"}'
curl -X POST "${serviceUrl}/api/v1/auth/register" -H "Content-Type: application/json" -d '{"email":"newuser@example.com","password":"StrongPass123!","code":"123456"}'
\`\`\`
### 2. 已注册用户登录
\`\`\`bash
# 密码登录
curl -X POST "${serviceUrl}/api/v1/auth/login-password" -H "Content-Type: application/json" -d '{"email":"newuser@example.com","password":"StrongPass123!"}'
# 验证码登录
curl -X POST "${serviceUrl}/api/v1/auth/request-code" -H "Content-Type: application/json" -d '{"email":"newuser@example.com","purpose":"login"}'
curl -X POST "${serviceUrl}/api/v1/auth/verify" -H "Content-Type: application/json" -d '{"email":"newuser@example.com","code":"123456"}'
\`\`\`
### 3. 提交视频理解任务
\`\`\`bash
curl -X POST "${serviceUrl}/api/v1/jobs" -H "Authorization: Bearer vw_xxxx" -H "Content-Type: application/json" -d '{"input":{"type":"bilibili_url","url":"https://www.bilibili.com/video/BVxxx"},"output":{"mode":"study_note","formats":["json","markdown"]},"options":{"show_source":true}}'
\`\`\`
### 4. 轮询任务状态
\`\`\`bash
curl "${serviceUrl}/api/v1/jobs/{job_id}" -H "Authorization: Bearer vw_xxxx"
\`\`\`

### 客户端参数边界
\`options\` 只允许 \`show_source\` 和 \`language\`。\`api_url\`、\`api_key\`、\`model\`、\`max_duration_sec\`、\`understand_mode\` 由服务端拥有，提交会返回 \`422\`，也不会落库。

---
## 完整 API 接口清单
| HTTP 方法 | 接口路径 | 鉴权要求 | 接口说明 |
| :--- | :--- | :--- | :--- |
| **GET** | \`/api/v1/health\` | 公开 | 服务健康状态与当前配额快照 |
| **POST** | \`/api/v1/auth/request-code\` | 公开 | 发送验证码（\`purpose=login/register/reset_password\`） |
| **POST** | \`/api/v1/auth/verify\` | 公开 | **已注册用户** 校验登录验证码并获取 JWT |
| **POST** | \`/api/v1/auth/register\` | 公开 | 新用户：邮箱 + 密码 + 验证码注册并直接获取 JWT |
| **POST** | \`/api/v1/auth/login-password\` | 公开 | 已注册用户：邮箱 + 密码登录 |
| **POST** | \`/api/v1/auth/reset-password\` | 公开 | 使用邮箱验证码重置密码 |
| **GET** | \`/api/v1/auth/me\` | 需登录 | 获取当前登录用户及 Key 绑定信息 |
| **POST** | \`/api/v1/uploads\` | 需登录/访客 | multipart 本地视频上传 |
| **POST** | \`/api/v1/jobs\` | 需登录/访客 | 提交新视频理解任务入队 |
| **GET** | \`/api/v1/jobs\` | 需登录 | 获取历史任务列表 (\`?limit=30\`) |
| **GET** | \`/api/v1/jobs/{id}\` | 需登录/访客 | 查询任务状态与进度 |
| **GET** | \`/api/v1/jobs/{id}/result\` | 需登录/访客 | 获取任务交付产物链接 |
| **GET** | \`/api/v1/jobs/{id}/result.json\` | 任务所有者/访客 bearer link | 下载 Canonical 结构化 JSON |
| **GET** | \`/api/v1/jobs/{id}/result.md\` | 任务所有者/访客 bearer link | 下载 Markdown 笔记 |
| **GET** | \`/api/v1/jobs/{id}/result.html\` | 任务所有者/访客 bearer link | 下载网页教学讲义 HTML；响应带 CSP sandbox |
| **POST** | \`/api/v1/jobs/{id}/rerender\` | 已认证任务所有者 | 不消耗 AI 额度，本地快速重渲输出模式 |
| **POST** | \`/api/v1/api-keys\` | 需登录 | 创建新 API Key |
| **GET** | \`/api/v1/api-keys\` | 需登录 | 列出 API Key |
| **DELETE** | \`/api/v1/api-keys/{id}\` | 需登录 | 禁用指定 API Key |

---
## 配额与并发控制规则
- **访客 (Guest)**: 全局共享 1 个并发槽位
- **注册用户 (User)**: 单人独享 2 个并发槽位
- **VIP 用户 (VIP)**: 单人独享 4 个并发槽位
- **全站硬上限**: 4 个并发 (保护服务器 CPU 与内存)
- **排队上限**: 访客 10、单用户 20、全站 200；触顶返回 \`429\`
- **长视频切分**: 单视频最大支持 **4 小时**，后台按分段自动调度处理

## 上传边界
* 后端分块写入，默认上限 500 MiB；超过返回 \`413\` 并删除残片。
* 上传会登记 \`UploadRow\`。已登录文件只能由同一用户创建任务；未登记旧文件不能复用。
* 访客没有稳定身份，访客 \`file_id\` 是随机 bearer token，请勿泄露。
`
const renderedDocs = computed(() => renderSafeMarkdown(docsContent))
const downloadDocs = () => { try { const blob=new Blob([docsContent],{type:'text/markdown;charset=utf-8'}); const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='VideoMind_API_Documentation.md'; a.click(); URL.revokeObjectURL(a.href); message.success('API 文档已导出') } catch { message.error('下载失败') } }
</script>

<style scoped>
.docs-view { max-width:1040px;width:100%;min-width:0;margin:0 auto }
.view-card { min-width:0;padding:20px }
.header-section { display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px;padding-bottom:14px;border-bottom:1px solid var(--border-soft) }
.header-section h1 { font-size:1.5rem;font-weight:800;color:var(--text-main);margin:0 0 4px }
.muted { color:var(--text-muted);font-size:0.9rem }
.markdown-body { min-width:0;line-height:1.85;color:var(--text-main);overflow-wrap:anywhere }
.markdown-body :deep(h2) { border-bottom:1px solid var(--border-soft);padding-bottom:8px;margin-top:28px;color:var(--warning);font-size:1.35rem }
.markdown-body :deep(h3) { margin-top:22px;color:var(--emerald-deep);font-size:1.1rem }
.markdown-body :deep(code) { background:var(--emerald-soft);padding:3px 8px;border-radius:6px;font-family:monospace;color:var(--emerald-deep) }
.markdown-body :deep(pre) { max-width:100%;background:#0f2e22;padding:20px;border-radius:12px;overflow-x:auto;border:1px solid rgba(14,159,110,0.4) }
.markdown-body :deep(pre code) { background:transparent;padding:0;color:#bbf7d0 }
.markdown-body :deep(table) { display:block;width:100%;max-width:100%;overflow-x:auto;border-collapse:collapse;margin-top:16px;-webkit-overflow-scrolling:touch }
.markdown-body :deep(th),.markdown-body :deep(td) { border-bottom:1px solid var(--border-soft);padding:12px 16px;text-align:left }
.markdown-body :deep(th) { background:var(--bg-subtle);color:var(--emerald-deep);font-weight:700 }
.markdown-body :deep(a) { color:var(--emerald-deep) }
@media (max-width: 640px) {
  .view-card { padding:8px }
  .header-section { flex-direction:column;align-items:stretch;gap:16px }
  .header-section :deep(.n-button) { width:100% }
  .markdown-body :deep(pre) { padding:14px }
  .markdown-body :deep(th),.markdown-body :deep(td) { padding:10px 12px;white-space:nowrap }
}
</style>
