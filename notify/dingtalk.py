import asyncio
import time
import hmac
import hashlib
import base64
import urllib.parse

import aiohttp


class DingTalkNotifier:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        dingtalk_cfg = config.get("dingtalk", {})
        self.webhook = dingtalk_cfg.get("webhook", "")
        self.secret = dingtalk_cfg.get("secret", "")
        self.message_type = dingtalk_cfg.get("message_type", "markdown")
        self._session = None
        self._min_interval = dingtalk_cfg.get("min_interval_seconds", 20)
        self._last_send_time = 0.0

    def _generate_sign_url(self) -> str:
        timestamp = str(round(time.time() * 1000))
        secret_enc = self.secret.encode("utf-8")
        string_to_sign = "{}\n{}".format(timestamp, self.secret)
        string_to_sign_enc = string_to_sign.encode("utf-8")
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return f"{self.webhook}&timestamp={timestamp}&sign={sign}"

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _send(self, payload: dict) -> bool:
        if not self.webhook or "YOUR_TOKEN" in self.webhook:
            self.logger.warning("钉钉Webhook未配置，跳过发送")
            return False

        now = time.time()
        elapsed = now - self._last_send_time
        if elapsed < self._min_interval:
            wait = self._min_interval - elapsed
            self.logger.debug(f"钉钉频控等待 {wait:.1f}s")
            await asyncio.sleep(wait)

        try:
            url = self._generate_sign_url()
            session = await self._get_session()
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                result = await resp.json()
                if result.get("errcode") == 0:
                    self._last_send_time = time.time()
                    return True
                else:
                    self.logger.error(f"钉钉发送失败: {result}")
                    return False
        except Exception as e:
            self.logger.error(f"钉钉发送异常: {e}")
            return False

    async def send_signal(self, symbol: str, signal_type: str, strength: str,
                          indicators: list[str], price: float, interval: str) -> bool:
        icon = "🟢" if signal_type == "buy" else "🔴"
        action = "买入" if signal_type == "buy" else "卖出"
        resonance = f"（{len(indicators)}个指标共振）" if len(indicators) > 1 else ""

        indicator_lines = "\n".join([f"- {ind}" for ind in indicators[:5]])
        now = time.strftime("%Y-%m-%d %H:%M:%S")

        if self.message_type == "markdown":
            text = (
                f"### {icon} {action}信号 - {symbol}\n\n"
                f"**信号强度**：{strength}{resonance}\n\n"
                f"**触发指标**：\n{indicator_lines}\n\n"
                f"**当前价格**：${price:,.2f}\n\n"
                f"**K线周期**：{interval}\n\n"
                f"**时间**：{now}"
            )
            payload = {
                "msgtype": "markdown",
                "markdown": {"title": f"{icon} {action}信号 - {symbol}", "text": text},
            }
        else:
            text = (
                f"{icon} {action}信号 - {symbol}\n"
                f"强度: {strength}{resonance}\n"
                f"指标: {'; '.join(indicators[:3])}\n"
                f"价格: ${price:,.2f}\n"
                f"周期: {interval}\n"
                f"时间: {now}"
            )
            payload = {
                "msgtype": "text",
                "text": {"content": text},
            }

        return await self._send(payload)

    async def send_price_alert(self, symbol: str, price: float, target: float, direction: str) -> bool:
        icon = "⚡" if direction == "突破" else "⚠️"
        now = time.strftime("%Y-%m-%d %H:%M:%S")

        if self.message_type == "markdown":
            text = (
                f"### {icon} 价格提醒 - {symbol}\n\n"
                f"**方向**：{direction}关键价位\n\n"
                f"**当前价格**：${price:,.2f}\n\n"
                f"**关键价位**：${target:,.2f}\n\n"
                f"**时间**：{now}"
            )
            payload = {
                "msgtype": "markdown",
                "markdown": {"title": f"{icon} 价格提醒 - {symbol}", "text": text},
            }
        else:
            text = (
                f"{icon} 价格提醒 - {symbol}\n"
                f"{direction} ${target:,.2f}\n"
                f"当前: ${price:,.2f}\n"
                f"时间: {now}"
            )
            payload = {
                "msgtype": "text",
                "text": {"content": text},
            }

        return await self._send(payload)

    async def send_price_change(self, symbol: str, direction: str, pct: float,
                                open_price: float, current_price: float) -> bool:
        icon = "🔥" if direction == "上涨" else "💧"
        sign = "+" if pct > 0 else ""
        now = time.strftime("%Y-%m-%d %H:%M:%S")

        if self.message_type == "markdown":
            text = (
                f"### {icon} 行情异动 - {symbol}\n\n"
                f"**方向**：{direction} {sign}{pct:.2f}%\n\n"
                f"**开盘价**：${open_price:,.2f}\n\n"
                f"**当前价**：${current_price:,.2f}\n\n"
                f"**变动额**：${current_price - open_price:+,.2f}\n\n"
                f"**时间**：{now}"
            )
            payload = {
                "msgtype": "markdown",
                "markdown": {"title": f"{icon} 行情异动 - {symbol}", "text": text},
            }
        else:
            text = (
                f"{icon} 行情异动 - {symbol}\n"
                f"{direction} {sign}{pct:.2f}%\n"
                f"开盘: ${open_price:,.2f}\n"
                f"当前: ${current_price:,.2f}\n"
                f"时间: {now}"
            )
            payload = {
                "msgtype": "text",
                "text": {"content": text},
            }

        return await self._send(payload)

    async def send_error(self, title: str, message: str) -> bool:
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        text = (
            f"### ❌ 异常告警\n\n"
            f"**类型**：{title}\n\n"
            f"**详情**：{message}\n\n"
            f"**时间**：{now}"
        )
        payload = {
            "msgtype": "markdown",
            "markdown": {"title": "❌ 异常告警", "text": text},
        }
        return await self._send(payload)

    async def send_test(self) -> bool:
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        text = (
            f"### ✅ 监控系统测试\n\n"
            f"钉钉机器人连接正常！\n\n"
            f"**时间**：{now}"
        )
        payload = {
            "msgtype": "markdown",
            "markdown": {"title": "✅ 监控系统测试", "text": text},
        }
        return await self._send(payload)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
