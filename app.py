from flask import Flask, request, redirect, session, render_template_string, Response
import bcrypt
import os
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")


# =========================
# DATABASE CONNECTION
# =========================
def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        return None

    return psycopg2.connect(
        database_url,
        cursor_factory=RealDictCursor,
        sslmode="require"
    )


# =========================
# HOME
# =========================
@app.route("/")
def home():
    return """
    <h1>Tele-Radiology System</h1>
    <a href="/login_page">Login</a> |
    <a href="/register">Register</a>
    """


# =========================
# INIT DATABASE
# =========================
@app.route("/init_db")
def init_db():
    conn = get_db_connection()
    if not conn:
        return "DATABASE_URL not set!"

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
        mrn VARCHAR(100),
        name VARCHAR(100),
        age VARCHAR(10),
        gender VARCHAR(20),
        contact VARCHAR(100),
        status VARCHAR(50),
        report TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS studies (
        id SERIAL PRIMARY KEY,
        patient_id INTEGER REFERENCES patients(id) ON DELETE CASCADE,
        file_name VARCHAR(255),
        image_data BYTEA
    );
    """)

    conn.commit()
    cur.close()
    conn.close()

    return "Database initialized successfully!"
    

# =========================
# LOGIN PAGE
# =========================
@app.route("/login_page")
def login_page():
    return """
    <h2>Login</h2>
    <form method="post" action="/login">
    Username: <input name="username"><br><br>
    Password: <input type="password" name="password"><br><br>
    <button>Login</button>
    </form>
    """


# =========================
# REGISTER
# =========================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        conn = get_db_connection()
        if not conn:
            return "DATABASE_URL not set!"

        cur = conn.cursor()

        hashed = bcrypt.hashpw(
            request.form["password"].encode(),
            bcrypt.gensalt()
        )

        try:
            cur.execute(
                "INSERT INTO users (username,password,role) VALUES (%s,%s,%s)",
                (request.form["username"], hashed, request.form["role"])
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            cur.close()
            conn.close()
            return f"Error: {e}"

        cur.close()
        conn.close()
        return redirect("/login_page")

    return """
    <h2>Register</h2>
    <form method="post">
    Username: <input name="username"><br><br>
    Password: <input type="password" name="password"><br><br>
    <select name="role">
        <option value="technician">Technician</option>
        <option value="radiologist">Radiologist</option>
    </select><br><br>
    <button>Register</button>
    </form>
    """


# =========================
# LOGIN
# =========================
@app.route("/login", methods=["POST"])
def login():
    conn = get_db_connection()
    if not conn:
        return "DATABASE_URL not set!"

    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE username=%s",
                (request.form["username"],))
    user = cur.fetchone()

    cur.close()
    conn.close()

    if not user:
        return "User not found"

    stored_password = user["password"]

    if isinstance(stored_password, memoryview):
        stored_password = stored_password.tobytes()

    if bcrypt.checkpw(request.form["password"].encode(), stored_password):
        session["username"] = user["username"]
        session["role"] = user["role"]
        return redirect("/dashboard")

    return "Invalid password"


# =========================
# DASHBOARD
# =========================
@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect("/")

    conn = get_db_connection()
    if not conn:
        return "DATABASE_URL not set!"

    cur = conn.cursor()
    cur.execute("SELECT * FROM patients ORDER BY id DESC")
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
    <h2>Dashboard</h2>
    <table border="1">
    <tr><th>MRN</th><th>Name</th><th>Status</th></tr>
    {rows}
    </table>
    <br><a href="/logout">Logout</a>
    """


# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")
