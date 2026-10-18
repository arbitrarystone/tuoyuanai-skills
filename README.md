# tuoyuanai-skills · 拓元AI

让 AI Agent 连接拓元AI：提交创作需求、上传参考素材、查看画布进展，并把完成的作品带回本地。

**开源的是轻量 skill 客户端，不是拓元AI平台服务端。** 使用服务需要自己的客户账号，
生成任务按平台当前规则计费。Python 3.10+，只使用标准库，无 Python 第三方依赖。

## 安装

```bash
npx skills add arbitrarystone/tuoyuanai-skills --skill tuoyuanai
```

也可以将 `skills/tuoyuanai` 整个目录复制到支持 Agent Skills 的工具所使用的技能目录。
安装器与兼容格式参考 [skills CLI](https://github.com/vercel-labs/skills) 和
[Agent Skills specification](https://agentskills.io/specification)。

## 首次连接

在终端交互登录，密码不进入命令参数，令牌不打印：

```bash
python3 skills/tuoyuanai/scripts/tuoyuanai.py login \
  --phone YOUR_PHONE \
  --token-file "$HOME/.config/tuoyuanai/session.json"
export TUOYUANAI_TOKEN_FILE="$HOME/.config/tuoyuanai/session.json"
```

Windows 将 `python3` 换为 `python`，环境变量使用：

```powershell
$env:TUOYUANAI_TOKEN_FILE = "$HOME/.config/tuoyuanai/session.json"
```

令牌文件请放在仓库外，且必须是新文件。默认连接 [拓元AI](https://tuoyuanai.com)。
**v0.1 使用现有账号登录令牌，不提供独立 API Key、scope 或刷新令牌。**
权限与该登录账号相同。完整安全说明见 [登录文档](skills/tuoyuanai/references/authentication.md)。

## 可以做什么

- 新建独立创作画布，继续指定会话，返回网页端可打开的画布链接。
- 发送自然语言写作、图像、分镜、视频创作需求，复用平台 Agent，不另写一套生成编排。
- 上传并关联参考素材；获取账号实际可用的模型与能力。
- 查看持久化回复、后台执行与节点状态；按需停止 Agent。
- 导出完成的文字、图片、音频或视频节点，不把预览或参考素材冒充生成结果。

默认只进行文本创作与画布规划，不提交媒体任务；文字调用也可能计费。
**真正提交图片/音频/视频生成需要明确添加 `--generate-media`。**
该开关是统一媒体授权，不是按媒体类型划分的权限；不要因请求图片而额外生成视频。

```bash
python3 skills/tuoyuanai/scripts/tuoyuanai.py capabilities
python3 skills/tuoyuanai/scripts/tuoyuanai.py create
# 下列 SESSION_ID 替换为 create 返回的整数 ID
python3 skills/tuoyuanai/scripts/tuoyuanai.py send SESSION_ID --message-file ./brief.txt
python3 skills/tuoyuanai/scripts/tuoyuanai.py query SESSION_ID --wait 180
python3 skills/tuoyuanai/scripts/tuoyuanai.py results SESSION_ID
python3 skills/tuoyuanai/scripts/tuoyuanai.py download SESSION_ID --output-dir ./output/deliverables
```

Agent 的入口是 [SKILL.md](skills/tuoyuanai/SKILL.md)，命令帮助为
`python3 skills/tuoyuanai/scripts/tuoyuanai.py --help`。
[API 契约](skills/tuoyuanai/references/api.md) 说明流式返回、失败、并发保存、费用与下载边界。

## 已知边界

请先阅读 [v0.1 已知边界](KNOWN_LIMITATIONS.md)，尤其是登录令牌权限、已有画布的素材引用，以及音视频验收范围。

## 开源边界与贡献

仅发布 skill 文档、客户端脚本和协议说明，不包含生产数据库、部署配置、验收账号、
服务端源码、提示词配置或供应商密钥。请勿把这些内容提交到 issue 或 pull request。
安全问题请见 [SECURITY.md](SECURITY.md)，贡献约定见 [CONTRIBUTING.md](CONTRIBUTING.md)。

MIT License。平台服务及其模型能力不因客户端开源而免费或获得额外授权。
