# -*- coding: utf-8 -*-
# Modu Bazler v6.1 – نسخه‌ی کامل با یک ربات اصلی، انتخاب و فعال/غیرفعال کردن تایم‌فریم‌ها، آلارم‌ها و نمودارها
# سازگار با Railway – توکن و چت‌آیدی از متغیرهای محیطی

import os, json, time, threading, datetime as dt
import requests, numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import telebot
from telebot import types

# =========================
# مسیرها و کانفیگ
# =========================

BASE_DIR   = os.path.abspath(os.path.dirname(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "data")
CHARTS_DIR = os.path.join(DATA_DIR, "charts")
PDF_DIR    = os.path.join(DATA_DIR, "pdf")

for d in [DATA_DIR, CHARTS_DIR, PDF_DIR]:
    os.makedirs(d, exist_ok=True)

CONFIG_PATH = os.path.join(DATA_DIR, "config_v6_1.json")

DEFAULT_CONFIG = {
    "symbols_15m": [
        "BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT","SOLUSDT","DOGEUSDT","DOTUSDT","MATICUSDT","LTCUSDT"
    ],
    "symbols_1h": [
        "BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT","SOLUSDT","DOGEUSDT","DOTUSDT","MATICUSDT","LTCUSDT"
    ],
    "symbols_4h": [
        "BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT","SOLUSDT","DOGEUSDT","DOTUSDT","MATICUSDT","LTCUSDT"
    ],
    "symbols_1d": [
        "BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT","SOLUSDT","DOGEUSDT","DOTUSDT","MATICUSDT","LTCUSDT"
    ],

    # فعال/غیرفعال بودن هر تایم‌فریم
    "enabled_15m": True,
    "enabled_1h": True,
    "enabled_4h": True,
    "enabled_1d": True,

    # lookback بر اساس روز/دوره، max_bars برای نمایش
    "lookback_15m": 3,
    "lookback_1h": 5,
    "lookback_4h": 15,
    "lookback_1d": 180,
    "max_bars": 300,

    # آلارم‌ها
    "alarm_wma_direction": True,
    "alarm_cross_sma20": False,
    "alarm_cross_sma100": False,
    "alarm_cross_sma200": False,
    "alarm_sma20_direction": False,
    "alarm_sma100_direction": False,
    "alarm_sma200_direction": False,

    # PDF
    "make_pdf_1h": True,
    "make_pdf_1d": True,

    # verbose
    "verbose_15m": True,
    "verbose_1h": True,
    "verbose_4h": True,
    "verbose_1d": True,

    # SmartLock
    "lock_timeout_sec": 600,
    "cycle_min_duration_sec": 5,

    # تایم‌فریم فعال (برای اجرای فوری از ربات اصلی)
    "active_interval": "15m",

    # chat_id اصلی
    "chat_id_main": None
}

def now_utc():
    return dt.datetime.now(dt.timezone.utc)

def now_utc_str():
    return now_utc().strftime("%Y-%m-%d %H:%M:%S")

def save_config(cfg: dict):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        cfg = DEFAULT_CONFIG.copy()
        cfg["chat_id_main"] = os.getenv("CHAT_ID_MAIN")
        save_config(cfg)
        return cfg
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_CONFIG.copy()

def reset_config():
    cfg = DEFAULT_CONFIG.copy()
    cfg["chat_id_main"] = os.getenv("CHAT_ID_MAIN")
    save_config(cfg)
    return cfg

# =========================
# ربات اصلی
# =========================

TOKEN_MAIN = (os.getenv("TOKEN_MAIN") or os.getenv("TOKEN_1H") or "").strip()
if not TOKEN_MAIN or ":" not in TOKEN_MAIN:
    raise ValueError("TOKEN_MAIN/TOKEN_1H تنظیم نشده یا اشتباه است؛ ربات اصلی نمی‌تواند ساخته شود.")

bot_main = telebot.TeleBot(TOKEN_MAIN, parse_mode="HTML")

LAST_ALARMS = {
    "15m": [],
    "1h": [],
    "4h": [],
    "1d": []
}

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
# راهنما
# =========================

HELP_TEXT = """
Modu Bazler v6.1 – نسخه‌ی کامل با یک ربات اصلی

📌 ربات:
- فقط یک ربات اصلی داریم؛ همهٔ پیام‌ها و عکس‌ها از همین ربات ارسال می‌شود.

🧭 منوی ربات اصلی:
- انتخاب تایم‌فریم فعال (15m / 1h / 4h / 1d)
- فعال/غیرفعال کردن هر تایم‌فریم
- اجرای فوری تایم‌فریم فعال
- اجرای فوری 15m / 1h / 4h / 1d
- مدیریت نمادهای هر تایم‌فریم
- تنظیم آلارم‌ها
- گزارش آلارم‌ها
- وضعیت سیستم
- تنظیمات پیشرفته
- اجرای چرخه‌ها (همه تایم‌فریم‌ها)
- ریست برنامه
- راهنما / رفرش منو

🔊 حالت پردازش (verbose):
- ON → پیام‌های پردازش + نمودار همه‌ی نمادها
- OFF → فقط نمودار نمادهای دارای آلارم

📄 PDF:
- برای سیکل‌های 1h و 1d در صورت فعال بودن، یک فایل PDF از همه‌ی نمودارها ساخته و ارسال می‌شود.
"""

# =========================
# منوی اصلی
# =========================

def send_main_menu(chat_id):
    cfg = load_config()
    active = cfg.get("active_interval", "15m")
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("انتخاب تایم‌فریم فعال", f"تایم‌فریم فعال: {active}")
    kb.row("فعال/غیرفعال کردن تایم‌فریم‌ها")
    kb.row("اجرای فوری تایم‌فریم فعال")
    kb.row("اجرای فوری 15m", "اجرای فوری 1h")
    kb.row("اجرای فوری 4h", "اجرای فوری 1d")
    kb.row("مدیریت نمادهای 15m", "مدیریت نمادهای 1h")
    kb.row("مدیریت نمادهای 4h", "مدیریت نمادهای 1d")
    kb.row("تنظیم آلارم‌ها", "گزارش آلارم‌ها")
    kb.row("وضعیت سیستم", "تنظیمات پیشرفته")
    kb.row("اجرای چرخه‌ها", "ریست برنامه")
    kb.row("راهنما", "رفرش منو")
    bot_main.send_message(chat_id, "منوی اصلی:", reply_markup=kb)

@bot_main.message_handler(commands=["start"])
def start_main(m):
    cfg = load_config()
    cfg["chat_id_main"] = m.chat.id
    save_config(cfg)
    bot_main.send_message(m.chat.id, HELP_TEXT)
    send_main_menu(m.chat.id)

@bot_main.message_handler(func=lambda m: m.text == "رفرش منو")
def refresh_main(m):
    send_main_menu(m.chat.id)

# =========================
# انتخاب تایم‌فریم فعال
# =========================

@bot_main.message_handler(func=lambda m: m.text == "انتخاب تایم‌فریم فعال")
def choose_active_interval(m):
    kb = types.InlineKeyboardMarkup()
    for tf in ["15m","1h","4h","1d"]:
        kb.add(types.InlineKeyboardButton(f"{tf}", callback_data=f"set_active_{tf}"))
    bot_main.send_message(m.chat.id, "تایم‌فریم فعال را انتخاب کنید:", reply_markup=kb)

@bot_main.callback_query_handler(func=lambda c: c.data.startswith("set_active_"))
def set_active_interval(c):
    cfg = load_config()
    tf = c.data.replace("set_active_", "")
    cfg["active_interval"] = tf
    save_config(cfg)
    bot_main.answer_callback_query(c.id, f"تایم‌فریم فعال: {tf}")
    send_main_menu(c.message.chat.id)

# =========================
# فعال/غیرفعال کردن تایم‌فریم‌ها
# =========================

@bot_main.message_handler(func=lambda m: m.text == "فعال/غیرفعال کردن تایم‌فریم‌ها")
def toggle_intervals_menu(m):
    cfg = load_config()
    kb = types.InlineKeyboardMarkup()
    for tf in ["15m","1h","4h","1d"]:
        key = f"enabled_{tf}"
        kb.add(types.InlineKeyboardButton(
            f"{tf} ({'ON' if cfg.get(key, True) else 'OFF'})",
            callback_data=f"toggle_tf_{tf}"
        ))
    bot_main.send_message(m.chat.id, "تایم‌فریم‌ها را فعال/غیرفعال کنید:", reply_markup=kb)

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
# ریست برنامه
# =========================

@bot_main.message_handler(func=lambda m: m.text == "ریست برنامه")
def reset_app(m):
    cfg = reset_config()
    cfg["chat_id_main"] = m.chat.id
    save_config(cfg)
    bot_main.send_message(m.chat.id, "برنامه و تنظیمات کامل ریست شد.")
    send_main_menu(m.chat.id)

# =========================
# مدیریت نمادها
# =========================

def get_symbols(cfg, group):
    return cfg[f"symbols_{group}"]

def set_symbols(cfg, group, symbols):
    cfg[f"symbols_{group}"] = symbols
    save_config(cfg)

def show_symbol_menu(chat_id, group):
    cfg = load_config()
    symbols = get_symbols(cfg, group)
    txt = f"نمادهای فعال در {group}:\n"
    txt += ", ".join(symbols) if symbols else "هیچ نمادی ثبت نشده است."
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(f"افزودن نماد به {group}", f"حذف نماد از {group}")
    kb.row(f"نمایش نمادهای {group}")
    kb.row("بازگشت به منوی اصلی")
    bot_main.send_message(chat_id, txt, reply_markup=kb)

@bot_main.message_handler(func=lambda m: m.text == "مدیریت نمادهای 15m")
def manage_15m(m): show_symbol_menu(m.chat.id, "15m")

@bot_main.message_handler(func=lambda m: m.text == "مدیریت نمادهای 1h")
def manage_1h(m): show_symbol_menu(m.chat.id, "1h")

@bot_main.message_handler(func=lambda m: m.text == "مدیریت نمادهای 4h")
def manage_4h(m): show_symbol_menu(m.chat.id, "4h")

@bot_main.message_handler(func=lambda m: m.text == "مدیریت نمادهای 1d")
def manage_1d(m): show_symbol_menu(m.chat.id, "1d")

def add_symbol_step(m, group):
    symbol = m.text.strip().upper()
    cfg = load_config()
    symbols = get_symbols(cfg, group)
    if symbol not in symbols:
        symbols.append(symbol)
        set_symbols(cfg, group, symbols)
        bot_main.send_message(m.chat.id, f"{symbol} به لیست {group} اضافه شد.")
    else:
        bot_main.send_message(m.chat.id, f"{symbol} قبلاً در لیست {group} وجود دارد.")
    show_symbol_menu(m.chat.id, group)

@bot_main.message_handler(func=lambda m: m.text.startswith("افزودن نماد به "))
def add_symbol_any(m):
    group = m.text.split()[-1]
    msg = bot_main.send_message(m.chat.id, "نماد را وارد کنید:")
    bot_main.register_next_step_handler(msg, lambda mm: add_symbol_step(mm, group))

def remove_symbol_step(m, group):
    symbol = m.text.strip().upper()
    cfg = load_config()
    symbols = get_symbols(cfg, group)
    if symbol in symbols:
        symbols.remove(symbol)
        set_symbols(cfg, group, symbols)
        bot_main.send_message(m.chat.id, f"{symbol} از لیست {group} حذف شد.")
    else:
        bot_main.send_message(m.chat.id, f"{symbol} در لیست {group} وجود ندارد.")
    show_symbol_menu(m.chat.id, group)

@bot_main.message_handler(func=lambda m: m.text.startswith("حذف نماد از "))
def remove_symbol_any(m):
    group = m.text.split()[-1]
    msg = bot_main.send_message(m.chat.id, "نماد مورد نظر را وارد کنید:")
    bot_main.register_next_step_handler(msg, lambda mm: remove_symbol_step(mm, group))

@bot_main.message_handler(func=lambda m: m.text.startswith("نمایش نمادهای "))
def show_symbols_any(m):
    group = m.text.split()[-1]
    cfg = load_config()
    symbols = get_symbols(cfg, group)
    txt = f"نمادهای {group}:\n"
    txt += ", ".join(symbols) if symbols else "هیچ نمادی ثبت نشده است."
    bot_main.send_message(m.chat.id, txt)

# =========================
# تنظیم آلارم‌ها
# =========================

@bot_main.message_handler(func=lambda m: m.text == "تنظیم آلارم‌ها")
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
    bot_main.send_message(m.chat.id, "آلارم‌ها را تنظیم کنید:", reply_markup=kb)

@bot_main.callback_query_handler(func=lambda c: c.data.startswith("alarm_"))
def toggle_alarm(c):
    cfg = load_config()
    key = c.data.replace("alarm_", "")
    cfg[key] = not cfg.get(key)
    save_config(cfg)
    bot_main.answer_callback_query(c.id, f"{key} -> {'ON' if cfg[key] else 'OFF'}")
    alarms_menu(c.message)

# =========================
# گزارش آلارم‌ها
# =========================

@bot_main.message_handler(func=lambda m: m.text == "گزارش آلارم‌ها")
def alarms_report(m):
    txt = ""
    for group in ["15m","1h","4h","1d"]:
        if LAST_ALARMS[group]:
            txt += f"آلارم‌های {group}:\n"
            for item in LAST_ALARMS[group]:
                txt += f"{item['symbol']} ({item['interval']}):\n"
                for a in item["alarms"]:
                    txt += f" - {a}\n"
                txt += f"زمان: {item['time']}\n\n"
    if not txt:
        txt = "هیچ آلارمی ثبت نشده است."
    bot_main.send_message(m.chat.id, txt)

# =========================
# وضعیت سیستم و تنظیمات پیشرفته
# =========================

@bot_main.message_handler(func=lambda m: m.text == "وضعیت سیستم")
def system_status(m):
    cfg = load_config()
    txt = "وضعیت سیستم:\n"
    txt += f"نمادهای 15m: {len(cfg['symbols_15m'])} (enabled: {cfg['enabled_15m']})\n"
    txt += f"نمادهای 1h: {len(cfg['symbols_1h'])} (enabled: {cfg['enabled_1h']})\n"
    txt += f"نمادهای 4h: {len(cfg['symbols_4h'])} (enabled: {cfg['enabled_4h']})\n"
    txt += f"نمادهای 1d: {len(cfg['symbols_1d'])} (enabled: {cfg['enabled_1d']})\n"
    txt += f"PDF 1h: {'ON' if cfg['make_pdf_1h'] else 'OFF'}\n"
    txt += f"PDF 1d: {'ON' if cfg['make_pdf_1d'] else 'OFF'}\n"
    txt += f"verbose 15m: {'ON' if cfg['verbose_15m'] else 'OFF'}\n"
    txt += f"verbose 1h: {'ON' if cfg['verbose_1h'] else 'OFF'}\n"
    txt += f"verbose 4h: {'ON' if cfg['verbose_4h'] else 'OFF'}\n"
    txt += f"verbose 1d: {'ON' if cfg['verbose_1d'] else 'OFF'}\n"
    txt += f"active_interval: {cfg.get('active_interval','15m')}\n"
    txt += f"lock_timeout_sec: {cfg.get('lock_timeout_sec', 600)}\n"
    txt += f"cycle_min_duration_sec: {cfg.get('cycle_min_duration_sec', 5)}\n"
    bot_main.send_message(m.chat.id, txt)

@bot_main.message_handler(func=lambda m: m.text == "تنظیمات پیشرفته")
def advanced_settings(m):
    cfg = load_config()
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(f"PDF 1h ({'ON' if cfg['make_pdf_1h'] else 'OFF'})", callback_data="adv_pdf_1h"))
    kb.add(types.InlineKeyboardButton(f"PDF 1d ({'ON' if cfg['make_pdf_1d'] else 'OFF'})", callback_data="adv_pdf_1d"))
    kb.add(types.InlineKeyboardButton(f"verbose 15m ({'ON' if cfg['verbose_15m'] else 'OFF'})", callback_data="adv_verbose_15m"))
    kb.add(types.InlineKeyboardButton(f"verbose 1h ({'ON' if cfg['verbose_1h'] else 'OFF'})", callback_data="adv_verbose_1h"))
    kb.add(types.InlineKeyboardButton(f"verbose 4h ({'ON' if cfg['verbose_4h'] else 'OFF'})", callback_data="adv_verbose_4h"))
    kb.add(types.InlineKeyboardButton(f"verbose 1d ({'ON' if cfg['verbose_1d'] else 'OFF'})", callback_data="adv_verbose_1d"))
    kb.add(types.InlineKeyboardButton("ریست کامل برنامه", callback_data="adv_reset_app"))
    bot_main.send_message(m.chat.id, "تنظیمات پیشرفته:", reply_markup=kb)

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
    bot_main.answer_callback_query(c.id, "تنظیمات اعمال شد.")
    advanced_settings(c.message)

# =========================
# راهنما
# =========================

@bot_main.message_handler(func=lambda m: m.text == "راهنما")
def help_menu(m):
    bot_main.send_message(m.chat.id, HELP_TEXT)

# =========================
# دیتا و اندیکاتورها (Binance + Matplotlib)
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
        rows = [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] for k in data]
        df = pd.DataFrame(rows, columns=["t","o","h","l","c","v"])
        df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True)
        df.set_index("t", inplace=True)
        return df.tail(max_bars)
    except Exception:
        return pd.DataFrame()

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if df.empty:
        return df
    df["SMA20"]  = df["c"].rolling(20).mean()
    df["SMA100"] = df["c"].rolling(100).mean()
    df["SMA200"] = df["c"].rolling(200).mean()
    df["WMA20"] = df["c"].rolling(20).apply(lambda x: np.average(x, weights=np.arange(1, len(x)+1)), raw=True)
    df["WMA20_slope"] = df["WMA20"].diff()
    delta = df["c"].diff()
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    roll_gain = pd.Series(gain, index=df.index).rolling(14).mean()
    roll_loss = pd.Series(loss, index=df.index).rolling(14).mean()
    rs = roll_gain / (roll_loss + 1e-9)
    df["RSI14"] = 100 - (100 / (1 + rs))
    ema12 = df["c"].ewm(span=12, adjust=False).mean()
    ema26 = df["c"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["MACD_signal"]
    return df

def create_matplotlib_chart(symbol: str, interval: str, lookback_days: int, max_bars: int, png_name: str):
    df = fetch_ohlc(symbol, interval, lookback_days, max_bars)
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
    fig = plt.figure(figsize=(8, 8))
    gs = fig.add_gridspec(3, 1, height_ratios=[3,1,1])

    ax_price = fig.add_subplot(gs[0])
    ax_rsi   = fig.add_subplot(gs[1], sharex=ax_price)
    ax_macd  = fig.add_subplot(gs[2], sharex=ax_price)

    # قیمت + SMA + WMA
    ax_price.plot(df.index, df["c"], color="black", label="Close")
    ax_price.plot(df.index, df["SMA20"],  color="blue",   label="SMA20")
    ax_price.plot(df.index, df["SMA100"], color="orange", label="SMA100")
    ax_price.plot(df.indexپلوی کن.

ویژگی‌ها اصلی (`bot_main`)** داریم؛ همه‌ ارسال می‌شود.
-م‌فریم‌ها) همگی **کار می‌کنند**.
- عکس‌ها با Matplotlib ساخته می‌شوند (بدly/kaleido) تا مشکل برای 1h و 1d، آ، منوی کامل، SmartLock، همه سرجایشان هستند.

---

```python
# -*- coding: utf-8 -*-
# Modu Bazler v6.1 – نسخه‌ی کامل با یک ربات اصلی، انتخاب و فعال/غیرفعال کردن تایم‌فریم‌ها، آلارم‌ها و نمودارها
# سازگار با Railway – توکن و چت‌آیدی از متغیرهای محیطی

import os, json, time, threading, datetime as dt
import requests, numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import telebot
from tele========

BASE_DIR   = os.path.abspath.join(DATA_DIR, ", "config_v6_1.json")

DEFAULT_CONFIGRPUSDT","ADAUSDT","SOLUSDT","DOGEUSDT","DOTUSDT","MATICUSDT","LTCUSDT"
    ],
    "symbols_1h": [
        "BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT","SOLUSDT","DOGEUSDT","DOTUSDT","MATICUSDT","LTCUSDT"
    ],
    "symbols_4h": [
        "BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT","SOLUSDT","DOGEUSDT","DOTUSDT","MATICUSDT","LTCUSDT"
    ],
    "symbols_1d": [
       DT","BNBUSDT","Xm": 3,
    "look "lookback_4h": 15,
    "lookback_1d": 180,
    "max_bars": 300,

    # آلارم‌ها
    "alarm_wma_direction": True,
    "alarm_sma200": False,
_direction": False,
    "alarm_sma100_direction": False,
    "alarm_sma,

    # PDF
    "make_pdf_1h": True1d": True,

    # verbose
    "verbose "verbose_1h": True_1d": True,

    "lock_timeout_sec": 5,

    # تای اجرای فوری از ر_interval": "15m اصلی
    "chat_iddef now_utc():
    return dt.datetime("%Y-%m-%d %H:%M open(CONFIG_PATHutf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
       () -> dict:
    if not os.path.exists["chat_id_main"]_ID_MAIN")
        cfg
    try:
       _PATH, "r", encoding            return json.load(f)
    except Exception DEFAULT_CONFIG.copy()

def reset_config cfg["chat_id_main"] = os.getenv("CHAT_ID_MAIN")
    save_config(cfg)
    return cfg========
# ربات اصلی
# =================_MAIN") or os.getenvstrip()
if not TOKEN_MAIN or ":" not    raise ValueError_1H تنظیم نشده یا اشتباه است؛ ربات(TOKEN_MAIN, parse_mode="HTML")

LAST_ALARMS = {
    "15m": [],
    "1 [],
    "1d": []
}

# =================Lock
# =========================

class SmartLock:
    def __init__(self):
        self.lock = threading.Lock()
        self.last_acquire = None

    def acquire(self, blocking=False):
        cfg = load_config()
        timeout = cfg.get("lock_timeout_sec", 600)
        if_acquire).total_seconds elapsed > timeout self.lock.release except:
                    pass
        ok)
        if ok:
.last_acquire = now_utc()
        return ok

    def release:
                self.lock.release()
            except:
                pass

CYCLE_LOCK(),
    "4h": SmartLock(),
    "1d":
# ================= = """
Modu Bazler v6.1 – نسخه‌ی کامل با یک ربات اصلی

📌 ربات:
- فقط یک ربات اصلی داریم؛ همهٔ پیام‌ها و عکس‌ها از همین ر:
- انتخاب تایم‌فریم فعال (15m / فوری تایم‌فریم فعالm / 1h / 4h / 1d
- مدیریت نمادهای هر تایم‌فریم
- تنظیم آلارم‌ها
- گزارش آلارم‌ها
- وضعیت چرخه‌ها (همه تای):
- ON → پیام‌های همه‌ی نمادها
- OFFم

📄 PDF:
- برایd در صورت فعال بودن، یک فایل PDF از و ارسال می‌شود.
"""

# =================
# ================= = cfg.get("active")
    kb = types(resize_keyboard=True)
    kb.row فعال", f"تایم‌ف}")
    kb.row(" تایم‌فریم‌ها")
 فوری تایم‌فریم فعال")
    kb.row("اجر 4h", "اجرای فوری 1d")
    kb.row 15m", "مدیریت نمادهای 1h")
    kb نمادهای 1d")
   لارم‌ها", "گزارش آلارم‌ها")
    kb.row("وضعیت سیستم.row("راهنما", "_main.send_message:", reply_markup=kb)

@bot_main.message=["start"])
def start_main"] = m.chat.id
    save_config    send_main_menu(m.chat.id)

@bot_main.message_handler(func=lambda m: m.text == "رفرش منو")
def refresh_main(m):
    send_main_menu(m.chat.id)

# =========================
# انتخاب# =========================

@bot_main.message_handler(func=lambda m: m.text == "انتخاب تایم‌فریم فعال")
_interval(m):
       for tf in ["15m","1h","4h",".add(types.Inline"{tf}", callback_main.send_message(m.chat.id, "تای کنید:", reply_markup_callback_query(c.idغیرفعال کردن تای(func=lambda m: m‌فریم‌ها")
def toggle_{tf}"
        kb(key, True) else 'OFF'})",
                   ))
    bot(m.chat.id, "تای_interval(c):
   .replace("toggle = f"enabled_{tf not cfg.get(key, True)
    save bot_main.answer_intervals_menu(c.message========

@bot_main.text == "ریست برنامه["chat_id_main"]========
# مدیریت_symbols(cfg, group[f"symbols_{group}"]

def set_symbols(cfg, group, symbols):
    cfg[f"symbols_{group}"] = symbols):
    cfg = load, group)
    txt = f"نمادهای فعال در {group}:\n"
    txt += ", ".join(symbols) if symbols else "هی است."
    kb = types, txt, reply_markup m: m.text == "مدیریت نمادهای 15mm(m): show_symbol.text == "مدیریت_symbol_menu(m.chat.text == "مدیریت_symbol_step(m, group()
    cfg = load = get_symbols(cfg, group)
    if symbol شد.")
    else:
        bot_main.send_message(m.chat.id, f"{symbol} قبلاً در لیست {group} وجود دارد.")
    show_symbol_menu(m.chat.id, group)

@bot_main.message_handler(func=lambda m: m.text.startswith("افزودن نماد به "))
def add_symbol_any(m):
    group = m.text.split()[-1]
    msg = bot_main.send_message(m.chat.id, "نماد را وارد کنید:")
    bot_main.register_next_step_handler(msg, lambda mm: add_symbol_step(mm, group))

def remove_symbol_step(m, group):
    symbol = m.text.strip().upper()
    cfg = load_config()
    symbols = get_symbols(cfg, group)
    if symbol in symbols:
        symbols.remove(symbol)
        set_symbols(cfg, group, symbols)
        bot_main.send_message(m.chat.id, f"{symbol} از لیست {group} حذف شد.")
    else:
        bot_main.send_message(m.chat.id, f"{symbol} در لیست {group} وجود ندارد.")
    show_symbol_menu(m.chat.id, group)

@bot_main.message_handler(func=lambda m: m.text.startswith("حذف نماد از "))
def remove_symbol_any(m):
    group = m.text.split()[-1]
    msg = bot_main.send_message(m.chat.id, "نماد مورد نظر را وارد کنید:")
    bot_main.register_next_step_handler(msg, lambda mm: remove_symbol_step(mm, group))

@bot_main.message_handler(func=lambda m: m.text.startswith("نمایش نمادهای "))
def show_symbols_any(m):
    group = m.text.split()[-1]
    cfg = load_config()
    symbols = get_symbols(cfg, group)
    txt = f"نمادهای {group}:\n"
    txt += ", ".join(symbols) if symbols else "هیچ نمادی ثبت نشده است."
    bot_main.send_message(m.chat.id, txt)

# =========================
# تنظیم آلارم‌ها
# =========================

@bot_main.message_handler(func=lambda m: m.text == "تنظیم آلارم‌ها")
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
    bot_main.send_message(m.chat.id, "آلارم‌ها را تنظیم کنید:", reply_markup=kb)

@bot_main.callback_query_handler(func=lambda c: c.data.startswith("alarm_"))
def toggle_alarm(c):
    cfg = load_config()
    key = c.data.replace("alarm_", "")
    cfg[key] = not cfg.get(key)
    save_config(cfg)
    bot_main.answer_callback_query(c.id, f"{key} -> {'ON' if cfg[key] else 'OFF'}")
    alarms_menu(c.message)

# =========================
# گزارش آلارم‌ها
# =========================

@bot_main.message_handler(func=lambda m: m.text == "گزارش آلارم‌ها")
def alarms_report(m):
    txt = ""
    for group in ["15m","1h","4h","1d"]:
        if LAST_ALARMS[group]:
            txt += f"آلارم‌های {group}:\n"
            for item in LAST_ALARMS[group]:
                txt += f"{item['symbol']} ({item['interval']}):\n"
                for a in item["alarms"]:
                    txt += f" - {a}\n"
                txt += f"زمان: {item['time']}\n\n"
    if not txt:
        txt = "هیچ آلارمی ثبت نشده است."
    bot_main.send_message(m.chat.id, txt)

# =========================
# وضعیت سیستم و تنظیمات پیشرفته
# =========================

@bot_main.message_handler(func=lambda m: m.text == "وضعیت سیستم")
def system_status(m):
    cfg = load_config()
    txt = "وضعیت سیستم:\n"
    txt += f"نمادهای 15m: {len(cfg['symbols_15m'])} (enabled: {cfg['enabled_15m']})\n"
    txt += f"نمادهای 1h: {len(cfg['symbols_1h'])} (enabled: {cfg['enabled_1h']})\n"
    txt += f"نمادهای 4h: {len(cfg['symbols_4h'])} (enabled: {cfg['enabled_4h']})\n"
    txt += f"نمادهای 1d: {len(cfg['symbols_1d'])} (enabled: {cfg['enabled_1d']})\n"
    txt += f"PDF 1h: {'ON' if cfg['make_pdf_1h'] else 'OFF'}\n"
    txt += f"PDF 1d: {'ON' if cfg['make_pdf_1d'] else 'OFF'}\n"
    txt += f"verbose 15m: {'ON' if cfg['verbose_15m'] else 'OFF'}\n"
    txt += f"verbose 1h: {'ON' if cfg['verbose_1h'] else 'OFF'}\n"
    txt += f"verbose 4h: {'ON' if cfg['verbose_4h'] else 'OFF'}\n"
    txt += f"verbose 1d: {'ON' if cfg['verbose_1d'] else 'OFF'}\n"
    txt += f"active_interval: {cfg.get('active_interval','15m')}\n"
    txt += f"lock_timeout_sec: {cfg.get('lock_timeout_sec', 600)}\n"
    txt += f"cycle_min_duration_sec: {cfg.get('cycle_min_duration_sec', 5)}\n"
    bot_main.send_message(m.chat.id, txt)

@bot_main.message_handler(func=lambda m: m.text == "تنظیمات پیشرفته")
def advanced_settings(m):
    cfg = load_config()
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(f"PDF 1h ({'ON' if cfg['make_pdf_1h'] else 'OFF'})", callback_data="adv_pdf_1h"))
    kb.add(types.InlineKeyboardButton(f"PDF 1d ({'ON' if cfg['make_pdf_1d'] else 'OFF'})", callback_data="adv_pdf_1d"))
    kb.add(types.InlineKeyboardButton(f"verbose 15m ({'ON' if cfg['verbose_15m'] else 'OFF'})", callback_data="adv_verbose_15m"))
    kb.add(types.InlineKeyboardButton(f"verbose 1h ({'ON' if cfg['verbose_1h'] else 'OFF'})", callback_data="adv_verbose_1h"))
    kb.add(types.InlineKeyboardButton(f"verbose 4h ({'ON' if cfg['verbose_4h'] else 'OFF'})", callback_data="adv_verbose_4h"))
    kb.add(types.InlineKeyboardButton(f"verbose 1d ({'ON' if cfg['verbose_1d'] else 'OFF'})", callback_data="adv_verbose_1d"))
    kb.add(types.InlineKeyboardButton("ریست کامل برنامه", callback_data="adv_reset_app"))
    bot_main.send_message(m.chat.id, "تنظیمات پیشرفته:", reply_markup=kb)

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
    bot_main.answer_callback_query(c.id, "تنظیمات اعمال شد.")
    advanced_settings(c.message)

# =========================
# راهنما
# =========================

@bot_main.message_handler(func=lambda m: m.text == "راهنما")
def help_menu(m):
    bot_main.send_message(m.chat.id, HELP_TEXT)

# =========================
# دیتا و اندیکاتورها (Binance + Matplotlib)
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
        rows = [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] for k in data]
        df = pd.DataFrame(rows, columns=["t","o","h","l","c","v"])
        df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True)
        df.set_index("t", inplace=True)
        return df.tail(max_bars)
    except Exception:
        return pd.DataFrame()

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if df.empty:
        return df
    df["SMA20"]  = df["c"].rolling(20).mean()
    df["SMA100"] = df["c"].rolling(100).mean()
    df["SMA200"] = df["c"].rolling(200).mean()
    df["WMA20"] = df["c"].rolling(20).apply(lambda x: np.average(x, weights=np.arange(1, len(x)+1)), raw=True)
    df["WMA20_slope"] = df["WMA20"].diff()
    delta = df["c"].diff()
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    roll_gain = pd.Series(gain, index=df.index).rolling(14).mean()
    roll_loss = pd.Series(loss, index=df.index).rolling(14).mean()
    rs = roll_gain / (roll_loss + 1e-9)
    df["RSI14"] = 100 - (100 / (1 + rs))
    ema12 = df["c"].ewm(span=12, adjust=False).mean()
    ema26 = df["c"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["MACD_signal"]
    return df

def create_matplotlib_chart(symbol: str, interval: str, lookback_days: int, max_bars: int, png_name: str):
    df = fetch_ohlc(symbol, interval, lookback_days, max_bars)
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
    fig = plt.figure(figsize=(8, 8))
    gs = fig.add_gridspec(3, 1, height_ratios=[3,1,1])

    ax_price = fig.add_subplot(gs[0])
    ax_rsi   = fig.add_subplot(gs[1], sharex=ax_price)
    ax_macd  = fig.add_subplot(gs[2], sharex=ax_price)

    # قیمت + SMA + WMA
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

def detect_alarms(cfg: dict, info: dict, group: str):
    alarms = []
    wma    = info["wma"]
    slope  = info["wma_slope"]
    sma20  = info["sma20"]
    sma100 = info["sma100"]
    sma200 = info["sma200"]
    if len(wma) < 3:
        return alarms

    if cfg.get("alarm_wma_direction", True):
        if slope[-2] < 0 and slope[-1] > 0:
            alarms.append("WMA20 جهت رو به بالا گرفت")
        if slope[-2] > 0 and slope[-1] < 0:
            alarms.append("WMA20 جهت رو به پایین گرفت")

    def cross(a, b):
        if len(a) < 2 or len(b) < 2:
            return False
        return (a[-2] - b[-2]) * (a[-1] - b[-1]) < 0

    if cfg.get("alarm_cross_sma20", False) and cross(wma, sma20):
        alarms.append("برخورد WMA20 با SMA20")
    if cfg.get("alarm_cross_sma100", False) and cross(wma, sma100):
        alarms.append("برخورد WMA20 با SMA100")
    if cfg.get("alarm_cross_sma200", False) and cross(wma, sma200):
        alarms.append("برخورد WMA20 با SMA200")

    def dir_change(arr, name):
        if len(arr) < 3:
            return
        d1 = arr[-1] - arr[-2]
        d2 = arr[-2] - arr[-3]
        if d2 < 0 and d1 > 0:
            alarms.append(f"{name} جهت رو به بالا گرفت")
        if d2 > 0 and d1 < 0:
            alarms.append(f"{name} جهت رو به پایین گرفت")

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
# اجرای سیکل‌ها (فقط با bot_main)
# =========================

def run_cycle(interval: str, manual: bool = False):
    cfg = load_config()
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
                f"شروع سیکل {interval} برای {len(symbols)} نماد...\n{now_utc_str()}")

        pdf_pages = None
        pdf_path = None
        if interval in ["1h","1d"] and cfg.get(f"make_pdf_{interval}", False) and chat_id:
            pdf_path = os.path.join(PDF_DIR, f"{interval}_cycle_{now_utc_str().replace(' ','_').replace(':','-')}.pdf")
            pdf_pages = PdfPages(pdf_path)

        for idx, sym in enumerate(symbols, start=1):
            info = create_matplotlib_chart(sym, interval, cfg[f"lookback_{interval}"], cfg["max_bars"], f"{interval}_{sym}.png")
            alarms = detect_alarms(cfg, info, interval)

            if pdf_pages:
                try:
                    img = plt.imread(info["png_path"])
                    fig_pdf, ax_pdf = plt.subplots(figsize=(8, 6))
                    ax_pdf.imshow(img)
                    ax_pdf.axis("off")
                    pdf_pages.savefig(fig_pdf)
                    plt.close(fig_pdf)
                except Exception:
                    pass

            if chat_id:
                if verbose or alarms:
                    try:
                        with open(info["png_path"], "rb") as img_file:
                            bot_main.send_photo(chat_id, img_file,
                                caption=f"{sym} – {interval}\n{now_utc_str()}")
                    except Exception:
                        pass
                if alarms:
                    txt = f"آلارم {interval} برای {sym}:\n" + "\n".join(f"- {a}" for a in alarms)
                    bot_main.send_message(chat_id, txt)

            if chat_id and idx % 5 == 0:
                bot_main.send_message(chat_id, f"پیشرفت {interval}: {idx}/{len(symbols)} نماد")

        if pdf_pages:
            try:
                pdf_pages.close()
                if chat_id and pdf_path:
                    with open(pdf_path, "rb") as pdf_file:
                        bot_main.send_document(chat_id, pdf_file,
                            caption=f"PDF سیکل {interval}\n{now_utc_str()}")
            except Exception:
                pass

        elapsed = (now_utc() - start_time).total_seconds()
        if chat_id:
            bot_main.send_message(chat_id,
                f"پایان سیکل {interval}.\nمدت زمان: {int(elapsed)} ثانیه")
    finally:
        lock.release