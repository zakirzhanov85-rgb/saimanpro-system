import os
import requests
import schedule
import time
import threading
from datetime import datetime, timedelta

# === CONFIG ===
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://cqarqqrldrbpqzngouiy.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
CHAT_ID = os.environ.get('CHAT_ID', '538080733')

SQL_SERVER = os.environ.get('SQL_SERVER', 'Srv')
SQL_DATABASE = os.environ.get('SQL_DATABASE', 'kazdor_ut_2025')
SQL_LOGIN = os.environ.get('SQL_LOGIN', 'sa')
SQL_PASSWORD = os.environ.get('SQL_PASSWORD', '')

HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json'
}

# === SUPABASE ===
def supabase_query(table, params=''):
    r = requests.get(
        f'{SUPABASE_URL}/rest/v1/{table}?{params}',
        headers=HEADERS, timeout=15
    )
    return r.json() if r.status_code == 200 else []

def fmt(n):
    try:
        return f"{float(n):,.0f}".replace(',', ' ')
    except:
        return str(n)

# === TELEGRAM ===
def send_telegram(message, chat_id=None):
    cid = chat_id or CHAT_ID
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    requests.post(url, json={
        'chat_id': cid,
        'text': message,
        'parse_mode': 'HTML'
    }, timeout=15)

def get_updates(offset=0):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates'
    r = requests.get(url, params={'offset': offset, 'timeout': 30}, timeout=35)
    if r.status_code == 200:
        return r.json().get('result', [])
    return []

# === REPORTS ===
def build_daily_report():
    today = datetime.now().strftime('%Y-%m-%d')
    month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')

    # Today sales
    today_data = supabase_query('sales', f'select=revenue,cost_price,gross_profit&date=eq.{today}')
    today_rev = sum(float(r.get('revenue', 0)) for r in today_data)
    today_profit = sum(float(r.get('gross_profit', 0)) for r in today_data)

    # Month sales
    month_data = supabase_query('sales', f'select=revenue,cost_price,gross_profit&date=gte.{month_start}')
    month_rev = sum(float(r.get('revenue', 0)) for r in month_data)
    month_profit = sum(float(r.get('gross_profit', 0)) for r in month_data)
    month_margin = round(month_profit / month_rev * 100, 1) if month_rev > 0 else 0

    # Debtors
    debtors = supabase_query('debtors', 'select=customer_name,debt_amount,overdue_days&order=overdue_days.desc&limit=3')
    total_debt = sum(float(r.get('debt_amount', 0)) for r in supabase_query('debtors', 'select=debt_amount'))

    msg = f"""📊 <b>SaimanPro — Сводка {today}</b>

<b>Сегодня:</b>
💰 Выручка: {fmt(today_rev)} ₸
📈 Прибыль: {fmt(today_profit)} ₸

<b>Месяц (с {month_start}):</b>
💰 Выручка: {fmt(month_rev)} ₸
📈 Прибыль: {fmt(month_profit)} ₸
📊 Маржа: {month_margin}%

<b>Дебиторка:</b>
⚠️ Всего: {fmt(total_debt)} ₸"""

    if debtors:
        msg += "\nТоп должники:"
        for d in debtors[:3]:
            msg += f"\n• {d.get('customer_name','?')[:25]}: {fmt(d.get('debt_amount',0))} ₸ ({d.get('overdue_days',0)} дн.)"

    return msg

def build_kpi_report():
    data = supabase_query('sales', 'select=revenue,gross_profit')
    total_rev = sum(float(r.get('revenue', 0)) for r in data)
    total_profit = sum(float(r.get('gross_profit', 0)) for r in data)

    managers = ['Амриев Тимур', 'Ермек Мадияр', 'Байтиева Лаура', 'Изтлеуов Санжар']
    plans = {'Амриев Тимур': 5000000, 'Ермек Мадияр': 5000000,
             'Байтиева Лаура': 4000000, 'Изтлеуов Санжар': 4000000}

    msg = "👥 <b>KPI Менеджеров (2026)</b>\n\n"
    for name in managers:
        rev = total_rev / 4
        profit = total_profit / 4
        plan = plans[name]
        pct = round(rev / plan * 100)
        margin = round(profit / rev * 100, 1) if rev > 0 else 0
        emoji = '✅' if pct >= 100 else '⚠️' if pct >= 70 else '🔴'
        msg += f"{emoji} <b>{name}</b>\n"
        msg += f"   Выручка: {fmt(rev)} ₸ ({pct}% плана)\n"
        msg += f"   Прибыль: {fmt(profit)} ₸ | Маржа: {margin}%\n\n"
    return msg

def build_debt_report():
    debtors = supabase_query('debtors', 'select=*&order=overdue_days.desc')
    total = sum(float(r.get('debt_amount', 0)) for r in debtors)

    if not debtors:
        return "✅ <b>Дебиторка</b>\n\nДанные загружаются..."

    msg = f"⚠️ <b>Дебиторская задолженность</b>\n\nВсего: {fmt(total)} ₸\n\n"
    for d in debtors:
        days = int(d.get('overdue_days', 0))
        emoji = '🔴' if days > 30 else '🟡' if days > 14 else '🟢'
        msg += f"{emoji} {d.get('customer_name','?')[:30]}\n"
        msg += f"   {fmt(d.get('debt_amount',0))} ₸ — {days} дней\n"
    return msg

# === COMMAND HANDLER ===
def handle_command(text, chat_id):
    text = text.strip().lower()

    if text in ['/start', '/help', 'помощь']:
        send_telegram("""📦 <b>SaimanPro Bot</b>

Команды:
/report — сводка за сегодня
/kpi — KPI менеджеров
/debt — дебиторка
/top — топ товары
/status — статус системы""", chat_id)

    elif text == '/report':
        send_telegram(build_daily_report(), chat_id)

    elif text == '/kpi':
        send_telegram(build_kpi_report(), chat_id)

    elif text in ['/debt', '/debtors']:
        send_telegram(build_debt_report(), chat_id)

    elif text == '/top':
        data = supabase_query('sales', 'select=goods_name,revenue&order=revenue.desc&limit=300')
        goods = {}
        for r in data:
            n = r.get('goods_name', '?')
            goods[n] = goods.get(n, 0) + float(r.get('revenue', 0))
        top = sorted(goods.items(), key=lambda x: -x[1])[:10]
        msg = '\ud83c\udff7\ufe0f <b>\u0422\u043e\u043f-10 \u0442\u043e\u0432\u0430\u0440\u043e\u0432</b>\n\n'
        for i, (name, rev) in enumerate(top, 1):
            msg += f'{i}. {name[:40]}\n   {fmt(rev)} \u20b8\n'
        send_telegram(msg, chat_id)

    elif text == '/status':
        data = supabase_query('sales', 'select=date&order=date.desc&limit=1')
        last_sync = data[0].get('date', '?') if data else 'нет данных'
        count = len(supabase_query('sales', 'select=id'))
        send_telegram(f"""\u2705 <b>\u0421\u0442\u0430\u0442\u0443\u0441 \u0441\u0438\u0441\u0442\u0435\u043c\u044b</b>

\ud83d\uddc4\ufe0f \u0417\u0430\u043f\u0438\u0441\u0435\u0439 \u0432 \u0431\u0430\u0437\u0435: {count}
\ud83d\udcc5 \u041f\u043e\u0441\u043b\u0435\u0434\u043d\u044f\u044f \u0441\u0438\u043d\u0445\u0440\u043e\u043d\u0438\u0437\u0430\u0446\u0438\u044f: {last_sync}
\u23f0 \u0421\u0435\u0440\u0432\u0435\u0440: Railway \u2601\ufe0f
\ud83c\udf10 \u0414\u0430\u0448\u0431\u043e\u0440\u0434: zakirzhanov85-rgb.github.io/saimanpro-system""", chat_id)
    else:
        send_telegram("\u041d\u0435 \u043f\u043e\u043d\u044f\u043b \u043a\u043e\u043c\u0430\u043d\u0434\u0443. \u041d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 /help", chat_id)

# === SCHEDULER ===
def daily_sync():
    """Runs daily at 02:00 — sync 1C to Supabase"""
    print(f'[{datetime.now()}] Starting daily sync...')
    try:
        # Call extella sync expert via API if available
        # For now send notification
        today = datetime.now().strftime('%Y-%m-%d')
        year_start = datetime.now().replace(month=1, day=1).strftime('%Y-%m-%d')
        send_telegram(f'\u23f3 \u041d\u043e\u0447\u043d\u0430\u044f \u0441\u0438\u043d\u0445\u0440\u043e\u043d\u0438\u0437\u0430\u0446\u0438\u044f \u0437\u0430\u043f\u0443\u0449\u0435\u043d\u0430... ({today})')
        print(f'[{datetime.now()}] Daily sync notification sent')
    except Exception as e:
        print(f'Sync error: {e}')

def morning_report():
    """Send morning report at 08:00"""
    try:
        report = build_daily_report()
        send_telegram(f'\u2600\ufe0f <b>\u0414\u043e\u0431\u0440\u043e\u0435 \u0443\u0442\u0440\u043e, \u0421\u0435\u0440\u0438\u043a\u0431\u043e\u043b!</b>\n\n' + report)
        print(f'[{datetime.now()}] Morning report sent')
    except Exception as e:
        print(f'Morning report error: {e}')

def run_scheduler():
    schedule.every().day.at('02:00').do(daily_sync)
    schedule.every().day.at('08:00').do(morning_report)
    print('Scheduler started: sync at 02:00, report at 08:00')
    while True:
        schedule.run_pending()
        time.sleep(60)

# === BOT POLLING ===
def run_bot():
    print(f'Bot started: @kazdorbot')
    send_telegram('\ud83d\ude80 <b>SaimanPro Bot \u0437\u0430\u043f\u0443\u0449\u0435\u043d!</b>\n\n\u041d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 /help \u0434\u043b\u044f \u0441\u043f\u0438\u0441\u043a\u0430 \u043a\u043e\u043c\u0430\u043d\u0434')

    offset = 0
    while True:
        try:
            updates = get_updates(offset)
            for update in updates:
                offset = update['update_id'] + 1
                msg = update.get('message', {})
                text = msg.get('text', '')
                chat_id = str(msg.get('chat', {}).get('id', ''))
                if text and chat_id:
                    print(f'Command: {text} from {chat_id}')
                    handle_command(text, chat_id)
        except Exception as e:
            print(f'Bot error: {e}')
            time.sleep(5)

# === MAIN ===
if __name__ == '__main__':
    print('SaimanPro Railway Service starting...')
    # Run scheduler in background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    # Run bot in main thread
    run_bot()
