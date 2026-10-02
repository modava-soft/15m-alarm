# -*- coding: utf-8 -*-
# Modu Bazler v5.3 – Optimized Single Bot Version
# Simple, stable, Railway-friendly

import os, json, threading, datetime as dt
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

CONFIG_PATH = os.path.join(DATA_DIR, "config_v5_3.json")

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

    "make_pdf_1h": True,
    "make_pdf_1d": True,

    "verbose_15m": True,
    "verbose_1h": True,
    "verbose_4h": True,
    "verbose_1d": True,

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
# Bot
# =========================

TOKEN_MAIN = (os.getenv("TOKEN_MAIN") or os.getenv("TOKEN_1H") or "").strip()
if not TOKEN_MAIN or ":" not in TOKEN_MAIN:
    raise ValueError("TOKEN_MAIN is missing or invalid")

bot = telebot.TeleBot(TOKEN_MAIN, parse_mode="HTML")

LAST_ALARMS = {"15m": [], "1h": [], "4h": [], "1d": []}

# =========================
# Menu
# =========================

HELP_TEXT = """
Modu Bazler v5.3 – Optimized Single Bot

دستورات اصلی:
- /start → ثبت chat_id و نمایش منو
- اجرای فوری 15m / 1h / 4h / 1d
- فعال/غیرفعال کردن تایم‌فریم‌ها
- تنظیم آلارم WMA و کراس‌ها
- ساخت PDF برای 1h و 1d
"""

def send_main_menu(chat_id):
    cfg = load_config()
    active = cfg.get("active_interval", "15m")
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("انتخاب تایم‌فریم فعال", f"تایم‌فریم فعال: {active}")
    kb.row("فعال/غیرفعال کردن تایم‌فریم‌ها")
    kb.row("اجرای فوری تایم‌فریم فعال")
    kb.row("اجرای فوری 15m", "اجرای فوری 1h")
    kb.row("اجرای فوری 4h", "اجرای فوری 1d")
    kb.row("تنظیم آلارم‌ها", "گزارش آلارم‌ها")
    kb.row("وضعیت سیستم", "ریست برنامه")
    kb.row("راهنما", "رفرش منو")
    bot.send_message(chat_id, "منوی اصلی:", reply_markup=kb)

@bot.message_handler(commands=["start"])
def start_main(m):
    cfg = load_config()
    cfg["chat_id_main"] = m.chat.id
    save_config(cfg)
    bot.send_message(m.chat.id, HELP_TEXT)
    send_main_menu(m.chat.id)

@bot.message_handler(func=lambda m: m.text == "رفرش منو")
def refresh_main(m):
    send_main_menu(m.chat.id)

# =========================
# انتخاب تایم‌فریم فعال
# =========================

@bot.message_handler(func=lambda m: m.text == "انتخاب تایم‌فریم فعال")
def choose_active_interval(m):
    kb = types.InlineKeyboardMarkup()
    for tf in ["15m","1h","4h","1d"]:
        kb.add(types.InlineKeyboardButton(tf, callback_data=f"set_active_{tf}"))
    bot.send_message(m.chat.id, "تایم‌فریم فعال را انتخاب کنید:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_active_"))
def set_active_interval(c):
    cfg = load_config()
    tf = c.data.replace("set_active_", "")
    cfg["active_interval"] = tf
    save_config(cfg)
    bot.answer_callback_query(c.id, f"تایم‌فریم فعال: {tf}")
    send_main_menu(c.message.chat.id)

# =========================
# فعال/غیرفعال کردن تایم‌فریم‌ها
# =========================

@bot.message_handler(func=lambda m: m.text == "فعال/غیرفعال کردن تایم‌فریم‌ها")
def toggle_intervals_menu(m):
    cfg = load_config()
    kb = types.InlineKeyboardMarkup()
    for tf in ["15m","1h","4h","1d"]:
        key = f"enabled_{tf}"
        kb.add(types.InlineKeyboardButton(
            f"{tf} ({'ON' if cfg.get(key, True) else 'OFF'})",
            callback_data=f"toggle_tf_{tf}"
        ))
    bot.send_message(m.chat.id, "تایم‌فریم‌ها را فعال/غیرفعال کنید:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("toggle_tf_"))
def toggle_interval(c):
    cfg = load_config()
    tf = c.data.replace("toggle_tf_", "")
    key = f"enabled_{tf}"
    cfg[key] = not cfg.get(key, True)
    save_config(cfg)
    bot.answer_callback_query(c.id, f"{tf} -> {'ON' if cfg[key] else 'OFF'}")
    toggle_intervals_menu(c.message)

# =========================
# تنظیم آلارم‌ها
# =========================

@bot.message_handler(func=lambda m: m.text == "تنظیم آلارم‌ها")
def alarms_menu(m):
    cfg = load_config()
    kb = types.InlineKeyboardMarkup()
    for key in [
        "alarm_wma_direction",
        "alarm_cross_sma20",
        "alarm_cross_sma100",
        "alarm_cross_sma200"
    ]:
        kb.add(types.InlineKeyboardButton(
            f"{key} ({'ON' if cfg.get(key) else 'OFF'})",
            callback_data=f"alarm_{key}"
        ))
    bot.send_message(m.chat.id, "آلارم‌ها را تنظیم کنید:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("alarm_"))
def toggle_alarm(c):
    cfg = load_config()
    key = c.data.replace("alarm_", "")
    cfg[key] = not cfg.get(key)
    save_config(cfg)
    bot.answer_callback_query(c.id, f"{key} -> {'ON' if cfg[key] else 'OFF'}")
    alarms_menu(c.message)

# =========================
# گزارش آلارم‌ها
# =========================

@bot.message_handler(func=lambda m: m.text == "گزارش آلارم‌ها")
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
    bot.send_message(m.chat.id, txt)

# =========================
# وضعیت سیستم
# =========================

@bot.message_handler(func=lambda m: m.text == "وضعیت سیستم")
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
    bot.send_message(m.chat.id, txt)

# =========================
# ریست برنامه
# =========================

@bot.message_handler(func=lambda m: m.text == "ریست برنامه")
def reset_app(m):
    cfg = reset_config()
    cfg["chat_id_main"] = m.chat.id
    save_config(cfg)
    bot.send_message(m.chat.id, "برنامه ریست شد.")
    send_main_menu(m.chat.id)

# =========================
# راهنما
# =========================

@bot.message_handler(func=lambda m: m.text == "راهنما")
def help_menu(m):
    bot.send_message(m.chat.id, HELP_TEXT)

# =========================
# دیتا و اندیکاتورها
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
    df["WMA20"] = df["c"].rolling(20).apply(
        lambda x: np.average(x, weights=np.arange(1, len(x)+1)),
        raw=True
    )
    df["WMA20_slope"] = df["WMA20"].diff()
    return df

def create_chart(symbol: str, interval: str, lookback_days: int, max_bars: int, png_name: str):
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

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(df.index, df["c"], color="black", label="Close")
    ax.plot(df.index, df["SMA20"],  color="blue",   label="SMA20")
    ax.plot(df.index, df["SMA100"], color="orange", label="SMA100")
    ax.plot(df.index, df["SMA200"], color="purple", label="SMA200")

    wma   = df["WMA20"]
    slope = df["WMA20_slope"]
    wma_up   = wma.where(slope >= 0)
    wma_down = wma.where(slope < 0)
    ax.plot(df.index, wma_up,   color="green", linestyle="--", label="WMA20 Up")
    ax.plot(df.index, wma_down, color="red",   linestyle="--", label="WMA20 Down")

    ax.set_title(f"{symbol} – {interval}")
    ax.grid(True)
    ax.legend(loc="upper left")

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

    if alarms:
        LAST_ALARMS[group] = [{
            "symbol": info["symbol"],
            "interval": info["interval"],
            "time": info["created_at"],
            "alarms": alarms
        }]
    return alarms

# =========================
# اجرای سیکل
# =========================

def run_cycle(interval: str):
    cfg = load_config()
    if not cfg.get(f"enabled_{interval}", True):
        return

    symbols = cfg.get(f"symbols_{interval}", [])
    chat_id = cfg.get("chat_id_main")
    verbose = cfg.get(f"verbose_{interval}", True)

    if chat_id:
        bot.send_message(chat_id,
            f"شروع سیکل {interval} برای {len(symbols)} نماد...\n{now_utc_str()}")

    pdf_pages = None
    pdf_path = None
    if interval in ["1h","1d"] and cfg.get(f"make_pdf_{interval}", False) and chat_id:
        pdf_path = os.path.join(PDF_DIR, f"{interval}_cycle_{now_utc_str().replace(' ','_').replace(':','-')}.pdf")
        pdf_pages = PdfPages(pdf_path)

    for idx, sym in enumerate(symbols, start=1):
        info = create_chart(sym, interval, cfg[f"lookback_{interval}"], cfg["max_bars"], f"{interval}_{sym}.png")
        alarms = detect_alarms(cfg, info, interval)

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

        if chat_id:
            if verbose or alarms:
                try:
                    with open(info["png_path"], "rb") as img_file:
                        bot.send_photo(chat_id, img_file,
                            caption=f"{sym} – {interval}\n{now_utc_str()}")
                except:
                    pass
            if alarms:
                txt = f"آلارم {interval} برای {sym}:\n" + "\n".join(f"- {a}" for a in alarms)
                bot.send_message(chat_id, txt)

        if chat_id and idx % 5 == 0:
            bot.send_message(chat_id, f"پیشرفت {interval}: {idx}/{len(symbols)} نماد")

    if pdf_pages:
        try:
            pdf_pages.close()
            if chat_id and pdf_path:
                with open(pdf_path, "rb") as pdf_file:
                    bot.send_document(chat_id, pdf_file,
                        caption=f"PDF سیکل {interval}\n{now_utc_str()}")
        except:
            pass

    if chat_id:
        bot.send_message(chat_id, f"پایان سیکل {interval}.\n{now_utc_str()}")

# =========================
# اجرای فوری
# =========================

@bot.message_handler(func=lambda m: m.text == "اجرای فوری تایم‌فریم فعال")
def run_now_active(m):
    cfg = load_config()
    tf = cfg.get("active_interval", "15m")
    bot.send_message(m.chat.id, f"اجرای فوری {tf}...")
    threading.Thread(target=run_cycle, args=(tf,), daemon=True).start()

@bot.message_handler(func=lambda m: m.text == "اجرای فوری 15m")
def run_now_15m(m):
    bot.send_message(m.chat.id, "اجرای فوری 15m...")
    threading.Thread(target=run_cycle, args=("15m",), daemon=True).start()

@bot.message_handler(func=lambda m: m.text == "اجرای فوری 1h")
def run_now_1h(m):
    bot.send_message(m.chat.id, "اجرای فوری 1h...")
    threading.Thread(target=run_cycle, args=("1h",), daemon=True).start()

@bot.message_handler(func=lambda m: m.text == "اجرای فوری 4h")
def run_now_4h(m):
    bot.send_message(m.chat.id, "اجرای فوری 4h...")
    threading.Thread(target=run_cycle, args=("4h",), daemon=True).start()

@bot.message_handler(func=lambda m: m.text == "اجرای فوری 1d")
def run_now_1d(m):
    bot.send_message(m.chat.id, "اجرای فوری 1d...")
    threading.Thread(target=run_cycle, args=("1d",), daemon=True).start()

# =========================
# main
# =========================

def main():
    cfg = load_config()
    if not cfg.get("chat_id_main"):
        print("⚠ اول /start را در تلگرام به ربات بفرست تا chat_id ثبت شود.")
    bot.infinity_polling()

if __name__ == "__main__":
    main()