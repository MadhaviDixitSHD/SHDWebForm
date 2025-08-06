from flask import Flask, render_template, request, redirect
import pyodbc
import re

app = Flask(__name__)

def get_connection():
    conn_str = (
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=shdfreesqldbserver.database.windows.net;'
        'DATABASE=SHDCMMCDB;'
        'UID=Madhavi;'
        'PWD=June23@2025-SHD;'
        'Encrypt=yes;'
        'TrustServerCertificate=no;'
        'Connection Timeout=30;'
    )
    return pyodbc.connect(conn_str)

@app.route('/', methods=['GET', 'POST'])
def index():
    controls = []
    show_create = False
    selected_level = None
    customer_id = None
    error = None
    customer = None  
    company_name = None
    existing_data = {}

    if request.method == 'POST':
        customer_id = request.form['customer_id']
        selected_level = request.form.get('level', 'Level 1')

        conn = get_connection()
        cursor = conn.cursor()

        # Check if customer exists
        cursor.execute("SELECT Company FROM Customers WHERE CustomerID = ?", (customer_id,))
        customer = cursor.fetchone()
        company_name = customer[0] if customer else None

        if customer:
            # Fetch controls based on selected level
            if selected_level == 'Level 1':
                cursor.execute("""
                    SELECT Identifier, SecurityRequirement, Discussion
                    FROM vw_ControlWithLevels
                    WHERE LevelName = 'Level 1'
                    ORDER BY CAST(PARSENAME(Identifier, 1) AS INT)
                """)
            elif selected_level == 'Level 2':
                cursor.execute("""
                    SELECT Identifier, SecurityRequirement, Discussion
                    FROM vw_ControlWithLevels
                    WHERE LevelName IN ('Level 1', 'Level 2')
                    ORDER BY CAST(PARSENAME(Identifier, 1) AS INT)
                """)
            controls = cursor.fetchall()

            def parse_identifier(identifier):
                return [int(x) for x in re.findall(r'\d+', identifier)]

            controls.sort(key=lambda row: parse_identifier(row[0]))

        else:
            error = "Customer ID not found. Please create a new customer."
            show_create = True

        cursor.execute("""SELECT Identifier, StatusID, Discussion FROM ControlCustomerMapping WHERE CustomerID = ?
        """, (customer_id,))
        existing_data = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}    

        conn.close()

    return render_template('form.html', controls=controls, customer_id=customer_id, show_create=show_create, selected_level=selected_level if customer else None, error=error if not customer else None, company_name=company_name, existing_data=existing_data)

@app.route('/create_customer', methods=['POST'])
def create_customer():
    #customer_id = request.form['customer_id']
    name = request.form['name']
    title = request.form['title']
    company = request.form['company']
    email = request.form['email']
    phone = request.form['phone']
    address = request.form['address']

    # Optional second contact details
    contact_name = request.form.get('contact_name')
    contact_title = request.form.get('contact_title')
    contact_email = request.form.get('contact_email')
    contact_phone = request.form.get('contact_phone')
    contact_address = request.form.get('contact_address')

    conn = get_connection()
    cursor = conn.cursor()

    # Insert into Customers table
    cursor.execute("""
        INSERT INTO Customers (Name, Title, Company, Email, Phone, Address)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, title, company, email, phone, address))

    cursor.execute("SELECT SCOPE_IDENTITY()")
    customer_id = cursor.fetchone()[0]

    # Optional: Insert into CustomerContacts if contact info exists
    if contact_name:
        cursor.execute("""
            INSERT INTO CustomerContacts (CustomerID, Name, Title, Email, Phone, Address)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (customer_id, contact_name, contact_title, contact_email, contact_phone, contact_address))

    conn.commit()
    conn.close()

    return redirect(f"/?customer_id={customer_id}")

@app.route('/submit', methods=['POST'])
def submit():
    customer_id = request.form['customer_id']
    conn = get_connection()
    cursor = conn.cursor()

    for key in request.form:
        if key.startswith('status_'):
            identifier = key.replace('status_', '')  # Extract Identifier
            status_id = int(request.form[key])
            discussion = request.form.get(f'desc_{identifier}', '')

            cursor.execute("""
                IF EXISTS (
                    SELECT 1 FROM ControlCustomerMapping
                    WHERE Identifier = ? AND CustomerID = ?
                )
                BEGIN
                    UPDATE ControlCustomerMapping
                    SET StatusID = ?, Discussion = ?
                    WHERE Identifier = ? AND CustomerID = ?
                END
                ELSE
                BEGIN
                    INSERT INTO ControlCustomerMapping (Identifier, CustomerID, StatusID, Discussion)
                    VALUES (?, ?, ?, ?)
                    END
            """, (identifier, customer_id, status_id, discussion, identifier, customer_id, identifier, customer_id, status_id, discussion))


    conn.commit()
    conn.close()
    return "Submitted successfully!"

if __name__ == '__main__':
    app.run(debug=True)
