# ZAP-Hosting Lifetime VPS 保活脚本

自动登录 ZAP-Hosting 并访问 VPS 详情页，用于保持 Lifetime VPS 活跃。

## ✅ 功能

- **多账号支持** - 一次运行可处理多个账号
- **自动登录** - 会话过期时自动重新登录
- **Cloudflare 验证** - 自动通过 Turnstile 人机验证
- **reCAPTCHA 解决** - 使用 YesCaptcha 服务自动解决
- **VPS 详情页访问** - 自动进入 VPS 管理页面
- **会话持久化** - 每个账号独立保存登录状态
- **Telegram 通知** - 任务完成后发送结果通知

## 📁 文件结构

```
zap-auto-login/
├── zap_keepalive.py      # 主脚本
├── .env.example          # 配置文件模板
├── .env                  # 配置文件 (需自己创建)
├── sessions/             # 会话文件目录 (自动生成)
└── README.md
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install playwright requests
playwright install chromium
```

### 2. 配置

```bash
# 复制配置文件
cp .env.example .env

# 编辑配置
nano .env
```

配置文件内容:

```env
# YesCaptcha API Key (用于解决 reCAPTCHA)
# 获取地址: https://yescaptcha.com
YESCAPTCHA_API_KEY=your_api_key_here

# 账号配置 (支持多账号，用逗号分隔)
# 格式: 邮箱:密码,邮箱:密码,...
ACCOUNTS=user1@example.com:password1,user2@example.com:password2

# VPS 详情页停留时间 (秒，可选)
STAY_DURATION=10

# Telegram 通知 (可选)
# Bot Token: 通过 @BotFather 创建机器人获取
# Chat ID: 通过 @userinfobot 获取
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 3. 运行

```bash
xvfb-run python3 zap_keepalive.py
```

## 📝 输出示例

```
============================================================
  ZAP-Hosting Lifetime VPS 保活脚本
============================================================
  账号数量: 2
  停留时间: 10 秒
  开始时间: 2026-01-05 16:51:27
============================================================

[进度] 处理账号 1/2
------------------------------------------------------------
[16:51:27] [账号] ⏳ 开始处理: user1@example.com
------------------------------------------------------------
[16:51:28] [启动] ✓ 浏览器已启动
[16:51:28] [会话] ✓ 已加载保存的会话
[16:51:36] [检查] ✓ Cloudflare 验证通过
[16:51:38] [检查] ✓ 会话有效，已登录
[16:51:47] [VPS] ✓ 点击了 My VPS
[16:51:52] [VPS] ✓ 进入 VPS 详情页
[16:51:58] [VPS] ✓ VPS 状态: ONLINE
[16:52:08] [保活] ✓ 停留完成
[16:52:18] [保活] ✓ 页面已刷新
[16:52:18] [结果] ✓ user1@example.com 保活完成!

[进度] 处理账号 2/2
...

============================================================
  📊 任务汇总
============================================================
  ✓ 成功: user1@example.com
  ✓ 成功: user2@example.com
------------------------------------------------------------
  总计: 2/2 成功
============================================================
```

## ⏰ 定时任务

建议每天运行一次以保持 Lifetime VPS 活跃。

```bash
# 编辑 crontab
crontab -e

# 添加以下行 (每天上午10点运行)
0 10 * * * cd /home/exedev/zap-auto-login && xvfb-run python3 zap_keepalive.py >> /tmp/zap_keepalive.log 2>&1
```

## ⚠️ 注意事项

- 会话 cookie 可能在几小时到几天内过期
- 如果会话过期，脚本会自动重新登录
- YesCaptcha 服务需要余额才能解决 reCAPTCHA
- `.env` 文件包含敏感信息，请勿提交到版本控制

## 免责声明

此脚本仅供学习网页自动化技术使用，请遵守 ZAP-Hosting 的服务条款。
