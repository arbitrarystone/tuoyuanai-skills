# 当前 API 契约

客户端复用网页端 `/api/v1`，不是另建的 OpenAPI 网关。接口采用
`{"success": true, "data": ...}` 响应；鉴权是 `Authorization: Bearer ...`。
服务端权限、积分、模型配置和租户隔离保持不变，skill 不绕过这些规则。

| CLI | 接口 |
| --- | --- |
| login / me | `POST /auth/login` / `GET /auth/me` |
| capabilities | `GET /assistant/capabilities` |
| create / list / query | `POST /assistant/sessions?force=true` / `GET /assistant/sessions` / `GET /assistant/sessions/{id}` |
| send | `PUT /assistant/sessions/{id}` 保存用户回合；`POST /assistant/chat/stream`；完成后通过带版本号的 PUT 保存回复 |
| upload | `POST /uploads`；按返回的 transport 执行 PUT；`POST /assistant/attachments` 认领 |
| attachments | `GET /assistant/attachments?session_id={id}` |
| results | 会话返回 project 的 `GET /canvas/{ref_type}/{ref_id}` |
| download | 图片 `/canvas/nodes/{id}/download`；音频 `/audio-download`；视频 `/media`；文本使用当前 body |
| stop | `POST /assistant/sessions/{id}/agent/stop` |
| cancel-upload | `DELETE /uploads/{uuid}` |

## 创作设置

用户明确选择图文或分镜视频时，可用 `send --creation-type graphic` 或
`--creation-type storyboard`；这对应请求的明确类型来源，不根据样例关键词自动路由。
未指定时服务端自行判断，必要时返回成品类型选择，请继续原会话完成选择。

`send --settings-file path.json` 只传 `CreationSettings` 对象，而非整个请求体。
支持的字段包括 `creative_method`、`llm_model`、`image_model`、`video_model`、
`aspect_ratio`、`duration_seconds`、`resolution`。以 `capabilities` 的当前返回为准，
不要把模型渠道密钥放进设置文件。未传设置时由服务端选择当前默认值和会话上下文。
自然语言创作要求仍保留在 `--message` / `--message-file` 中。

`auto_generate_media` 由 `--generate-media` 单独控制，不放在设置文件中。
它是平台现有的统一媒体开关，不是按图片/视频分别隔离的权限 scope。
仅需文字或规划时保持关闭；要求单一媒体时原样保留用户的范围，不扩展为整片制作。

## 输出与退出状态

普通读取输出一个 JSON；`send`、`upload`、`download` 输出 JSON Lines。
退出 0 表示命令正常完成，不表示所有后台生成已成功；1 表示 API/文件/协议失败，
2 表示命令参数错误，130 表示用户中断。失败详情在 stderr；没有自动网络重试。

`send` 的 SSE `done` 是本轮对话完成。`query` 的 `executions` / `agent` 和
`results` 的 `generation_runs` / 节点状态才用于判断后台进度。`query --wait` 只等待，
超时返回 `still_running=true`，不新建任务、不重复收费。

## 数据保护

会话保存使用 `expected_updated_at`，读取并保留原消息结构，仅追加当前回合。
409 不覆盖、不合并重试。一个会话同一时间只使用一个写入客户端。
当前页面和 CLI 不应同时向同一会话发送消息。

素材上传使用平台返回的地址、方法和头；上传凭据与平台登录令牌分开。
仅使用当次会话内处于 ready 状态的附件 ID。当前会话附件支持 PNG/JPG/WEBP/PDF/DOCX/TXT/MD，不支持直接上传音频或视频；
具体大小限制以服务端返回为准，客户端总上限为 100 MiB。

下载从当前画布节点读取结果，不从消息里用正则找链接，不使用 preview/poster
代替成品；文字导出已保存的正文（未运行或 done），媒体仅导出 done；
不下载 asset 类型节点或正在运行/失败节点的旧结果。导入素材也可能是图片/音频/文字节点，列表本身不等于来源证明。图片/音频仍走
平台下载权限接口。默认导出该画布所有已完成节点内容（包括已经导入为图片/音频节点的素材），若只需本次产物，请明确传
`--node-id`（可重复）。所有文件使用稳定 node ID 命名，已存在文件不会覆盖。
按顺序下载；部分失败时先前成功文件保留并已逐个输出，未完成文件删除。
结果链接可能过期，需要重新查询，不能把带签名 URL 当成永久公开链接。
