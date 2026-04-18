import asyncio
import json
import time

import aiohttp
from aiohttp_socks import ProxyConnector

import pandas as pd


class BinanceMarket:
    def __init__(self, config, logger, storage=None, signal_engine=None, indicator_registry=None):
        self.config = config
        self.logger = logger
        self.storage = storage
        self.signal_engine = signal_engine
        self.indicator_registry = indicator_registry

        binance_cfg = config.get("binance", {})
        self.base_url = binance_cfg.get("base_url", "https://api.binance.com")
        self.ws_url = binance_cfg.get("ws_url", "wss://stream.binance.com:9443/ws")

        proxy_cfg = config.get("proxy", {})
        self.proxy_enabled = proxy_cfg.get("enabled", False)
        self.proxy_http = proxy_cfg.get("http", "")
        self.proxy_https = proxy_cfg.get("https", "")

        self.symbols = config.get("symbols", [])
        self.ws_session = None
        self.ws_connection = None
        self._running = False
        self._reconnect_delay = 1
        self._max_reconnect_delay = 60
        self._kline_buffer = {}

    def _get_proxy_connector(self):
        if not self.proxy_enabled:
            return None
        proxy_url = self.proxy_https or self.proxy_http
        if not proxy_url:
            return None
        return ProxyConnector.from_url(proxy_url)

    def _get_proxy_url(self):
        if not self.proxy_enabled:
            return None
        return self.proxy_https or self.proxy_http or None

    async def test_connection(self):
        connector = self._get_proxy_connector()
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                url = f"{self.base_url}/api/v3/ping"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        self.logger.info("币安REST API连接成功")
                        return True
                    else:
                        self.logger.error(f"币安REST API返回状态码: {resp.status}")
                        return False
        except Exception as e:
            self.logger.error(f"币安REST API连接失败: {e}")
            return False

    async def fetch_klines(self, symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
        connector = self._get_proxy_connector()
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                url = f"{self.base_url}/api/v3/klines"
                params = {"symbol": symbol, "interval": interval, "limit": limit}
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        self.logger.error(f"获取K线数据失败: {symbol} {interval}, 状态码: {resp.status}")
                        return pd.DataFrame()
                    data = await resp.json()
                    return self._parse_klines(data, symbol, interval)
        except Exception as e:
            self.logger.error(f"获取K线数据异常: {symbol} {interval}, {e}")
            return pd.DataFrame()

    async def fetch_latest_price(self, symbol: str) -> float:
        connector = self._get_proxy_connector()
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                url = f"{self.base_url}/api/v3/ticker/price"
                params = {"symbol": symbol}
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return float(data["price"])
                    return 0.0
        except Exception as e:
            self.logger.error(f"获取最新价格失败: {symbol}, {e}")
            return 0.0

    def _parse_klines(self, data: list, symbol: str, interval: str) -> pd.DataFrame:
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades",
            "taker_buy_volume", "taker_buy_quote_volume", "ignore"
        ])
        df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        df["symbol"] = symbol
        df["interval"] = interval
        return df

    async def start(self):
        self._running = True
        await self._load_history()
        await self._connect_websocket()

    async def stop(self):
        self._running = False
        if self.ws_connection and not self.ws_connection.closed:
            await self.ws_connection.close()
        if self.ws_session and not self.ws_session.closed:
            await self.ws_session.close()

    async def _load_history(self):
        self.logger.info("正在加载历史K线数据...")
        for symbol_cfg in self.symbols:
            symbol = symbol_cfg["name"]
            intervals = symbol_cfg.get("intervals", ["1h", "4h", "1d"])
            for interval in intervals:
                df = await self.fetch_klines(symbol, interval, limit=500)
                if not df.empty:
                    key = f"{symbol}_{interval}"
                    self._kline_buffer[key] = df
                    self.logger.info(f"已加载 {symbol} {interval} 历史K线 {len(df)} 根")
                    if self.storage:
                        await self.storage.save_klines(df)
                    if self.indicator_registry:
                        self.indicator_registry.calculate_all(key, df)
        self.logger.info("历史K线数据加载完成")

    async def _connect_websocket(self):
        streams = []
        for symbol_cfg in self.symbols:
            symbol = symbol_cfg["name"].lower()
            intervals = symbol_cfg.get("intervals", ["1h", "4h", "1d"])
            for interval in intervals:
                streams.append(f"{symbol}@kline_{interval}")

        if not streams:
            self.logger.error("没有可订阅的数据流")
            return

        stream_url = f"{self.ws_url}/{'/'.join(streams)}"

        while self._running:
            try:
                connector = self._get_proxy_connector()
                self.ws_session = aiohttp.ClientSession(connector=connector)
                proxy = self._get_proxy_url()

                self.logger.info(f"正在连接WebSocket: {stream_url[:80]}...")
                self.ws_connection = await self.ws_session.ws_connect(
                    stream_url,
                    proxy=proxy,
                    heartbeat=30,
                    receive_timeout=60,
                )

                self._reconnect_delay = 1
                self.logger.info("WebSocket连接成功，开始接收数据")

                async for msg in self.ws_connection:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        await self._on_kline_message(data)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        self.logger.error(f"WebSocket错误: {self.ws_connection.exception()}")
                        break
                    elif msg.type == aiohttp.WSMsgType.CLOSED:
                        self.logger.warning("WebSocket连接已关闭")
                        break

            except Exception as e:
                self.logger.error(f"WebSocket连接异常: {e}")

            finally:
                if self.ws_session and not self.ws_session.closed:
                    await self.ws_session.close()

            if self._running:
                self.logger.info(f"将在 {self._reconnect_delay} 秒后重连...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)

    async def _on_kline_message(self, data: dict):
        try:
            kline = data.get("k")
            if not kline:
                return

            symbol = kline["s"]
            interval = kline["i"]
            is_closed = kline["x"]

            key = f"{symbol}_{interval}"

            new_row = pd.DataFrame([{
                "open_time": pd.Timestamp.fromtimestamp(kline["t"] / 1000),
                "open": float(kline["o"]),
                "high": float(kline["h"]),
                "low": float(kline["l"]),
                "close": float(kline["c"]),
                "volume": float(kline["v"]),
                "symbol": symbol,
                "interval": interval,
            }])

            if key in self._kline_buffer:
                df = self._kline_buffer[key]
                if not df.empty and df.iloc[-1]["open_time"] == new_row.iloc[0]["open_time"]:
                    df.iloc[-1] = new_row.iloc[0]
                else:
                    self._kline_buffer[key] = pd.concat([df, new_row], ignore_index=True).tail(500)
            else:
                self._kline_buffer[key] = new_row

            if is_closed:
                self.logger.info(f"K线收盘: {symbol} {interval} 收盘价={kline['c']}")
                if self.storage:
                    await self.storage.save_klines(self._kline_buffer[key].tail(1))
                if self.indicator_registry:
                    self.indicator_registry.calculate_all(key, self._kline_buffer[key])
                if self.signal_engine:
                    await self.signal_engine.evaluate(key, symbol, interval, float(kline["c"]))

        except Exception as e:
            self.logger.error(f"处理K线消息异常: {e}")

    def get_kline_buffer(self, key: str) -> pd.DataFrame:
        return self._kline_buffer.get(key, pd.DataFrame())
