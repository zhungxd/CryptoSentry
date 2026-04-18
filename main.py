import asyncio
import argparse
import signal
import sys
import os

import yaml

from core.market import BinanceMarket
from core.storage import Storage
from core.indicators import IndicatorRegistry
from core.signal import SignalEngine
from notify.dingtalk import DingTalkNotifier


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_logging(config: dict):
    import logging
    level = getattr(logging, config.get("logging", {}).get("level", "INFO").upper(), logging.INFO)
    log_file = config.get("logging", {}).get("file", "data/trace.log")
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("trace")
    logger.setLevel(level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_fmt = logging.Formatter(
        "\033[36m%(asctime)s\033[0m [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_fmt)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(file_fmt)
    logger.addHandler(file_handler)

    return logger


async def run(config: dict, logger):
    storage = Storage(config, logger)
    await storage.init()

    notifier = DingTalkNotifier(config, logger)
    indicator_registry = IndicatorRegistry(config, logger)
    signal_engine = SignalEngine(config, logger, indicator_registry, notifier, storage)

    market = BinanceMarket(config, logger, storage, signal_engine, indicator_registry)
    signal_engine._market_ref = market

    logger.info("正在连接币安API...")
    await market.start()

    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: stop_event.set())

    logger.info("监控系统已启动，按 Ctrl+C 退出")
    await stop_event.wait()

    logger.info("正在关闭...")
    await market.stop()
    await storage.close()
    logger.info("已安全退出")


async def test(config: dict, logger):
    notifier = DingTalkNotifier(config, logger)
    logger.info("测试钉钉通知...")
    success = await notifier.send_test()
    if success:
        logger.info("钉钉通知测试成功！")
    else:
        logger.error("钉钉通知测试失败！")

    market = BinanceMarket(config, logger, None, None, None)
    logger.info("测试币安API连接...")
    connected = await market.test_connection()
    if connected:
        logger.info("币安API连接测试成功！")
    else:
        logger.error("币安API连接测试失败！")


def main():
    parser = argparse.ArgumentParser(description="虚拟货币价格监控系统")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--daemon", action="store_true", help="后台运行")
    parser.add_argument("--test", action="store_true", help="测试模式")
    parser.add_argument("--status", action="store_true", help="查看运行状态")
    args = parser.parse_args()

    config = load_config(args.config)
    logger = setup_logging(config)

    if args.test:
        asyncio.run(test(config, logger))
        return

    if args.daemon:
        pid = os.fork()
        if pid > 0:
            logger.info(f"后台进程已启动，PID: {pid}")
            sys.exit(0)
        os.setsid()

    try:
        asyncio.run(run(config, logger))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
