# ZAP-Hosting Lifetime VPS 保活脚本

自动登录 ZAP-Hosting 并访问 VPS 详情页，保持 Lifetime VPS 活跃。

## ⚠️ 免责声明

本项目仅供学习网页自动化技术使用。使用本脚本可能违反相关网站的服务条款，包括但不限于：
- 禁止使用自动化工具访问
- 禁止绕过安全验证措施（如 reCAPTCHA）

**使用本项目的风险由用户自行承担**，包括但不限于账号被封禁、服务被终止等后果。请在使用前仔细阅读相关网站的服务条款。

## 功能

- 支持多账号
- 自动登录
- 自动处理 Cloudflare 验证
- 自动解决 reCAPTCHA (YesCaptcha)
- 访问 VPS 详情页保活
- 会话持久化
- Telegram 通知

## 安装

```bash
# 安装系统依赖
sudo apt install xvfb  # Debian/Ubuntu
# sudo yum install xorg-x11-server-Xvfb  # CentOS/RHEL

# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装项目依赖
uv sync

# 安装 Playwright 浏览器
uv run playwright install chromium
```

## 配置

```bash
cp .env.example .env
vim .env
```

```env
# YesCaptcha API Key (必需，用于解决 reCAPTCHA)
YESCAPTCHA_API_KEY=your_api_key

# 账号配置 (格式: 邮箱:密码，多账号逗号分隔)
ACCOUNTS=user@example.com:password

# VPS 详情页停留时间 (秒)
STAY_DURATION=10

# Telegram 通知 (可选)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

## 运行

```bash
xvfb-run uv run python zap_keepalive.py
```

## 定时任务

由于 YesCaptcha 需要付费，建议每月运行一次即可保持 VPS 活跃。

```bash
crontab -e

# 每月 1 号上午 10 点运行
0 10 1 * * cd /path/to/zap-auto-login && xvfb-run /home/user/.local/bin/uv run python zap_keepalive.py >> /tmp/zap.log 2>&1
```

## 支持作者

本项目使用 [YesCaptcha](https://yescaptcha.com/i/p3c40o) 服务解决 reCAPTCHA 验证码。

如果你觉得这个项目有帮助，可以通过以下方式支持作者（对你没有任何额外费用）：

- **注册 YesCaptcha 时使用推荐链接**: https://yescaptcha.com/i/p3c40o

另外，代码中包含了作者的 softID (`26129`)，YesCaptcha 会给予作者少量推荐奖励。如果你介意，可以在 `zap_keepalive.py` 中搜索 `softID` 并移除。
