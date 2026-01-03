# app.py
import os
import json
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session, flash, g
import pyrebase
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from firebase_admin import credentials, firestore


app = Flask(__name__)
app.secret_key = "super-secret-key-change-this"

# ---- Load firebase_config.json safely ----
with open("firebase_config.json") as f:
    cfg = json.load(f)

pyrebase_config = cfg["pyrebase"]

firebase = pyrebase.initialize_app(pyrebase_config)   # client SDK (optional)
auth = firebase.auth()                                # if you ever use email/password

# Admin SDK for secure server-side access
cred = credentials.Certificate("firebase_config.json")
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()
# Collections: users, transactions, services, etc.

def generate_upi_id(usn: str) -> str:
    return f"{usn.lower()}@bmscepay"

def get_current_user():
    uid = session.get("uid")
    if not uid:
        return None
    doc = db.collection("users").document(uid).get()
    if doc.exists:
        user = doc.to_dict()
        user["id"] = uid
        return user
    return None

@app.context_processor
def inject_current_user():
    user = get_current_user()
    if user:
        initial = user.get("name", "U")[:1].upper()
        short = user.get("name", "User").split()[0]
    else:
        initial = "U"
        short = "User"
    g.user_initial = initial
    g.user_short_name = short
    return dict(current_user=user)



def get_current_user():
    uid = session.get("uid")
    if not uid:
        return None
    doc = db.collection("users").document(uid).get()
    if doc.exists:
        user = doc.to_dict()
        user["id"] = uid
        return user
    return None

def create_fake_balance(uid: str):
    # For project demo: keep a numeric 'balance' field in user document
    user_ref = db.collection("users").document(uid)
    user_ref.set({"balance": 1000.0}, merge=True)
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usn = request.form.get("usn", "").strip()
        password = request.form.get("password", "").strip()

        # Simple query: match USN and password
        q = (
            db.collection("users")
            .where("usn", "==", usn)
            .where("password", "==", password)
            .stream()
        )

        user_doc = None
        for d in q:
            user_doc = d
            break

        if not user_doc:
            flash("Invalid USN or password", "danger")
            # IMPORTANT: always return a response here
            return render_template("login.html")

        # Valid user: set session and redirect
        session["uid"] = user_doc.id
        return redirect(url_for("dashboard"))

    # IMPORTANT: for GET request, always return login.html
    return render_template("login.html")

@app.route("/scan-pay")
def scan_pay():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    return render_template("scan_pay.html", user=user)



@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        college_id = request.form.get("college_id", "").strip()
        phone = request.form.get("phone", "").strip()
        usn = request.form.get("usn", "").strip()
        class_name = request.form.get("class", "").strip()

        # new fields
        semester = request.form.get("semester", "").strip()
        year = request.form.get("year", "").strip()
        pin = request.form.get("pin", "").strip()
        password = request.form.get("password", "").strip()
        residence_type = request.form.get("residence_type", "").strip()
        food_pref = request.form.get("food_pref", "").strip()
        primary_use = request.form.get("primary_use", "").strip()

        upi_id = generate_upi_id(usn)

        # Simple uniqueness check on USN
        q = db.collection("users").where("usn", "==", usn).stream()
        for _ in q:
            flash("USN already registered", "danger")
            return render_template("register.html")

        user_doc = {
            "name": name,
            "college_id": college_id,
            "phone": phone,
            "usn": usn,
            "class": class_name,
            "semester": semester,
            "year": year,
            "pin": pin,
            "password": password,   # remember: for a real app hash this
            "upi_id": upi_id,
            "residence_type": residence_type,
            "food_pref": food_pref,
            "primary_use": primary_use,
            "created_at": datetime.utcnow(),
        }

        ref = db.collection("users").document()
        ref.set(user_doc)
        create_fake_balance(ref.id)
        flash(f"Account created! Your UPI ID is {upi_id}", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/dashboard")
def dashboard():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    uid = user["id"]
    bal = user.get("balance", 0.0)

    # Fetch last 5 transactions
    txns = (
        db.collection("transactions")
        .where("user_id", "==", uid)
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(5)
        .stream()
    )
    latest_txns = [t.to_dict() for t in txns]

    # Simple monthly spend for chart
    now = datetime.utcnow()
    start_of_month = datetime(now.year, now.month, 1)
    monthly_stream = (
        db.collection("transactions")
        .where("user_id", "==", uid)
        .where("timestamp", ">=", start_of_month)
        .stream()
    )
    total_sent = 0.0
    total_received = 0.0
    for t in monthly_stream:
        d = t.to_dict()
        amt = float(d.get("amount", 0))
        if d.get("type") == "sent":
            total_sent += amt
        elif d.get("type") == "received":
            total_received += amt

    return render_template(
        "dashboard.html",
        user=user,
        balance=bal,
        latest_txns=latest_txns,
        total_sent=total_sent,
        total_received=total_received,
    )
@app.route("/send", methods=["GET"])
def send():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    to = request.args.get("to", "")
    name = request.args.get("name", "")
    amount = request.args.get("amount", "")
    note = request.args.get("note", "")
    return render_template(
        "make_transaction.html",
        user=user,
        prefill=dict(to=to, name=name, amount=amount, note=note),
    )

@app.route("/make-transaction", methods=["GET", "POST"])
def make_transaction():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        uid = user["id"]
        from_upi = user["upi_id"]

        to_upi_or_phone = request.form.get("to", "").strip()
        name = request.form.get("name", "").strip()
        amount_raw = request.form.get("amount", "0").strip()
        note = request.form.get("note", "").strip()
        pin = request.form.get("pin", "").strip()    # <-- PIN from form

        # Parse amount safely
        try:
            amount = float(amount_raw or 0)
        except ValueError:
            amount = 0.0

        if amount <= 0:
            flash("Enter a valid amount.", "danger")
            return redirect(url_for("make_transaction"))

        # ----- PIN check -----
        if pin != user.get("pin"):
            flash("Invalid PIN.", "danger")
            return redirect(url_for("make_transaction"))

        # ----- Balance check -----
        current_balance = float(user.get("balance", 0.0))
        if amount > current_balance:
            flash("Payment failed: insufficient wallet balance.", "danger")
            return redirect(url_for("make_transaction"))

        # ----- Find receiver by UPI ID or phone -----
        recv_doc = None

        # 1) Try UPI ID
        q_upi = (
            db.collection("users")
            .where("upi_id", "==", to_upi_or_phone)
            .limit(1)
            .stream()
        )
        for d in q_upi:
            recv_doc = d
            break

        # 2) If not found, try phone
        if not recv_doc:
            q_phone = (
                db.collection("users")
                .where("phone", "==", to_upi_or_phone)
                .limit(1)
                .stream()
            )
            for d in q_phone:
                recv_doc = d
                break

        # If still not found, block payment
        if not recv_doc:
            flash("No user found with that UPI ID or phone number.", "danger")
            return redirect(url_for("make_transaction"))

        recv_user = recv_doc.to_dict()
        recv_id = recv_doc.id
        recv_upi = recv_user.get("upi_id", to_upi_or_phone)
        recv_name = recv_user.get("name", name or "Friend")

        # ----- Create transactions and update balances -----

        # Sender transaction (money sent)
        sender_txn = {
            "user_id": uid,
            "from_upi": from_upi,
            "to": recv_upi,
            "display_name": recv_name,
            "amount": amount,
            "note": note,
            "type": "sent",
            "timestamp": datetime.utcnow(),
        }
        db.collection("transactions").add(sender_txn)

        # Decrease sender balance
        db.collection("users").document(uid).update(
            {"balance": firestore.Increment(-amount)}
        )

        # Receiver transaction (money received)
        receiver_txn = {
            "user_id": recv_id,
            "from_upi": from_upi,
            "to": recv_upi,
            "display_name": user.get("name", "Friend"),
            "amount": amount,
            "note": note,
            "type": "received",
            "timestamp": datetime.utcnow(),
        }
        db.collection("transactions").add(receiver_txn)

        # Increase receiver balance
        db.collection("users").document(recv_id).update(
            {"balance": firestore.Increment(amount)}
        )

        flash("Payment sent successfully.", "success")
        return redirect(url_for("dashboard"))

    # GET request – show form
    return render_template("make_transaction.html", user=user, prefill={})


@app.route("/receive", methods=["GET", "POST"])
def receive():
    """Page where user can create a money request to another user."""
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        to_identifier = request.form.get("to_identifier", "").strip()  # UPI or phone
        amount_raw = request.form.get("amount", "0").strip()
        note = request.form.get("note", "").strip()

        try:
            amount = float(amount_raw or 0)
        except ValueError:
            amount = 0.0

        if not to_identifier or amount <= 0:
            flash("Enter a valid UPI / phone and amount.", "danger")
            return redirect(url_for("receive"))

        # Check that the target user exists by UPI ID or phone
        recv_doc = None

        # 1) by upi_id
        q_upi = (
            db.collection("users")
            .where("upi_id", "==", to_identifier)
            .limit(1)
            .stream()
        )
        for d in q_upi:
            recv_doc = d
            break

        # 2) if not found, by phone
        if not recv_doc:
            q_phone = (
                db.collection("users")
                .where("phone", "==", to_identifier)
                .limit(1)
                .stream()
            )
            for d in q_phone:
                recv_doc = d
                break

        if not recv_doc:
            flash("No user found with that UPI ID or phone number.", "danger")
            return redirect(url_for("receive"))

        recv_user = recv_doc.to_dict()
        recv_upi = recv_user.get("upi_id", "")

        # Create a pending request document
        req_doc = {
            "from_user_id": user["id"],       # requester
            "from_upi": user["upi_id"],
            "to_user_id": recv_doc.id,        # who should pay
            "to_upi": recv_upi,
            "to_identifier": to_identifier,   # what was typed
            "amount": amount,
            "note": note,
            "status": "pending",
            "timestamp": datetime.utcnow(),
        }
        db.collection("requests").add(req_doc)

        flash("Money request sent.", "success")
        return redirect(url_for("dashboard"))

    return render_template("receive.html", user=user)

@app.route("/requests")
def requests_page():
    """Show money requests where the current user is the target."""
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    uid = user["id"]
    upi = user.get("upi_id", "")

    # Fetch pending requests where this user is the receiver
    q = (
        db.collection("requests")
        .where("to_user_id", "==", uid)
        .where("status", "==", "pending")
        .stream()
    )   

    requests_list = []
    for r in q:
        d = r.to_dict()
        d["id"] = r.id
        requests_list.append(d)

    return render_template("requests.html", user=user, requests=requests_list)



@app.route("/history")
def history():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    uid = user["id"]
    txns_stream = (
        db.collection("transactions")
        .where("user_id", "==", uid)
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .stream()
    )
    txns = [t.to_dict() for t in txns_stream]

    # You can group in template by date ranges
    return render_template("history.html", user=user, txns=txns)
@app.route("/expense-tracker")
def expense_tracker():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    return render_template("expense_tracker.html", user=user)

@app.route("/expense-data")
def expense_data():
    user = get_current_user()
    if not user:
        return {"error": "Unauthorized"}, 401

    uid = user["id"]
    txns_stream = db.collection("transactions").where("user_id", "==", uid).stream()

    monthly_sent = {}
    monthly_received = {}
    total_sent_all = 0.0
    total_received_all = 0.0

    from datetime import datetime
    now = datetime.utcnow()
    this_month_key = f"{now.year}-{now.month:02d}"
    this_month_spent = 0.0

    for t in txns_stream:
        d = t.to_dict()
        ts = d["timestamp"]
        key = f"{ts.year}-{ts.month:02d}"
        amt = float(d.get("amount", 0))
        ttype = d.get("type")

        if ttype == "sent":
            monthly_sent[key] = monthly_sent.get(key, 0) + amt
            total_sent_all += amt
            if key == this_month_key:
                this_month_spent += amt
        elif ttype == "received":
            monthly_received[key] = monthly_received.get(key, 0) + amt
            total_received_all += amt

    labels = sorted(set(monthly_sent.keys()) | set(monthly_received.keys()))
    sent_data = [monthly_sent.get(k, 0) for k in labels]
    recv_data = [monthly_received.get(k, 0) for k in labels]

    return {
        "labels": labels,
        "sent": sent_data,
        "received": recv_data,
        "total_sent": total_sent_all,
        "total_received": total_received_all,
        "this_month_spent": this_month_spent,
    }



@app.route("/college-services")
def college_services():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    services = [
        {"code": "canteen", "name": "Canteen", "image": "canteen.jpg"},
        {"code": "bookmart", "name": "Bookmart", "image": "bookmart.jpg"},
        {"code": "vending", "name": "Vending Machine", "image": "vending.jpg"},
        {"code": "fees", "name": "College Fees", "image": "fees.jpg"},
        {"code": "events", "name": "Club Events", "image": "events.jpg"},
    ]
    return render_template("college_services.html", user=user, services=services)
@app.route("/college-services/<code>", methods=["GET", "POST"])
def pay_service(code):
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    services = {
        "canteen": "Canteen",
        "bookmart": "Bookmart",
        "vending": "Vending Machine",
        "fees": "College Fees",
        "events": "Club Events",
    }
    service_name = services.get(code, "Service")

    if request.method == "POST":
        amount = float(request.form.get("amount"))
        note = f"{service_name} payment"
        uid = user["id"]

        current_balance = float(user.get("balance", 0.0))
        if amount > current_balance:
            flash("Payment failed: insufficient wallet balance.", "danger")
            return redirect(url_for("pay_service", code=code))

        txn = {
            "user_id": uid,
            "from_upi": user["upi_id"],
            "to": code,
            "display_name": service_name,
            "amount": amount,
            "note": note,
            "type": "sent",
            "timestamp": datetime.utcnow(),
        }
        db.collection("transactions").add(txn)
        db.collection("users").document(uid).update(
            {"balance": firestore.Increment(-amount)}
        )
        flash(f"Paid ₹{amount:.2f} to {service_name}", "success")
        return redirect(url_for("college_services"))

    return render_template("pay_service.html", user=user, service_name=service_name, code=code)


@app.route("/profile", methods=["GET", "POST"])
def profile():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form.get("name").strip()
        phone = request.form.get("phone").strip()
        class_name = request.form.get("class").strip()
        batch = request.form.get("batch").strip()
        year = request.form.get("year").strip()

        db.collection("users").document(user["id"]).update(
            {
                "name": name,
                "phone": phone,
                "class": class_name,
                "batch": batch,
                "year": year,
            }
        )
        flash("Profile updated", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html", user=user)
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
