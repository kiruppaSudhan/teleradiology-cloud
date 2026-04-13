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


print("App starting...")
app = Flask(__name__)



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



from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether, BaseDocTemplate, Frame, PageTemplate
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import datetime

def generate_pdf(patient, report_text, dose, studies, dose_level):
    file_path = f"/tmp/report_{patient['id']}.pdf"
    W, H = A4

    DARK_BLUE  = colors.HexColor("#0D2B4E")
    MID_BLUE   = colors.HexColor("#1A5276")
    LIGHT_BLUE = colors.HexColor("#D6EAF8")
    RED_COLOR  = colors.HexColor("#C0392B")
    ORANGE_COL = colors.HexColor("#D35400")
    GREEN_COL  = colors.HexColor("#1E8449")
    GRAY_BG    = colors.HexColor("#F2F3F4")
    GRAY_TEXT  = colors.HexColor("#555555")

    def draw_header_footer(canvas, doc):
        canvas.saveState()
        # Header
        canvas.setFillColor(DARK_BLUE)
        canvas.rect(0, H - 60, W, 60, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 16)
        canvas.drawString(20*mm, H - 32, "Tele-Radiology System")
        canvas.setFont("Helvetica", 9)
        canvas.drawString(20*mm, H - 46, "AI-Assisted Radiology Reporting Platform")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(W - 20*mm, H - 30, f"Report ID: RPT-{patient['id']:04d}")
        canvas.drawRightString(W - 20*mm, H - 42, f"MRN: {patient['mrn']}")
        # Footer
        canvas.setFillColor(DARK_BLUE)
        canvas.rect(0, 0, W, 18*mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica", 8)
        today = datetime.datetime.now().strftime("%d %B %Y, %I:%M %p")
        canvas.drawString(20*mm, 10*mm, f"Generated: {today}")
        canvas.drawCentredString(W/2, 10*mm, "CONFIDENTIAL — Authorized Medical Personnel Only")
        canvas.drawRightString(W - 20*mm, 10*mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = BaseDocTemplate(
        file_path, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=68, bottomMargin=55,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  W - doc.leftMargin - doc.rightMargin,
                  H - doc.topMargin - doc.bottomMargin, id='main')
    doc.addPageTemplates([PageTemplate(id='main', frames=[frame], onPage=draw_header_footer)])

    def ps(name, size=10, color=colors.black, bold=False, align=TA_LEFT, sb=4, sa=4, lead=14):
        return ParagraphStyle(name, fontName="Helvetica-Bold" if bold else "Helvetica",
                              fontSize=size, textColor=color, alignment=align,
                              spaceBefore=sb, spaceAfter=sa, leading=lead)

    s_sec   = ps("sec",  size=11, color=colors.white, bold=True, sb=0, sa=0)
    s_lbl   = ps("lbl",  size=9,  color=GRAY_TEXT, bold=True)
    s_val   = ps("val",  size=10)
    s_norm  = ps("norm", size=10, lead=16)
    s_small = ps("sm",   size=8,  color=GRAY_TEXT)
    s_warn  = ps("wrn",  size=11, color=RED_COLOR, bold=True, align=TA_CENTER)

    CW = W - 40*mm  # content width

    def sec_hdr(title):
        t = Table([[Paragraph(title, s_sec)]], colWidths=[CW])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), MID_BLUE),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ]))
        return t

    def info_table(rows):
        t = Table([[Paragraph(r[0], s_lbl), Paragraph(str(r[1]) if r[1] else "—", s_val)]
                   for r in rows], colWidths=[50*mm, CW - 50*mm])
        t.setStyle(TableStyle([
            ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#CCCCCC")),
            ("ROWBACKGROUNDS",(0,0), (-1,-1), [colors.white, GRAY_BG]),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ]))
        return t

    content = []

    # 1. Patient Info
    content.append(Spacer(1, 6))
    content.append(sec_hdr("1.  Patient Information"))
    content.append(Spacer(1, 4))
    content.append(info_table([
        ("Full Name",   patient.get("name")),
        ("MRN",         patient.get("mrn")),
        ("Age",         patient.get("age")),
        ("Gender",      patient.get("gender")),
        ("Contact",     patient.get("contact")),
        ("Email",       patient.get("email")),
    ]))
    content.append(Spacer(1, 10))

    # 2. Clinical Vitals
    content.append(sec_hdr("2.  Clinical Vitals"))
    content.append(Spacer(1, 4))
    content.append(info_table([
        ("Blood Pressure",   patient.get("bp")),
        ("Heart Rate",       patient.get("hr")),
        ("Temperature (°F)", patient.get("temperature")),
        ("SpO2 (%)",         patient.get("spo2")),
        ("Respiratory Rate", patient.get("rr")),
        ("Diabetes (AI)",    patient.get("diabetes_result")),
    ]))
    content.append(Spacer(1, 10))

    # 3. Radiation Dose
    content.append(sec_hdr("3.  Radiation Dose Summary"))
    content.append(Spacer(1, 4))
    dose_str   = f"{dose} mGy·cm" if dose else "Not Available"
    risk_color = RED_COLOR if dose_level == "high" else (ORANGE_COL if dose_level == "moderate" else GREEN_COL)
    risk_hex   = f"#{risk_color.hexval()[2:]}"
    dose_t = Table([[
        Paragraph("Total Dose", s_lbl),
        Paragraph(dose_str, s_val),
        Paragraph("Risk Level", s_lbl),
        Paragraph(f'<font color="{risk_hex}"><b>{dose_level.upper()}</b></font>', s_val),
    ]], colWidths=[35*mm, 55*mm, 35*mm, CW - 125*mm])
    dose_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), LIGHT_BLUE),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#AAAAAA")),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
    ]))
    content.append(dose_t)
    if dose_level == "high":
        content.append(Spacer(1, 4))
        content.append(Paragraph("⚠  HIGH RADIATION DOSE — Immediate clinical review required.", s_warn))
    elif dose_level == "moderate":
        content.append(Spacer(1, 4))
        content.append(Paragraph("⚠  Moderate radiation dose — Monitor patient exposure carefully.", s_warn))
    content.append(Spacer(1, 10))

    # 4. Scan Details
    content.append(sec_hdr("4.  Scan Details"))
    content.append(Spacer(1, 4))
    hdr_style = ps("sh", size=9, color=colors.white, bold=True)
    scan_rows = [[Paragraph(h, hdr_style) for h in ["Scan #", "CTDI (mGy)", "DLP (mGy·cm)", "File Name"]]]
    for i, s in enumerate(studies):
        scan_rows.append([
            Paragraph(str(i+1), s_val),
            Paragraph(str(s["ctdi"]) if s["ctdi"] else "—", s_val),
            Paragraph(str(s["dlp"])  if s["dlp"]  else "—", s_val),
            Paragraph(str(s.get("file_name","—")), s_small),
        ])
    st = Table(scan_rows, colWidths=[20*mm, 38*mm, 42*mm, CW - 100*mm])
    st.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), MID_BLUE),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.white, GRAY_BG]),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
    ]))
    content.append(st)
    content.append(Spacer(1, 10))

    # 5. Radiologist Report
    content.append(sec_hdr("5.  Radiologist Findings & Report"))
    content.append(Spacer(1, 6))
    rtext = report_text.replace("\n", "<br/>") if report_text else "No report submitted."
    rbox = Table([[Paragraph(rtext, s_norm)]], colWidths=[CW])
    rbox.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), GRAY_BG),
        ("BOX",           (0,0), (-1,-1), 0.8, MID_BLUE),
        ("TOPPADDING",    (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
        ("LEFTPADDING",   (0,0), (-1,-1), 12),
        ("RIGHTPADDING",  (0,0), (-1,-1), 12),
    ]))
    content.append(rbox)
    content.append(Spacer(1, 20))

    # 6. Signature
    sig = Table([
        [Paragraph("Radiologist Signature", s_lbl), Paragraph("Date", s_lbl)],
        [Paragraph("_" * 35, s_norm), Paragraph(datetime.datetime.now().strftime("%d / %m / %Y"), s_norm)],
    ], colWidths=[100*mm, CW - 100*mm])
    sig.setStyle(TableStyle([
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    content.append(sig)

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
{% if role=='technician' %}
<a href="/delete_patient/{{ p.id }}" class="btn btn-danger btn-sm" onclick="return confirm('Delete this patient?')">Delete</a>
{% endif %}
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
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT dicom_data FROM studies WHERE id=%s", (id,))
    study = cur.fetchone()
    if not study:
        return "No image found", 404
    cur.close()
    conn.close()

    dicom_bytes = study["dicom_data"]
    if isinstance(dicom_bytes, memoryview):
        dicom_bytes = dicom_bytes.tobytes()

    # Try JPG/PNG first
    try:
        img = Image.open(io.BytesIO(dicom_bytes)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf.read(), 200, {"Content-Type": "image/png"}
    except Exception:
        pass

    # Fall back to DICOM
    try:
        ds = pydicom.dcmread(io.BytesIO(dicom_bytes), force=True)
        if not hasattr(ds, "file_meta") or not hasattr(ds.file_meta, "TransferSyntaxUID"):
            from pydicom.uid import ImplicitVRLittleEndian
            ds.file_meta = ds.file_meta if hasattr(ds, "file_meta") else pydicom.dataset.FileMetaDataset()
            ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        arr = ds.pixel_array.astype(float)
        min_val, max_val = arr.min(), arr.max()
        if max_val - min_val != 0:
            arr = (arr - min_val) / (max_val - min_val)
        else:
            arr = arr * 0
        arr = (arr * 255).astype(np.uint8)
        img = Image.fromarray(arr)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf.read(), 200, {"Content-Type": "image/png"}
    except Exception as e:
        return f"Invalid image: {str(e)}", 400

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

    cur.execute("""SELECT id, ctdi, dlp, annotation_data FROM studies WHERE patient_id=%s""",(id,))
    studies = cur.fetchall()

    # ================= TUMOR DETECTION =================
   
    tumor_result = "Not Available"

    try:
       if studies:
           cur.execute("SELECT dicom_data FROM studies WHERE id=%s", (studies[0]["id"],))
           row = cur.fetchone()

           if not row:
               raise Exception("No scan data found")

           data = row["dicom_data"]
           if isinstance(data, memoryview):
               data = data.tobytes()

           from tumor_model import detect_tumor

           # Try JPG/PNG first (most common for demo)
           try:
               img = Image.open(io.BytesIO(data)).convert('RGB')
               img = img.resize((224, 224))
               arr = np.array(img) / 255.0
               tumor_result = detect_tumor(arr)

           except Exception:
               # Fall back to DICOM
               try:
                   ds = pydicom.dcmread(io.BytesIO(data), force=True)
                   if not hasattr(ds, "file_meta") or not hasattr(ds.file_meta, "TransferSyntaxUID"):
                       from pydicom.uid import ImplicitVRLittleEndian
                       ds.file_meta = ds.file_meta if hasattr(ds, "file_meta") else pydicom.dataset.FileMetaDataset()
                       ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian

                   arr = ds.pixel_array.astype(float)
                   min_val = arr.min()
                   max_val = arr.max()
                   if max_val - min_val != 0:
                       arr = (arr - min_val) / (max_val - min_val)
                   else:
                       arr = arr * 0
                   if len(arr.shape) == 3:
                       arr = arr[:, :, 0]
                   img = Image.fromarray((arr * 255).astype(np.uint8))
                   img = img.resize((224, 224))
                   arr = np.array(img) / 255.0
                   tumor_result = detect_tumor(arr)

               except Exception as e2:
                   tumor_result = f"Could not read scan: {str(e2)}"

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
     id="scan-{{ s.id }}"
     data-study-id="{{ s.id }}"
     onclick="selectImage(this); openAnnotation(this, '{{ s.id }}')">

<br>

<small style="color:white;">
CTDI: {{ s.ctdi if s.ctdi else "N/A" }} |
DLP: {{ s.dlp if s.dlp else "N/A" }}
</small>

</div>

{% endfor %}

</div>

<div class="report-panel">

{% if role=='technician' and patient.status=='Reviewed' %}

<h5>Radiologist Report</h5>

<div class="alert alert-secondary">

{{ patient.report }}

</div>

{% endif %}

</div>

</div>

<!-- DEBUG role=[{{ role }}] --> {% if role and 'radiologist' in role %}
<div class="mt-4 p-4" style="background:#f5f5f5; border-radius:10px;">
<h5>Radiology Report</h5>

<form method="post">

<textarea name="report" rows="10" class="form-control">{{ patient.report }}</textarea>

<br>

<button class="btn btn-success">Submit Report</button>

</form>
<a href="/download/{{ patient.id }}" class="btn btn-dark mt-2">
📄 Download PDF Report
</a>
</div>
{% endif %}

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


<!-- ===== ANNOTATION MODAL ===== -->
<div id="annotationModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); z-index:9999; justify-content:center; align-items:center;">
  <div style="background:#1a1a2e; border-radius:15px; padding:20px; width:90%; max-width:750px; position:relative;">
    
    <h5 style="color:white;">🖊️ Annotate Scan — Draw ellipse around tumor region</h5>
    
    <div style="position:relative; display:inline-block; width:100%;">
      <canvas id="annotationCanvas" style="border:2px solid #00ff88; border-radius:8px; cursor:crosshair; width:100%; display:block;"></canvas>
    </div>

    <br>
    <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:10px;">
      <button onclick="clearAnnotation()" class="btn btn-warning btn-sm">🗑️ Clear</button>
      <button onclick="undoAnnotation()" class="btn btn-secondary btn-sm">↩️ Undo</button>
      <label style="color:white; margin-top:6px;">Color:</label>
      <input type="color" id="annotationColor" value="#ff0000" style="height:35px; width:50px; border:none; cursor:pointer;">
      <label style="color:white; margin-top:6px;">Thickness:</label>
      <input type="range" id="lineThickness" min="1" max="8" value="3" style="width:80px; margin-top:8px;">
      <button onclick="saveAnnotation()" class="btn btn-success btn-sm">💾 Save & Email Patient</button>
      <button onclick="closeAnnotation()" class="btn btn-danger btn-sm">✖ Close</button>
    </div>

    <div id="annotationStatus" style="color:#00ff88; margin-top:10px; font-weight:bold;"></div>
  </div>
</div>

<script>
let annotationStudyId = null;
let isDrawing = false;
let startX, startY;
let canvas, ctx;
let baseImage = null;
let ellipses = [];
let currentEllipse = null;

function openAnnotation(imgEl, studyId) {
  annotationStudyId = studyId;
  canvas = document.getElementById("annotationCanvas");
  ctx = canvas.getContext("2d");
  document.getElementById("annotationModal").style.display = "flex";
  document.getElementById("annotationStatus").innerText = "";

  // Load image onto canvas
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.onload = function() {
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    baseImage = img;
    ellipses = [];
    redraw();
  };
  img.src = imgEl.src;
}

function redraw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (baseImage) ctx.drawImage(baseImage, 0, 0);
  
  const color = document.getElementById("annotationColor").value;
  const thickness = parseInt(document.getElementById("lineThickness").value);

  ellipses.forEach(e => {
    ctx.beginPath();
    ctx.strokeStyle = e.color;
    ctx.lineWidth = e.thickness;
    ctx.ellipse(e.cx, e.cy, Math.abs(e.rx), Math.abs(e.ry), 0, 0, 2 * Math.PI);
    ctx.stroke();
  });

  if (currentEllipse) {
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = thickness;
    ctx.setLineDash([6, 3]);
    ctx.ellipse(currentEllipse.cx, currentEllipse.cy,
      Math.abs(currentEllipse.rx), Math.abs(currentEllipse.ry), 0, 0, 2 * Math.PI);
    ctx.stroke();
    ctx.setLineDash([]);
  }
}

function getCanvasPos(e) {
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  return {
    x: (e.clientX - rect.left) * scaleX,
    y: (e.clientY - rect.top) * scaleY
  };
}

canvas && canvas.addEventListener("mousedown", function(e) {
  const pos = getCanvasPos(e);
  startX = pos.x; startY = pos.y;
  isDrawing = true;
});

document.getElementById("annotationCanvas").addEventListener("mousedown", function(e) {
  const pos = getCanvasPos(e);
  startX = pos.x; startY = pos.y;
  isDrawing = true;
});

document.getElementById("annotationCanvas").addEventListener("mousemove", function(e) {
  if (!isDrawing) return;
  const pos = getCanvasPos(e);
  currentEllipse = {
    cx: (startX + pos.x) / 2,
    cy: (startY + pos.y) / 2,
    rx: (pos.x - startX) / 2,
    ry: (pos.y - startY) / 2,
    color: document.getElementById("annotationColor").value,
    thickness: parseInt(document.getElementById("lineThickness").value)
  };
  redraw();
});

document.getElementById("annotationCanvas").addEventListener("mouseup", function(e) {
  if (!isDrawing) return;
  isDrawing = false;
  if (currentEllipse) {
    ellipses.push({...currentEllipse});
    currentEllipse = null;
    redraw();
  }
});

function clearAnnotation() {
  ellipses = [];
  currentEllipse = null;
  redraw();
}

function undoAnnotation() {
  ellipses.pop();
  redraw();
}

function closeAnnotation() {
  document.getElementById("annotationModal").style.display = "none";
}

function saveAnnotation() {
  const dataURL = canvas.toDataURL("image/png");
  document.getElementById("annotationStatus").innerText = "Saving & emailing...";

  fetch("/save_annotation/" + annotationStudyId, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({image: dataURL})
  })
  .then(r => r.json())
  .then(data => {
    document.getElementById("annotationStatus").innerText = "✅ Saved & emailed to patient!";
  })
  .catch(err => {
    document.getElementById("annotationStatus").innerText = "❌ Error: " + err;
  });
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

@app.route("/delete_patient/<int:id>")
def delete_patient(id):
    if session.get("role") != "technician":
        return "Unauthorized"
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM patients WHERE id=%s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/dashboard")




# ================= ANNOTATION COLUMN =================
@app.route("/add_annotation_column")
def add_annotation_column():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("ALTER TABLE studies ADD COLUMN IF NOT EXISTS annotation_data TEXT;")
    conn.commit()
    cur.close()
    conn.close()
    return "Annotation column added!"

# ================= SAVE ANNOTATION =================
@app.route("/save_annotation/<int:study_id>", methods=["POST"])
def save_annotation(study_id):
    if session.get("role") != "radiologist":
        return "Unauthorized", 403

    data = request.get_json()
    annotation_data_url = data.get("image")  # base64 PNG from canvas

    conn = get_db_connection()
    cur = conn.cursor()

    # Save annotation as base64 in DB
    cur.execute("UPDATE studies SET annotation_data=%s WHERE id=%s", (annotation_data_url, study_id))

    # Get patient email for sending
    cur.execute("""
        SELECT p.email, p.name, p.id as patient_id
        FROM patients p
        JOIN studies s ON s.patient_id = p.id
        WHERE s.id = %s
    """, (study_id,))
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    # Email the annotated image
    if row and row["email"]:
        try:
            # Convert base64 data URL to bytes
            header, encoded = annotation_data_url.split(",", 1)
            img_bytes = base64.b64decode(encoded)

            # Save to temp file
            tmp_path = f"/tmp/annotation_{study_id}.png"
            with open(tmp_path, "wb") as f:
                f.write(img_bytes)

            # Send email with annotation attached
            message = Mail(
                from_email=os.environ.get("EMAIL_USER"),
                to_emails=row["email"],
                subject="Annotated Scan from Your Radiologist",
                html_content=f"""
                <h2>Hello {row['name']}</h2>
                <p>Your radiologist has annotated your brain scan to highlight the region of interest.</p>
                <p>Please find the annotated image attached.</p>
                <br>
                Tele-Radiology System
                """
            )
            with open(tmp_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode()

            attachment = Attachment(
                FileContent(img_data),
                FileName("annotated_scan.png"),
                FileType("image/png"),
                Disposition("attachment")
            )
            message.attachment = attachment

            sg = SendGridAPIClient(os.environ.get("SENDGRID_API_KEY"))
            sg.send(message)
            print("Annotation email sent to:", row["email"])
        except Exception as e:
            print("Annotation email error:", e)

    return {"status": "saved"}

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
