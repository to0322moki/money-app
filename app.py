from flask import Flask, render_template, jsonify, redirect, url_for, request
from datetime import datetime
import sqlite3
import json
import os

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

DB_NAME = "data.db"
SETTINGS_FILE = "settings.json"

# --- デフォルト設定 ---
default_settings = {
    "income": 185000,
    "saving_goal": 40000,
    "phone": 0,
    "car_insurance": 0,
    "life_insurance": 0,
    "subscription": 0,
    "car_loan": 0,
    "rent": 0,
    "gasoline": 0,
    "beauty": 0,
    "electricity": 0,
    "water": 0,
    "gas": 0
}

# --- JSON 読み込み ---
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return default_settings.copy()

# --- JSON 保存 ---
def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- DB 初期化（支出履歴のみ管理） ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year_month TEXT,
            date TEXT,
            amount INTEGER,
            memo TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# =============================
# メインページ
# =============================
@app.route("/", methods=["GET", "POST"])
def index():
    today = datetime.now()
    current_month = today.strftime("%Y-%m")

    # 設定読み込み
    settings = load_settings()

    # 固定費合計
    fixed_cost = (settings["phone"] + settings["car_insurance"] + settings["life_insurance"] +
                  settings["subscription"] + settings["car_loan"] + settings["rent"] +
                  settings["gasoline"] + settings["beauty"] + settings["electricity"] +
                  settings["water"] + settings["gas"])

    usable_amount = settings["income"] - fixed_cost - settings["saving_goal"]

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # 入力処理
    if request.method == "POST":
        try:
            amount = int(request.form["amount"])
            memo = request.form.get("memo", "")
            cur.execute("INSERT INTO expenses (year_month, date, amount, memo) VALUES (?, ?, ?, ?)",
                        (current_month, today.strftime("%Y-%m-%d"), amount, memo))
            conn.commit()
        except:
            pass

    # 今月の履歴取得
    cur.execute("SELECT id, date, amount, memo FROM expenses WHERE year_month=?", (current_month,))
    history = [{"id": i, "date": d, "amount": a, "memo": m} for i, d, a, m in cur.fetchall()]

    # 使用額の合計
    cur.execute("SELECT SUM(amount) FROM expenses WHERE year_month=?", (current_month,))
    used_amount = cur.fetchone()[0] or 0

    conn.close()

    # 計算
    free_balance = usable_amount - used_amount
    total_saving = settings["saving_goal"] + free_balance
    remain_ratio = int(free_balance / usable_amount * 100) if usable_amount > 0 else 0

    if remain_ratio > 50:
        bar_color = "green"
    elif remain_ratio > 10:
        bar_color = "yellow"
    else:
        bar_color = "red"

    return render_template("index.html",
                           income=settings["income"],
                           fixed_cost=fixed_cost,
                           saving_goal=settings["saving_goal"],
                           usable_amount=usable_amount,
                           used_amount=used_amount,
                           free_balance=free_balance,
                           total_saving=total_saving,
                           remain_ratio=remain_ratio,
                           bar_color=bar_color,
                           history=history)

# =============================
# 履歴ページ一覧
# =============================
@app.route("/history")
def history_select():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT year_month FROM expenses ORDER BY year_month DESC")
    months = [m[0] for m in cur.fetchall()]
    conn.close()
    return render_template("history_select.html", months=months)

# =============================
# 特定の月の履歴詳細
# =============================
@app.route("/history/<year_month>")
def history_detail(year_month):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("SELECT date, amount, memo FROM expenses WHERE year_month=?", (year_month,))
    history = [{"date": d, "amount": a, "memo": m} for d, a, m in cur.fetchall()]

    cur.execute("SELECT SUM(amount) FROM expenses WHERE year_month=?", (year_month,))
    used_amount = cur.fetchone()[0] or 0

    conn.close()

    # 設定は常に「現在のJSON」を使う（過去月の設定は保持しない）
    settings = load_settings()
    fixed_cost = (settings["phone"] + settings["car_insurance"] + settings["life_insurance"] +
                  settings["subscription"] + settings["car_loan"] + settings["rent"] +
                  settings["gasoline"] + settings["beauty"] + settings["electricity"] +
                  settings["water"] + settings["gas"])
    usable_amount = settings["income"] - fixed_cost - settings["saving_goal"]

    free_balance = usable_amount - used_amount
    total_saving = settings["saving_goal"] + free_balance
    remain_ratio = int(free_balance / usable_amount * 100) if usable_amount > 0 else 0

    if remain_ratio > 50:
        bar_color = "green"
    elif remain_ratio > 10:
        bar_color = "yellow"
    else:
        bar_color = "red"

    return render_template("history_detail.html",
                           year_month=year_month,
                           income=settings["income"],
                           fixed_cost=fixed_cost,
                           saving_goal=settings["saving_goal"],
                           usable_amount=usable_amount,
                           used_amount=used_amount,
                           free_balance=free_balance,
                           total_saving=total_saving,
                           remain_ratio=remain_ratio,
                           bar_color=bar_color,
                           history=history)

# =============================
# データ削除
# =============================
@app.route("/delete/<int:expense_id>", methods=["POST"])
def delete_expense(expense_id):
    today = datetime.now()
    current_month = today.strftime("%Y-%m")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("SELECT year_month FROM expenses WHERE id=?", (expense_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "message": "データが見つかりませんでした"})
    year_month = row[0]

    if year_month != current_month:
        conn.close()
        return jsonify({"success": False, "message": "過去のデータは削除できません"})

    cur.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    conn.commit()

    # 再計算
    cur.execute("SELECT SUM(amount) FROM expenses WHERE year_month=?", (current_month,))
    used_amount = cur.fetchone()[0] or 0
    conn.close()

    settings = load_settings()
    fixed_cost = (settings["phone"] + settings["car_insurance"] + settings["life_insurance"] +
                  settings["subscription"] + settings["car_loan"] + settings["rent"] +
                  settings["gasoline"] + settings["beauty"] + settings["electricity"] +
                  settings["water"] + settings["gas"])
    usable_amount = settings["income"] - fixed_cost - settings["saving_goal"]

    free_balance = usable_amount - used_amount
    total_saving = settings["saving_goal"] + free_balance
    remain_ratio = int(free_balance / usable_amount * 100) if usable_amount > 0 else 0

    if remain_ratio > 50:
        bar_color = "green"
    elif remain_ratio > 10:
        bar_color = "yellow"
    else:
        bar_color = "red"

    return jsonify({
        "success": True,
        "free_balance": free_balance,
        "total_saving": total_saving,
        "used_amount": used_amount,
        "remain_ratio": remain_ratio,
        "bar_color": bar_color
    })

# =============================
# 固定費設定ページ
# =============================
@app.route("/settings", methods=["GET", "POST"])
def settings():
    settings_data = load_settings()

    if request.method == "POST":
        def to_int(value):
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0

        settings_data["income"] = to_int(request.form.get("income"))
        settings_data["saving_goal"] = to_int(request.form.get("saving_goal"))
        settings_data["phone"] = to_int(request.form.get("phone"))
        settings_data["car_insurance"] = to_int(request.form.get("car_insurance"))
        settings_data["life_insurance"] = to_int(request.form.get("life_insurance"))
        settings_data["subscription"] = to_int(request.form.get("subscription"))
        settings_data["car_loan"] = to_int(request.form.get("car_loan"))
        settings_data["rent"] = to_int(request.form.get("rent"))
        settings_data["gasoline"] = to_int(request.form.get("gasoline"))
        settings_data["beauty"] = to_int(request.form.get("beauty"))
        settings_data["electricity"] = to_int(request.form.get("electricity"))
        settings_data["water"] = to_int(request.form.get("water"))
        settings_data["gas"] = to_int(request.form.get("gas"))

        save_settings(settings_data)
        return redirect(url_for("index"))

    return render_template("settings.html", settings=settings_data)

# =============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
