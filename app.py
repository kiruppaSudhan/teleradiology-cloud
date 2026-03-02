from flask import Flask, request, redirect, session, render_template_string
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
# =========================
# DASHBOARD (PROFESSIONAL UI RESTORED)
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
<body class="bg-light">

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
<div class="col-md-6 col-lg-4">
<div class="card shadow-sm mb-4 border-0">
<div class="card-body">

<h5 class="card-title">{{ p.mrn }}</h5>
<p><strong>Name:</strong> {{ p.name }}</p>

{% if p.status == "Pending" %}
<p>Status:
<span class="badge bg-warning text-dark">Pending</span>
</p>
{% else %}
<p>Status:
<span class="badge bg-success">Reviewed</span>
</p>
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
    Name: <input name="name"><br><br>
    Age: <input name="age"><br><br>
    Gender: <input name="gender"><br><br>
    Contact: <input name="contact"><br><br>
    BP: <input name="bp"><br><br>
    HR: <input name="hr"><br><br>
    Temp: <input name="temperature"><br><br>
    SPO2: <input name="spo2"><br><br>
    RR: <input name="rr"><br><br>
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

    if "file" in request.files:
        file = request.files["file"]
        if file and file.filename != "":
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
# IMAGE ROUTE (IMPORTANT)
# =========================
@app.route("/image/<int:patient_id>")
def get_image(patient_id):

    if "username" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT dicom_data
        FROM studies
        WHERE patient_id=%s
    """, (patient_id,))

    study = cur.fetchone()
    cur.close()
    conn.close()

    if not study:
        return "No Study Found", 404

    dicom_bytes = study["dicom_data"]

    if isinstance(dicom_bytes, memoryview):
        dicom_bytes = dicom_bytes.tobytes()

    try:
        ds = pydicom.dcmread(io.BytesIO(dicom_bytes))

        # Handle multi-frame
        if hasattr(ds, "NumberOfFrames") and ds.NumberOfFrames > 1:
            pixel_array = ds.pixel_array[0]
        else:
            pixel_array = ds.pixel_array

        pixel_array = pixel_array.astype(float)

        # Prevent division by zero
        if pixel_array.max() == pixel_array.min():
            scaled = np.zeros(pixel_array.shape, dtype=np.uint8)
        else:
            scaled = (pixel_array - pixel_array.min()) / \
                     (pixel_array.max() - pixel_array.min())
            scaled = (scaled * 255).astype(np.uint8)

        image = Image.fromarray(scaled)

        img_io = io.BytesIO()
        image.save(img_io, format="PNG")
        img_io.seek(0)

        return img_io.read(), 200, {
            "Content-Type": "image/png"
        }

    except Exception as e:
        return f"DICOM Error: {str(e)}", 500

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

    cur.close()
    conn.close()

    return render_template_string("""
    <h3>{{ patient.name }} ({{ patient.mrn }})</h3>
    <p>Status: {{ patient.status }}</p>
    <img src="/image/{{ patient.id }}" width="400"><br><br>

    {% if role == 'radiologist' %}
    <form method="post">
    <textarea name="report" rows="5" cols="50">{{ patient.report }}</textarea><br><br>
    <button>Submit Report</button>
    </form>
    {% endif %}
    <br><a href="/dashboard">Back</a>
    """, patient=patient, role=session["role"])

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")
@app.route("/fix_db")
def fix_db():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Drop old studies table
        cur.execute("DROP TABLE IF EXISTS studies;")

        # Create new studies table
        cur.execute("""
        CREATE TABLE studies (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER REFERENCES patients(id) ON DELETE CASCADE,
            file_name VARCHAR(255),
            dicom_data BYTEA NOT NULL
        );
        """)

        conn.commit()
        return "Studies table recreated successfully!"

    except Exception as e:
        conn.rollback()
        return f"Error: {str(e)}"

    finally:
        cur.close()
        conn.close()

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
