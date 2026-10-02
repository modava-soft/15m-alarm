# -*- coding: utf-8 -*-
# Modu Bazler v5.1 – نسخه‌ی پایدار با زمان‌بندی و قفل سیکل‌ها

import os, json, time, threading, datetime as dt
import requests, numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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

CONFIG_PATH = os.path.join(DATA_DIR, "config_v5_1.json")

DEFAULT_CONFIG = {
    "symbols_1h": [
        "BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT",
        "SOLUSDT","DOGEUSDT","DOTUSDT","MATICUSDT","LTCUSDT",
        "TRXUSDT","AVAXUSDT","LINKUSDT","ATOMUSDT","XMRUSDT",
        "ETCUSDT","XLMUSDT","FILUSDT","APTUSDT","NEARUSDT"
    ],
    "symbols_4h": [
        "BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT",
        "SOLUSDT","DOGEUSDT","DOTUSDT","MATICUSDT","LTCUSDT",
        "TRXUSDT","AVAXUSDT","LINKUSDT","ATOMUSDT","XMRUSDT",
        "ETCUSDT","XLMUSDT","FILUSDT","APTUSDT","NEARUSDT"
    ],
    "symbols_1d": [
        "BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT",
        "SOLUSDT","DOGEUSDT","DOTUSDT","MATICUSDT","LTCUSDT",
        "TRXUSDT","AVAXUSDT","LINKUSDT","ATOMUSDT","XMRUSDT",
        "ETCUSDT","XLMUSDT","FILUSDT","APTUSDT","NEARUSDT"
    ],
    "symbols_15m": [
        "BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT","SOLUSDT","DOGEUSDT","DOTUSDT","MATICUSDT","LTCUSDT",
        "TRXUSDT","AVAXUSDT","LINKUSDT","ATOMUSDT","XMRUSDT","ETCUSDT","XLMUSDT","FILUSDT","APTUSDT","NEARUSDT",
        "OPUSDT","ARBUSDT","SUIUSDT","PEPEUSDT","TONUSDT","UNIUSDT","AAVEUSDT","INJUSDT","RNDRUSDT","FTMUSDT",
        "NEOUSDT","GALAUSDT","SEIUSDT","TIAUSDT","PYTHUSDT","JTOUSDT","WIFUSDT","JUPUSDT","STRKUSDT","BLURUSDT",
        "RUNEUSDT","RAYUSDT","LDOUSDT","COMPUSDT","CRVUSDT","MKRUSDT","SNXUSDT","GMXUSDT","DYDXUSDT","ENSUSDT"
    ],

    "lookback_1h": 5,
    "lookback_4h": 15,
    "lookback_1d": 180,
    "lookback_15m": 3,
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

    "chat_id_1h": None,
    "chat_id_4h": None,
    "chat_id_1d": None,
    "chat_id_15m": None,

    "verbose_1h": True,
    "verbose_4h": True,
    "verbose_1d": True,
    "verbose_15m": True,

    "cycle_progress_batch": 5
}

def save_config(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def reset_config():
    cfg = DEFAULT_CONFIG.copy()
    save_config(cfg)
    return cfg

def now_utc():
    return dt.datetime.now(dt.timezone.utc)

def now_utc_str():
    return now_utc().strftime("%Y-%m-%d %H:%M:%S")

# =========================
# توکن‌ها و ربات‌ها
# =========================

TOKEN_1H   = (os.getenv("TOKEN_1H") or "").strip()
TOKEN_4H   = (os.getenv("TOKEN_4H") or "").strip()
TOKEN_1D   = (os.getenv("TOKEN_1D") or "").strip()
TOKEN_15M  = (os.getenv("TOKEN_15M") or "").strip()
ADMIN_CHAT = (os.getenv("ADMIN_CHAT_ID") or "").strip()

def create_bot(token: str):
    if not token or not isinstance(token, str):
        return None
    if any(ch.isspace() for ch in token):
        return None
    try:
        return telebot.TeleBot(token, parse_mode="HTML")
    except:
        return None

bot_1h  = create_bot(TOKEN_1H)
bot_4h  = create_bot(TOKEN_4H)
bot_1d  = create_bot(TOKEN_1D)
bot_15m = create_bot(TOKEN_15M)

LAST_ALARMS = {
    "1h": [],
    "4h": [],
    "1d": [],
    "15m": []
}

# قفل‌ها برای جلوگیری از اجرای هم‌زمان سیکل‌ها
CYCLE_LOCKS = {
    "1h": threading.Lock(),
    "4h": threading.Lock(),
    "1d": threading.Lock(),
    "15m": threading.Lock()
}

# =========================
# راهنما
# =========================

HELP_TEXT = """
Modu Bazler v5.1 – نسخه‌ی پایدار

📌 ربات‌ها:
- 1h: ربات اصلی مدیریت و منو
- 4h: ربات ۴ساعته
- 1d: ربات روزانه
- 15m: ربات ۱۵دقیقه‌ای

✅ ثبت چت هر ربات:
- در هر ربات دستور /start را بفرست تا chat_id ثبت شود.

🧭 منوی ربات 1h:
- چک یک نماد → بررسی پیشرفته یک نماد در 1h
- اجرای دستی 1h → اجرای کامل سیکل 1h (با PDF در صورت فعال بودن)
- اجرای فوری 4h / 1d / 15m → اجرای سیکل همان تایم‌فریم
- مدیریت نمادهای 1h / 4h / 1d / 15m → افزودن/حذف نمادها
- تنظیم آلارم‌ها → فعال/غیرفعال کردن انواع آلارم‌ها
- گزارش آلارم‌ها → نمایش آخرین آلارم‌های هر گروه
- وضعیت سیستم → نمایش تنظیمات و تعداد نمادها
- تنظیمات پیشرفته → کنترل PDF و verbose برای هر ربات
- اجرای چرخه‌ها → اجرای فوری همه‌ی تایم‌فریم‌ها
- ریست برنامه → بازگشت به تنظیمات اولیه

🔊 حالت پردازش (verbose):
- ON → پیام‌های پردازش + نمودار همه‌ی نمادها
- OFF → فقط نمودار نمادهای دارای آلارم، بدون پیام‌های میانی

📄 PDF:
- برای سیکل‌های 1h و 1d در صورت فعال بودن، یک فایل PDF از همه‌ی نمودارها ساخته و ارسال می‌شود.

⏱ زمان‌بندی خودکار:
- 1h: هر ساعت در دقیقه 22
- 4h: در ساعات 2، 6، 10، 14، 18، 22 (دقیقه 7)
- 1d: هر روز ساعت 1:05
- 15m: هر ۱۵ دقیقه
"""

# =========================
# منوی اصلی ربات 1h
# =========================

def send_main_menu(chat_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("چک یک نماد", "اجرای دستی 1h")
    kb.row("اجرای فوری 4h", "اجرای فوری 1d")
    kb.row("اجرای فوری 15m")
    kb.row("مدیریت نمادهای 1h", "مدیریت نمادهای 4h")
    kb.row("مدیریت نمادهای 1d", "مدیریت نمادهای 15m")
    kb.row("تنظیم آلارم‌ها", "گزارش آلارم‌ها")
    kb.row("وضعیت سیستم", "تنظیمات پیشرفته")
    kb.row("اجرای چرخه‌ها", "ریست برنامه")
    kb.row("راهنما", "رفرش منو")
    bot_1h.send_message(chat_id, "منوی اصلی:", reply_markup=kb)

@bot_1h.message_handler(commands=["start"])
def start_main(m):
    cfg = load_config()
    cfg["chat_id_1h"] = m.chat.id
    save_config(cfg)
    bot_1h.send_message(m.chat.id, HELP_TEXT)
    send_main_menu(m.chat.id)

@bot_1h.message_handler(commands=["refresh"])
@bot_1h.message_handler(func=lambda m: m.text == "رفرش منو")
def refresh_main(m):
    send_main_menu(m.chat.id)

# =========================
# استارت سایر ربات‌ها (ثبت chat_id)
# =========================

if bot_4h:
    @bot_4h.message_handler(commands=["start"])
    def start_4h(m):
        cfg = load_config()
        cfg["chat_id_4h"] = m.chat.id
        save_config(cfg)
        bot_4h.send_message(m.chat.id, "ربات ۴ساعته فعال شد.\n" + now_utc_str())

if bot_1d:
    @bot_1d.message_handler(commands=["start"])
    def start_1d(m):
        cfg = load_config()
        cfg["chat_id_1d"] = m.chat.id
        save_config(cfg)
        bot_1d.send_message(m.chat.id, "ربات روزانه فعال شد.\n" + now_utc_str())

if bot_15m:
    @bot_15m.message_handler(commands=["start"])
    def start_15m(m):
        cfg = load_config()
        cfg["chat_id_15m"] = m.chat.id
        save_config(cfg)
        bot_15m.send_message(m.chat.id, "ربات ۱۵دقیقه‌ای فعال شد.\n" + now_utc_str())

# =========================
# ریست برنامه
# =========================

@bot_1h.message_handler(func=lambda m: m.text == "ریست برنامه")
def reset_app(m):
    cfg = reset_config()
    cfg["chat_id_1h"] = m.chat.id
    save_config(cfg)
    bot_1h.send_message(m.chat.id, "برنامه و تنظیمات کامل ریست شد.")
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
    bot_1h.send_message(chat_id, txt, reply_markup=kb)

@bot_1h.message_handler(func=lambda m: m.text == "مدیریت نمادهای 1h")
def manage_1h(m): show_symbol_menu(m.chat.id, "1h")

@bot_1h.message_handler(func=lambda m: m.text == "مدیریت نمادهای 4h")
def manage_4h(m): show_symbol_menu(m.chat.id, "4h")

@bot_1h.message_handler(func=lambda m: m.text == "مدیریت نمادهای 1d")
def manage_1d(m): show_symbol_menu(m.chat.id, "1d")

@bot_1h.message_handler(func=lambda m: m.text == "مدیریت نمادهای 15m")
def manage_15m(m): show_symbol_menu(m.chat.id, "15m")

def add_symbol_step(m, group):
    symbol = m.text.strip().upper()
    cfg = load_config()
    symbols = get_symbols(cfg, group)
    if symbol not in symbols:
        symbols.append(symbol)
        set_symbols(cfg, group, symbols)
        bot_1h.send_message(m.chat.id, f"{symbol} به لیست {group} اضافه شد.")
    else:
        bot_1h.send_message(m.chat.id, f"{symbol} قبلاً در لیست {group} وجود دارد.")
    show_symbol_menu(m.chat.id, group)

@bot_1h.message_handler(func=lambda m: m.text.startswith("افزودن نماد به "))
def add_symbol_any(m):
    group = m.text.split()[-1]
    msg = bot_1h.send_message(m.chat.id, "نماد را وارد کنید:")
    bot_1h.register_next_step_handler(msg, lambda mm: add_symbol_step(mm, group))

def remove_symbol_step(m, group):
    symbol = m.text.strip().upper()
    cfg = load_config()
    symbols = get_symbols(cfg, group)
    if symbol in symbols:
        symbols.remove(symbol)
        set_symbols(cfg, group, symbols)
        bot_1h.send_message(m.chat.id, f"{symbol} از لیست {group} حذف شد.")
    else:
        bot_1h.send_message(m.chat.id, f"{symbol} در لیست {group} وجود ندارد.")
    show_symbol_menu(m.chat.id, group)

@bot_1h.message_handler(func=lambda m: m.text.startswith("حذف نماد از "))
def remove_symbol_any(m):
    group = m.text.split()[-1]
    msg = bot_1h.send_message(m.chat.id, "نماد مورد نظر را وارد کنید:")
    bot_1h.register_next_step_handler(msg, lambda mm: remove_symbol_step(mm, group))

@bot_1h.message_handler(func=lambda m: m.text.startswith("نمایش نمادهای "))
def show_symbols_any(m):
    group = m.text.split()[-1]
    cfg = load_config()
    symbols = get_symbols(cfg, group)
    txt = f"نمادهای {group}:\n"
    txt += ", ".join(symbols) if symbols else "هیچ نمادی ثبت نشده است."
    bot_1h.send_message(m.chat.id, txt)

# =========================
# تنظیم آلارم‌ها
# =========================

@bot_1h.message_handler(func=lambda m: m.text == "تنظیم آلارم‌ها")
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
    bot_1h.send_message(m.chat.id, "آلارم‌ها را تنظیم کنید:", reply_markup=kb)

@bot_1h.callback_query_handler(func=lambda c: c.data.startswith("alarm_"))
def toggle_alarm(c):
    cfg = load_config()
    key = c.data.replace("alarm_", "")
    cfg[key] = not cfg.get(key)
    save_config(cfg)
    bot_1h.answer_callback_query(c.id, f"{key} -> {'ON' if cfg[key] else 'OFF'}")
    alarms_menu(c.message)

# =========================
# گزارش آلارم‌ها
# =========================

@bot_1h.message_handler(func=lambda m: m.text == "گزارش آلارم‌ها")
def alarms_report(m):
    txt = ""
    for group in ["1h","4h","1d","15m"]:
        if LAST_ALARMS[group]:
            txt += f"آلارم‌های {group}:\n"
            for item in LAST_ALARMS[group]:
                txt += f"{item['symbol']} ({item['interval']}):\n"
                for a in item["alarms"]:
                    txt += f" - {a}\n"
                txt += f"زمان: {item['time']}\n\n"
    if not txt:
        txt = "هیچ آلارمی ثبت نشده است."
    bot_1h.send_message(m.chat.id, txt)

# =========================
# وضعیت سیستم و تنظیمات پیشرفته
# =========================

@bot_1h.message_handler(func=lambda m: m.text == "وضعیت سیستم")
def system_status(m):
    cfg = load_config()
    txt = "وضعیت سیستم:\n"
    txt += f"نمادهای 1h: {len(cfg['symbols_1h'])}\n"
    txt += f"نمادهای 4h: {len(cfg['symbols_4h'])}\n"
    txt += f"نمادهای 1d: {len(cfg['symbols_1d'])}\n"
    txt += f"نمادهای 15m: {len(cfg['symbols_15m'])}\n"
    txt += f"PDF 1h: {'ON' if cfg['make_pdf_1h'] else 'OFF'}\n"
    txt += f"PDF 1d: {'ON' if cfg['make_pdf_1d'] else 'OFF'}\n"
    txt += f"verbose 1h: {'ON' if cfg['verbose_1h'] else 'OFF'}\n"
    txt += f"verbose 4h: {'ON' if cfg['verbose_4h'] else 'OFF'}\n"
    txt += f"verbose 1d: {'ON' if cfg['verbose_1d'] else 'OFF'}\n"
    txt += f"verbose 15m: {'ON' if cfg['verbose_15m'] else 'OFF'}\n"
    bot_1h.send_message(m.chat.id, txt)

@bot_1h.message_handler(func=lambda m: m.text == "تنظیمات پیشرفته")
def advanced_settings(m):
    cfg = load_config()
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(f"PDF 1h ({'ON' if cfg['make_pdf_1h'] else 'OFF'})", callback_data="adv_pdf_1h"))
    kb.add(types.InlineKeyboardButton(f"PDF 1d ({'ON' if cfg['make_pdf_1d'] else 'OFF'})", callback_data="adv_pdf_1d"))
    kb.add(types.InlineKeyboardButton(f"verbose 1h ({'ON' if cfg['verbose_1h'] else 'OFF'})", callback_data="adv_verbose_1h"))
    kb.add(types.InlineKeyboardButton(f"verbose 4h ({'ON' if cfg['verbose_4h'] else 'OFF'})", callback_data="adv_verbose_4h"))
    kb.add(types.InlineKeyboardButton(f"verbose 1d ({'ON' if cfg['verbose_1d'] else 'OFF'})", callback_data="adv_verbose_1d"))
    kb.add(types.InlineKeyboardButton(f"verbose 15m ({'ON' if cfg['verbose_15m'] else 'OFF'})", callback_data="adv_verbose_15m"))
    kb.add(types.InlineKeyboardButton("ریست کامل برنامه", callback_data="adv_reset_app"))
    bot_1h.send_message(m.chat.id, "تنظیمات پیشرفته:", reply_markup=kb)

@bot_1h.callback_query_handler(func=lambda c: c.data.startswith("adv_"))
def advanced_settings_handler(c):
    cfg = load_config()
    if c.data == "adv_pdf_1h":
        cfg["make_pdf_1h"] = not cfg["make_pdf_1h"]
    elif c.data == "adv_pdf_1d":
        cfg["make_pdf_1d"] = not cfg["make_pdf_1d"]
    elif c.data == "adv_verbose_1h":
        cfg["verbose_1h"] = not cfg["verbose_1h"]
    elif c.data == "adv_verbose_4h":
        cfg["verbose_4h"] = not cfg["verbose_4h"]
    elif c.data == "adv_verbose_1d":
        cfg["verbose_1d"] = not cfg["verbose_1d"]
    elif c.data == "adv_verbose_15m":
        cfg["verbose_15m"] = not cfg["verbose_15m"]
    elif c.data == "adv_reset_app":
        cfg = reset_config()
    save_config(cfg)
    bot_1h.answer_callback_query(c.id, "تنظیمات اعمال شد.")
    advanced_settings(c.message)

# =========================
# راهنما
# =========================

@bot_1h.message_handler(func=lambda m: m.text == "راهنما")
def help_menu(m):
    bot_1h.send_message(m.chat.id, HELP_TEXT)

# =========================
# دیتا، اندیکاتورها، نمودار
# =========================

def _binance_interval(i: str) -> str:
    return {"1h": "1h", "4h": "4h", "1d": "1d", "15m": "15m"}[i]

def _kucoin_interval(i: str) -> str:
    return {"1h": "1hour", "4h": "4hour", "1d": "1day", "15m": "15min"}[i]

def fetch_ohlc(symbol: str, interval: str, lookback_days: int, max_bars: int) -> pd.DataFrame:
    limit = max(200, max_bars)
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
        return df
    except:
        pass
    try:
        sym = symbol.replace("USDT", "-USDT")
        end = int(now_utc().timestamp())
        start = end - 60 * 60 * (limit + 10)
        url = "https://api.kucoin.com/api/v1/market/candles"
        r = requests.get(url, params={
            "symbol": sym,
            "type": _kucoin_interval(interval),
            "startAt": start,
            "endAt": end
        }, timeout=10)
        r.raise_for_status()
        data = r.json()["data"]
        rows = [[int(k[0]), float(k[1]), float(k[3]), float(k[4]), float(k[2]), float(k[5])] for k in data]
        df = pd.DataFrame(rows, columns=["t","o","h","l","c","v"])
        df["t"] = pd.to_datetime(df["t"], unit="s", utc=True)
        df.sort_values("t", inplace=True)
        df.set_index("t", inplace=True)
        return df
    except:
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

def create_plotly_chart(symbol: str, interval: str, lookback_days: int, max_bars: int, png_name: str):
    df = fetch_ohlc(symbol, interval, lookback_days, max_bars)
    if df.empty:
        df = pd.DataFrame(columns=["o","h","l","c","v"])
        df.index = pd.to_datetime([])
    else:
        df = df[["o","h","l","c","v"]]
    df = compute_indicators(df)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6,0.2,0.2], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(x=df.index, open=df["o"], high=df["h"], low=df["l"], close=df["c"], name="Price"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA20"],  mode="lines", name="SMA20",  line=dict(color="blue")),   row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA100"], mode="lines", name="SMA100", line=dict(color="orange")), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA200"], mode="lines", name="SMA200", line=dict(color="purple")), row=1, col=1)
    wma   = df["WMA20"]
    slope = df["WMA20_slope"]
    wma_up   = wma.where(slope >= 0)
    wma_down = wma.where(slope < 0)
    fig.add_trace(go.Scatter(x=df.index, y=wma_up,   mode="lines", name="WMA20 Up",   line=dict(color="green", width=2, dash="dot")), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=wma_down, mode="lines", name="WMA20 Down", line=dict(color="red",   width=2, dash="dot")), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["RSI14"], mode="lines", name="RSI14", line=dict(color="brown")), row=2, col=1)
    fig.add_hline(y=70, line=dict(color="red", dash="dash"), row=2, col=1)
    fig.add_hline(y=30, line=dict(color="green", dash="dash"), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD"],        mode="lines", name="MACD",   line=dict(color="black")),   row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD_signal"], mode="lines", name="Signal", line=dict(color="magenta")), row=3, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df["MACD_hist"], name="Hist", marker_color="gray"), row=3, col=1)
    fig.update_layout(title=f"{symbol} – {interval}", xaxis_rangeslider_visible=False, template="plotly_white", height=1000)
    fig.add_annotation(text=f"{symbol} – {interval}", xref="paper", yref="paper", x=0.5, y=1.05, showarrow=False, font=dict(size=30, color="black"))
    fig.update_yaxes(side="right", showgrid=True)
    png_path = os.path.join(CHARTS_DIR, png_name)
    try:
        fig.write_image(png_path, width=1800, height=1100, scale=3)
    except:
        pass
    return {
        "symbol": symbol,
        "interval": interval,
        "png_path": png_path,
        "created_at": now_utc_str(),
        "wma": df["WMA20"].tolist() if "WMA20" in df.columns else [],
        "wma_slope": df["WMA20_slope"].tolist() if "WMA20_slope" in df.columns else [],
        "sma20": df["SMA20"].tolist() if "SMA20" in df.columns else [],
        "sma100": df["SMA100"].tolist() if "SMA100" in df.columns else [],
        "sma200": df["SMA200"].tolist() if "SMA200" in df.columns else []
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
# اجرای سیکل‌ها با قفل (verbose ON/OFF)
# =========================

def run_cycle(group: str, bot, chat_id: int, symbols: list, interval: str, lookback_days: int, max_bars: int, make_pdf: bool):
    lock = CYCLE_LOCKS.get(group)
    if lock is None:
        return
    if not lock.acquire(blocking=False):
        # اگر سیکل قبلی هنوز در حال اجراست، سیکل جدید را نادیده بگیر
        return
    try:
        cfg = load_config()
        verbose = cfg.get(f"verbose_{group}", True)
        if chat_id is None:
            return
        if verbose:
            bot.send_message(chat_id, f"شروع چرخه {group}\n{now_utc_str()} UTC")
        unique_symbols = list(dict.fromkeys(symbols))
        total = len(unique_symbols)
        processed = 0
        batch_size = cfg.get("cycle_progress_batch", 5)
        pdf = None
        pdf_filename = None
        if make_pdf and group in ["1h","1d"]:
            pdf_filename = os.path.join(PDF_DIR, f"{group}_{now_utc().strftime('%Y%m%d_%H%M%S')}.pdf")
            pdf = PdfPages(pdf_filename)
        for sym in unique_symbols:
            processed += 1
            if verbose and (processed % batch_size == 0 or processed == 1 or processed == total):
                bot.send_message(chat_id, f"چرخه {group}: {processed}/{total} نماد، {total - processed} باقی مانده.")
            ts = now_utc().strftime("%Y%m%d_%H%M%S")
            png = f"{group}_{sym}_{ts}.png"
            info = create_plotly_chart(sym, interval, lookback_days, max_bars, png)
            alarms = detect_alarms(cfg, info, group)
            if verbose or alarms:
                caption = f"{sym} ({group})"
                if alarms:
                    caption += "\n" + "\n".join(alarms)
                else:
                    caption += " – بدون آلارم"
                try:
                    with open(info["png_path"], "rb") as f:
                        bot.send_photo(chat_id, f, caption=caption)
                except:
                    pass
            if pdf is not None:
                try:
                    img = plt.imread(info["png_path"])
                    fig, ax = plt.subplots(figsize=(10,6))
                    ax.imshow(img); ax.axis("off"); ax.set_title(f"{sym} – {group}")
                    pdf.savefig(fig); plt.close(fig)
                except:
                    pass
            time.sleep(0.3)
        if pdf is not None:
            try:
                pdf.close()
                with open(pdf_filename, "rb") as f:
                    bot.send_document(chat_id, f, caption=f"گزارش PDF کامل سیکل {group}")
            except:
                pass
        if verbose:
            bot.send_message(chat_id, f"پایان چرخه {group}")
    finally:
        lock.release()

# =========================
# تک نماد و اجراهای فوری
# =========================

@bot_1h.message_handler(func=lambda m: m.text == "چک یک نماد")
def check_single_symbol(m):
    msg = bot_1h.send_message(m.chat.id, "نماد مورد نظر را وارد کنید (مثلاً BTCUSDT):")
    bot_1h.register_next_step_handler(msg, process_single_symbol)

def process_single_symbol(m):
    symbol = m.text.strip().upper()
    cfg = load_config()
    bot_1h.send_message(m.chat.id, f"در حال بررسی {symbol} در تایم‌فریم 1h ...")
    ts = now_utc().strftime("%Y%m%d_%H%M%S")
    png = f"single_1h_{symbol}_{ts}.png"
    info = create_plotly_chart(symbol, "1h", cfg["lookback_1h"], cfg["max_bars"], png)
    try:
        with open(info["png_path"], "rb") as f:
            bot_1h.send_photo(m.chat.id, f, caption=f"{symbol} – بررسی 1h")
    except:
        pass
    bot_1h.send_message(m.chat.id, "بررسی تک نماد پایان یافت.")

@bot_1h.message_handler(func=lambda m: m.text == "اجرای دستی 1h")
def manual_1h(m):
    cfg = load_config()
    chat = cfg.get("chat_id_1h") or m.chat.id
    threading.Thread(
        target=run_cycle,
        args=("1h", bot_1h, chat, cfg["symbols_1h"], "1h", cfg["lookback_1h"], cfg["max_bars"], cfg.get("make_pdf_1h", True)),
        daemon=True
    ).start()

@bot_1h.message_handler(func=lambda m: m.text == "اجرای فوری 4h")
def manual_4h(m):
    cfg = load_config()
    chat = cfg.get("chat_id_4h") or m.chat.id
    if bot_4h:
        threading.Thread(
            target=run_cycle,
            args=("4h", bot_4h, chat, cfg["symbols_4h"], "4h", cfg["lookback_4h"], cfg["max_bars"], False),
            daemon=True
        ).start()
    else:
        bot_1h.send_message(m.chat.id, "توکن ربات 4h تنظیم نشده یا ربات ساخته نشده است.")

@bot_1h.message_handler(func=lambda m: m.text == "اجرای فوری 1d")
def manual_1d(m):
    cfg = load_config()
    chat = cfg.get("chat_id_1d") or m.chat.id
    if bot_1d:
        threading.Thread(
            target=run_cycle,
            args=("1d", bot_1d, chat, cfg["symbols_1d"], "1d", cfg["lookback_1d"], cfg["max_bars"], cfg.get("make_pdf_1d", True)),
            daemon=True
        ).start()
    else:
        bot_1h.send_message(m.chat.id, "توکن ربات 1d تنظیم نشده یا ربات ساخته نشده است.")

@bot_1h.message_handler(func=lambda m: m.text == "اجرای فوری 15m")
def manual_15m(m):
    cfg = load_config()
    chat = cfg.get("chat_id_15m") or m.chat.id
    if bot_15m:
        threading.Thread(
            target=run_cycle,
            args=("15m", bot_15m, chat, cfg["symbols_15m"], "15m", cfg["lookback_15m"], cfg["max_bars"], False),
            daemon=True
        ).start()
        bot_1h.send_message(m.chat.id, "اجرای فوری چرخه 15m شروع شد.")
    else:
        bot_1h.send_message(m.chat.id, "توکن ربات 15m تنظیم نشده یا ربات ساخته نشده است.")

# =========================
# دکمه اجرای چرخه‌ها (همه‌ی تایم‌فریم‌ها)
# =========================

@bot_1h.message_handler(func=lambda m: m.text == "اجرای چرخه‌ها")
def run_all_cycles(m):
    cfg = load_config()
    if cfg.get("chat_id_1h"):
        threading.Thread(target=run_cycle, args=("1h", bot_1h, cfg["chat_id_1h"], cfg["symbols_1h"], "1h", cfg["lookback_1h"], cfg["max_bars"], cfg.get("make_pdf_1h", True)), daemon=True).start()
    if cfg.get("chat_id_4h") and bot_4h:
        threading.Thread(target=run_cycle, args=("4h", bot_4h, cfg["chat_id_4h"], cfg["symbols_4h"], "4h", cfg["lookback_4h"], cfg["max_bars"], False), daemon=True).start()
    if cfg.get("chat_id_1d") and bot_1d:
        threading.Thread(target=run_cycle, args=("1d", bot_1d, cfg["chat_id_1d"], cfg["symbols_1d"], "1d", cfg["lookback_1d"], cfg["max_bars"], cfg.get("make_pdf_1d", True)), daemon=True).start()
    if cfg.get("chat_id_15m") and bot_15m:
        threading.Thread(target=run_cycle, args=("15m", bot_15m, cfg["chat_id_15m"], cfg["symbols_15m"], "15m", cfg["lookback_15m"], cfg["max_bars"], False), daemon=True).start()
    bot_1h.send_message(m.chat.id, "اجرای چرخه‌ها برای همه‌ی تایم‌فریم‌ها شروع شد.")

# =========================
# زمان‌بندی خودکار پایدار
# =========================

def scheduler_loop():
    last_run = {
        "1h": None,
        "4h": None,
        "1d": None,
        "15m": None
    }
    while True:
        try:
            cfg = load_config()
            now = now_utc()
            minute = now.minute
            second = now.second
            hour   = now.hour

            # پنجره‌ی ۲۰ ثانیه‌ای برای هر تریگر تا از دست نرود
            def should_run(key, window_sec=20):
                lr = last_run[key]
                if lr is None:
                    return True
                return (now - lr).total_seconds() > window_sec

            # 1h – هر ساعت در دقیقه 22
            if minute == 22 and second < 20 and should_run("1h"):
                if bot_1h and cfg.get("chat_id_1h"):
                    threading.Thread(
                        target=run_cycle,
                        args=("1h", bot_1h, cfg["chat_id_1h"], cfg["symbols_1h"], "1h", cfg["lookback_1h"], cfg["max_bars"], cfg.get("make_pdf_1h", True)),
                        daemon=True
                    ).start()
                    last_run["1h"] = now

            # 4h – در ساعات 2، 6، 10، 14، 18، 22 (دقیقه 7)
            if minute == 7 and second < 20 and hour in [2,6,10,14,18,22] and should_run("4h"):
                if bot_4h and cfg.get("chat_id_4h"):
                    threading.Thread(
                        target=run_cycle,
                        args=("4h", bot_4h, cfg["chat_id_4h"], cfg["symbols_4h"], "4h", cfg["lookback_4h"], cfg["max_bars"], False),
                        daemon=True
                    ).start()
                    last_run["4h"] = now

            # 1d – هر روز ساعت 1:05
            if hour == 1 and minute == 5 and second < 20 and should_run("1d", window_sec=3600):
                if bot_1d and cfg.get("chat_id_1d"):
                    threading.Thread(
                        target=run_cycle,
                        args=("1d", bot_1d, cfg["chat_id_1d"], cfg["symbols_1d"], "1d", cfg["lookback_1d"], cfg["max_bars"], cfg.get("make_pdf_1d", True)),
                        daemon=True
                    ).start()
                    last_run["1d"] = now

            # 15m – هر ۱۵ دقیقه
            if minute % 15 == 0 and second < 20 and should_run("15m"):
                if bot_15m and cfg.get("chat_id_15m"):
                    threading.Thread(
                        target=run_cycle,
                        args=("15m", bot_15m, cfg["chat_id_15m"], cfg["symbols_15m"], "15m", cfg["lookback_15m"], cfg["max_bars"], False),
                        daemon=True
                    ).start()
                    last_run["15m"] = now

            time.sleep(5)
        except:
            time.sleep(10)

# =========================
# راه‌اندازی نهایی
# =========================

if __name__ == "__main__":
    if ADMIN_CHAT and bot_1h:
        try:
            bot_1h.send_message(ADMIN_CHAT, "Modu Bazler v5.1 – ربات اصلی راه‌اندازی شد.")
        except:
            pass
    if bot_1h:
        threading.Thread(target=bot_1h.infinity_polling, daemon=True).start()
    if bot_4h:
        threading.Thread(target=bot_4h.infinity_polling, daemon=True).start()
    if bot_1d:
        threading.Thread(target=bot_1d.infinity_polling, daemon=True).start()
    if bot_15m:
        threading.Thread(target=bot_15m.infinity_polling, daemon=True).start()
    threading.Thread(target=scheduler_loop, daemon=True).start()
    while True:
        time.sleep(60)