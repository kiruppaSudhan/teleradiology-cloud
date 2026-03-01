from flask import Flask, request, redirect, url_for, session
import bcrypt
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# ========================
# APP CONFIG
# ========================
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set!")

# ========================
# DATABASE CONNECTION
# ========================
def get_db_connection():
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor
    )

# ========================
# CREATE TABLES
# ========================
def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(100) UNIQUE NOT NULL,
        password BYTEA NOT NULL,
        role VARCHAR(50) NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id SERIAL PRIMARY KEY,
        fhir_id VARCHAR(100),
        identifier_system VARCHAR(100),
        mrn VARCHAR(100),
        name VARCHAR(100),
        age VARCHAR(10),
        gender VARCHAR(20),
        contact VARCHAR(100),
        status VARCHAR(50),
        report TEXT
    );
    """)

    conn.commit()
    cur.close()
    conn.close()

create_tables()

# ========================
# HOME
# ========================
@app.route('/')
def home():
    return '''
    <h1>Tele-Radiology System</h1>
    <a href="/login">Login</a> |
    <a href="/register">Register</a>
    '''

# ========================
# REGISTER
# ========================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            hashed = bcrypt.hashpw(
                request.form['password'].encode(),
                bcrypt.gensalt()
            )

            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute(
                "INSERT INTO users (username,password,role) VALUES (%s,%s,%s)",
                (request.form['username'], hashed, request.form['role'])
            )

            conn.commit()
            cur.close()
            conn.close()

            return redirect(url_for('login'))

        except Exception as e:
            return f"Error: {e}"

    return '''
    <h2>Create Account</h2>
    <form method="post">
    Username: <input name="username" required><br><br>
    Password: <input type="password" name="password" required><br><br>
    <select name="role">
        <option value="technician">Technician</option>
        <option value="radiologist">Radiologist</option>
    </select><br><br>
    <button>Register</button>
    </form>
    '''

# ========================
# LOGIN
# ========================
@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM users WHERE username=%s",
            (request.form['username'],)
        )
        user = cur.fetchone()

        cur.close()
        conn.close()

        if user:
            stored_password = user['password']

            # IMPORTANT for PostgreSQL BYTEA
            if isinstance(stored_password, memoryview):
                stored_password = stored_password.tobytes()

            if bcrypt.checkpw(
                request.form['password'].encode(),
                stored_password
            ):
                session['username'] = user['username']
                session['role'] = user['role']
                return redirect('/dashboard')

        return "Invalid credentials"

    return '''
    <h2>Login</h2>
    <form method="post">
    Username: <input name="username" required><br><br>
    Password: <input type="password" name="password" required><br><br>
    <button>Login</button>
    </form>
    '''

# ========================
# DASHBOARD
# ========================
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect('/')

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM patients")
    patients = cur.fetchall()

    cur.close()
    conn.close()

    rows = ""
    for p in patients:
        rows += f"""
        <tr>
        <td>{p['mrn']}</td>
        <td>{p['name']}</td>
        <td>{p['status']}</td>
        </tr>
        """

    add_btn = ""
    if session['role'] == "technician":
        add_btn = '<a href="/add_patient_page">Add Patient</a><br><br>'

    return f"""
    <h2>{session['role'].capitalize()} Dashboard</h2>
    {add_btn}
    <table border="1">
    <tr><th>MRN</th><th>Name</th><th>Status</th></tr>
    {rows}
    </table>
    <br>
    <a href="/logout">Logout</a>
    """

# ========================
# ADD PATIENT
# ========================
@app.route('/add_patient_page')
def add_patient_page():
    if session.get('role') != "technician":
        return "Unauthorized"

    return '''
    <h2>Register Patient</h2>
    <form method="post" action="/add_patient">
    Name: <input name="name" required><br><br>
    Age: <input name="age" required><br><br>
    Gender: <input name="gender" required><br><br>
    Contact: <input name="contact" required><br><br>
    <button>Add Patient</button>
    </form>
    '''

@app.route('/add_patient', methods=['POST'])
def add_patient():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) as count FROM patients")
    count = cur.fetchone()['count'] + 1

    mrn = f"MRN{count:04d}"
    fhir_id = f"PAT{count:04d}"

    cur.execute("""
        INSERT INTO patients
        (fhir_id,identifier_system,mrn,name,age,gender,contact,status,report)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """,
    (fhir_id, "hospital", mrn,
     request.form['name'],
     request.form['age'],
     request.form['gender'],
     request.form['contact'],
     "Pending", ""))

    conn.commit()
    cur.close()
    conn.close()

    return redirect('/dashboard')

# ========================
# LOGOUT
# ========================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ========================
# LOCAL RUN
# ========================
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8000)
