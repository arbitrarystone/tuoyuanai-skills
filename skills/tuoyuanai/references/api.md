# OpenAPI 契约

平台根地址下的 `/openapi`。所有请求使用独立 Access Key；业务成功为 `{success:true,data:...}`。错误不会被当作成功或切到其他接口。

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/capabilities` | 当前渠道可用能力与模型 |
| POST | `/session` | 创建空会话，或创建／继续一次后台执行 |
| GET | `/session/{id}?afterSeq=0&limit=100` | 状态和增量消息 |
| POST | `/session/{id}/stop` | 停止当前目标 |
| GET | `/session/{id}/results` | 当前画布节点及生成状态 |
| GET | `/session/{id}/nodes/{node_id}/download` | 当前节点下载地址 |
| GET | `/session/{id}/attachments` | 当前会话附件 |
| POST | `/uploads` | 申请会话附件上传 |
| PUT | `/uploads/{id}/content` | 本地存储文件传输，仅在服务端指定时使用 |
| DELETE | `/uploads/{id}` | 取消未完成的上传 |
| POST | `/attachments` | 确认附件并绑定会话 |

## 提交

必填 `requestId`：UUID。选填 `sessionId`、`message`、`settings`、`creationType`（graphic/storyboard）、`attachmentIds`、`allowMedia`。继续已有会话时消息不能为空。首个空请求可创建会话用于上传。

接口返回 HTTP 202 和 `sessionId`、`executionId`、`project`、`projectUrl`。空会话的 executionId 为 null。任务和消息身份在同一数据库事务中受理，HTTP 返回不需要等待模型执行。

同一用户、同一 requestId、同一正文只对应一次受理；正文不同返回 409。同会话活动执行时新请求返回 409。客户端不自动重试写请求。

## 查询

`messages` 只包含用户消息和面向用户的终态回复，不包含模型内部上下文。每条有 `seq`、`executionId`、`role`、`content`、`createdAt`。

`nextSeq` 传给下次 afterSeq；`hasMore` 表示下一页。limit 为 1–200。消息序号可以不连续，不能按数量自行加一。

`status`：idle / queued / running / waiting / waiting_user / completed / blocked / canceled。

- waiting 表示仍在等待后台工作，不是终态。
- waiting_user 表示需要用户继续；读取回复，不要报告生成已完成。
- execution 包含进度和准确的子任务状态；results 是当前画布交付内容。

## 上传与下载

上传依次申请、传输、确认。purpose 固定为 assistant_attachment，context 为 `{session_id:实际ID}`。按 prepared.transport 使用 API 上传 URL 或对象存储签名 URL；对象存储不发送 Access Key。

文本节点保存 body；媒体节点按节点下载接口返回的当前 URL 下载。只允许当前 Skill 会话的未删除节点。客户端不覆盖已有文件，下载有大小上限。

## 授权边界

普通网页登录令牌不能调用 OpenAPI；Access Key 不能调用网页账号接口。会话、上传与下载都限定为密钥所属用户及租户。跨会话附件和节点被拒绝。

网页可查看 Skill 对话、停止目标并编辑画布；网页消息保存和聊天接口不接受 Skill 会话。历史网页会话及其持久化格式不变。
