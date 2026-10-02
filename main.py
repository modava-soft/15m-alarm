# -*- coding: utf-8 -*-
# Modu Bazler v6.1 – Single Bot Version (Main bot sends all photos)
# Fully compatible with Railway
# All comments are English to avoid Unicode SyntaxError

import os, json, time, threading, datetime as dt
import requests, numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import telebot
from telebot import types

# =========================
# Paths & Config
# =========================

BASE_DIR   = os.path.abspath(os.path.dirname(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "data")
CHARTS_DIR = os.path.join(DATA_DIR, "charts")
PDF_DIR    = os.path.join(DATA_DIR, "pdf")

for d in [DATA_DIR, CHARTS_DIR, PDF_DIR]:
    os.makedirs(d, exist_ok=True)

CONFIG_PATH = os.path.join(DATA_DIR, "config_v6_1.json")

DEFAULT_CONFIG = {
    "symbols_15m": ["BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT"],
    "symbols_1h":  ["BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT"],
    "symbols_4h":  ["BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT"],
    "symbols_1d":  ["BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT"],

    "enabled_15m": True,
    "enabled_1h": True,
    "enabled_4h": True,
    "enabled_1d": True,

    "lookback_15m": 3,
    "lookback_1h": 5,
    "lookback_4h": 15,
    "lookback_1d": 180,
    "max_bars": 300,

    "alarm_wma_direction": True,
    "alarm_cross_sma20": False,
    "alarm_cross_sma100": False,
    "alarm_cross_sma200": False,
    "alarm_sma20_direction": False,
    "alarm_sma100_direction": False,
    "alarm_sma200_direction": False,

    "make_pdf_1h": True,
    "make_pdf_1d": True,

    "verbose_15m": True,
    "verbose_1h": True,
    "verbose_4h": True,
    "verbose_1d": True,

    "lock_timeout_sec": 600,
    "cycle_min_duration_sec": 5,

    "active_interval": "15m",
    "chat_id_main": None
}

def now_utc():
    return dt.datetime.now(dt.timezone.utc)

def now_utc_str():
    return now_utc().strftime("%Y-%m-%d %H:%M:%S")

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def load_config():
    if not os.path.exists(CONFIG_PATH):
        cfg = DEFAULT_CONFIG.copy()
        cfg["chat_id_main"] = os.getenv("CHAT_ID_MAIN")
        save_config(cfg)
        return cfg
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def reset_config():
    cfg = DEFAULT_CONFIG.copy()
    cfg["chat_id_main"] = os.getenv("CHAT_ID_MAIN")
    save_config(cfg)
    return cfg

# =========================
# Bot Setup
# =========================

TOKEN_MAIN = (os.getenv("TOKEN_MAIN") or os.getenv("TOKEN_1H") or "").strip()
if not TOKEN_MAIN or ":" not in TOKEN_MAIN:
    raise ValueError("TOKEN_MAIN is missing or invalid")

bot_main = telebot.TeleBot(TOKEN_MAIN, parse_mode="HTML")

LAST_ALARMS = {"15m": [], "1h": [], "4h": [], "1d": []}

# =========================
# SmartLock
# =========================

class SmartLock:
    def __init__(self):
        self.lock = threading.Lock()
        self.last_acquire = None

    def acquire(self, blocking=False):
        cfg = load_config()
        timeout = cfg.get("lock_timeout_sec", 600)
        if self.lock.locked() and self.last_acquire:
            elapsed = (now_utc() - self.last_acquire).total_seconds()
            if elapsed > timeout:
                try:
                    self.lock.release()
                except:
                    pass
        ok = self.lock.acquire(blocking=blocking)
        if ok:
            self.last_acquire = now_utc()
        return ok

    def release(self):
        if self.lock.locked():
            try:
                self.lock.release()
            except:
                pass

CYCLE_LOCKS = {
    "15m": SmartLock(),
    "1h": SmartLock(),
    "4h": SmartLock(),
    "1d": SmartLock()
}

# =========================
# Help Text
# =========================

HELP_TEXT = """
Modu Bazler v6.1 – Single Bot Version
All photos, PDFs, alarms and cycle messages are sent ONLY by bot_main.

Features:
• Enable/Disable each timeframe (15m / 1h / 4h / 1d)
• Full symbol management
• Full alarm system
• Full PDF system (1h & 1d)
• Full verbose control
• Full cycle runner
• Full immediate run
"""

# =========================
# Main Menu
# =========================

def send_main_menu(chat_id):
    cfg = load_config()
    active = cfg.get("active_interval", "15m")

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("Select Active Timeframe", f"Active: {active}")
    kb.row("Enable/Disable Timeframes")
    kb.row("Run Active Now")
    kb.row("Run 15m", "Run 1h")
    kb.row("Run 4h", "Run 1d")
    kb.row("Manage 15m", "Manage 1h")
    kb.row("Manage 4h", "Manage 1d")
    kb.row("Alarm Settings", "Alarm Report")
    kb.row("System Status", "Advanced Settings")
    kb.row("Run All Cycles", "Reset App")
    kb.row("Help", "Refresh Menu")

    bot_main.send_message(chat_id, "Main Menu:", reply_markup=kb)

@bot_main.message_handler(commands=["start"])
def start_main(m):
    cfg = load_config()
    cfg["chat_id_main"] = m.chat.id
    save_config(cfg)
    bot_main.send_message(m.chat.id, HELP_TEXT)
    send_main_menu(m.chat.id)

@bot_main.message_handler(func=lambda m: m.text == "Refresh Menu")
def refresh_main(m):
    send_main_menu(m.chat.id)

# =========================
# Symbol Management
# =========================

def get_symbols(cfg, group):
    return cfg[f"symbols_{group}"]

def set_symbols(cfg, group, symbols):
    cfg[f"symbols_{group}"] = symbols
    save_config(cfg)

def show_symbol_menu(chat_id, group):
    cfg = load_config()
    symbols = get_symbols(cfg, group)
    txt = f"Symbols in {group}:\n"
    txt += ", ".join(symbols) if symbols else "No symbols."
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(f"Add Symbol {group}", f"Remove Symbol {group}")
    kb.row(f"Show Symbols {group}")
    kb.row("Back to Menu")
    bot_main.send_message(chat_id, txt, reply_markup=kb)

@bot_main.message_handler(func=lambda m: m.text == "Manage 15m")
def manage_15m(m): show_symbol_menu(m.chat.id, "15m")

@bot_main.message_handler(func=lambda m: m.text == "Manage 1h")
def manage_1h(m): show_symbol_menu(m.chat.id, "1h")

@bot_main.message_handler(func=lambda m: m.text == "Manage 4h")
def manage_4h(m): show_symbol_menu(m.chat.id, "4h")

@bot_main.message_handler(func=lambda m: m.text == "Manage 1d")
def manage_1d(m): show_symbol_menu(m.chat.id, "1d")

def add_symbol_step(m, group):
    symbol = m.text.strip().upper()
    cfg = load_config()
    symbols = get_symbols(cfg, group)
    if symbol not in symbols:
        symbols.append(symbol)
        set_symbols(cfg, group, symbols)
        bot_main.send_message(m.chat.id, f"{symbol} added to {group}.")
    else:
        bot_main.send_message(m.chat.id, f"{symbol} already exists.")
    show_symbol_menu(m.chat.id, group)

@bot_main.message_handler(func=lambda m: m.text.startswith("Add Symbol "))
def add_symbol_any(m):
    group = m.text.split()[-1]
    msg = bot_main.send_message(m.chat.id, "Enter symbol:")
    bot_main.register_next_step_handler(msg, lambda mm: add_symbol_step(mm, group))

def remove_symbol_step(m, group):
    symbol = m.text.strip().upper()
    cfg = load_config()
    symbols = get_symbols(cfg, group)
    if symbol in symbols:
        symbols.remove(symbol)
        set_symbols(cfg, group, symbols)
        bot_main.send_message(m.chat.id, f"{symbol} removed from {group}.")
    else:
        bot_main.send_message(m.chat.id, f"{symbol} not found.")
    show_symbol_menu(m.chat.id, group)

@bot_main.message_handler(func=lambda m: m.text.startswith("Remove Symbol "))
def remove_symbol_any(m):
    group = m.text.split()[-1]
    msg = bot_main.send_message(m.chat.id, "Enter symbol:")
    bot_main.register_next_step_handler(msg, lambda mm: remove_symbol_step(mm, group))

@bot_main.message_handler(func=lambda m: m.text.startswith("Show Symbols "))
def show_symbols_any(m):
    group = m.text.split()[-1]
    cfg = load_config()
    symbols = get_symbols(cfg, group)
    txt = f"Symbols in {group}:\n"
    txt += ", ".join(symbols) if symbols else "No symbols."
    bot_main.send_message(m.chat.id, txt)

# =========================
# Enable / Disable Timeframes
# =========================

@bot_main.message_handler(func=lambda m: m.text == "Enable/Disable Timeframes")
def toggle_intervals_menu(m):
    cfg = load_config()
    kb = types.InlineKeyboardMarkup()
    for tf in ["15m","1h","4h","1d"]:
        key = f"enabled_{tf}"
        kb.add(types.InlineKeyboardButton(
            f"{tf} ({'ON' if cfg.get(key, True) else 'OFF'})",
            callback_data=f"toggle_tf_{tf}"
        ))
    bot_main.send_message(m.chat.id, "Toggle timeframes:", reply_markup=kb)

@bot_main.callback_query_handler(func=lambda c: c.data.startswith("toggle_tf_"))
def toggle_interval(c):
    cfg = load_config()
    tf = c.data.replace("toggle_tf_", "")
    key = f"enabled_{tf}"
    cfg[key] = not cfg.get(key, True)
    save_config(cfg)
    bot_main.answer_callback_query(c.id, f"{tf} -> {'ON' if cfg[key] else 'OFF'}")
    toggle_intervals_menu(c.message)

# =========================
# Alarm Settings
# =========================

@bot_main.message_handler(func=lambda m: m.text == "Alarm Settings")
def alarms_menu(m):
    cfg = load_config()
    kb = types.InlineKeyboardMarkup()
    for key in [
        "alarm_wma_direction",
        "alarm_cross_sma20",
        "alarm_cross_sma100",
        "alarm_cross_sma200",
        "alarm_sma20_direction",
        "alarm_sma100_direction",
        "alarm_sma200_direction"
    ]:
        kb.add(types.InlineKeyboardButton(
            f"{key} ({'ON' if cfg.get(key) else 'OFF'})",
            callback_data=f"alarm_{key}"
        ))
    bot_main.send_message(m.chat.id, "Alarm settings:", reply_markup=kb)

@bot_main.callback_query_handler(func=lambda c: c.data.startswith("alarm_"))
def toggle_alarm(c):
    cfg = load_config()
    key = c.data.replace("alarm_", "")
    cfg[key] = not cfg.get(key)
    save_config(cfg)
    bot_main.answer_callback_query(c.id, f"{key} -> {'ON' if cfg[key] else 'OFF'}")
    alarms_menu(c.message)

# =========================
# Alarm Report
# =========================

@bot_main.message_handler(func=lambda m: m.text == "Alarm Report")
def alarms_report(m):
    txt = ""
    for group in ["15m","1h","4h","1d"]:
        if LAST_ALARMS[group]:
            txt += f"Alarms {group}:\n"
            for item in LAST_ALARMS[group]:
                txt += f"{item['symbol']} ({item['interval']}):\n"
                for a in item["alarms"]:
                    txt += f" - {a}\n"
                txt += f"Time: {item['time']}\n\n"
    if not txt:
        txt = "No alarms."
    bot_main.send_message(m.chat.id, txt)

# =========================
# System Status
# =========================

@bot_main.message_handler(func=lambda m: m.text == "System Status")
def system_status(m):
    cfg = load_config()
    txt = "System Status:\n"
    txt += f"15m symbols: {len(cfg['symbols_15m'])} (enabled: {cfg['enabled_15m']})\n"
    txt += f"1h symbols: {len(cfg['symbols_1h'])} (enabled: {cfg['enabled_1h']})\n"
    txt += f"4h symbols: {len(cfg['symbols_4h'])} (enabled: {cfg['enabled_4h']})\n"
    txt += f"1d symbols: {len(cfg['symbols_1d'])} (enabled: {cfg['enabled_1d']})\n"
    txt += f"PDF 1h: {'ON' if cfg['make_pdf_1h'] else 'OFF'}\n"
    txt += f"PDF 1d: {'ON' if cfg['make_pdf_1d'] else 'OFF'}\n"
    txt += f"Verbose 15m: {'ON' if cfg['verbose_15m'] else 'OFF'}\n"
    txt += f"Verbose 1h: {'ON' if cfg['verbose_1h'] else 'OFF'}\n"
    txt += f"Verbose 4h: {'ON' if cfg['verbose_4h'] else 'OFF'}\n"
    txt += f"Verbose 1d: {'ON' if cfg['verbose_1d'] else 'OFF'}\n"
    txt += f"Active interval: {cfg.get('active_interval','15m')}\n"
    txt += f"Lock timeout: {cfg.get('lock_timeout_sec', 600)}\n"
    txt += f"Min cycle duration: {cfg.get('cycle_min_duration_sec', 5)}\n"
    bot_main.send_message(m.chat.id, txt)

# =========================
# Advanced Settings
# =========================

@bot_main.message_handler(func=lambda m: m.text == "Advanced Settings")
def advanced_settings(m):
    cfg = load_config()
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(f"PDF 1h ({'ON' if cfg['make_pdf_1h'] else 'OFF'})", callback_data="adv_pdf_1h"))
    kb.add(types.InlineKeyboardButton(f"PDF 1d ({'ON' if cfg['make_pdf_1d'] else 'OFF'})", callback_data="adv_pdf_1d"))
    kb.add(types.InlineKeyboardButton(f"Verbose 15m ({'ON' if cfg['verbose_15m'] else 'OFF'})", callback_data="adv_verbose_15m"))
    kb.add(types.InlineKeyboardButton(f"Verbose 1h ({'ON' if cfg['verbose_1h'] else 'OFF'})", callback_data="adv_verbose_1h"))
    kb.add(types.InlineKeyboardButton(f"Verbose 4h ({'ON' if cfg['verbose_4h'] else 'OFF'})", callback_data="adv_verbose_4h"))
    kb.add(types.InlineKeyboardButton(f"Verbose 1d ({'ON' if cfg['verbose_1d'] else 'OFF'})", callback_data="adv_verbose_1d"))
    kb.add(types.InlineKeyboardButton("Reset App", callback_data="adv_reset_app"))
    bot_main.send_message(m.chat.id, "Advanced settings:", reply_markup=kb)

@bot_main.callback_query_handler(func=lambda c: c.data.startswith("adv_"))
def advanced_settings_handler(c):
    cfg = load_config()
    if c.data == "adv_pdf_1h":
        cfg["make_pdf_1h"] = not cfg["make_pdf_1h"]
    elif c.data == "adv_pdf_1d":
        cfg["make_pdf_1d"] = not cfg["make_pdf_1d"]
    elif c.data == "adv_verbose_15m":
        cfg["verbose_15m"] = not cfg["verbose_15m"]
    elif c.data == "adv_verbose_1h":
        cfg["verbose_1h"] = not cfg["verbose_1h"]
    elif c.data == "adv_verbose_4h":
        cfg["verbose_4h"] = not cfg["verbose_4h"]
    elif c.data == "adv_verbose_1d":
        cfg["verbose_1d"] = not cfg["verbose_1d"]
    elif c.data == "adv_reset_app":
        cfg = reset_config()

    save_config(cfg)
    bot_main.answer_callback_query(c.id, "Updated.")
    advanced_settings(c.message)

# =========================
# Data Fetch (Binance)
# =========================

def _binance_interval(i: str) -> str:
    return {"15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}[i]

def fetch_ohlc(symbol: str, interval: str, lookback_days: int, max_bars: int) -> pd.DataFrame:
    limit = max(500, max_bars)
    try:
        url = "https://api.binance.com/api/v3/klines"
        r = requests.get(url, params={
            "symbol": symbol,
            "interval": _binance_interval(interval),
            "limit": limit
        }, timeout=10)
        r.raise_for_status()
        data = r.json()

        rows = [
            [int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])]
            for k in data
        ]

        df = pd.DataFrame(rows, columns=["t","o","h","l","c","v"])
        df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True)
        df.set_index("t", inplace=True)

        return df.tail(max_bars)

    except Exception:
        return pd.DataFrame()

# =========================
# Indicators
# =========================

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if df.empty:
        return df

    # SMA
    df["SMA20"]  = df["c"].rolling(20).mean()
    df["SMA100"] = df["c"].rolling(100).mean()
    df["SMA200"] = df["c"].rolling(200).mean()

    # WMA20
    df["WMA20"] = df["c"].rolling(20).apply(
        lambda x: np.average(x, weights=np.arange(1, len(x)+1)),
        raw=True
    )
    df["WMA20_slope"] = df["WMA20"].diff()

    # RSI14
    delta = df["c"].diff()
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)

    roll_gain = pd.Series(gain, index=df.index).rolling(14).mean()
    roll_loss = pd.Series(loss, index=df.index).rolling(14).mean()

    rs = roll_gain / (roll_loss + 1e-9)
    df["RSI14"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = df["c"].ewm(span=12, adjust=False).mean()
    ema26 = df["c"].ewm(span=26, adjust=False).mean()

    df["MACD"]        = ema12 - ema26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"]   = df["MACD"] - df["MACD_signal"]

    return df

# =========================
# Matplotlib Chart Builder
# =========================

def create_matplotlib_chart(symbol: str, interval: str, lookback_days: int, max_bars: int, png_name: str):
    df = fetch_ohlc(symbol, interval, lookback_days, max_bars)

    # If no data → generate placeholder image
    if df.empty:
        png_path = os.path.join(CHARTS_DIR, png_name)
        plt.figure(figsize=(8, 5))
        plt.text(0.5, 0.5, f"No data for {symbol}", ha="center", va="center")
        plt.axis("off")
        plt.savefig(png_path, dpi=120, bbox_inches="tight")
        plt.close()
        return {
            "symbol": symbol,
            "interval": interval,
            "png_path": png_path,
            "created_at": now_utc_str(),
            "wma": [],
            "wma_slope": [],
            "sma20": [],
            "sma100": [],
            "sma200": []
        }

    df = compute_indicators(df)

    png_path = os.path.join(CHARTS_DIR, png_name)

    # Create figure
    fig = plt.figure(figsize=(8, 8))
    gs = fig.add_gridspec(3, 1, height_ratios=[3,1,1])

    ax_price = fig.add_subplot(gs[0])
    ax_rsi   = fig.add_subplot(gs[1], sharex=ax_price)
    ax_macd  = fig.add_subplot(gs[2], sharex=ax_price)

    # Price + SMA + WMA
    ax_price.plot(df.index, df["c"], color="black", label="Close")
    ax_price.plot(df.index, df["SMA20"],  color="blue",   label="SMA20")
    ax_price.plot(df.index, df["SMA100"], color="orange", label="SMA100")
    ax_price.plot(df.index, df["SMA200"], color="purple", label="SMA200")

    wma   = df["WMA20"]
    slope = df["WMA20_slope"]

    wma_up   = wma.where(slope >= 0)
    wma_down = wma.where(slope < 0)

    ax_price.plot(df.index, wma_up,   color="green", linestyle="--", label="WMA20 Up")
    ax_price.plot(df.index, wma_down, color="red",   linestyle="--", label="WMA20 Down")

    ax_price.set_title(f"{symbol} – {interval}")
    ax_price.grid(True)
    ax_price.legend(loc="upper left")

    # RSI
    ax_rsi.plot(df.index, df["RSI14"], color="brown", label="RSI14")
    ax_rsi.axhline(70, color="red", linestyle="--")
    ax_rsi.axhline(30, color="green", linestyle="--")
    ax_rsi.set_ylim(0, 100)
    ax_rsi.grid(True)
    ax_rsi.legend(loc="upper left")

    # MACD
    ax_macd.plot(df.index, df["MACD"],        color="black", label="MACD")
    ax_macd.plot(df.index, df["MACD_signal"], color="magenta", label="Signal")
    ax_macd.bar(df.index, df["MACD_hist"], color="gray", alpha=0.5, label="Hist")
    ax_macd.grid(True)
    ax_macd.legend(loc="upper left")

    plt.tight_layout()
    plt.savefig(png_path, dpi=120)
    plt.close(fig)

    return {
        "symbol": symbol,
        "interval": interval,
        "png_path": png_path,
        "created_at": now_utc_str(),
        "wma": df["WMA20"].tolist(),
        "wma_slope": df["WMA20_slope"].tolist(),
        "sma20": df["SMA20"].tolist(),
        "sma100": df["SMA100"].tolist(),
        "sma200": df["SMA200"].tolist()
    }

# =========================
# Alarm Detection
# =========================

def detect_alarms(cfg: dict, info: dict, group: str):
    alarms = []

    wma    = info["wma"]
    slope  = info["wma_slope"]
    sma20  = info["sma20"]
    sma100 = info["sma100"]
    sma200 = info["sma200"]

    if len(wma) < 3:
        return alarms

    # WMA direction change
    if cfg.get("alarm_wma_direction", True):
        if slope[-2] < 0 and slope[-1] > 0:
            alarms.append("WMA20 turned UP")
        if slope[-2] > 0 and slope[-1] < 0:
            alarms.append("WMA20 turned DOWN")

    # Cross detection
    def cross(a, b):
        if len(a) < 2 or len(b) < 2:
            return False
        return (a[-2] - b[-2]) * (a[-1] - b[-1]) < 0

    if cfg.get("alarm_cross_sma20", False) and cross(wma, sma20):
        alarms.append("WMA20 crossed SMA20")
    if cfg.get("alarm_cross_sma100", False) and cross(wma, sma100):
        alarms.append("WMA20 crossed SMA100")
    if cfg.get("alarm_cross_sma200", False) and cross(wma, sma200):
        alarms.append("WMA20 crossed SMA200")

    # SMA direction change
    def dir_change(arr, name):
        if len(arr) < 3:
            return
        d1 = arr[-1] - arr[-2]
        d2 = arr[-2] - arr[-3]
        if d2 < 0 and d1 > 0:
            alarms.append(f"{name} turned UP")
        if d2 > 0 and d1 < 0:
            alarms.append(f"{name} turned DOWN")

    if cfg.get("alarm_sma20_direction", False):
        dir_change(sma20, "SMA20")
    if cfg.get("alarm_sma100_direction", False):
        dir_change(sma100, "SMA100")
    if cfg.get("alarm_sma200_direction", False):
        dir_change(sma200, "SMA200")

    if alarms:
        LAST_ALARMS[group] = [{
            "symbol": info["symbol"],
            "interval": info["interval"],
            "time": info["created_at"],
            "alarms": alarms
        }]

    return alarms


# =========================
# Cycle Runner (ONLY bot_main sends photos)
# =========================

def run_cycle(interval: str, manual: bool = False):
    cfg = load_config()

    # If timeframe disabled → skip
    if not cfg.get(f"enabled_{interval}", True):
        return

    lock = CYCLE_LOCKS[interval]
    if not lock.acquire(blocking=False):
        return

    start_time = now_utc()
    try:
        symbols_key = f"symbols_{interval}"
        symbols = cfg.get(symbols_key, [])
        chat_id = cfg.get("chat_id_main")
        verbose_key = f"verbose_{interval}"
        verbose = cfg.get(verbose_key, True)

        if chat_id:
            bot_main.send_message(chat_id,
                f"Starting {interval} cycle for {len(symbols)} symbols...\n{now_utc_str()}")

        # PDF builder (only for 1h and 1d)
        pdf_pages = None
        pdf_path = None
        if interval in ["1h","1d"] and cfg.get(f"make_pdf_{interval}", False) and chat_id:
            pdf_path = os.path.join(
                PDF_DIR,
                f"{interval}_cycle_{now_utc_str().replace(' ','_').replace(':','-')}.pdf"
            )
            pdf_pages = PdfPages(pdf_path)

        # Process symbols
        for idx, sym in enumerate(symbols, start=1):
            info = create_matplotlib_chart(
                sym,
                interval,
                cfg[f"lookback_{interval}"],
                cfg["max_bars"],
                f"{interval}_{sym}.png"
            )

            alarms = detect_alarms(cfg, info, interval)

            # Add chart to PDF
            if pdf_pages:
                try:
                    img = plt.imread(info["png_path"])
                    fig_pdf, ax_pdf = plt.subplots(figsize=(8, 6))
                    ax_pdf.imshow(img)
                    ax_pdf.axis("off")
                    pdf_pages.savefig(fig_pdf)
                    plt.close(fig_pdf)
                except:
                    pass

            # Send photo
            if chat_id:
                if verbose or alarms:
                    try:
                        with open(info["png_path"], "rb") as img_file:
                            bot_main.send_photo(
                                chat_id,
                                img_file,
                                caption=f"{sym} – {interval}\n{now_utc_str()}"
                            )
                    except:
                        pass

                # Send alarms
                if alarms:
                    txt = f"Alarms {interval} for {sym}:\n" + "\n".join(f"- {a}" for a in alarms)
                    bot_main.send_message(chat_id, txt)

            # Progress update
            if chat_id and idx % 5 == 0:
                bot_main.send_message(chat_id, f"Progress {interval}: {idx}/{len(symbols)}")

        # Send PDF
        if pdf_pages:
            try:
                pdf_pages.close()
                if chat_id and pdf_path:
                    with open(pdf_path, "rb") as pdf_file:
                        bot_main.send_document(
                            chat_id,
                            pdf_file,
                            caption=f"{interval} PDF\n{now_utc_str()}"
                        )
            except:
                pass

        # End message
        elapsed = (now_utc() - start_time).total_seconds()
        if chat_id:
            bot_main.send_message(chat_id,
                f"Finished {interval} cycle.\nDuration: {int(elapsed)} seconds")

    finally:
        lock.release()

# =========================
# Immediate Run Buttons
# =========================

@bot_main.message_handler(func=lambda m: m.text == "Run Active Now")
def run_now_active(m):
    cfg = load_config()
    tf = cfg.get("active_interval", "15m")
    bot_main.send_message(m.chat.id, f"Running {tf} now...")
    threading.Thread(target=run_cycle, args=(tf,), kwargs={"manual": True}, daemon=True).start()

@bot_main.message_handler(func=lambda m: m.text == "Run 15m")
def run_now_15m(m):
    bot_main.send_message(m.chat.id, "Running 15m now...")
    threading.Thread(target=run_cycle, args=("15m",), kwargs={"manual": True}, daemon=True).start()

@bot_main.message_handler(func=lambda m: m.text == "Run 1h")
def run_now_1h(m):
    bot_main.send_message(m.chat.id, "Running 1h now...")
    threading.Thread(target=run_cycle, args=("1h",), kwargs={"manual": True}, daemon=True).start()

@bot_main.message_handler(func=lambda m: m.text == "Run 4h")
def run_now_4h(m):
    bot_main.send_message(m.chat.id, "Running 4h now...")
    threading.Thread(target=run_cycle, args=("4h",), kwargs={"manual": True}, daemon=True).start()

@bot_main.message_handler(func=lambda m: m.text == "Run 1d")
def run_now_1d(m):
    bot_main.send_message(m.chat.id, "Running 1d now...")
    threading.Thread(target=run_cycle, args=("1d",), kwargs={"manual": True}, daemon=True).start()

# =========================
# Run All Cycles
# =========================

@bot_main.message_handler(func=lambda m: m.text == "Run All Cycles")
def run_all_cycles(m):
    bot_main.send_message(m.chat.id, "Running ALL cycles (15m, 1h, 4h, 1d)...")
    for tf in ["15m","1h","4h","1d"]:
        threading.Thread(target=run_cycle, args=(tf,), kwargs={"manual": True}, daemon=True).start()

# =========================
# Reset App
# =========================

@bot_main.message_handler(func=lambda m: m.text == "Reset App")
def reset_app(m):
    cfg = reset_config()
    cfg["chat_id_main"] = m.chat.id
    save_config(cfg)
    bot_main.send_message(m.chat.id, "App reset successfully.")
    send_main_menu(m.chat.id)

# =========================
# Main
# =========================

def main():
    cfg = load_config()
    if not cfg.get("chat_id_main"):
        print("⚠ Send /start to the bot in Telegram to register chat_id_main.")
    bot_main.infinity_polling()

if __name__ == "__main__":
    main()