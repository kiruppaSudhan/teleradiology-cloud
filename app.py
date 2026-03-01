from flask import Flask, request, redirect, session, render_template_string, send_from_directory
import bcrypt
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# =========================
# FILE CONFIG
# =========================
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "dcm"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


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
<!DOCTYPE html>
<html>
<head>
<title>Tele-Radiology System</title>

<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css" rel="stylesheet">

<style>
body {
    background: url('https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?auto=format&fit=crop&w=1600&q=80') no-repeat center center fixed;
    background-size: cover;
}
.overlay {
    background-color: rgba(0,0,0,0.6);
    height: 100vh;
}
.center-box {
    background: white;
    padding: 40px;
    border-radius: 15px;
    box-shadow: 0 0 25px rgba(0,0,0,0.4);
}
</style>
</head>

<body>
<div class="overlay d-flex justify-content-center align-items-center">
<div class="center-box text-center">
<h2 class="mb-4"><i class="fa-solid fa-x-ray"></i> Tele-Radiology System</h2>

<a href="/login_page" class="btn btn-primary btn-lg m-2">
<i class="fa-solid fa-right-to-bracket"></i> Login
</a>

<a href="/register" class="btn btn-success btn-lg m-2">
<i class="fa-solid fa-user-plus"></i> Register
</a>

</div>
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

    # USERS TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(100) UNIQUE NOT NULL,
        password BYTEA NOT NULL,
        role VARCHAR(50) NOT NULL
    );
    """)

    # PATIENTS TABLE
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

    # SINGLE STUDIES TABLE (FIXED)
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
            cur.close()
            conn.close()
            return "Username already exists"

        cur.close()
        conn.close()
        return redirect("/login_page")

    return render_template_string("""
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
    """)


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
<!DOCTYPE html>
<html>
<head>
<title>Dashboard</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css" rel="stylesheet">
</head>
<body>

<nav class="navbar navbar-dark bg-dark px-4">
<span class="navbar-brand">
<i class="fa-solid fa-hospital"></i> {{ role.capitalize() }} Dashboard
</span>
<a href="/logout" class="btn btn-danger">Logout</a>
</nav>

<div class="container mt-4">

{% if role == "technician" %}
<a href="/add_patient_page" class="btn btn-success mb-4">
<i class="fa-solid fa-user-plus"></i> Add Patient
</a>
{% endif %}

<div class="row">
{% for p in patients %}
<div class="col-md-4">
<div class="card shadow mb-4">
<div class="card-body">
<h5 class="card-title">{{ p.mrn }}</h5>
<p><strong>Name:</strong> {{ p.name }}</p>

{% if p.status == "Pending" %}
<p>Status: <span class="badge bg-warning text-dark">Pending</span></p>
{% else %}
<p>Status: <span class="badge bg-success">Reviewed</span></p>
{% endif %}

<a href="/view/{{ p.id }}" class="btn btn-primary btn-sm">
<i class="fa-solid fa-folder-open"></i> Open Case
</a>
</div>
</div>
</div>
{% endfor %}
</div>

</div>
</body>
</html>
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
    Name: <input name="name" required><br><br>
    Age: <input name="age" required><br><br>
    Gender: <input name="gender" required><br><br>
    Contact: <input name="contact" required><br><br>
    Upload Image: <input type="file" name="file"><br><br>
    <button>Add</button>
    </form>
    """


@app.route("/add_patient", methods=["POST"])
def add_patient():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) as count FROM patients")
    count = cur.fetchone()["count"] + 1

    mrn = f"MRN{count:04d}"
    fhir_id = f"PAT{count:04d}"

    cur.execute("""
        INSERT INTO patients
        (fhir_id,identifier_system,mrn,name,age,gender,contact,status,report)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
    """,
    (fhir_id, "hospital", mrn,
     request.form["name"],
     request.form["age"],
     request.form["gender"],
     request.form["contact"],
     "Pending", ""))

    patient_id = cur.fetchone()["id"]
    conn.commit()

    if "file" in request.files:
        file = request.files["file"]
        if file and allowed_file(file.filename):
            image_binary = file.read()

            cur.execute("""
                INSERT INTO studies (patient_id, file_name, image_data)
                VALUES (%s,%s,%s)
            """, (patient_id, file.filename, psycopg2.Binary(image_binary)))
            conn.commit()

    cur.close()
    conn.close()

    return redirect("/dashboard")


# =========================
# VIEW PATIENT
# =========================
@app.route("/view/<int:patient_id>", methods=["GET", "POST"])
def view_patient(patient_id):
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

    cur.execute("SELECT * FROM studies WHERE patient_id=%s", (patient_id,))
    study = cur.fetchone()

    cur.close()
    conn.close()

    return render_template_string("""
    <h3>{{ patient.name }} ({{ patient.mrn }})</h3>
    <p>Status: {{ patient.status }}</p>

    {% if study %}
        <img src="/uploads/{{ study.file_name }}" width="400"><br><br>
    {% endif %}

    {% if role == 'radiologist' %}
    <form method="post">
    <textarea name="report" rows="5" cols="50">{{ patient.report }}</textarea><br><br>
    <button>Submit Report</button>
    </form>
    {% endif %}

    <br><a href="/dashboard">Back</a>
    """, patient=patient, study=study, role=session["role"])


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")
