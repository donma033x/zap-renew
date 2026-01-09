# ZAP-Hosting Lifetime VPS 保活脚本

自动登录 ZAP-Hosting 并访问 VPS 详情页，保持 Lifetime VPS 活跃。

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
# 注册地址: https://yescaptcha.com/i/p3c40o
YESCAPTCHA_API_KEY=your_api_key

# 账号配置 (格式: 邮箱:密码，多账号逗号分隔)
ACCOUNTS=user@example.com:password

# VPS 详情页停留时间 (秒)
STAY_DURATION=10

# Telegram 通知 (可选)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 获取 YesCaptcha API Key

本脚本使用 [YesCaptcha](https://yescaptcha.com/i/p3c40o) 服务自动解决 reCAPTCHA 验证码。

1. 访问 [YesCaptcha](https://yescaptcha.com/i/p3c40o) 注册账号
2. 充值余额（解决 reCAPTCHA 约 ¥0.01/次）
3. 在后台获取 API Key 填入配置文件

## 运行

```bash
xvfb-run uv run python zap_keepalive.py
```

## 定时任务

```bash
crontab -e

# 每天上午 10 点运行
0 10 * * * cd /path/to/zap-auto-login && xvfb-run /home/user/.local/bin/uv run python zap_keepalive.py >> /tmp/zap.log 2>&1
```
