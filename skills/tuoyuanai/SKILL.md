---
name: tuoyuanai
description: Use TuoyuanAI to create or continue cloud creative sessions, upload reference materials, query progress, and download generated writing, images, storyboards, or authorized video and audio outputs.
---

# 拓元AI

通过拓元AI平台上的创作 Agent 完成用户需求。Python 只是 HTTP 客户端；理解需求、规划、生成和会话持久化均在服务器。不要在本地另做编排，也不需要浏览器登录态或本地 session 文件。

## 接入

本版需要平台已部署 `/openapi/` 和个人中心 Access Key 功能。它不是账号密码登录客户端；旧版网页接口不会被自动调用。

1. 用户在平台「个人中心 → Skill 接入」创建 Access Key。
2. 用户在运行环境配置 `TUOYUANAI_ACCESS_KEY`。不要要求用户把完整密钥发送到聊天，不要打印环境变量值。
3. Python 3.10+，不需要额外 Python 依赖。默认服务是 `https://tuoyuanai.com`；私有或验收环境可用 `TUOYUANAI_BASE_URL` 指定 HTTPS 地址，本机回环可使用 HTTP。

详细设置见 [authentication.md](references/authentication.md)，接口和状态见 [api.md](references/api.md)。

## 使用

以下命令在本 Skill 目录运行：

```bash
python scripts/tuoyuanai.py capabilities
python scripts/tuoyuanai.py create --message "用户的完整创作需求"
```

提交立即返回 `sessionId`、`executionId`、`request_id` 和网页地址。记住这些非秘密标识，不要把服务器返回的 ID 当作本地数据库。

```bash
python scripts/tuoyuanai.py query SESSION_ID --wait 180
python scripts/tuoyuanai.py query SESSION_ID --after-seq LAST_SEQ
python scripts/tuoyuanai.py send SESSION_ID --message "用户追加的修改需求"
python scripts/tuoyuanai.py results SESSION_ID
python scripts/tuoyuanai.py download SESSION_ID --node-id NODE_ID --output-dir ./outputs
```

- 首次请求可仅 `create` 创建空会话，然后上传参考图或文档，再 `send`。
- 使用 `--message-file` 传入 UTF-8 长文本，与 `--message` 二选一。
- 服务端决定任务是否完成；`queued`、`running`、`waiting` 都不是完成。`waiting_user` 表示需补充信息或下一步选择，`blocked` / `canceled` 不得报告成功。
- `query --wait` 只轮询读取，超时或退出客户端不会中止后台执行。不要把本地进程存活当作生成条件。
- `nextSeq` 是下次 `--after-seq` 的游标；`hasMore` 为真时继续获取下一页。游标属于当前会话，不要混用。
- `results` 读取当前画布；选择真实节点 ID 下载，不从聊天文字中猜测下载 URL。
- 网页可查看 Skill 对话、停止执行、编辑画布；继续聊天通过 Skill。客户端不能覆盖服务器聊天记录。

## 素材与生成授权

```bash
python scripts/tuoyuanai.py create
python scripts/tuoyuanai.py upload SESSION_ID ./reference.png
python scripts/tuoyuanai.py send SESSION_ID --message "用户的创作需求" --attachment-id ATTACHMENT_ID
```

文件上传本身不代表授权生成媒体。默认请求只允许文字和规划。

只有用户明确要求相应媒体生成，且密钥已启用媒体权限时，才加 `--allow-media`。用户只要求图片，不得扩大为视频或音频；素材可用不等于可以付费生成。不要为了展示效果擅自提交付费生成。

如用户指定模型、比例、时长或创作方式，先读取 capabilities，再通过 `--settings-json` 使用当前平台支持的字段。不要自行固定模型、镜头数量、分板或时长。服务端 Agent 执行创意规划。

## 失败与中断

- 每次提交前会输出请求 UUID；也可通过 `--request-id` 明确指定。网络中断后先查询已知会话。若受理回执未知，只能用同一个 UUID 和原请求正文查回原受理结果，不能生成新 UUID 盲目重做。
- 同 UUID 不同正文会被拒绝；同会话有活动执行时新消息会被拒绝。不要绕过这些约束。
- 脚本不会自动重试写请求或切换旧接口。鉴权、余额、附件、模型或服务错误要如实告知。
- `stop SESSION_ID` 是显式停止目标；已经提交的媒体任务不会重复发起，也不保证外部付费任务能撤回。
- 下载使用独占创建，不覆盖已有文件。上传中断可用回执中的 `upload_id` 调用 `cancel-upload`。
- 密钥不写入文件、不输出；下载对象存储时不发送 Access Key，重定向也不会携带凭据。
