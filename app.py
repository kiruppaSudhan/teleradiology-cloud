from flask import Flask, request, redirect, session, render_template_string
import bcrypt
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import io
import pydicom
import numpy as np
from PIL import Image

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# =========================
# DATABASE CONNECTION
# =========================
def get_db_connection():
    return psycopg2.connect(
        os.environ["DATABASE_URL"],
        cursor_factory=RealDictCursor,
        sslmode="require"
    )

# =========================
# HOME
# =========================
@app.route("/")
def home():
    return render_template_string("""
    <html>
    <head>
    <title>Tele-Radiology System</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-dark text-center text-white d-flex align-items-center justify-content-center" style="height:100vh;">
        <div>
            <h1>Tele-Radiology System</h1>
            <a href="/login_page" class="btn btn-primary m-2">Login</a>
            <a href="/register" class="btn btn-success m-2">Register</a>
        </div>
    </body>
    </html>
    """)

# =========================
# INIT DATABASE
# =========================
@app.route("/init_db")
def init_db():
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
        bp VARCHAR(20),
        hr VARCHAR(20),
        temperature VARCHAR(20),
        spo2 VARCHAR(20),
        rr VARCHAR(20),
        status VARCHAR(50),
        report TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS studies (
        id SERIAL PRIMARY KEY,
        patient_id INTEGER REFERENCES patients(id) ON DELETE CASCADE,
        file_name VARCHAR(255),
        dicom_data BYTEA NOT NULL
    );
    """)

    conn.commit()
    cur.close()
    conn.close()

    return "Database initialized successfully!"

# =========================
# REGISTER
# =========================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        conn = get_db_connection()
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
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            return "Username already exists"

        cur.close()
        conn.close()
        return redirect("/login_page")

    return """
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
    """

# =========================
# LOGIN
# =========================
@app.route("/login", methods=["POST"])
def login():
    conn = get_db_connection()
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
# DASHBOARD
# =========================
@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM patients ORDER BY id DESC")
    patients = cur.fetchall()
    cur.close()
    conn.close()

    return render_template_string("""
    <h2>{{ role.capitalize() }} Dashboard</h2>
    {% if role == "technician" %}
    <a href="/add_patient_page">Add Patient</a><br><br>
    {% endif %}

    <table border="1">
    <tr><th>MRN</th><th>Name</th><th>Status</th><th>Open</th></tr>
    {% for p in patients %}
    <tr>
        <td>{{ p.mrn }}</td>
        <td>{{ p.name }}</td>
        <td>{{ p.status }}</td>
        <td><a href="/view/{{ p.id }}">Open</a></td>
    </tr>
    {% endfor %}
    </table>
    <br><a href="/logout">Logout</a>
    """, patients=patients, role=session["role"])

# =========================
# ADD PATIENT
# =========================
@app.route("/add_patient_page")
def add_patient_page():
    if session.get("role") != "technician":
        return "Unauthorized"
    return """
    <h2>Add Patient</h2>
    <form method="post" action="/add_patient" enctype="multipart/form-data">
    Name: <input name="name"><br>
    Age: <input name="age"><br>
    Gender: <input name="gender"><br>
    Contact: <input name="contact"><br>
    BP: <input name="bp"><br>
    HR: <input name="hr"><br>
    Temp: <input name="temperature"><br>
    SPO2: <input name="spo2"><br>
    RR: <input name="rr"><br>
    DICOM File: <input type="file" name="file"><br><br>
    <button>Add</button>
    </form>
    """

@app.route("/add_patient", methods=["POST"])
def add_patient():
    if session.get("role") != "technician":
        return "Unauthorized"

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT COUNT(*) as count FROM patients")
        count = cur.fetchone()["count"] + 1

        mrn = f"MRN{count:04d}"
        fhir_id = f"PAT{count:04d}"

        cur.execute("""
        INSERT INTO patients
        (fhir_id,identifier_system,mrn,name,age,gender,contact,
         bp,hr,temperature,spo2,rr,status,report)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
        """,
        (fhir_id, "hospital", mrn,
         request.form["name"],
         request.form["age"],
         request.form["gender"],
         request.form["contact"],
         request.form["bp"],
         request.form["hr"],
         request.form["temperature"],
         request.form["spo2"],
         request.form["rr"],
         "Pending", ""))

        patient_id = cur.fetchone()["id"]
        conn.commit()

        file = request.files.get("file")
        if not file:
            return "No file uploaded"

        dicom_binary = file.read()

        cur.execute("""
        INSERT INTO studies (patient_id, file_name, dicom_data)
        VALUES (%s,%s,%s)
        """, (patient_id, file.filename,
              psycopg2.Binary(dicom_binary)))

        conn.commit()

    except Exception as e:
        conn.rollback()
        return str(e)

    finally:
        cur.close()
        conn.close()

    return redirect("/dashboard")

# =========================
# IMAGE ROUTE
# =========================
@app.route("/image/<int:patient_id>")
def get_image(patient_id):

    if "username" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT dicom_data FROM studies WHERE patient_id=%s",
                (patient_id,))
    study = cur.fetchone()

    cur.close()
    conn.close()

    if not study:
        return "No Study Found"

    dicom_bytes = study["dicom_data"]
    if isinstance(dicom_bytes, memoryview):
        dicom_bytes = dicom_bytes.tobytes()

    ds = pydicom.dcmread(io.BytesIO(dicom_bytes))
    pixel_array = ds.pixel_array.astype(float)

    scaled = (pixel_array - pixel_array.min()) / \
             (pixel_array.max() - pixel_array.min())
    scaled = (scaled * 255).astype(np.uint8)

    image = Image.fromarray(scaled)
    img_io = io.BytesIO()
    image.save(img_io, format="PNG")
    img_io.seek(0)

    return img_io.read(), 200, {"Content-Type": "image/png"}

# =========================
# VIEW PATIENT
# =========================
@app.route("/view/<int:patient_id>", methods=["GET", "POST"])
def view_patient(patient_id):

    if "username" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST" and session["role"] == "radiologist":
        cur.execute("""
        UPDATE patients
        SET report=%s, status='Reviewed'
        WHERE id=%s
        """, (request.form["report"], patient_id))
        conn.commit()

    cur.execute("SELECT * FROM patients WHERE id=%s", (patient_id,))
    patient = cur.fetchone()

    cur.close()
    conn.close()

    return render_template_string("""
    <h3>{{ patient.name }} ({{ patient.mrn }})</h3>
    <p>Status: {{ patient.status }}</p>
    <img src="/image/{{ patient.id }}" width="400"><br><br>

    {% if role == 'radiologist' %}
    <form method="post">
    <textarea name="report" rows="5" cols="50">{{ patient.report }}</textarea><br>
    <button>Submit Report</button>
    </form>
    {% endif %}

    <br><a href="/dashboard">Back</a>
    """, patient=patient, role=session["role"])

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/reset_all")
def reset_all():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("DROP TABLE IF EXISTS studies CASCADE;")
        cur.execute("DROP TABLE IF EXISTS patients CASCADE;")
        cur.execute("DROP TABLE IF EXISTS users CASCADE;")
        conn.commit()
        return "All tables deleted successfully!"
    except Exception as e:
        conn.rollback()
        return str(e)
    finally:
        cur.close()
        conn.close()
