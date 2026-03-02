from flask import Flask, request, redirect, session, render_template_string
import bcrypt
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import pydicom
import numpy as np
from PIL import Image
import io
import logging

# ================= LOGGING SETUP =================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    return render_template_string("""<!DOCTYPE html>
<html>
<head>
<title>Tele-Radiology System</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body {
    background: linear-gradient(135deg,#0f2027,#203a43,#2c5364);
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

    logger.info("Database initialized")
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

        logger.info(f"New user registered: {request.form['username']} as {request.form['role']}")
        return redirect("/login_page")

    return """
    <h2>Register</h2>
    <form method="post">
    Username:<input name="username"><br><br>
    Password:<input type="password" name="password"><br><br>
    <select name="role">
        <option value="technician">Technician</option>
        <option value="radiologist">Radiologist</option>
    </select><br><br>
    <button>Register</button>
    </form>
    """

# ================= LOGIN =================
@app.route("/login_page")
def login_page():
    return """
    <h2>Login</h2>
    <form method="post" action="/login">
    Username:<input name="username"><br><br>
    Password:<input type="password" name="password"><br><br>
    <button>Login</button>
    </form>
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
        logger.warning(f"Login failed: user {request.form['username']} not found")
        return "User not found"

    pwd=user["password"]
    if isinstance(pwd,memoryview):
        pwd=pwd.tobytes()

    if bcrypt.checkpw(request.form["password"].encode(),pwd):
        session["username"]=user["username"]
        session["role"]=user["role"]

        logger.info(f"User '{user['username']}' logged in as {user['role']}")
        return redirect("/dashboard")

    logger.warning(f"Login failed: wrong password for {request.form['username']}")
    return "Wrong password"

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect("/")

    logger.info(f"Dashboard accessed by {session['username']}")

    conn=get_db_connection()
    cur=conn.cursor()
    cur.execute("SELECT * FROM patients ORDER BY id DESC")
    patients=cur.fetchall()
    cur.close()
    conn.close()

    return render_template_string(""" ... SAME HTML AS BEFORE ... """,
                                 patients=patients,
                                 role=session["role"])

# ================= ADD PATIENT =================
@app.route("/add_patient_page")
def add_patient_page():
    if session.get("role")!="technician":
        return "Unauthorized"
    return """ ... SAME HTML AS BEFORE ... """

@app.route("/add_patient",methods=["POST"])
def add_patient():
    conn=get_db_connection()
    cur=conn.cursor()

    cur.execute("SELECT COUNT(*) as count FROM patients")
    count=cur.fetchone()["count"]+1
    mrn=f"MRN{count:04d}"

    logger.info(f"Technician '{session.get('username')}' is adding patient {mrn}")

    cur.execute("""
    INSERT INTO patients (mrn,name,age,gender,contact,bp,hr,temperature,spo2,rr,status,report)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'Pending','')
    RETURNING id
    """,(mrn,
         request.form["name"],
         request.form["age"],
         request.form["gender"],
         request.form["contact"],
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

        logger.info(f"DICOM uploaded for patient {mrn}")

    cur.close()
    conn.close()
    return redirect("/dashboard")

# ================= IMAGE =================
@app.route("/image/<int:id>")
def image(id):

    logger.info(f"Fetching DICOM image for patient ID {id}")

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

        logger.info(f"Radiologist '{session.get('username')}' submitted report for patient ID {id}")

        cur.execute("UPDATE patients SET report=%s,status='Reviewed' WHERE id=%s",
                    (request.form["report"],id))
        conn.commit()

    cur.execute("SELECT * FROM patients WHERE id=%s",(id,))
    patient=cur.fetchone()
    cur.close()
    conn.close()

    return render_template_string(""" ... SAME HTML AS BEFORE ... """,
                                 patient=patient,
                                 role=session["role"])

@app.route("/logout")
def logout():
    logger.info(f"User '{session.get('username')}' logged out")
    session.clear()
    return redirect("/")
