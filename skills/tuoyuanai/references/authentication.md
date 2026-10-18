# 登录与凭据

首版复用拓元AI现有手机号/密码登录，**不是独立、长期有效、可单独撤销的 API Key**。
登录令牌具有该账号的现有权限，受服务端有效期、账号状态与套餐限制。建议使用专用普通客户账号。
401 时重新登录，不自动保存密码、续期或重试付费请求。

需要 Python 3.10+。下列路径均从仓库根目录执行；安装后的 Agent 应使用 skill 的实际路径。

## macOS / Linux

```bash
python3 skills/tuoyuanai/scripts/tuoyuanai.py login \
  --phone YOUR_PHONE \
  --token-file "$HOME/.config/tuoyuanai/session.json"
export TUOYUANAI_TOKEN_FILE="$HOME/.config/tuoyuanai/session.json"
```

## Windows PowerShell

```powershell
python skills/tuoyuanai/scripts/tuoyuanai.py login `
  --phone YOUR_PHONE `
  --token-file "$HOME/.config/tuoyuanai/session.json"
$env:TUOYUANAI_TOKEN_FILE = "$HOME/.config/tuoyuanai/session.json"
```

密码通过终端隐藏输入，不作为命令行参数，也不打印到输出。令牌文件在 POSIX 下以 `0600`
创建；Windows 下在写入令牌前使用 `icacls` 移除继承权限并只授权当前用户。
文件以明文存储，并非操作系统密码保险箱；不要放入共享目录、仓库或同步盘。
文件必须不存在，以防意外覆盖其他登录。重新登录请使用新文件并更新环境变量；旧文件由用户自行清理。

自动化场景可以从受保护的进程环境注入 `TUOYUANAI_PASSWORD`，只用于 `login`。
不要把赋值写入 shell 历史、配置文件或 CI 日志，使用后从进程环境移除。
也可由自己的安全登录流程注入 `TUOYUANAI_ACCESS_TOKEN`；此时必须取消设置
`TUOYUANAI_TOKEN_FILE`，两者不允许同时设置。

默认访问 `https://tuoyuanai.com`。本地完整部署验收可设置
`TUOYUANAI_BASE_URL=http://127.0.0.1:PORT`；只接受 HTTPS 或 loopback HTTP，
不能包含 `/api/v1`。令牌文件绑定登录时的 origin，不能跨站点复用。

平台令牌只发给所配置 origin 的 `/api/v1` 接口；对象存储直传和结果下载不携带令牌。
客户端拒绝 HTTP 重定向。不要把 API 错误、原始请求头或带签名的素材 URL 发布到 issue。
