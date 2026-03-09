from flask import Flask, request, redirect, session, render_template_string
import bcrypt
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import pydicom
import numpy as np
from PIL import Image
import io

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# ================= DATABASE =================
def get_db_connection():
    return psycopg2.connect(
        os.environ["DATABASE_URL"],
        cursor_factory=RealDictCursor,
        sslmode="require"
    )

# ================= HOME =================
@app.route("/")
def home():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>Tele-Radiology System</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body {
    background:url('https://images.unsplash.com/photo-1588776814546-1ffcf47267a5') no-repeat center center fixed;
    background-size:cover;
    height:100vh;
    color:white;
}
.center-box {
    background:white;
    color:black;
    padding:40px;
    border-radius:15px;
    box-shadow:0 0 30px rgba(0,0,0,0.4);
}
</style>
</head>
<body class="d-flex justify-content-center align-items-center">
<div class="center-box text-center">
<h2 class="mb-4">🏥 Tele-Radiology System</h2>
<a href="/login_page" class="btn btn-primary m-2">Login</a>
<a href="/register" class="btn btn-success m-2">Register</a>
</div>
</body>
</html>
""")

# ================= INIT DB =================
@app.route("/init_db")
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(100) UNIQUE,
        password BYTEA,
        role VARCHAR(50)
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
        email VARCHAR(150),
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
        dicom_data BYTEA
    );
    """)

    conn.commit()
    cur.close()
    conn.close()

    return "Database Ready"

# ================= REGISTER =================
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        conn=get_db_connection()
        cur=conn.cursor()

        hashed=bcrypt.hashpw(request.form["password"].encode(),bcrypt.gensalt())

        cur.execute(
            "INSERT INTO users (username,password,role) VALUES (%s,%s,%s)",
            (request.form["username"],hashed,request.form["role"])
        )
        conn.commit()
        cur.close()
        conn.close()
        return redirect("/login_page")

    return """
<!DOCTYPE html>
<html>
<head>
<title>Register</title>

<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">

<style>

body{
background: linear-gradient(135deg,#0f2027,#203a43,#2c5364);
height:100vh;
}

.register-box{
background:white;
padding:40px;
border-radius:15px;
width:420px;
box-shadow:0 10px 40px rgba(0,0,0,0.4);
}

</style>
</head>

<body class="d-flex justify-content-center align-items-center">

<div class="register-box">

<h3 class="text-center mb-4">📝 Create Account</h3>

<form method="post">

<div class="mb-3">
<label class="form-label">Username</label>
<input class="form-control" name="username" required>
</div>

<div class="mb-3">
<label class="form-label">Password</label>
<input type="password" class="form-control" name="password" required>
</div>

<div class="mb-3">
<label class="form-label">Role</label>
<select class="form-select" name="role">
<option value="technician">Technician</option>
<option value="radiologist">Radiologist</option>
</select>
</div>

<div class="d-grid">
<button class="btn btn-success">Register</button>
</div>

</form>

<br>

<div class="text-center">
<a href="/" class="btn btn-secondary btn-sm">Back</a>
</div>

</div>

</body>
</html>
"""

# ================= LOGIN =================
@app.route("/login_page")
def login_page():
    return """
<!DOCTYPE html>
<html>
<head>
<title>Login</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">

<style>

body{
    background: linear-gradient(135deg,#0f2027,#203a43,#2c5364);
    height:100vh;
}

.login-box{
    background:rgba(255,255,255,0.95);
    padding:40px;
    border-radius:15px;
    width:400px;
    box-shadow:0 10px 40px rgba(0,0,0,0.4);
}

.title{
    font-weight:600;
}

</style>
</head>

<body class="d-flex justify-content-center align-items-center">

<div class="login-box">
<h3 class="text-center mb-4">🔐 Tele-Radiology Login System</h3>

<form method="post" action="/login">

<div class="mb-3">
<label class="form-label">Username</label>
<input class="form-control" name="username" required>
</div>

<div class="mb-3">
<label class="form-label">Password</label>
<input type="password" class="form-control" name="password" required>
</div>

<div class="d-grid">
<button class="btn btn-primary">Login</button>
</div>

</form>

<br>

<div class="text-center">
<a href="/" class="btn btn-secondary btn-sm">Back</a>
</div>

</div>

</body>
</html>
"""


@app.route("/login",methods=["POST"])
def login():
    conn=get_db_connection()
    cur=conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=%s",(request.form["username"],))
    user=cur.fetchone()
    cur.close()
    conn.close()

    if not user:
        return "User not found"

    pwd=user["password"]
    if isinstance(pwd,memoryview):
        pwd=pwd.tobytes()

    if bcrypt.checkpw(request.form["password"].encode(),pwd):
        session["username"]=user["username"]
        session["role"]=user["role"]
        return redirect("/dashboard")

    return "Wrong password"

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect("/")

    conn=get_db_connection()
    cur=conn.cursor()
    cur.execute("SELECT * FROM patients ORDER BY id DESC")
    patients=cur.fetchall()
    cur.close()
    conn.close()

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>Dashboard</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">

<nav class="navbar navbar-dark bg-dark px-4">
<span class="navbar-brand">{{ role.capitalize() }} Dashboard</span>
<a href="/logout" class="btn btn-danger">Logout</a>
</nav>

<div class="container mt-4">

{% if role=='technician' %}
<a href="/add_patient_page" class="btn btn-success mb-3">+ Add Patient</a>
{% endif %}

<div class="row">
{% for p in patients %}
<div class="col-md-4">
<div class="card shadow mb-4">
<div class="card-body">
<h5>{{ p.mrn }}</h5>
<p>Name: {{ p.name }}</p>

{% if p.status=="Pending" %}
<span class="badge bg-warning text-dark">Pending</span>
{% else %}
<span class="badge bg-success">Reviewed</span>
{% endif %}

<br><br>
<a href="/view/{{ p.id }}" class="btn btn-primary btn-sm">Open Case</a>
</div>
</div>
</div>
{% endfor %}
</div>

</div>
</body>
</html>
""",patients=patients,role=session["role"])

# ================= ADD PATIENT =================
@app.route("/add_patient_page")
def add_patient_page():
    if session.get("role")!="technician":
        return "Unauthorized"

    return """
<!DOCTYPE html>
<html>
<head>
<title>Add Patient</title>

<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">

<style>

body{
background: linear-gradient(135deg,#0f2027,#203a43,#2c5364);
min-height:100vh;
padding-top:40px;
}

.patient-box{
background:white;
padding:40px;
border-radius:15px;
width:650px;
margin:auto;
box-shadow:0 10px 40px rgba(0,0,0,0.4);
}

</style>

</head>

<body>

<div class="patient-box">

<h3 class="text-center mb-4">🩺 Add New Patient</h3>

<form method="post" action="/add_patient" enctype="multipart/form-data">

<div class="row">

<div class="col-md-6 mb-3">
<label>Name</label>
<input class="form-control" name="name" required>
</div>

<div class="col-md-6 mb-3">
<label>Age</label>
<input class="form-control" name="age">
</div>

<div class="col-md-6 mb-3">
<label>Gender</label>
<input class="form-control" name="gender">
</div>

<div class="col-md-6 mb-3">
<label>Contact</label>
<input class="form-control" name="contact">
</div>

<div class="col-md-6 mb-3">
<label>Email</label>
<input class="form-control" type="email" name="email">
</div>

<div class="col-md-4 mb-3">
<label>BP</label>
<input class="form-control" name="bp">
</div>

<div class="col-md-4 mb-3">
<label>HR</label>
<input class="form-control" name="hr">
</div>

<div class="col-md-4 mb-3">
<label>Temp</label>
<input class="form-control" name="temperature">
</div>

<div class="col-md-4 mb-3">
<label>SPO2</label>
<input class="form-control" name="spo2">
</div>

<div class="col-md-4 mb-3">
<label>RR</label>
<input class="form-control" name="rr">
</div>

<div class="col-md-12 mb-3">
<label>DICOM File</label>
<input type="file" class="form-control" name="file">
</div>

</div>

<div class="d-grid">
<button class="btn btn-success">Add Patient</button>
</div>

</form>

<br>

<div class="text-center">
<a href="/dashboard" class="btn btn-secondary btn-sm">Back</a>
</div>

</div>

</body>
</html>
"""

@app.route("/add_patient",methods=["POST"])
def add_patient():
    conn=get_db_connection()
    cur=conn.cursor()

    cur.execute("SELECT COUNT(*) as count FROM patients")
    count=cur.fetchone()["count"]+1
    mrn=f"MRN{count:04d}"

    cur.execute("""
    INSERT INTO patients (mrn,name,age,gender,contact,email,bp,hr,temperature,spo2,rr,status,report)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'Pending','')
    RETURNING id
    """,(mrn,
         request.form["name"],
         request.form["age"],
         request.form["gender"],
         request.form["contact"],
         request.form["email"],
         request.form["bp"],
         request.form["hr"],
         request.form["temperature"],
         request.form["spo2"],
         request.form["rr"]))

    patient_id=cur.fetchone()["id"]
    conn.commit()

    file=request.files["file"]
    if file:
        cur.execute("""
        INSERT INTO studies (patient_id,file_name,dicom_data)
        VALUES (%s,%s,%s)
        """,(patient_id,file.filename,psycopg2.Binary(file.read())))
        conn.commit()

    cur.close()
    conn.close()
    return redirect("/dashboard")

# ================= IMAGE =================
@app.route("/image/<int:id>")
def image(id):
    conn=get_db_connection()
    cur=conn.cursor()
    cur.execute("SELECT dicom_data FROM studies WHERE patient_id=%s",(id,))
    study=cur.fetchone()
    cur.close()
    conn.close()

    dicom_bytes=study["dicom_data"]
    if isinstance(dicom_bytes,memoryview):
        dicom_bytes=dicom_bytes.tobytes()

    ds=pydicom.dcmread(io.BytesIO(dicom_bytes))
    arr=ds.pixel_array.astype(float)
    arr=(arr-arr.min())/(arr.max()-arr.min())
    arr=(arr*255).astype(np.uint8)

    img=Image.fromarray(arr)
    buf=io.BytesIO()
    img.save(buf,format="PNG")
    buf.seek(0)
    return buf.read(),200,{"Content-Type":"image/png"}

# ================= VIEW =================
@app.route("/view/<int:id>",methods=["GET","POST"])
def view(id):
    conn=get_db_connection()
    cur=conn.cursor()

    if request.method=="POST" and session["role"]=="radiologist":
        cur.execute("UPDATE patients SET report=%s,status='Reviewed' WHERE id=%s",
                    (request.form["report"],id))
        conn.commit()

    cur.execute("SELECT * FROM patients WHERE id=%s",(id,))
    patient=cur.fetchone()
    cur.close()
    conn.close()

    return render_template_string("""
<h3>{{ patient.name }} ({{ patient.mrn }})</h3>
<p>Status: {{ patient.status }}</p>
<img src="/image/{{ patient.id }}" width="400"><br><br>

{% if role=='radiologist' %}
<form method="post">
<textarea name="report" rows="5" cols="60">{{ patient.report }}</textarea><br><br>
<button>Submit Report</button>
</form>
{% endif %}

{% if role=='technician' and patient.status=='Reviewed' %}
<h4>Radiologist Report:</h4>
<div style="background:#f5f5f5;padding:10px;">
{{ patient.report }}
</div>
{% endif %}

<br><a href="/dashboard">Back</a>
""",patient=patient,role=session["role"])


@app.route("/health")
def health():
    return "OK", 200

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")
