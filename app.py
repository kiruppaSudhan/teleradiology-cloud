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
        raise Exception("DATABASE_URL not set")
    return psycopg2.connect(
        database_url,
        cursor_factory=RealDictCursor,
        sslmode="require"
    )


# =========================
# HOME (Render health check safe)
# =========================
@app.route("/")
def home():
    return "Tele-Radiology System is Running ✅"


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
@app.route("/login_page")
def login_page():
    return """
    <h2>Login</h2>
    <form method="post" action="/login">
    Username: <input name="username" required><br><br>
    Password: <input type="password" name="password" required><br><br>
    <button>Login</button>
    </form>
    """


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

    rows = ""
    for p in patients:
        rows += f"""
        <tr>
        <td>{p['mrn']}</td>
        <td>{p['name']}</td>
        <td>{p['status']}</td>
        <td><a href="/view/{p['id']}">Open</a></td>
        </tr>
        """

    add_btn = ""
    if session["role"] == "technician":
        add_btn = '<a href="/add_patient_page">Add Patient</a><br><br>'

    return f"""
    <h2>{session['role'].capitalize()} Dashboard</h2>
    {add_btn}
    <table border="1">
    <tr><th>MRN</th><th>Name</th><th>Status</th><th>Action</th></tr>
    {rows}
    </table>
    <br>
    <a href="/logout">Logout</a>
    """


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
# IMAGE ROUTE
# =========================
@app.route("/image/<int:patient_id>")
def get_image(patient_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT image_data FROM studies WHERE patient_id=%s", (patient_id,))
    study = cur.fetchone()
    cur.close()
    conn.close()

    if study and study["image_data"]:
        return Response(study["image_data"], mimetype="image/jpeg")

    return "No Image", 404


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


# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# IMPORTANT FOR LOCAL TESTING
if __name__ == "__main__":
    app.run(debug=True)
