# VideoMind API 速查（skill 参考）

本 skill 通过 `videomind` CLI 调用 VideoMind HTTP API。以下为接口与字段速查，
完整面向用户的文档见仓库根目录 `README.md`。

## 认证

请求头：`Authorization: Bearer vw_<API Key>`。CLI 已自动携带。

## 关键端点

| 方法 | 路径 | 说明 |
| :--- | :--- | :--- |
| POST | `/api/v1/jobs` | 创建理解任务 |
| POST | `/api/v1/uploads` | multipart 上传本地视频（默认 500 MiB） |
| GET | `/api/v1/jobs/{id}` | 查询状态/进度 |
| GET | `/api/v1/jobs` | 历史列表（`?limit=`）|
| GET | `/api/v1/jobs/{id}/result` | 元数据 + 产物链接 |
| GET | `/api/v1/jobs/{id}/result.md` | Markdown 笔记 |
| GET | `/api/v1/jobs/{id}/result.json` | 结构化 JSON |
| GET | `/api/v1/jobs/{id}/result.html` | teaching_html 网页讲义 |
| POST | `/api/v1/jobs/{id}/rerender` | 切换模式重渲（不重跑 AI）|

## 提交任务请求体

```json
{
  "input":   {"type": "bilibili_url", "url": "https://www.bilibili.com/video/BV..."},
  "output":  {"mode": "study_note", "formats": ["json", "markdown"]},
  "options": {"show_source": true, "language": "zh-CN"}
}
```

- `input.type`：`bilibili_url`（带 `url`）或 `upload`（带 `file_id`）
- `output.mode`：`study_note` / `article` / `cards` / `teaching_html`
- `options` 只允许 `show_source` / `language`；上游 URL、Key、模型、时长和理解模式由服务端拥有。

已登录任务的状态、结果和产物只对任务所有者开放；访客任务是随机 `job_id` bearer link，访客不能 rerender。上传超限返回 `413` 并清理残片，已认证上传的 `file_id` 不能跨用户使用。队列上限为访客 10、单用户 20、全站 200，触顶返回 `429`。

## 任务状态机

`queued`（排队）→ `running`（处理中，含分段 `segment_done/segment_total`）→ `succeeded` / `failed`

## result.json 字段（canonical）

```
summary     主旨摘要（200–500 字）
chapters    章节 [{id,title,start_time,end_time,summary}]
claims      核心观点 [{id,text,type,importance}]
methods     方法/步骤 [{id,name,description,steps[]}]
examples    案例 [{id,title,description}]
actions     行动建议 [{id,item,priority}]
evidence    证据 [{id,timestamp,quote_or_visual_clue}]
source      来源 {title,uploader,duration_sec,source_url,language}
```

## 配额

| 身份 | 并发 |
| :--- | :--- |
| guest | 1（全站共享）|
| user | 2 |
| vip | 4 |
| 全站硬上限 | 4 |

满载时新任务进入 `queued` 排队，无需重提。
