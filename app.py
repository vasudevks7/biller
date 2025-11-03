from flask import Flask, render_template, request, redirect, jsonify, url_for # type: ignore
import sqlite3
import os

app = Flask(__name__)

# -------------------------------
# Initialize Database
# -------------------------------
def init_db():
    conn = sqlite3.connect('database.db')
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
                        extra_amount REAL
                    )''')

    
    # Bill Items Table with HSN Code
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

    # 🔹 Add HSN column if old table exists
    cursor.execute("PRAGMA table_info(bill_items)")
    cols = [col[1] for col in cursor.fetchall()]
    if "hsn" not in cols:
        cursor.execute("ALTER TABLE bill_items ADD COLUMN hsn TEXT")



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

    cursor.execute("PRAGMA table_info(bills)")
    columns = [col[1] for col in cursor.fetchall()]
    if "tax_type" not in columns:
        cursor.execute("ALTER TABLE bills ADD COLUMN tax_type TEXT")


    conn.commit()
    conn.close()

# -------------------------------
# ROUTES
# -------------------------------
@app.route('/')
def home():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # ✅ Fetch company logo (existing logic)
    cursor.execute("SELECT * FROM company LIMIT 1")
    company = cursor.fetchone()

    # ✅ Get bills count in this month
    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM bills
        WHERE strftime('%m', date) = strftime('%m', 'now')
          AND strftime('%Y', date) = strftime('%Y', 'now')
    """)
    bills_count = cursor.fetchone()['count']

    # ✅ Get last invoice number
    cursor.execute("SELECT invoice_number FROM bills ORDER BY id DESC LIMIT 1")
    last_invoice_row = cursor.fetchone()
    last_invoice = last_invoice_row['invoice_number'] if last_invoice_row else "—"

    conn.close()

    # ✅ Handle logo
    logo = url_for('static', filename=f'uploads/{company["logo"]}') if company and company['logo'] else url_for('static', filename='uploads/default.png')

    return render_template('index.html',
                           logo=logo,
                           bills_count=bills_count,
                           last_invoice=last_invoice)



@app.route('/customers')
def customers():
    conn = sqlite3.connect('database.db')
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

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (name, address, phone, gst, state) VALUES (?, ?, ?, ?, ?)",
                       (name, address, phone, gst, state))
        conn.commit()
        conn.close()
        return redirect('/customers')

    return render_template('newCustomer.html')


@app.route('/delete/<int:id>')
def delete_customer(id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect('/customers')


# -------------------------------
# BILL ROUTES
# -------------------------------
@app.route('/new-bill')
def new_bill():
    return render_template('new_bill.html')


@app.route('/save-bill', methods=['POST'])
def save_bill():
    data = request.get_json()
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Save main bill details
    cursor.execute("""
        INSERT INTO bills (date, invoice_number, customer_name, grand_total, extra_title, extra_amount, tax_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (data['date'], data['invoice_number'], data['customer_name'],
          data['grand_total'], data.get('extra_title', ''), data.get('extra_amount', 0), data.get('tax_type', '')))

    bill_id = cursor.lastrowid

    # Save each item with HSN code
    for item in data['items']:
        cursor.execute("""
            INSERT INTO bill_items (bill_id, name, hsn, qty, rate, total)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            bill_id,
            item.get('name'),
            item.get('hsn', ''),  # ✅ Save HSN code
            item.get('qty'),
            item.get('rate'),
            item.get('total')
        ))

    conn.commit()
    conn.close()
    return jsonify({"message": "Bill saved successfully!"})



@app.route('/history')
def history():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all bills
    cursor.execute("SELECT * FROM bills ORDER BY id DESC")
    bills = cursor.fetchall()

    all_bills = []
    for bill in bills:
        # Get items for each bill
        cursor.execute("SELECT * FROM bill_items WHERE bill_id = ?", (bill['id'],))
        items = cursor.fetchall()

        # Get customer details
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
            "extra_title": bill['extra_title'] if 'extra_title' in bill.keys() else '',
            "extra_amount": bill['extra_amount'] if 'extra_amount' in bill.keys() else '',
            "tax_type": bill['tax_type'] if 'tax_type' in bill.keys() else '',  # 👈 add this line
            "items": items,
            "customer": customer_details
        })

    conn.close()
    return render_template('history.html', bills=all_bills)


@app.route('/delete-bill/<int:bill_id>', methods=['POST'])
def delete_bill(bill_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bill_items WHERE bill_id = ?", (bill_id,))
    cursor.execute("DELETE FROM bills WHERE id = ?", (bill_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Bill deleted successfully"})


@app.route('/edit-bill/<int:bill_id>')
def edit_bill(bill_id):
    conn = sqlite3.connect('database.db')
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
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE bills
        SET date = ?, invoice_number = ?, customer_name = ?, grand_total = ?, tax_type = ?
        WHERE id = ?
    """, (data['date'], data['invoice_number'], data['customer_name'],
          data['grand_total'], data['tax_type'], data['bill_id']))

    cursor.execute("DELETE FROM bill_items WHERE bill_id = ?", (data['bill_id'],))

    for item in data['items']:
        cursor.execute("""
            INSERT INTO bill_items (bill_id, name, hsn, qty, rate, total)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data['bill_id'],
            item.get('name'),
            item.get('hsn', ''),  # ✅ Include HSN
            item.get('qty'),
            item.get('rate'),
            item.get('total')
        ))

    conn.commit()
    conn.close()
    return jsonify({"message": "Bill updated successfully!"})


# -------------------------------
# SEARCH & CUSTOMER DETAILS
# -------------------------------
@app.route('/search-customer')
def search_customer():
    q = request.args.get('q', '').lower()
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM users WHERE lower(name) LIKE ?", (f"%{q}%",))
    results = [row[0] for row in cursor.fetchall()]
    conn.close()
    return jsonify(results)


@app.route('/get-customer-details')
def get_customer_details():
    name = request.args.get('name', '')
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT address, phone, gst, state FROM users WHERE name = ?", (name,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return jsonify({"address": row[0], "phone": row[1], "gst": row[2], "state": row[3]})
    return jsonify({})


# -------------------------------
# COMPANY DETAILS
# -------------------------------
@app.route('/company', methods=['GET', 'POST'])
def company():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM company LIMIT 1")
    existing = cursor.fetchone()

    if request.method == 'POST':
        data = {k: request.form.get(k) for k in [
            "name", "address", "phone", "gst", "state",
            "bank_name", "ifsc", "account_number", "account_name"
        ]}

        upload_dir = os.path.join('static', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)

        # --- Logo Upload ---
        logo_file = request.files.get('logo_file')
        logo_name = existing['logo'] if existing else None
        if logo_file and logo_file.filename.strip():
            logo_name = 'company_logo_' + logo_file.filename
            logo_file.save(os.path.join(upload_dir, logo_name))

        # --- Signature Upload ---
        signature_file = request.files.get('signature_file')
        signature_name = existing['signature'] if existing else None
        if signature_file and signature_file.filename.strip():
            signature_name = 'company_sign_' + signature_file.filename
            signature_file.save(os.path.join(upload_dir, signature_name))

        # Save new data
        cursor.execute("DELETE FROM company")
        cursor.execute("""
            INSERT INTO company (name, address, phone, gst, state, bank_name, ifsc, account_number, account_name, logo, signature)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (data['name'], data['address'], data['phone'], data['gst'], data['state'],
              data['bank_name'], data['ifsc'], data['account_number'], data['account_name'], logo_name, signature_name))
        conn.commit()

    cursor.execute("SELECT * FROM company LIMIT 1")
    company = cursor.fetchone()
    conn.close()
    return render_template('company.html', company=company)

# -------------------------------
# PRINT BILL
# -------------------------------
@app.route('/print-bill/<int:bill_id>')
def print_bill(bill_id):
    def number_to_words(n):
        units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
        teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen",
                 "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
        tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

        def words(num):
            if num < 10:
                return units[num]
            elif num < 20:
                return teens[num - 10]
            elif num < 100:
                return tens[num // 10] + (" " + units[num % 10] if num % 10 != 0 else "")
            elif num < 1000:
                return units[num // 100] + " Hundred" + (" and " + words(num % 100) if num % 100 != 0 else "")
            elif num < 100000:
                return words(num // 1000) + " Thousand" + (" " + words(num % 1000) if num % 1000 != 0 else "")
            elif num < 10000000:
                return words(num // 100000) + " Lakh" + (" " + words(num % 100000) if num % 100000 != 0 else "")
            else:
                return words(num // 10000000) + " Crore" + (" " + words(num % 10000000) if num % 10000000 != 0 else "")

        if n == 0:
            return "Zero Rupees Only"
        else:
            return words(int(n)) + " Rupees Only"

    # Database connection
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM bills WHERE id = ?", (bill_id,))
    bill = cursor.fetchone()
    if not bill:
        conn.close()
        return "Bill not found", 404

    cursor.execute("SELECT * FROM users WHERE name = ?", (bill['customer_name'],))
    customer = cursor.fetchone()

    cursor.execute("SELECT * FROM company LIMIT 1")
    company = cursor.fetchone()

    cursor.execute("SELECT * FROM bill_items WHERE bill_id = ?", (bill_id,))
    items = cursor.fetchall()

    # Convert total to words
    grand_total = bill['grand_total'] if 'grand_total' in bill.keys() else 0
    amount_in_words = number_to_words(grand_total)

    conn.close()

    # Pass amount_in_words to template
    return render_template(
        'print_bill.html',
        bill=bill,
        items=items,
        company=company,
        customer=customer,
        amount_in_words=amount_in_words
    )

@app.route('/about')
def about():
    return render_template('about.html')


# -------------------------------
# Run the App
# -------------------------------
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
