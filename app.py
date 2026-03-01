from flask import Flask, request, redirect, url_for, session, send_from_directory
import os
import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"

# =========================
# CONFIG
# =========================
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "dcm"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set!")

# =========================
# DATABASE CONNECTION
# =========================
def get_db_connection():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode="require",
        cursor_factory=RealDictCursor
    )

# =========================
# CREATE TABLES
# =========================
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
        file_name VARCHAR(255)
    );
    """)

    conn.commit()
    cur.close()
    conn.close()

create_tables()

# =========================
# PROFESSIONAL UI TEMPLATE
# =========================
def render_template(title, body):
    return f"""
    <html>
    <head>
    <title>{title}</title>
    <style>
    body {{
        font-family: Arial;
        background: #f4f6f9;
        margin: 0;
    }}
    .navbar {{
        background: #1e2a38;
        padding: 15px;
        color: white;
        font-size: 20px;
    }}
    .container {{
        padding: 30px;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        background: white;
    }}
    th {{
        background: #2f3e4e;
        color: white;
        padding: 10px;
    }}
    td {{
        padding: 10px;
        border-bottom: 1px solid #ddd;
    }}
    button {{
        background: #007bff;
        color: white;
        padding: 8px 15px;
        border: none;
        cursor: pointer;
    }}
    input, textarea, select {{
        padding: 8px;
        width: 100%;
        margin-bottom: 10px;
    }}
    .card {{
        background: white;
        padding: 20px;
        margin-bottom: 20px;
        border-radius: 5px;
    }}
    </style>
    </head>
    <body>
    <div class="navbar">Tele-Radiology System</div>
    <div class="container">
    {body}
    </div>
    </body>
    </html>
    """

# =========================
# HOME
# =========================
@app.route('/')
def home():
    return render_template("Home", """
    <h2>Welcome</h2>
    <a href='/login_page'>Login</a> |
    <a href='/register'>Register</a>
    """)

# =========================
# REGISTER
# =========================
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == "POST":
        conn = get_db_connection()
        cur = conn.cursor()

        hashed = bcrypt.hashpw(request.form['password'].encode(), bcrypt.gensalt())

        cur.execute(
            "INSERT INTO users (username,password,role) VALUES (%s,%s,%s)",
            (request.form['username'], hashed, request.form['role'])
        )

        conn.commit()
        cur.close()
        conn.close()

        return redirect('/login_page')

    return render_template("Register", """
    <div class="card">
    <h2>Create Account</h2>
    <form method="post">
    <input name="username" placeholder="Username" required>
    <input type="password" name="password" placeholder="Password" required>
    <select name="role">
        <option value="technician">Technician</option>
        <option value="radiologist">Radiologist</option>
    </select>
    <button>Register</button>
    </form>
    </div>
    """)

# =========================
# LOGIN
# =========================
@app.route('/login_page')
def login_page():
    return render_template("Login", """
    <div class="card">
    <h2>Login</h2>
    <form method="post" action="/login">
    <input name="username" placeholder="Username" required>
    <input type="password" name="password" placeholder="Password" required>
    <button>Login</button>
    </form>
    </div>
    """)

@app.route('/login', methods=['POST'])
def login():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE username=%s",
                (request.form['username'],))
    user = cur.fetchone()

    cur.close()
    conn.close()

    if not user:
        return "User not found"

    stored_password = user['password']

    # 🔥 FIX FOR memoryview
    if isinstance(stored_password, memoryview):
        stored_password = stored_password.tobytes()

    if bcrypt.checkpw(request.form['password'].encode(), stored_password):
        session['username'] = user['username']
        session['role'] = user['role']
        return redirect('/dashboard')
    else:
        return "Invalid password"

# =========================
# DASHBOARD
# =========================
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
        <td><a href='/view/{p['id']}'>Open</a></td>
        </tr>
        """

    add_btn = ""
    if session['role'] == "technician":
        add_btn = "<a href='/add_patient_page'><button>Add Patient</button></a><br><br>"

    body = f"""
    <h2>{session['role'].capitalize()} Dashboard</h2>
    {add_btn}
    <table>
    <tr><th>MRN</th><th>Name</th><th>Status</th><th>Action</th></tr>
    {rows}
    </table>
    <br><a href='/logout'>Logout</a>
    """

    return render_template("Dashboard", body)

# =========================
# ADD PATIENT
# =========================
@app.route('/add_patient_page')
def add_patient_page():
    if session.get('role') != "technician":
        return "Unauthorized"

    return render_template("Add Patient", """
    <div class="card">
    <h2>Register Patient</h2>
    <form method="post" action="/add_patient" enctype="multipart/form-data">
    <input name="name" placeholder="Name" required>
    <input name="age" placeholder="Age" required>
    <input name="gender" placeholder="Gender" required>
    <input name="contact" placeholder="Contact" required>
    <input name="bp" placeholder="BP">
    <input name="hr" placeholder="HR">
    <input name="temperature" placeholder="Temperature">
    <input name="spo2" placeholder="SPO2">
    <input name="rr" placeholder="RR">
    Upload Image:
    <input type="file" name="image">
    <button>Add Patient</button>
    </form>
    </div>
    """)

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
        (fhir_id,identifier_system,mrn,name,age,gender,contact,bp,hr,temperature,spo2,rr,status,report)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """,
    (fhir_id,"hospital",mrn,
     request.form['name'],
     request.form['age'],
     request.form['gender'],
     request.form['contact'],
     request.form['bp'],
     request.form['hr'],
     request.form['temperature'],
     request.form['spo2'],
     request.form['rr'],
     "Pending",""))

    patient_id = cur.fetchone() if False else None

    if 'image' in request.files:
        file = request.files['image']
        if file.filename != "":
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            cur.execute("INSERT INTO studies (patient_id,file_name) VALUES (%s,%s)",
                        (count, filename))

    conn.commit()
    cur.close()
    conn.close()

    return redirect('/dashboard')

# =========================
# VIEW PATIENT
# =========================
@app.route('/view/<int:patient_id>', methods=['GET','POST'])
def view_patient(patient_id):
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        cur.execute("""
            UPDATE patients SET report=%s, status=%s WHERE id=%s
        """, (request.form['report'], "Completed", patient_id))
        conn.commit()

    cur.execute("SELECT * FROM patients WHERE id=%s", (patient_id,))
    patient = cur.fetchone()

    cur.execute("SELECT * FROM studies WHERE patient_id=%s", (patient_id,))
    study = cur.fetchone()

    cur.close()
    conn.close()

    image_html = ""
    if study:
        image_html = f"<img src='/uploads/{study['file_name']}' width='400'>"

    report_box = ""
    if session.get("role") == "radiologist":
        report_box = f"""
        <form method="post">
        <textarea name="report">{patient['report'] or ''}</textarea>
        <button>Submit Report</button>
        </form>
        """

    body = f"""
    <div class='card'>
    <h2>Patient Details</h2>
    <b>Name:</b> {patient['name']}<br>
    <b>BP:</b> {patient['bp']}<br>
    <b>HR:</b> {patient['hr']}<br>
    <b>Temp:</b> {patient['temperature']}<br>
    <b>SPO2:</b> {patient['spo2']}<br>
    <b>RR:</b> {patient['rr']}<br>
    <b>Status:</b> {patient['status']}<br><br>
    {image_html}
    <br><br>
    {report_box}
    <br><a href='/dashboard'>Back</a>
    </div>
    """

    return render_template("Patient View", body)

# =========================
# SERVE UPLOADS
# =========================
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# =========================
# LOGOUT
# =========================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')
