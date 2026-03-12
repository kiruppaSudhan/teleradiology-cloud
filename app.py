from flask import Flask, request, redirect, session, render_template_string
import bcrypt
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import pydicom
import numpy as np
from PIL import Image
import io
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# ================= DATABASE =================
def get_db_connection():
    return psycopg2.connect(
        os.environ["DATABASE_URL"],
        cursor_factory=RealDictCursor,
        sslmode="require"
    )


# ================= EMAIL FUNCTION =================
def send_report_email(to_email, patient_name, report_text):

    message = Mail(
        from_email=os.environ.get("EMAIL_USER"),
        to_emails=to_email,
        subject="Radiology Report Available",
        html_content=f"""
        <h2>Hello {patient_name}</h2>

        <p>Your radiology report is ready.</p>

        <b>Report Summary:</b><br>
        {report_text}

        <br><br>
        Tele-Radiology System
        """
    )

    try:
        sg = SendGridAPIClient(os.environ.get("SENDGRID_API_KEY"))
        response = sg.send(message)

        print("EMAIL SENT SUCCESSFULLY")
        print(response.status_code)

    except Exception as e:
        print("EMAIL ERROR:", e)

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

    # Add email column if table already existed
    cur.execute("""
    ALTER TABLE patients
    ADD COLUMN IF NOT EXISTS email VARCHAR(150);
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS studies (
        id SERIAL PRIMARY KEY,
        patient_id INTEGER REFERENCES patients(id) ON DELETE CASCADE,
        file_name VARCHAR(255),
        dicom_data BYTEA
    );
    """)

    cur.execute("""
    ALTER TABLE studies
    ADD COLUMN IF NOT EXISTS ctdi FLOAT;
    """)

    cur.execute("""
    ALTER TABLE studies
    ADD COLUMN IF NOT EXISTS dlp FLOAT;
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
<input type="file" class="form-control" name="file" multiple>
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
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'Pending','')
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

    files = request.files.getlist("file")

    for file in files:
        if file and file.filename != "":

           dicom_bytes = file.read()

           ds = pydicom.dcmread(io.BytesIO(dicom_bytes), force=True)

           ctdi = None
           dlp = None

           if "CTDIvol" in ds:
               ctdi = float(ds.CTDIvol)

           if "DLP" in ds:
               dlp = float(ds.DLP)

           cur.execute("""
           INSERT INTO studies (patient_id,file_name,dicom_data,ctdi,dlp)
           VALUES (%s,%s,%s,%s,%s)
           """,(patient_id,file.filename,psycopg2.Binary(dicom_bytes),ctdi,dlp))

    conn.commit()

    cur.close()
    conn.close()
    return redirect("/dashboard")


# ================= UPLOAD ADDITIONAL SCAN =================
@app.route("/upload_scan/<int:id>", methods=["POST"])
def upload_scan(id):

    if session.get("role") != "technician":
        return "Unauthorized"

    conn = get_db_connection()
    cur = conn.cursor()

    files = request.files.getlist("file")

    for file in files:
        if file and file.filename != "":

           dicom_bytes = file.read()

           ds = pydicom.dcmread(io.BytesIO(dicom_bytes), force=True)

           ctdi = None
           dlp = None

           if "CTDIvol" in ds:
               ctdi = float(ds.CTDIvol)

           if "DLP" in ds:
               dlp = float(ds.DLP)

           cur.execute("""
           INSERT INTO studies (patient_id,file_name,dicom_data,ctdi,dlp)
           VALUES (%s,%s,%s,%s,%s)
           """,(id,file.filename,psycopg2.Binary(dicom_bytes),ctdi,dlp))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(f"/view/{id}")

# ================= IMAGE =================
@app.route("/image/<int:id>")
def image(id):
    conn=get_db_connection()
    cur=conn.cursor()
    cur.execute("SELECT dicom_data FROM studies WHERE id=%s",(id,))
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
    if "role" not in session:
        return redirect("/login_page")
    
    conn=get_db_connection()
    cur=conn.cursor()

    if request.method=="POST" and session["role"]=="radiologist":

       report_text = request.form["report"]

       cur.execute("UPDATE patients SET report=%s,status='Reviewed' WHERE id=%s",
                (report_text,id))
       conn.commit()

       # get patient email
       cur.execute("SELECT email,name FROM patients WHERE id=%s",(id,))
       p = cur.fetchone()
       print("Patient email:", p["email"])

       if p and p["email"]:
           try:
               send_report_email(p["email"], p["name"], report_text)
               print("Email sent to:", p["email"])
           except Exception as e:
               print("Email sending failed:", e)

    cur.execute("SELECT * FROM patients WHERE id=%s",(id,))
    patient=cur.fetchone()
    cur.execute("SELECT id FROM studies WHERE patient_id=%s",(id,))
    studies = cur.fetchall()
    cur.execute("SELECT SUM(dlp) as total_dose FROM studies WHERE patient_id=%s",(id,))
    dose_row = cur.fetchone()
    dose = dose_row["total_dose"] if dose_row else None
    # ADD THIS PART HERE
    dose_warning = False

    if dose and dose > 1000:
       dose_warning = True
    cur.close()
    conn.close()

    return render_template_string("""
<!DOCTYPE html>
<html>

<head>

<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">

<style>

.viewer{
display:flex;
gap:20px;
}

.image-panel{
flex:2;
background:#111;
padding:20px;
border-radius:10px;
}

.report-panel{
flex:1;
background:#f5f5f5;
padding:20px;
border-radius:10px;
}

.scan-img{
max-width:100%;
margin-bottom:10px;
border:3px solid #333;
transition: all 0.2s ease;
}

.dicom-image.active{
border:3px solid red;
}
</style>

</head>

<body class="container mt-4">

<h3>{{ patient.name }} ({{ patient.mrn }})</h3>

<p>Status: {{ patient.status }}</p>

<h4>Total Radiation Dose</h4>

<p>{{ dose if dose else 0 }} mGy*cm</p>

{% if dose_warning %}
<div class="alert alert-danger">
⚠ High Radiation Dose
</div>
{% endif %}

<div class="viewer">

<div class="image-panel">

<h5 class="text-white">Patient Scans</h5>

{% if role=='technician' %}

<form method="post" action="/upload_scan/{{ patient.id }}" enctype="multipart/form-data">

<input type="file" name="file" multiple class="form-control mb-2">

<button class="btn btn-primary btn-sm">Upload Additional Scan</button>

</form>

<br>

{% endif %}
<h5 class="text-white">Viewer Controls</h5>

<label class="text-white">Zoom</label>
<input type="range" id="zoomSlider" min="1" max="3" step="0.1" value="1">

<br>

<label class="text-white">Brightness</label>
<input type="range" id="brightnessSlider" min="50" max="200" value="100">

<br>

<label class="text-white">Contrast</label>
<input type="range" id="contrastSlider" min="50" max="200" value="100">

<br><br>

{% for s in studies %}
<img src="/image/{{ s.id }}" class="scan-img dicom-image" onclick="selectImage(this)">
{% endfor %}

</div>

<div class="report-panel">

{% if role=='radiologist' %}

<h5>Radiology Report</h5>

<form method="post">

<textarea name="report" rows="10" class="form-control">{{ patient.report }}</textarea>

<br>

<button class="btn btn-success">Submit Report</button>

</form>

{% endif %}

{% if role=='technician' and patient.status=='Reviewed' %}

<h5>Radiologist Report</h5>

<div class="alert alert-secondary">

{{ patient.report }}

</div>

{% endif %}

</div>

</div>

<br>

<a href="/dashboard" class="btn btn-secondary">Back</a>
<script>

let zoom = 1
let brightness = 100
let contrast = 100
let activeImage = null
function selectImage(img){

document.querySelectorAll(".dicom-image").forEach(i=>{
i.classList.remove("active")
})

img.classList.add("active")

activeImage = img

}
function updateImage(){
if(!activeImage) return
let img = activeImage

img.style.transform = "scale("+zoom+")"

img.style.filter =
"brightness("+brightness+"%) contrast("+contrast+"%)"

}

document.getElementById("zoomSlider").oninput = function(){
zoom = this.value
updateImage()
}

document.getElementById("brightnessSlider").oninput = function(){
brightness = this.value
updateImage()
}

document.getElementById("contrastSlider").oninput = function(){
contrast = this.value
updateImage()
}

</script>

</body>

</html>

""",patient=patient,studies=studies,role=session.get("role"),dose=dose,dose_warning=dose_warning)

@app.route("/health")
def health():
    return "OK", 200

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")
