from flask import Flask, request, redirect, url_for, session
import bcrypt
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# ==============================
# APP CONFIG
# ==============================
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set!")

# ==============================
# DATABASE CONNECTION FUNCTION
# ==============================
def get_db_connection():
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor
    )

# ==============================
# CREATE TABLES FUNCTION
# ==============================
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

# ==============================
# RUN TABLE CREATION
# ==============================
create_tables()

# ==============================
# ROUTES
# ==============================
@app.route('/')
def home():
    return '''
    <h1>Tele-Radiology System</h1>
    <a href="/login">Login</a> |
    <a href="/register">Register</a>
    '''

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
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

            # 🔥 FIX FOR PostgreSQL BYTEA
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

    return f"""
    <h2>{session['role'].capitalize()} Dashboard</h2>
    <table border="1">
    <tr><th>MRN</th><th>Name</th><th>Status</th></tr>
    {rows}
    </table>
    <br>
    <a href="/logout">Logout</a>
    """

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8000)
