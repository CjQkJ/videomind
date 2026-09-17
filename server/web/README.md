# VideoMind Web

Vue 3 + TypeScript + Vite + Naive UI 前端。生产由 Nginx 托管 `dist/`，开发时 `/api` 走 Vite 代理。

## 命令

```bash
npm install
npm test       # Vitest + jsdom 回归
npm run build  # vue-tsc + Vite，生成 dist/
npm run dev    # 开发服务器，/api 默认代理到 http://127.0.0.1:8000
```

开发代理目标可用 `VITE_API_PROXY` 覆盖，例如：

```bash
VITE_API_PROXY=https://video.example.com npm run dev
```

回归覆盖 DOMPurify Markdown、教学 HTML sandbox、浅色主题契约、移动端局部横向滚动、轮询失败终止、重置状态和真实 health 状态。任何 Markdown/HTML 改动都必须继续通过净化测试。

## 安全边界

- `src/utils/safeMarkdown.ts` 是唯一富文本入口；不要直接把 `marked.parse` 结果交给 `v-html`。
- 教学讲义只能通过无权限 `iframe sandbox=""` 的 `srcdoc` 预览；不要恢复同源 `window.open(result.html)`。
- API 请求从当前 origin 发送，Token 只放在请求头；上游 Key、模型、时长等不是前端配置。
- 线上必须部署 `web/dist`。旧 `frontend/index.html` 未同步全部净化和权限合同，不能作为安全回退页面。

## 响应式约束

导航在窄屏换行并只在链接容器内滚动；历史/文档表格和代码块在自身容器内滚动，不得造成根页面横向溢出。发布前至少用 375px 和桌面宽度检查。
