#!/usr/bin/env python3
"""
ZAP-Hosting Lifetime VPS 保活脚本

功能:
1. 支持多账号
2. 自动登录 ZAP-Hosting (如果会话过期)
3. 进入 Dashboard
4. 找到并进入 VPS 详情页
5. 停留指定时间后刷新
6. 保存会话供下次使用

使用方法:
    1. 复制 .env.example 为 .env
    2. 填写 YesCaptcha API Key 和账号信息
    3. 运行: xvfb-run python3 zap_keepalive.py
"""

import asyncio
import json
import time
import os
import requests
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

# ==================== 加载配置 ====================
def load_env():
    """从 .env 文件加载配置"""
    env_file = Path(__file__).parent / '.env'
    env_vars = {}
    
    if not env_file.exists():
        print("错误: 未找到 .env 文件")
        print("请复制 .env.example 为 .env 并填写配置")
        exit(1)
    
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    return env_vars

# 加载配置
ENV = load_env()

# YesCaptcha 配置
YESCAPTCHA_API_KEY = ENV.get('YESCAPTCHA_API_KEY', '')
YESCAPTCHA_API_URL = "https://api.yescaptcha.com"

# 账号配置 (格式: email:password,email:password)
ACCOUNTS_STR = ENV.get('ACCOUNTS', '')

# VPS 详情页停留时间 (秒)
STAY_DURATION = int(ENV.get('STAY_DURATION', '10'))

# Telegram 配置
TELEGRAM_BOT_TOKEN = ENV.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = ENV.get('TELEGRAM_CHAT_ID', '')

# ZAP-Hosting 配置
LOGIN_URL = "https://zap-hosting.com/en/#login"
DASHBOARD_URL = "https://zap-hosting.com/en/customer/home/"
SESSION_DIR = Path(__file__).parent / "sessions"

# reCAPTCHA sitekey
RECAPTCHA_SITEKEY = "6Lc8WwosAAAAABY42gdwB6ShcYBPW_YHTQeIhjav"


def parse_accounts(accounts_str: str) -> list:
    """解析账号配置"""
    accounts = []
    if not accounts_str:
        return accounts
    
    for item in accounts_str.split(','):
        item = item.strip()
        if ':' in item:
            email, password = item.split(':', 1)
            accounts.append({'email': email.strip(), 'password': password.strip()})
    
    return accounts


def get_session_file(email: str) -> Path:
    """获取账号对应的会话文件路径"""
    SESSION_DIR.mkdir(exist_ok=True)
    safe_name = email.replace('@', '_at_').replace('.', '_')
    return SESSION_DIR / f"{safe_name}.json"


# ==================== 工具类 ====================
class TelegramNotifier:
    """Telegram 通知发送器"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)
    
    def send(self, message: str) -> bool:
        """发送消息到 Telegram"""
        if not self.enabled:
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Telegram 发送失败: {e}")
            return False


class Logger:
    """带时间戳的日志输出"""
    @staticmethod
    def log(step: str, msg: str, status: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        symbols = {"INFO": "ℹ", "OK": "✓", "WARN": "⚠", "ERROR": "✗", "WAIT": "⏳"}
        symbol = symbols.get(status, "•")
        print(f"[{timestamp}] [{step}] {symbol} {msg}")


class YesCaptchaSolver:
    """使用 YesCaptcha API 解决 reCAPTCHA"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = YESCAPTCHA_API_URL
    
    def create_task(self, site_key: str, page_url: str) -> str:
        payload = {
            "clientKey": self.api_key,
            "task": {
                "type": "NoCaptchaTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": site_key,
                "softID": "26129",
            }
        }
        response = requests.post(f"{self.base_url}/createTask", json=payload, timeout=30)
        result = response.json()
        
        if result.get("errorId") == 0:
            return result.get("taskId")
        raise Exception(f"YesCaptcha 创建任务失败: {result.get('errorDescription')}")
    
    def get_result(self, task_id: str, max_wait: int = 120) -> str:
        payload = {"clientKey": self.api_key, "taskId": task_id}
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            response = requests.post(f"{self.base_url}/getTaskResult", json=payload, timeout=30)
            result = response.json()
            
            if result.get("errorId") != 0:
                raise Exception(f"YesCaptcha 错误: {result.get('errorDescription')}")
            
            if result.get("status") == "ready":
                return result.get("solution", {}).get("gRecaptchaResponse")
            time.sleep(3)
        
        raise Exception("YesCaptcha 超时")
    
    def solve(self, site_key: str, page_url: str) -> str:
        Logger.log("验证码", "创建 YesCaptcha 任务...", "WAIT")
        task_id = self.create_task(site_key, page_url)
        Logger.log("验证码", f"任务 ID: {task_id}")
        Logger.log("验证码", "等待验证码解决...", "WAIT")
        token = self.get_result(task_id)
        Logger.log("验证码", "验证码已解决!", "OK")
        return token


class ZapKeepAlive:
    """ZAP-Hosting 保活主类"""
    
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.session_file = get_session_file(email)
        self.solver = YesCaptchaSolver(YESCAPTCHA_API_KEY) if YESCAPTCHA_API_KEY else None
        self.browser = None
        self.context = None
        self.page = None
        self.cdp = None
    
    async def handle_cloudflare(self, max_attempts: int = 20) -> bool:
        """处理 Cloudflare Turnstile 验证"""
        for attempt in range(max_attempts):
            try:
                await self.page.wait_for_load_state('domcontentloaded', timeout=5000)
                title = await self.page.title()
                if "Just a moment" not in title:
                    return True
            except:
                await asyncio.sleep(1)
                continue
            
            wrapper = await self.page.query_selector('.main-wrapper')
            if wrapper:
                rect = await wrapper.bounding_box()
                if rect:
                    x, y = int(rect['x'] + 25), int(rect['y'] + rect['height'] / 2)
                    await self.cdp.send('Input.dispatchMouseEvent', {
                        'type': 'mousePressed', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1
                    })
                    await asyncio.sleep(0.1)
                    await self.cdp.send('Input.dispatchMouseEvent', {
                        'type': 'mouseReleased', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1
                    })
            await asyncio.sleep(2)
        return False
    
    async def close_modals(self):
        """关闭所有弹窗"""
        try:
            # 点击 "Don't show again"
            dont_show = await self.page.query_selector('button:has-text("Don\'t show again")')
            if dont_show and await dont_show.is_visible():
                await dont_show.click()
                await asyncio.sleep(1)
            
            # 关闭其他模态框
            close_btns = await self.page.query_selector_all('.modal .close, button.close, [data-dismiss="modal"]')
            for btn in close_btns:
                try:
                    if await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(0.5)
                except:
                    pass
            
            # 按 Escape
            await self.page.keyboard.press('Escape')
            await asyncio.sleep(0.5)
        except:
            pass
    
    async def login(self) -> bool:
        """执行登录流程"""
        Logger.log("登录", f"开始登录 {self.email}...", "WAIT")
        
        # 导航到登录页
        Logger.log("登录", "导航到登录页面...")
        await self.page.goto(LOGIN_URL)
        await asyncio.sleep(3)
        
        # Cloudflare 验证
        Logger.log("登录", "处理 Cloudflare 验证...", "WAIT")
        if not await self.handle_cloudflare():
            Logger.log("登录", "Cloudflare 验证超时", "ERROR")
            return False
        Logger.log("登录", "Cloudflare 验证通过!", "OK")
        await asyncio.sleep(2)
        
        # 接受 cookies
        try:
            btn = await self.page.query_selector('button:has-text("Accept all")')
            if btn:
                await btn.click()
                Logger.log("登录", "已接受 cookies", "OK")
        except:
            pass
        await asyncio.sleep(1)
        
        # 点击登录链接打开对话框
        Logger.log("登录", "打开登录对话框...")
        login_link = await self.page.query_selector('text="Log in!"') or \
                     await self.page.query_selector('text="Already registered"') or \
                     await self.page.query_selector('a:has-text("Log in")')
        if login_link:
            await login_link.click()
            await asyncio.sleep(2)
        
        # 填写表单
        Logger.log("登录", "填写登录表单...")
        
        # 查找邮箱输入框
        email_input = None
        for selector in ['input[placeholder*="E-Mail"]', 'input[placeholder*="e-mail"]', 
                         'input[placeholder*="Username"]', '.modal input[type="text"]']:
            email_input = await self.page.query_selector(selector)
            if email_input and await email_input.is_visible():
                break
            email_input = None
        
        if not email_input:
            all_inputs = await self.page.query_selector_all('input[type="text"], input[type="email"]')
            for inp in all_inputs:
                if await inp.is_visible():
                    placeholder = await inp.get_attribute('placeholder') or ''
                    if 'search' not in placeholder.lower():
                        email_input = inp
                        break
        
        if email_input:
            await email_input.click()
            await email_input.fill(self.email)
            Logger.log("登录", f"用户名: {self.email}", "OK")
        else:
            Logger.log("登录", "找不到用户名输入框", "ERROR")
            return False
        
        # 查找密码输入框
        password_input = None
        all_passwords = await self.page.query_selector_all('input[type="password"]')
        for pwd in all_passwords:
            if await pwd.is_visible():
                password_input = pwd
                break
        
        if password_input:
            await password_input.click()
            await password_input.fill(self.password)
            Logger.log("登录", "密码: ********", "OK")
        else:
            Logger.log("登录", "找不到密码输入框", "ERROR")
            return False
        
        # 点击 Login 按钮
        Logger.log("登录", "点击 Login 按钮...")
        login_btn = None
        for selector in ['button:has-text("Login")', 'button:has-text("Log in")', 'input[type="submit"]']:
            btns = await self.page.query_selector_all(selector)
            for btn in btns:
                if await btn.is_visible():
                    login_btn = btn
                    break
            if login_btn:
                break
        
        if login_btn:
            await login_btn.click()
        else:
            await password_input.press('Enter')
        await asyncio.sleep(3)
        
        # 解决 reCAPTCHA
        if self.solver:
            Logger.log("登录", "解决 reCAPTCHA 验证码...", "WAIT")
            try:
                recaptcha_token = self.solver.solve(RECAPTCHA_SITEKEY, LOGIN_URL)
                await self.page.evaluate('''
                    (token) => {
                        const textareas = document.querySelectorAll('textarea[name="g-recaptcha-response"]');
                        textareas.forEach(ta => { ta.style.display = 'block'; ta.value = token; });
                        return true;
                    }
                ''', recaptcha_token)
                Logger.log("登录", "reCAPTCHA token 已注入", "OK")
            except Exception as e:
                Logger.log("登录", f"reCAPTCHA 错误: {e}", "WARN")
        else:
            Logger.log("登录", "未配置 YesCaptcha API Key，跳过验证码", "WARN")
        
        await asyncio.sleep(2)
        
        # 点击确认登录按钮
        Logger.log("登录", "点击确认登录按钮...")
        modal_btn = await self.page.query_selector('#recaptcha-login button:has-text("Log in"), .modal button:has-text("Log in")')
        if modal_btn and await modal_btn.is_visible():
            await modal_btn.click(force=True)
        else:
            await self.page.keyboard.press('Enter')
        
        # 等待登录结果
        Logger.log("登录", "等待登录结果...", "WAIT")
        await asyncio.sleep(8)
        
        url = self.page.url
        if 'customer' in url:
            Logger.log("登录", "登录成功!", "OK")
            return True
        
        Logger.log("登录", "登录失败", "ERROR")
        return False
    
    async def visit_vps_detail(self) -> bool:
        """访问 VPS 详情页"""
        Logger.log("VPS", "访问 Dashboard...", "WAIT")
        await self.page.goto(DASHBOARD_URL, wait_until='domcontentloaded')
        await asyncio.sleep(3)
        
        # Cloudflare
        if not await self.handle_cloudflare():
            Logger.log("VPS", "Cloudflare 验证超时", "ERROR")
            return False
        Logger.log("VPS", "Cloudflare 验证通过!", "OK")
        await asyncio.sleep(2)
        
        # 关闭弹窗
        await self.close_modals()
        
        # 点击 My VPS
        Logger.log("VPS", "查找 My VPS 入口...")
        vps_link = None
        for selector in ['a:has-text("My VPS")', 'a[href*="vserver"]', 'text=My VPS']:
            try:
                link = await self.page.query_selector(selector)
                if link and await link.is_visible():
                    vps_link = link
                    break
            except:
                continue
        
        if vps_link:
            await vps_link.click()
            Logger.log("VPS", "点击了 My VPS", "OK")
            await asyncio.sleep(3)
        
        # Cloudflare
        await self.handle_cloudflare(10)
        await asyncio.sleep(2)
        
        # 查找 VPS 详情页链接
        Logger.log("VPS", "查找 VPS 详情页...")
        links = await self.page.evaluate('''
            () => {
                const links = document.querySelectorAll('a');
                return Array.from(links).map(a => ({
                    text: a.innerText.trim().substring(0, 100),
                    href: a.href
                })).filter(l => l.href && l.href.includes('vserver'));
            }
        ''')
        
        # 找到并进入第一个 VPS 详情页
        for link in links:
            if '/id/' in link['href'] or '/show/' in link['href']:
                await self.page.goto(link['href'])
                Logger.log("VPS", f"进入 VPS 详情页", "OK")
                break
        
        await asyncio.sleep(3)
        await self.handle_cloudflare(10)
        await asyncio.sleep(2)
        
        # 关闭弹窗
        await self.close_modals()
        
        current_url = self.page.url
        Logger.log("VPS", f"当前页面: {current_url}")
        
        # 获取 VPS 信息
        try:
            page_text = await self.page.evaluate('() => document.body.innerText')
            if 'ONLINE' in page_text:
                Logger.log("VPS", "VPS 状态: ONLINE", "OK")
            elif 'OFFLINE' in page_text:
                Logger.log("VPS", "VPS 状态: OFFLINE", "WARN")
        except:
            pass
        
        return 'vserver' in current_url
    
    async def stay_and_refresh(self):
        """停留并刷新页面"""
        Logger.log("保活", f"在 VPS 详情页停留 {STAY_DURATION} 秒...", "WAIT")
        for i in range(STAY_DURATION, 0, -1):
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] [保活] ⏳ 剩余 {i} 秒...", end='', flush=True)
            await asyncio.sleep(1)
        print()
        Logger.log("保活", "停留完成", "OK")
        
        Logger.log("保活", "刷新页面 (F5)...", "WAIT")
        await self.page.reload()
        await asyncio.sleep(5)
        await self.handle_cloudflare(10)
        await asyncio.sleep(2)
        Logger.log("保活", "页面已刷新", "OK")
    
    async def save_session(self):
        """保存会话"""
        cookies = await self.context.cookies()
        with open(self.session_file, 'w') as f:
            json.dump(cookies, f, indent=2)
        Logger.log("会话", f"会话已保存到 {self.session_file.name}", "OK")
    
    async def load_session(self) -> bool:
        """加载已保存的会话"""
        if self.session_file.exists():
            try:
                with open(self.session_file) as f:
                    cookies = json.load(f)
                await self.context.add_cookies(cookies)
                Logger.log("会话", "已加载保存的会话", "OK")
                return True
            except Exception as e:
                Logger.log("会话", f"加载会话失败: {e}", "WARN")
        return False
    
    async def run(self) -> bool:
        """单个账号的运行流程"""
        print()
        print("-" * 60)
        Logger.log("账号", f"开始处理: {self.email}", "WAIT")
        print("-" * 60)
        
        async with async_playwright() as p:
            # 启动浏览器
            Logger.log("启动", "启动浏览器...")
            self.browser = await p.chromium.launch(
                headless=False,
                args=['--disable-blink-features=AutomationControlled']
            )
            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 900},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            self.page = await self.context.new_page()
            self.cdp = await self.context.new_cdp_session(self.page)
            Logger.log("启动", "浏览器已启动", "OK")
            
            # 加载会话
            await self.load_session()
            
            # 访问 Dashboard 检查是否已登录
            Logger.log("检查", "检查登录状态...", "WAIT")
            await self.page.goto(DASHBOARD_URL, wait_until='domcontentloaded')
            await asyncio.sleep(5)
            
            # Cloudflare
            cf_passed = await self.handle_cloudflare()
            if cf_passed:
                Logger.log("检查", "Cloudflare 验证通过", "OK")
            await asyncio.sleep(2)
            
            # 检查是否需要登录
            current_url = self.page.url
            need_login = 'login' in current_url.lower() or '#login' in current_url or 'customer' not in current_url
            
            if need_login:
                Logger.log("检查", "需要登录", "WARN")
                if not await self.login():
                    Logger.log("结果", "登录失败，任务终止", "ERROR")
                    await self.browser.close()
                    return False
            else:
                Logger.log("检查", "会话有效，已登录", "OK")
            
            # 访问 VPS 详情页
            if not await self.visit_vps_detail():
                Logger.log("结果", "访问 VPS 详情页失败", "ERROR")
                await self.browser.close()
                return False
            
            # 停留并刷新
            await self.stay_and_refresh()
            
            # 保存会话
            await self.save_session()
            
            Logger.log("结果", f"{self.email} 保活完成!", "OK")
            
            await self.browser.close()
            return True


async def main():
    # 检查配置
    if not YESCAPTCHA_API_KEY:
        print("警告: 未配置 YESCAPTCHA_API_KEY，登录时可能无法自动解决验证码")
    
    accounts = parse_accounts(ACCOUNTS_STR)
    if not accounts:
        print("错误: 未配置账号信息")
        print("请在 .env 文件中配置 ACCOUNTS=email:password")
        exit(1)
    
    # 初始化 Telegram 通知
    telegram = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    if telegram.enabled:
        print("✓ Telegram 通知已启用")
    
    print()
    print("=" * 60)
    print("  ZAP-Hosting Lifetime VPS 保活脚本")
    print("=" * 60)
    print(f"  账号数量: {len(accounts)}")
    print(f"  停留时间: {STAY_DURATION} 秒")
    print(f"  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    results = []
    for i, account in enumerate(accounts, 1):
        print(f"\n[进度] 处理账号 {i}/{len(accounts)}")
        keeper = ZapKeepAlive(account['email'], account['password'])
        success = await keeper.run()
        results.append({'email': account['email'], 'success': success})
    
    # 汇总结果
    print()
    print("=" * 60)
    print("  📊 任务汇总")
    print("=" * 60)
    success_count = sum(1 for r in results if r['success'])
    for r in results:
        status = "✓ 成功" if r['success'] else "✗ 失败"
        print(f"  {status}: {r['email']}")
    print("-" * 60)
    print(f"  总计: {success_count}/{len(results)} 成功")
    print(f"  完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    # 发送 Telegram 通知
    if telegram.enabled:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 构建消息
        if success_count == len(results):
            emoji = "✅"
            title = "ZAP 保活成功"
        elif success_count > 0:
            emoji = "⚠️"
            title = "ZAP 保活部分成功"
        else:
            emoji = "❌"
            title = "ZAP 保活失败"
        
        msg_lines = [f"{emoji} <b>{title}</b>", ""]
        for r in results:
            status = "✅" if r['success'] else "❌"
            msg_lines.append(f"{status} {r['email']}")
        msg_lines.append("")
        msg_lines.append(f"📊 结果: {success_count}/{len(results)} 成功")
        msg_lines.append(f"🕒 时间: {now}")
        
        message = "\n".join(msg_lines)
        telegram.send(message)
        print("✓ 已发送 Telegram 通知")
    
    return success_count == len(results)


if __name__ == '__main__':
    result = asyncio.run(main())
    exit(0 if result else 1)
