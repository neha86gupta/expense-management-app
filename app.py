from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timedelta
from collections import defaultdict

app = Flask(__name__)

# ── MongoDB connection ─────────────────────────────────────────────────────────
client = MongoClient("mongodb://localhost:27017/")
db = client["spendwise"]
expenses_col = db["expenses"]

# ── helpers ────────────────────────────────────────────────────────────────────
CAT_ICONS = {
    "Food": "🍔", "Transport": "🚗", "Shopping": "🛍️",
    "Bills": "📄", "Health": "💊", "Entertainment": "🎬", "Other": "📦"
}

def cleanup_old_data():
    """Remove expenses older than 3 months."""
    cutoff = datetime.now() - timedelta(days=90)
    expenses_col.delete_many({"date": {"$lt": cutoff}})

def serialize(exp):
    """Convert MongoDB document to JSON-safe dict."""
    return {
        "id":       str(exp["_id"]),
        "item":     exp["item"],
        "amount":   exp["amount"],
        "category": exp.get("category", "Other"),
        "date":     exp["date"].strftime("%d %b %Y, %I:%M %p"),
        "icon":     CAT_ICONS.get(exp.get("category", "Other"), "📦")
    }

# ── routes ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/api/add", methods=["POST"])
def add_expense():
    data = request.get_json()
    item     = data.get("item", "").strip()
    amount   = data.get("amount")
    category = data.get("category", "Other").strip()

    if not item:
        return jsonify({"error": "Item name is required"}), 400
    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "Enter a valid positive amount"}), 400

    expenses_col.insert_one({
        "item":     item,
        "amount":   amount,
        "category": category,
        "date":     datetime.now()
    })
    cleanup_old_data()
    return jsonify({"success": True})

@app.route("/api/expenses")
def get_expenses():
    now = datetime.now()
    months_data = []

    for i in range(3):
        mo = now.month - i
        yr = now.year
        if mo <= 0:
            mo += 12
            yr -= 1

        start = datetime(yr, mo, 1)
        end   = datetime(yr + 1, 1, 1) if mo == 12 else datetime(yr, mo + 1, 1)

        docs = list(expenses_col.find(
            {"date": {"$gte": start, "$lt": end}}
        ).sort("date", -1))

        total = round(sum(d["amount"] for d in docs), 2)
        count = len(docs)
        avg   = round(total / count, 2) if count else 0

        cat_totals = defaultdict(float)
        for d in docs:
            cat_totals[d.get("category", "Other")] += d["amount"]

        months_data.append({
            "month":      start.strftime("%B %Y"),
            "is_current": i == 0,
            "total":      total,
            "count":      count,
            "avg":        avg,
            "categories": {k: round(v, 2) for k, v in sorted(cat_totals.items(), key=lambda x: -x[1])},
            "expenses":   [serialize(d) for d in docs]
        })

    return jsonify(months_data)

@app.route("/api/delete/<expense_id>", methods=["DELETE"])
def delete_expense(expense_id):
    expenses_col.delete_one({"_id": ObjectId(expense_id)})
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(debug=True)
