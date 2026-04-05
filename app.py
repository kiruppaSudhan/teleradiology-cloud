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
from sendgrid.helpers.mail import Attachment, FileContent, FileName, FileType, Disposition
import base64
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from ml_model import predict_diabetes
from tumor_model import get_model, download_model

print("Downloading tumor model...")
download_model()   # 🔥 FIRST DOWNLOAD

print("Loading tumor model...")
get_model()        # 🔥 THEN LOAD

print("Model ready")

app = Flask(__name__)


@app.route("/warmup")
def warmup():
    from tumor_model import get_model
    get_model()
    return "Model loaded"
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# ================= DATABASE =================
def get_db_connection():
    import time

    for i in range(5):
        try:
            return psycopg2.connect( 
                os.environ.get("DATABASE_URL"),
                cursor_factory=RealDictCursor,
                sslmode="require",
                connect_timeout=10
            )
        except Exception as e:
            print("DB connection failed, retrying...", e)
            time.sleep(2)

    raise Exception("Database connection failed")

# ================= EMAIL FUNCTION =================
def send_report_email(to_email, patient_name, report_text, dose, studies, dose_level, pdf_path):
    dose_details = ""

    for i, s in enumerate(studies):
        dose_details += f"Scan {i+1} → CTDI: {s['ctdi']} | DLP: {s['dlp']}<br>"

    message = Mail(
        from_email=os.environ.get("EMAIL_USER"),
        to_emails=to_email,
        subject="Radiology Report Available",
        html_content=f"""
        <h2>Hello {patient_name}</h2>

        <p>Your radiology report is ready.</p>

        <h3>Radiation Dose Summary</h3>

        <b>Total Dose:</b> {dose} mGy·cm <br>
        <b>Risk Level:</b> {dose_level.upper()} ⚠ <br><br>

        <b>Scan-wise Dose:</b><br>
        {dose_details}

        <br><br>

        <h3>Report Summary</h3>
        {report_text}

        <br><br>
        Tele-Radiology System
        """
    )
        # Attach PDF
    with open(pdf_path, "rb") as f:
        data = f.read()

    encoded = base64.b64encode(data).decode()

    attachment = Attachment(
        FileContent(encoded),
        FileName("Radiology_Report.pdf"),
        FileType("application/pdf"),
        Disposition("attachment")
    )

    message.attachment = attachment

    try:
        sg = SendGridAPIClient(os.environ.get("SENDGRID_API_KEY"))
        response = sg.send(message)

        print("Email sent successfully:", response.status_code)

    except Exception as e:
        print("EMAIL ERROR:", e)



from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

def generate_pdf(patient, report_text, dose, studies, dose_level):

    file_path = f"/tmp/report_{patient['id']}.pdf"

    doc = SimpleDocTemplate(file_path, pagesize=A4)
    styles = getSampleStyleSheet()

    content = []

    # Title
    content.append(Paragraph("<b>Tele-Radiology Report</b>", styles["Title"]))
    content.append(Spacer(1, 10))

    # Patient Info
    content.append(Paragraph("<b>Patient Details</b>", styles["Heading2"]))
    content.append(Spacer(1, 10))

    patient_data = [
        ["Name", patient["name"]],
        ["MRN", patient["mrn"]],
        ["Age", patient["age"]],
        ["Gender", patient["gender"]],
    ]

    table = Table(patient_data)
    table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 1, colors.black),
    ]))

    content.append(table)
    content.append(Spacer(1, 15))

    # Dose
    content.append(Paragraph("<b>Radiation Dose Summary</b>", styles["Heading2"]))
    content.append(Spacer(1, 10))

    dose_color = "green"
    if dose_level == "high":
        dose_color = "red"
    elif dose_level == "moderate":
        dose_color = "orange"

    content.append(Paragraph(f"Total Dose: {dose} mGy·cm", styles["Normal"]))
    content.append(Paragraph(f"<font color='{dose_color}'>Risk Level: {dose_level.upper()}</font>", styles["Normal"]))
    content.append(Spacer(1, 15))

    # Scan table
    content.append(Paragraph("<b>Scan Details</b>", styles["Heading2"]))
    content.append(Spacer(1, 10))

    scan_data = [["Scan", "CTDI", "DLP"]]

    for i, s in enumerate(studies):
        scan_data.append([f"{i+1}", str(s["ctdi"]), str(s["dlp"])])

    scan_table = Table(scan_data)
    scan_table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 1, colors.black),
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
    ]))

    content.append(scan_table)
    content.append(Spacer(1, 15))

    # Report
    content.append(Paragraph("<b>Radiologist Report</b>", styles["Heading2"]))
    content.append(Spacer(1, 10))

    formatted_report = report_text.replace("\n", "<br/>")
    content.append(Paragraph(formatted_report, styles["Normal"]))

    doc.build(content)

    return file_path
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
        diabetes_result VARCHAR(50),
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
    ALTER TABLE patients
    ADD COLUMN IF NOT EXISTS diabetes_result VARCHAR(50);
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

<div class="col-md-4 mb-3">
<label>Glucose</label>
<input class="form-control" name="glucose" required>
</div>

<div class="col-md-4 mb-3">
<label>BMI</label>
<input class="form-control" name="bmi" required>
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

    glucose = float(request.form["glucose"])
    bmi = float(request.form["bmi"])
    age = float(request.form["age"])

    diabetes_result = predict_diabetes(glucose, bmi, age)
    print("Diabetes Prediction:", diabetes_result)

    cur.execute("""
    INSERT INTO patients (mrn,name,age,gender,contact,email,bp,hr,temperature,spo2,rr,diabetes_result,status,report)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'Pending','')
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
     request.form["rr"],
     diabetes_result))

    patient_id=cur.fetchone()["id"]
    conn.commit()

    files = request.files.getlist("file")

    for file in files:
        if file and file.filename != "":

           dicom_bytes = file.read()

           ds = pydicom.dcmread(io.BytesIO(dicom_bytes), force=True)

           ctdi = None
           dlp = None

           # Try standard tags
           if hasattr(ds, "CTDIvol"):
              ctdi = float(ds.CTDIvol)
 
           if hasattr(ds, "DLP"):
              dlp = float(ds.DLP)
           # DEMO PURPOSE ONLY (simulate dose if missing)
           if dlp is None:
               import random
               dlp = random.randint(300, 1200)

           if ctdi is None:
               ctdi = round(dlp / 50, 2)
               
           print("DEBUG → CTDI:", ctdi, "DLP:", dlp)
           
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

           # Try standard tags
           if hasattr(ds, "CTDIvol"):
              ctdi = float(ds.CTDIvol)

           if hasattr(ds, "DLP"):
              dlp = float(ds.DLP)
              
           # DEMO PURPOSE ONLY (simulate dose if missing)
           if dlp is None:
               import random
               dlp = random.randint(300, 1200)

           if ctdi is None:
              ctdi = round(dlp / 50, 2)   
           print("DEBUG → CTDI:", ctdi, "DLP:", dlp)
           
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
    if not study:
       return "No image found", 404
    cur.close()
    conn.close()

    dicom_bytes=study["dicom_data"]
    if isinstance(dicom_bytes,memoryview):
        dicom_bytes=dicom_bytes.tobytes()

    ds = pydicom.dcmread(io.BytesIO(dicom_bytes), force=True)

    # 🔥 FIX: add Transfer Syntax if missing
    if not hasattr(ds, "file_meta") or not hasattr(ds.file_meta, "TransferSyntaxUID"):
        from pydicom.uid import ImplicitVRLittleEndian
        ds.file_meta = ds.file_meta if hasattr(ds, "file_meta") else pydicom.dataset.FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian

    try:
       arr = ds.pixel_array.astype(float)
    except Exception as e:
       print("Pixel read failed:", e)
       return "Invalid DICOM", 400
    min_val = arr.min()
    max_val = arr.max()

    if max_val - min_val != 0:
        arr = (arr - min_val) / (max_val - min_val)
    else:
        arr = arr * 0
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

    p = None


    # STEP 1: Save report
    if request.method=="POST" and session["role"]=="radiologist":

        report_text = request.form["report"]

        cur.execute("UPDATE patients SET report=%s,status='Reviewed' WHERE id=%s",
                    (report_text,id))
        conn.commit()

        cur.execute("SELECT email,name FROM patients WHERE id=%s",(id,))
        p = cur.fetchone()

    # STEP 2: Fetch data
    cur.execute("SELECT * FROM patients WHERE id=%s",(id,))
    patient=cur.fetchone()
    report_text = patient["report"]

    cur.execute("""SELECT id, ctdi, dlp FROM studies WHERE patient_id=%s""",(id,))
    studies = cur.fetchall()

    # ================= TUMOR DETECTION =================
   

    tumor_result = "Not Available"

    try:
        if studies:
           # get first scan
           cur.execute("SELECT dicom_data FROM studies WHERE id=%s", (studies[0]["id"],))
           row = cur.fetchone()

           if not row:
              raise Exception("No DICOM data found")

           data = row["dicom_data"]


           # convert memoryview → bytes
           if isinstance(data, memoryview):
              data = data.tobytes()
           ds = pydicom.dcmread(io.BytesIO(data), force=True)

           # 🔥 FIX HERE ALSO
           if not hasattr(ds, "file_meta") or not hasattr(ds.file_meta, "TransferSyntaxUID"):
               from pydicom.uid import ImplicitVRLittleEndian
               ds.file_meta = ds.file_meta if hasattr(ds, "file_meta") else pydicom.dataset.FileMetaDataset()
               ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
           try:
               arr = ds.pixel_array.astype(float)
           except Exception as e:
               print("Pixel read failed:", e)
               tumor_result = "Invalid DICOM"
               arr = None   # 🔥 IMPORTANT
           if arr is not None:

              # normalize safely
              min_val = arr.min()
              max_val = arr.max()

              if max_val - min_val != 0:
                  arr = (arr - min_val) / (max_val - min_val)
              else:
                  arr = arr * 0

              # ensure grayscale
              if len(arr.shape) == 3:
                  arr = arr[:, :, 0]

              # resize for model
              img = Image.fromarray((arr * 255).astype(np.uint8))
              img = img.resize((128, 128))
              arr = np.array(img) / 255.0

              # AI prediction
              from tumor_model import detect_tumor
              tumor_result = detect_tumor(arr)

    except Exception as e:
        import traceback
        traceback.print_exc()
        tumor_result = str(e)

    cur.execute("SELECT SUM(dlp) as total_dose FROM studies WHERE patient_id=%s",(id,))
    dose_row = cur.fetchone()

    dose = None
    if dose_row and dose_row["total_dose"]:
        dose = float(dose_row["total_dose"])

    # STEP 3: Dose level
    dose_level = "safe"
    if dose:
        if dose > 1000:
            dose_level = "high"
        elif dose > 500:
            dose_level = "moderate"

    # STEP 4: Generate PDF + Email ONLY on POST
    if request.method=="POST" and session["role"]=="radiologist":

        pdf_path = generate_pdf(patient, report_text, dose, studies, dose_level)
        print("PDF generated at:", pdf_path)

        if p and p["email"]:
            try:
                send_report_email(
                    p["email"], p["name"],
                    report_text, dose, studies,
                    dose_level, pdf_path
                )
                print("Email sent to:", p["email"])
            except Exception as e:
                print("Email sending failed:", e)

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

<h5>Patient Risk Assessment</h5>
<p><b>Diabetes (clinical input):</b> {{ patient.diabetes_result }}</p>

<h5>AI Imaging Analysis</h5>
<p><b>Brain Tumor Detection:</b> {{ tumor_result }}</p>

<p>Status: {{ patient.status }}</p>

<h4>Total Radiation Dose</h4>
{% if dose %}
<p>{{ dose }} mGy*cm</p>
{% else %}
<p style="color:orange;">Dose data not available</p>
{% endif %}

{% if dose_level == "high" %}
<div class="alert alert-danger">
⚠ High Radiation Dose – Immediate Attention Required
</div>

{% elif dose_level == "moderate" %}
<div class="alert alert-warning">
⚠ Moderate Radiation Dose – Monitor Patient Exposure
</div>

{% else %}
<div class="alert alert-success">
✔ Safe Radiation Level
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

<div style="margin-bottom:20px; display:inline-block;">

<img src="/image/{{ s.id }}" 
     class="scan-img dicom-image" 
     onclick="selectImage(this)">

<br>

<small style="color:white;">
CTDI: {{ s.ctdi if s.ctdi else "N/A" }} |
DLP: {{ s.dlp if s.dlp else "N/A" }}
</small>

</div>

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
<a href="/download/{{ patient.id }}" class="btn btn-dark mt-2">
📄 Download PDF Report
</a>

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

""",patient=patient,studies=studies,role=session.get("role"),dose=dose,dose_level=dose_level,tumor_result=tumor_result)

@app.route("/health")
def health():
    return "OK", 200

from flask import send_file

@app.route("/download/<int:id>")
def download(id):

    conn = get_db_connection()
    cur = conn.cursor()

    # Get patient
    cur.execute("SELECT * FROM patients WHERE id=%s", (id,))
    patient = cur.fetchone()

    # Get studies
    cur.execute("SELECT ctdi, dlp FROM studies WHERE patient_id=%s", (id,))
    studies = cur.fetchall()

    # Get total dose
    cur.execute("SELECT SUM(dlp) as total_dose FROM studies WHERE patient_id=%s", (id,))
    dose_row = cur.fetchone()

    cur.close()
    conn.close()

    dose = None
    if dose_row and dose_row["total_dose"]:
        dose = float(dose_row["total_dose"])

    # Dose classification
    dose_level = "safe"
    if dose:
        if dose > 1000:
            dose_level = "high"
        elif dose > 500:
            dose_level = "moderate"

    # Generate PDF again (safe approach)
    pdf_path = generate_pdf(patient, patient["report"], dose, studies, dose_level)

    return send_file(pdf_path, as_attachment=True)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
