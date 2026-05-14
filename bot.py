import os
import requests
import schedule
import time
import threading
from datetime import datetime

# === CONFIG FROM ENV ===
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://cqarqqrldrbpqzngouiy.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
CHAT_ID = os.environ.get('CHAT_ID', '538080733')

if not SUPABASE_KEY:
    print('ERROR: SUPABASE_KEY not set!')
if not TELEGRAM_TOKEN:
    print('ERROR: TELEGRAM_TOKEN not set!')

SB_HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json'
}

# === SUPABASE ===
def sb(table, params=''):
    try:
        r = requests.get(
            f'{SUPABASE_URL}/rest/v1/{table}?{params}',
            headers=SB_HEADERS, timeout=15
        )
        if r.status_code == 200:
            return r.json()
        print(f'Supabase error {r.status_code}: {r.text[:200]}')
        return []
    except Exception as e:
        print(f'Supabase exception: {e}')
        return []

def fmt(n):
    try:
        return f"{int(float(n)):,}".replace(',', ' ')
    except:
        return str(n)

# === TELEGRAM ===
def tg(message, chat_id=None):
    try:
        cid = chat_id or CHAT_ID
        requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
            json={'chat_id': cid, 'text': message, 'parse_mode': 'HTML'},
            timeout=15
        )
    except Exception as e:
        print(f'Telegram error: {e}')

def get_updates(offset=0):
    try:
        r = requests.get(
            f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates',
            params={'offset': offset, 'timeout': 25},
            timeout=30
        )
        if r.status_code == 200:
            return r.json().get('result', [])
    except Exception as e:
        print(f'getUpdates error: {e}')
    return []

# === REPORTS ===
def report_daily():
    today = datetime.now().strftime('%Y-%m-%d')
    month = datetime.now().replace(day=1).strftime('%Y-%m-%d')

    all_sales = sb('sales', 'select=date,revenue,cost_price,gross_profit')

    today_sales = [r for r in all_sales if r.get('date') == today]
    month_sales = [r for r in all_sales if r.get('date', '') >= month]

    t_rev = sum(float(r.get('revenue', 0)) for r in today_sales)
    t_profit = sum(float(r.get('gross_profit', 0)) for r in today_sales)
    m_rev = sum(float(r.get('revenue', 0)) for r in month_sales)
    m_profit = sum(float(r.get('gross_profit', 0)) for r in month_sales)
    m_margin = round(m_profit / m_rev * 100, 1) if m_rev > 0 else 0

    # Total for year
    y_rev = sum(float(r.get('revenue', 0)) for r in all_sales)
    y_profit = sum(float(r.get('gross_profit', 0)) for r in all_sales)
    y_margin = round(y_profit / y_rev * 100, 1) if y_rev > 0 else 0

    debtors = sb('debtors', 'select=debt_amount')
    total_debt = sum(float(r.get('debt_amount', 0)) for r in debtors)

    return f"""📊 <b>SaimanPro — {today}</b>

<b>Today:</b>
💰 Выручка: {fmt(t_rev)} ₸
📈 Прибыль: {fmt(t_profit)} ₸

<b>Месяц (c {month[:7]}):</b>
💰 {fmt(m_rev)} ₸ | 📈 {fmt(m_profit)} ₸ | 📊 {m_margin}%

<b>2026 год:</b>
💰 {fmt(y_rev)} ₸ | 📈 {fmt(y_profit)} ₸ | 📊 {y_margin}%

⚠️ Дебиторка: {fmt(total_debt)} ₸"""

def report_kpi():
    data = sb('sales', 'select=revenue,gross_profit')
    y_rev = sum(float(r.get('revenue', 0)) for r in data)
    y_profit = sum(float(r.get('gross_profit', 0)) for r in data)

    managers = [
        ('Амриев Тимур', 5000000),
        ('Ермек Мадияр', 5000000),
        ('Байтиева Лаура', 4000000),
        ('Изтлеуов Санжар', 4000000)
    ]

    msg = '👥 <b>KPI Менеджеров (2026)</b>\n\n'
    for name, plan in managers:
        rev = y_rev / 4
        profit = y_profit / 4
        pct = round(rev / plan * 100)
        margin = round(profit / rev * 100, 1) if rev > 0 else 0
        e = '✅' if pct >= 100 else '⚠️' if pct >= 70 else '🔴'
        msg += f'{e} <b>{name}</b>\n'
        msg += f'   Выручка: {fmt(rev)} ₸ ({pct}% плана)\n'
        msg += f'   Прибыль: {fmt(profit)} ₸ | Маржа: {margin}%\n\n'
    return msg

def report_debt():
    data = sb('debtors', 'select=*&order=overdue_days.desc')
    if not data:
        return '✅ <b>Дебиторка</b>\n\nДанных нет. Загрузите из 1С.'
    total = sum(float(r.get('debt_amount', 0)) for r in data)
    msg = f'⚠️ <b>Дебиторка</b>\n\u0412сего: {fmt(total)} ₸\n\n'
    for r in data:
        d = int(r.get('overdue_days', 0))
        e = '🔴' if d > 30 else '🟡' if d > 14 else '🟢'
        msg += f'{e} {str(r.get("customer_name","?"))[:30]} — {fmt(r.get("debt_amount",0))} ₸ ({d} дн.)\n'
    return msg

def report_top():
    data = sb('sales', 'select=goods_name,revenue&limit=500')
    goods = {}
    for r in data:
        n = r.get('goods_name', '?')
        goods[n] = goods.get(n, 0) + float(r.get('revenue', 0))
    top = sorted(goods.items(), key=lambda x: -x[1])[:10]
    msg = '🏷️ <b>Топ-10 товаров</b>\n\n'
    for i, (name, rev) in enumerate(top, 1):
        msg += f'{i}. {name[:40]}\n   {fmt(rev)} ₸\n'
    return msg

def report_status():
    count = len(sb('sales', 'select=id&limit=1000'))
    debt_count = len(sb('debtors', 'select=id'))
    last = sb('sales', 'select=date&order=date.desc&limit=1')
    last_date = last[0].get('date', '?') if last else '?'
    return f"""✅ <b>Статус SaimanPro</b>

🗄️ Записей продаж: {count}
📅 Последняя дата: {last_date}
🏢 Клиентов с долгом: {debt_count}
☁️ Сервер: Railway (24/7)
🌐 Дашборд: zakirzhanov85-rgb.github.io/saimanpro-system"""

# === COMMAND HANDLER ===
def handle(text, chat_id):
    cmd = text.strip().lower().split()[0] if text.strip() else ''
    print(f'CMD: {cmd} from {chat_id}')

    if cmd in ['/start', '/help']:
        tg("""📦 <b>SaimanPro Bot</b>

Команды:
/report — сводка продаж
/kpi — KPI менеджеров
/debt — дебиторка
/top — топ товары
/status — статус системы""", chat_id)
    elif cmd == '/report':
        tg(report_daily(), chat_id)
    elif cmd == '/kpi':
        tg(report_kpi(), chat_id)
    elif cmd in ['/debt', '/debtors']:
        tg(report_debt(), chat_id)
    elif cmd == '/top':
        tg(report_top(), chat_id)
    elif cmd == '/status':
        tg(report_status(), chat_id)
    else:
        tg('Не понял команду. Напишите /help', chat_id)

# === SCHEDULER ===
def morning_report():
    print(f'[{datetime.now()}] Sending morning report...')
    tg('☀️ <b>Доброе утро, Серикбол!</b>\n\n' + report_daily())

def run_scheduler():
    schedule.every().day.at('08:00').do(morning_report)
    print('Scheduler: morning report at 08:00')
    while True:
        schedule.run_pending()
        time.sleep(30)

# === MAIN LOOP ===
def run_bot():
    print('SaimanPro Bot starting...')
    tg('🚀 <b>SaimanPro Bot запущен!</b>\n\u041dапишите /help')

    offset = 0
    while True:
        try:
            updates = get_updates(offset)
            for u in updates:
                offset = u['update_id'] + 1
                msg = u.get('message', {})
                text = msg.get('text', '')
                cid = str(msg.get('chat', {}).get('id', ''))
                if text and cid:
                    handle(text, cid)
        except Exception as e:
            print(f'Loop error: {e}')
            time.sleep(5)

if __name__ == '__main__':
    t = threading.Thread(target=run_scheduler, daemon=True)
    t.start()
    run_bot()
