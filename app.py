from flask import Flask, render_template, request, redirect, jsonify, url_for
import sqlite3
import os

app = Flask(__name__)

# -------------------------------
# Database Path (✅ Vercel Compatible)
# -------------------------------
DB_PATH = os.path.join("/tmp", "database.db")

# -------------------------------
# Initialize Database
# -------------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Users Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        address TEXT,
                        phone TEXT,
                        gst TEXT,
                        state TEXT
                    )''')

    # Bills Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS bills (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT,
                        invoice_number TEXT,
                        customer_name TEXT,
                        grand_total REAL,
                        extra_title TEXT,
                        extra_amount REAL,
                        tax_type TEXT
                    )''')

    # Bill Items Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS bill_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        bill_id INTEGER,
                        name TEXT,
                        hsn TEXT,
                        qty REAL,
                        rate REAL,
                        total REAL,
                        FOREIGN KEY (bill_id) REFERENCES bills(id)
                    )''')

    # Company Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS company (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    address TEXT,
                    phone TEXT,
                    gst TEXT,
                    state TEXT,
                    bank_name TEXT,
                    ifsc TEXT,
                    account_number TEXT,
                    account_name TEXT,
                    logo TEXT,
                    signature TEXT
                )''')

    conn.commit()
    conn.close()

# -------------------------------
# ROUTES
# -------------------------------
@app.route('/')
def home():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM company LIMIT 1")
    company = cursor.fetchone()

    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM bills
        WHERE strftime('%m', date) = strftime('%m', 'now')
          AND strftime('%Y', date) = strftime('%Y', 'now')
    """)
    bills_count = cursor.fetchone()['count']

    cursor.execute("SELECT invoice_number FROM bills ORDER BY id DESC LIMIT 1")
    last_invoice_row = cursor.fetchone()
    last_invoice = last_invoice_row['invoice_number'] if last_invoice_row else "—"

    conn.close()

    logo = url_for('static', filename=f'uploads/{company["logo"]}') if company and company['logo'] else url_for('static', filename='uploads/default.png')

    return render_template('index.html',
                           logo=logo,
                           bills_count=bills_count,
                           last_invoice=last_invoice)

@app.route('/customers')
def customers():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    data = cursor.fetchall()
    conn.close()
    return render_template('customers.html', data=data)

@app.route('/new-customer', methods=['GET', 'POST'])
def new_customer():
    if request.method == 'POST':
        name = request.form['name']
        address = request.form['address']
        phone = request.form['phone']
        gst = request.form['gst']
        state = request.form['state']

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (name, address, phone, gst, state) VALUES (?, ?, ?, ?, ?)",
                       (name, address, phone, gst, state))
        conn.commit()
        conn.close()
        return redirect('/customers')

    return render_template('newCustomer.html')

@app.route('/delete/<int:id>')
def delete_customer(id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect('/customers')

@app.route('/new-bill')
def new_bill():
    return render_template('new_bill.html')

@app.route('/save-bill', methods=['POST'])
def save_bill():
    data = request.get_json()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO bills (date, invoice_number, customer_name, grand_total, extra_title, extra_amount, tax_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (data['date'], data['invoice_number'], data['customer_name'],
          data['grand_total'], data.get('extra_title', ''), data.get('extra_amount', 0), data.get('tax_type', '')))

    bill_id = cursor.lastrowid

    for item in data['items']:
        cursor.execute("""
            INSERT INTO bill_items (bill_id, name, hsn, qty, rate, total)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (bill_id, item.get('name'), item.get('hsn', ''), item.get('qty'), item.get('rate'), item.get('total')))

    conn.commit()
    conn.close()
    return jsonify({"message": "Bill saved successfully!"})

@app.route('/history')
def history():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM bills ORDER BY id DESC")
    bills = cursor.fetchall()

    all_bills = []
    for bill in bills:
        cursor.execute("SELECT * FROM bill_items WHERE bill_id = ?", (bill['id'],))
        items = cursor.fetchall()
        cursor.execute("SELECT address, phone, gst, state FROM users WHERE name = ?", (bill['customer_name'],))
        user = cursor.fetchone()

        customer_details = {
            "address": user['address'] if user else '',
            "phone": user['phone'] if user else '',
            "gst": user['gst'] if user else '',
            "state": user['state'] if user else ''
        }

        all_bills.append({
            "id": bill['id'],
            "date": bill['date'],
            "invoice_number": bill['invoice_number'],
            "customer_name": bill['customer_name'],
            "grand_total": bill['grand_total'],
            "extra_title": bill['extra_title'],
            "extra_amount": bill['extra_amount'],
            "tax_type": bill['tax_type'],
            "items": items,
            "customer": customer_details
        })

    conn.close()
    return render_template('history.html', bills=all_bills)

@app.route('/delete-bill/<int:bill_id>', methods=['POST'])
def delete_bill(bill_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bill_items WHERE bill_id = ?", (bill_id,))
    cursor.execute("DELETE FROM bills WHERE id = ?", (bill_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Bill deleted successfully"})

@app.route('/edit-bill/<int:bill_id>')
def edit_bill(bill_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM bills WHERE id = ?", (bill_id,))
    bill = cursor.fetchone()

    cursor.execute("SELECT * FROM bill_items WHERE bill_id = ?", (bill_id,))
    items = cursor.fetchall()

    conn.close()
    return render_template('edit_bill.html', bill=dict(bill), items=[dict(i) for i in items])

@app.route('/update-bill', methods=['POST'])
def update_bill():
    data = request.get_json()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE bills
        SET date = ?, invoice_number = ?, customer_name = ?, grand_total = ?, tax_type = ?
        WHERE id = ?
    """, (data['date'], data['invoice_number'], data['customer_name'], data['grand_total'], data['tax_type'], data['bill_id']))

    cursor.execute("DELETE FROM bill_items WHERE bill_id = ?", (data['bill_id'],))

    for item in data['items']:
        cursor.execute("""
            INSERT INTO bill_items (bill_id, name, hsn, qty, rate, total)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (data['bill_id'], item.get('name'), item.get('hsn', ''), item.get('qty'), item.get('rate'), item.get('total')))

    conn.commit()
    conn.close()
    return jsonify({"message": "Bill updated successfully!"})

@app.route('/about')
def about():
    return render_template('about.html')

# -------------------------------
# Run the App
# -------------------------------
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
