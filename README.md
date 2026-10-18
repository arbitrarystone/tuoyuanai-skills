# 拓元AI Skill

将拓元AI的创作能力接入你的 AI 助手。用自然语言发起文字、图文、分镜及经过授权的媒体创作，上传参考素材，随时查看进度和下载结果。

> **OpenAPI 预览版本**：需要平台配套的 Access Key / `/openapi/` 版本。本仓库更新不等于生产平台已经上线。未部署新接口的环境请勿安装此预览版；既有 v0.1.1 版本保持不变。

## 工作方式

**独立 Access Key → 提交请求 → 返回会话与执行 ID → 服务端执行 → 增量查询和下载。**

关闭终端不会停止后台创作。会话、消息和结果保存在平台，不依赖本地 session 文件。Skill 不保存账户密码，不持有网页登录令牌，不回写聊天记录。

## 安装

预览版本按发布标签安装：

```bash
npx skills add https://github.com/arbitrarystone/tuoyuanai-skills/tree/v0.2.0-rc.1 --skill tuoyuanai
```

也可以下载本预览版 ZIP，将 `skills/tuoyuanai` 放入你的助手支持的 Skill 目录。

## 配置

- Python 3.10 或更新版本，无第三方 Python 依赖。
- 在平台「个人中心 → Skill 接入」创建 Access Key。
- 在运行环境安全设置 `TUOYUANAI_ACCESS_KEY`，不要将密钥贴进聊天或提交到代码仓库。
- `TUOYUANAI_BASE_URL` 可设置配套平台地址，默认 `https://tuoyuanai.com`。非本机地址要求 HTTPS。
- 密钥默认仅允许文字与规划。需要媒体生成时，创建密钥时启用相应权限，并对本次生成明确授权。

配置细节：[认证](skills/tuoyuanai/references/authentication.md)。

## 示例

在 `skills/tuoyuanai` 目录：

```bash
python scripts/tuoyuanai.py capabilities
python scripts/tuoyuanai.py create --message "写一段介绍城市夜景的短文，只要文字"
python scripts/tuoyuanai.py query SESSION_ID --wait 180
python scripts/tuoyuanai.py send SESSION_ID --message "把结尾改得简洁一些"
python scripts/tuoyuanai.py results SESSION_ID
python scripts/tuoyuanai.py download SESSION_ID --node-id NODE_ID --output-dir ./outputs
```

返回的 `sessionId` 用于后续查询与继续创作，`executionId` 标识本次执行，`project_url` 可直接打开网页。示例中的 ID 必须替换为实际回执。

### 上传参考素材

```bash
python scripts/tuoyuanai.py create
python scripts/tuoyuanai.py upload SESSION_ID ./reference.png
python scripts/tuoyuanai.py send SESSION_ID --message "根据参考图创作一张宣传图" --attachment-id ATTACHMENT_ID --allow-media
```

只有用户授权相应生成时才使用 `--allow-media`。图片授权不包含视频授权。

### 查询与停止

```bash
python scripts/tuoyuanai.py query SESSION_ID --after-seq LAST_SEQ
python scripts/tuoyuanai.py attachments SESSION_ID
python scripts/tuoyuanai.py stop SESSION_ID
```

查询支持游标分页。等待超时不取消服务器任务；只有实际完成状态和结果才能作为完成依据。网络中断不要用新请求 ID 重复提交付费生成。同请求 ID、同正文会返回原受理身份，不会创建第二次执行。

完整说明：[Skill](skills/tuoyuanai/SKILL.md) · [API](skills/tuoyuanai/references/api.md) · [边界](KNOWN_LIMITATIONS.md) · [安全](SECURITY.md)。

## 开源范围

本仓库采用 MIT 许可证，只包含 Skill、HTTP 客户端与文档，不包含平台私有服务端代码、服务商配置、密钥或验收账户。
