import os
import time
import warnings
import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from PIL import Image
import telebot
import ccxt

warnings.filterwarnings("ignore")

# ==========================
# تنظیمات قابل تغییر
# ==========================

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT",
    "AVAXUSDT", "TRXUSDT", "DOTUSDT", "LINKUSDT", "MATICUSDT", "TONUSDT", "LTCUSDT",
    "ATOMUSDT", "XLMUSDT", "APTUSDT", "FILUSDT", "ETCUSDT", "HBARUSDT", "ICPUSDT",
    "NEARUSDT", "SANDUSDT", "AAVEUSDT", "XAUUSDT", "XAGUSDT"
]

MAX_SYMBOLS        = 28
CHARTS_PER_FILE    = 14
CANDLE_LIMIT       = 150
INTERVAL_MINUTES   = 15

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")
SEND_TO_TELEGRAM   = True

ALERT_SYMBOL       = "BTCUSDT"
ALERT_ENABLED      = True

SLEEP_ON_ERROR_MIN = 15
OUTPUT_FORMAT      = "png"

# ==========================
# تلگرام (telebot)
# ==========================

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode=None)

def send_text(msg: str):
    if not SEND_TO_TELEGRAM:
        return
    try:
        bot.send_message(TELEGRAM_CHAT_ID, msg)
    except Exception:
        pass

def send_photo(filename: str, caption: str):
    if not SEND_TO_TELEGRAM:
        return
    if not os.path.exists(filename):
        return
    try:
        with open(filename, "rb") as f:
            bot.send_photo(TELEGRAM_CHAT_ID, f, caption=caption)
    except Exception:
        pass

# ==========================
# ccxt برای بایننس
# ==========================

binance = ccxt.binance()

# ==========================
# OKX
# ==========================

def symbol_to_okx_inst(symbol: str) -> str:
    if symbol.endswith("USDT"):
        base = symbol[:-4]
        return f"{base}-USDT"
    return symbol

def fetch_from_okx(symbol: str, limit: int = CANDLE_LIMIT):
    try:
        inst_id = symbol_to_okx_inst(symbol)
        url = "https://www.okx.com/api/v5/market/candles"
        params = {"instId": inst_id, "bar": "15m", "limit": str(limit)}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if "data" not in data or len(data["data"]) == 0:
            return None

        rows = data["data"]
        rows.reverse()

        df = pd.DataFrame(rows, columns=[
            "ts", "open", "high", "low", "close", "vol",
            "volCcy", "volCcyQuote", "confirm", "idxPx"
        ])

        df["open"]   = df["open"].astype(float)
        df["high"]   = df["high"].astype(float)
        df["low"]    = df["low"].astype(float)
        df["close"]  = df["close"].astype(float)
        df["volume"] = df["vol"].astype(float)
        df["time"]   = pd.to_datetime(df["ts"].astype(int), unit="ms")

        return df[["time", "open", "high", "low", "close", "volume"]]
    except Exception:
        return None

# ==========================
# بایننس با ccxt
# ==========================

def fetch_from_binance(symbol: str, limit: int = CANDLE_LIMIT):
    try:
        ohlcv = binance.fetch_ohlcv(symbol, timeframe="15m", limit=limit)
        if not ohlcv:
            return None
        df = pd.DataFrame(ohlcv, columns=["time", "open", "high", "low", "close", "volume"])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        return df
    except Exception:
        return None

# ==========================
# سوئیچ OKX → Binance
# ==========================

def fetch_data(symbol: str):
    df = fetch_from_okx(symbol)
    if df is not None and len(df) > 0:
        return df
    df = fetch_from_binance(symbol)
    if df is not None and len(df) > 0:
        return df
    return None

# ==========================
# اندیکاتورها
# ==========================

def WMA(series: pd.Series, period: int) -> pd.Series:
    weights = np.arange(1, period + 1)
    return series.rolling(period).apply(
        lambda prices: np.dot(prices, weights) / weights.sum(), raw=True
    )

# ==========================
# رسم نمودار
# ==========================

def plot_candles(ax, df: pd.DataFrame, title: str):
    for i in range(len(df)):
        o = df["open"].iloc[i]
        h = df["high"].iloc[i]
        l = df["low"].iloc[i]
        c = df["close"].iloc[i]
        color = "green" if c >= o else "red"

        ax.plot([i, i], [l, h], color=color, linewidth=1.5)
        ax.add_patch(plt.Rectangle(
            (i - 0.3, min(o, c)),
            0.6,
            abs(c - o),
            color=color,
            linewidth=0
        ))

    df["SMA10"] = df["close"].rolling(10).mean()
    df["SMA30"] = df["close"].rolling(30).mean()
    ax.plot(df["SMA10"].values, color="blue", linewidth=1)
    ax.plot(df["SMA30"].values, color="orange", linewidth=1)

    df["WMA"] = WMA(df["close"], 10)
    colors = []
    for i in range(len(df)):
        if i == 0 or np.isnan(df["WMA"].iloc[i]) or np.isnan(df["WMA"].iloc[i - 1]):
            colors.append("gray")
        else:
            colors.append("green" if df["WMA"].iloc[i] > df["WMA"].iloc[i - 1] else "red")
    df["WMA_COLOR"] = colors

    for i in range(len(df)):
        if not np.isnan(df["WMA"].iloc[i]):
            ax.scatter(i, df["WMA"].iloc[i], color=df["WMA_COLOR"].iloc[i], s=20)

    ax.set_title(title, fontsize=20)

    ax2 = ax.twinx()
    ax2.set_ylim(ax.get_ylim())
    ax2.set_yticks(ax.get_yticks())
    ax2.grid(False)

    times = df["time"]
    bottom_ticks, bottom_labels = [], []
    top_ticks, top_labels = [], []

    for i, t in enumerate(times):
        if t.minute == 0 and t.hour % 2 == 0:
            bottom_ticks.append(i)
            bottom_labels.append(t.strftime("%H:%M"))
        elif t.minute == 0 and t.hour % 2 == 1:
            top_ticks.append(i)
            top_labels.append(t.strftime("%H:%M"))

    ax.set_xticks(bottom_ticks)
    ax.set_xticklabels(bottom_labels, rotation=45, fontsize=8)

    ax_top = ax.twiny()
    ax_top.set_xlim(ax.get_xlim())
    ax_top.set_xticks(top_ticks)
    ax_top.set_xticklabels(top_labels, rotation=45, fontsize=8)

# ==========================
# هشدار WMA
# ==========================

def check_wma_alert(df: pd.DataFrame, symbol: str):
    if not ALERT_ENABLED:
        return
    if symbol != ALERT_SYMBOL:
        return
    if len(df) < 3:
        return

    wma = df["WMA"].values
    if np.isnan(wma[-1]) or np.isnan(wma[-2]):
        return

    prev_dir = wma[-2] - wma[-3] if len(wma) >= 3 and not np.isnan(wma[-3]) else 0
    curr_dir = wma[-1] - wma[-2]

    if prev_dir * curr_dir < 0:
        send_text(f"⚠️ تغییر جهت WMA در {symbol}")

# ==========================
# ساخت فایل‌های چندنموداری
# ==========================

def build_grid_images(symbols):
    images = []
    total = min(len(symbols), MAX_SYMBOLS)
    symbols = symbols[:total]

    groups = [symbols[i:i + CHARTS_PER_FILE] for i in range(0, total, CHARTS_PER_FILE)]

    for gi, group in enumerate(groups, start=1):
        rows = 7
        cols = 2
        fig, axes = plt.subplots(rows, cols, figsize=(20, 30))
        axes = axes.flatten()

        for ax in axes[len(group):]:
            ax.axis("off")

        for idx, sym in enumerate(group):
            ax = axes[idx]
            df = fetch_data(sym)
            if df is None or len(df) == 0:
                ax.axis("off")
                continue
            plot_candles(ax, df, sym)
            check_wma_alert(df, sym)

        plt.tight_layout()
        fname = f"charts_group_{gi}.{OUTPUT_FORMAT}"
        fig.savefig(fname, dpi=400, bbox_inches="tight")
        plt.close(fig)
        images.append(fname)

    return images

# ==========================
# اجرای یک سیکل
# ==========================

def run_cycle():
    start_msg = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_text(f"🚀 شروع سیکل جدید — {start_msg}")
    print(f"شروع سیکل جدید — {start_msg}")

    try:
        files = build_grid_images(SYMBOLS)
    except Exception:
        send_text("⚠️ خطا در ارتباط با اینترنت یا صرافی‌ها — مکث ۱۵ دقیقه")
        print("خطا در ارتباط با اینترنت یا صرافی‌ها — مکث ۱۵ دقیقه")
        time.sleep(SLEEP_ON_ERROR_MIN * 60)
        return

    for f in files:
        send_photo(f, f"📊 نمودارها — {f}")

    end_msg = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_text(f"🏁 پایان سیکل — {end_msg}")
    print(f"پایان سیکل — {end_msg}")

# ==========================
# حلقهٔ دائمی برای Railway
# ==========================

if __name__ == "__main__":
    while True:
        run_cycle()
        time.sleep(INTERVAL_MINUTES * 60)