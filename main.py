import os
import time
import telebot
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from binance.client import Client
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import threading

# -----------------------------
# تنظیمات اصلی
# -----------------------------
BOT_TOKEN = "YOUR_TELEGRAM_TOKEN"
CHAT_ID   = "YOUR_CHAT_ID"

bot = telebot.TeleBot(BOT_TOKEN)
client = Client()

# تنظیمات پیشرفته
ADVANCED_MODE = False
PROCESS_LIMIT = 10
DISPLAY_COUNT = 12
CYCLE_HISTORY = []
RUNNING = True

# -----------------------------
# اندیکاتورها
# -----------------------------
def compute_indicators(df):
    df["SMA10"]  = df["c"].rolling(10).mean()
    df["SMA50"]  = df["c"].rolling(50).mean()
    df["SMA100"] = df["c"].rolling(100).mean()
    df["SMA200"] = df["c"].rolling(200).mean()

    # WMA20
    df["WMA20"] = df["c"].rolling(20).apply(
        lambda x: np.average(x, weights=np.arange(1, len(x)+1)),
        raw=True
    )
    df["WMA20_slope"] = df["WMA20"].diff()

    # RSI
    delta = df["c"].diff()
    gain  = delta.where(delta > 0, 0)
    loss  = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # MACD
    df["EMA12"] = df["c"].ewm(span=12, adjust=False).mean()
    df["EMA26"] = df["c"].ewm(span=26, adjust=False).mean()
    df["MACD"] = df["EMA12"] - df["EMA26"]
    df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

    return df
# -----------------------------
# دریافت داده از بایننس
# -----------------------------
def fetch_ohlc(symbol="BTCUSDT", interval="15m", lookback_days=1, max_bars=500):
    klines = client.get_klines(symbol=symbol, interval=interval, limit=max_bars)
    df = pd.DataFrame(klines, columns=[
        "t","o","h","l","c","v","ct","qv","n","tb","tbv","i"
    ])
    df["t"] = pd.to_datetime(df["t"], unit="ms")
    df.set_index("t", inplace=True)
    df = df[["o","h","l","c","v"]].astype(float)
    return df


# -----------------------------
# ساخت نمودار کندل + اندیکاتورها
# -----------------------------
def create_chart(df, symbol="BTCUSDT", file_name="chart.jpg"):

    df = compute_indicators(df)

    plt.style.use("ggplot")
    fig = plt.figure(figsize=(18, 12))

    # -----------------------------
    # نمودار کندل (Close)
    # -----------------------------
    ax1 = fig.add_subplot(3, 1, 1)
    ax1.plot(df.index, df["c"], color="black", label="Close")

    # SMAها
    ax1.plot(df.index, df["SMA10"],  color="blue",   label="SMA10")
    ax1.plot(df.index, df["SMA50"],  color="orange", label="SMA50")
    ax1.plot(df.index, df["SMA100"], color="purple", label="SMA100")
    ax1.plot(df.index, df["SMA200"], color="brown",  label="SMA200")

    # -----------------------------
    # WMA رنگی
    # -----------------------------
    wma = df["WMA20"]
    slope = df["WMA20_slope"]

    wma_up   = wma.where(slope >= 0)
    wma_down = wma.where(slope < 0)

    ax1.plot(df.index, wma_up,   color="green", linewidth=2, label="WMA20 Up")
    ax1.plot(df.index, wma_down, color="red",   linewidth=2, label="WMA20 Down")

    ax1.legend(loc="upper left")
    ax1.set_title(f"{symbol} - 15m Chart")

    # -----------------------------
    # RSI
    # -----------------------------
    ax2 = fig.add_subplot(3, 1, 2)
    ax2.plot(df.index, df["RSI"], color="blue")
    ax2.axhline(70, color="red", linestyle="--")
    ax2.axhline(30, color="green", linestyle="--")
    ax2.set_title("RSI")

    # -----------------------------
    # MACD
    # -----------------------------
    ax3 = fig.add_subplot(3, 1, 3)
    ax3.plot(df.index, df["MACD"],   color="black", label="MACD")
    ax3.plot(df.index, df["Signal"], color="red",   label="Signal")
    ax3.legend(loc="upper left")
    ax3.set_title("MACD")

    plt.tight_layout()
    plt.savefig(file_name, dpi=300)
    plt.close()

    return file_name


# -----------------------------
# ساخت ۱۲ نمودار در یک فایل JPG
# -----------------------------
def create_12_charts(symbol="BTCUSDT"):
    df = fetch_ohlc(symbol, "15m", 1, 500)

    folder = "charts"
    os.makedirs(folder, exist_ok=True)

    files = []

    for i in range(12):
        file_name = f"{folder}/chart_{i+1}.jpg"
        create_chart(df, symbol, file_name)
        files.append(file_name)

    return files

# -----------------------------
# سیستم آلارم‌ها
# -----------------------------
def check_alarms(df):
    alarms = []

    # برخورد قیمت با SMA10
    if df["c"].iloc[-1] > df["SMA10"].iloc[-1]:
        alarms.append("قیمت بالای SMA10")
    elif df["c"].iloc[-1] < df["SMA10"].iloc[-1]:
        alarms.append("قیمت پایین SMA10")

    # برخورد قیمت با SMA50
    if df["c"].iloc[-1] > df["SMA50"].iloc[-1]:
        alarms.append("قیمت بالای SMA50")
    elif df["c"].iloc[-1] < df["SMA50"].iloc[-1]:
        alarms.append("قیمت پایین SMA50")

    # برخورد قیمت با SMA100
    if df["c"].iloc[-1] > df["SMA100"].iloc[-1]:
        alarms.append("قیمت بالای SMA100")
    elif df["c"].iloc[-1] < df["SMA100"].iloc[-1]:
        alarms.append("قیمت پایین SMA100")

    # برخورد قیمت با SMA200
    if df["c"].iloc[-1] > df["SMA200"].iloc[-1]:
        alarms.append("قیمت بالای SMA200")
    elif df["c"].iloc[-1] < df["SMA200"].iloc[-1]:
        alarms.append("قیمت پایین SMA200")

    # RSI
    rsi = df["RSI"].iloc[-1]
    if rsi > 70:
        alarms.append("RSI بالای 70 → اشباع خرید")
    elif rsi < 30:
        alarms.append("RSI پایین 30 → اشباع فروش")

    # MACD کراس
    if df["MACD"].iloc[-1] > df["Signal"].iloc[-1]:
        alarms.append("MACD کراس صعودی")
    else:
        alarms.append("MACD کراس نزولی")

    return alarms


# -----------------------------
# ذخیره گزارش ۱۰ سیکل
# -----------------------------
def save_cycle_report(alarms):
    global CYCLE_HISTORY

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    CYCLE_HISTORY.append({"time": timestamp, "alarms": alarms})

    # فقط ۱۰ سیکل نگه داریم
    if len(CYCLE_HISTORY) > 10:
        CYCLE_HISTORY = CYCLE_HISTORY[-10:]


# -----------------------------
# ارسال گزارش به ربات
# -----------------------------
def send_report_to_bot(alarms, chart_files):
    text = "📊 گزارش پردازش جدید:\n\n"

    for a in alarms:
        text += f"• {a}\n"

    bot.send_message(CHAT_ID, text)

    # ارسال عکس‌ها
    for f in chart_files:
        with open(f, "rb") as img:
            bot.send_photo(CHAT_ID, img)

    # ارسال تاریخچه ۱۰ سیکل
    history_text = "🕒 تاریخچه ۱۰ سیکل اخیر:\n\n"
    for item in CYCLE_HISTORY:
        history_text += f"{item['time']}:\n"
        for a in item["alarms"]:
            history_text += f"  • {a}\n"
        history_text += "\n"

    bot.send_message(CHAT_ID, history_text)


# -----------------------------
# اجرای پردازش اصلی
# -----------------------------
def process_cycle(symbol="BTCUSDT"):
    if not RUNNING:
        return

    df = fetch_ohlc(symbol, "15m", 1, 500)

    # ساخت ۱۲ نمودار
    chart_files = create_12_charts(symbol)

    # آلارم‌ها
    alarms = check_alarms(df)

    # ذخیره در تاریخچه
    save_cycle_report(alarms)

    # ارسال به ربات
    send_report_to_bot(alarms, chart_files)


# -----------------------------
# اجرای خودکار هر ۱۵ دقیقه
# -----------------------------
def auto_runner():
    while True:
        if RUNNING:
            process_cycle()
        time.sleep(900)   # هر ۱۵ دقیقه


# -----------------------------
# دکمه‌های حرفه‌ای ربات
# -----------------------------
def main_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔄 ریست سیکل‌ها", callback_data="reset"))
    kb.add(InlineKeyboardButton("⚙️ تنظیمات پیشرفته", callback_data="advanced"))
    kb.add(InlineKeyboardButton("▶️ شروع پردازش", callback_data="start"))
    kb.add(InlineKeyboardButton("⏸ توقف پردازش", callback_data="stop"))
    kb.add(InlineKeyboardButton("🔢 تنظیم تعداد پردازش", callback_data="set_process"))
    kb.add(InlineKeyboardButton("📸 ساخت نمودار دستی", callback_data="manual"))
    return kb


@bot.message_handler(commands=["start"])
def start_cmd(msg):
    bot.send_message(msg.chat.id, "منوی اصلی:", reply_markup=main_menu())


# -----------------------------
# هندل دکمه‌ها
# -----------------------------
@bot.callback_query_handler(func=lambda c: True)
def cb(c):

    global RUNNING, ADVANCED_MODE, PROCESS_LIMIT

    # ریست سیکل‌ها
    if c.data == "reset":
        CYCLE_HISTORY.clear()
        bot.answer_callback_query(c.id, "ریست شد")
        bot.send_message(c.message.chat.id, "✔ تاریخچه ۱۰ سیکل پاک شد")

    # فعال/غیرفعال کردن حالت پیشرفته
    elif c.data == "advanced":
        ADVANCED_MODE = not ADVANCED_MODE
        status = "فعال شد" if ADVANCED_MODE else "غیرفعال شد"
        bot.answer_callback_query(c.id, status)
        bot.send_message(c.message.chat.id, f"⚙️ حالت پیشرفته: {status}")

    # شروع پردازش
    elif c.data == "start":
        RUNNING = True
        bot.answer_callback_query(c.id, "شروع شد")
        bot.send_message(c.message.chat.id, "▶️ پردازش هر ۱۵ دقیقه فعال شد")

    # توقف پردازش
    elif c.data == "stop":
        RUNNING = False
        bot.answer_callback_query(c.id, "متوقف شد")
        bot.send_message(c.message.chat.id, "⏸ پردازش متوقف شد")

    # تنظیم تعداد پردازش
    elif c.data == "set_process":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("۵", callback_data="pl_5"))
        kb.add(InlineKeyboardButton("۱۰", callback_data="pl_10"))
        kb.add(InlineKeyboardButton("۲۰", callback_data="pl_20"))
        bot.send_message(c.message.chat.id, "🔢 تعداد پردازش را انتخاب کن:", reply_markup=kb)

    elif c.data.startswith("pl_"):
        PROCESS_LIMIT = int(c.data.split("_")[1])
        bot.answer_callback_query(c.id, "تنظیم شد")
        bot.send_message(c.message.chat.id, f"✔ تعداد پردازش: {PROCESS_LIMIT}")

    # ساخت نمودار دستی
    elif c.data == "manual":
        files = create_12_charts()
        bot.answer_callback_query(c.id, "ساخته شد")
        bot.send_message(c.message.chat.id, "📸 نمودارها ساخته شدند")
        for f in files:
            with open(f, "rb") as img:
                bot.send_photo(c.message.chat.id, img)


# -----------------------------
# شروع ربات + اجرای خودکار
# -----------------------------
t = threading.Thread(target=auto_runner)
t.daemon = True
t.start()

bot.infinity_polling()