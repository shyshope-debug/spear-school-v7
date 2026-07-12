from flask import (
    Flask, render_template_string, request,
    redirect, session, send_file
)
import sqlite3, csv, io, requests
from datetime import datetime, timedelta
from functools import wraps
from io import BytesIO
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = "spear_school_secure_key_v7"

# ================= CONFIG =================
DB = "school.db"
CURRENT_TERM = "Term 1 2026"

WHATSAPP_PHONE_ID = "PASTE_YOUR_PHONE_ID"
WHATSAPP_TOKEN = "PASTE_YOUR_TOKEN"
WHATSAPP_URL = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_ID}/messages"

FEE_STRUCTURE = {"S.1": 850000,"S.2": 850000,"S.3": 900000,"S.4": 900000,"S.5": 950000,"S.6": 950000}
REGISTRATION_FEE = {"S.1": 100000,"S.2": 0,"S.3": 0,"S.4": 0,"S.5": 100000,"S.6": 0}

COMPULSORY_SUBJECTS = ["Mathematics","English","Physics","Chemistry","Biology","History","Geography"]
ELECTIVE_SUBJECTS = ["ICT","CRE","IRE","Agriculture","Art and Design","Literature in English","Entrepreneurship",
"Technology and Design","Nutrition and Food Technology","Performing Arts","French","German","Arabic","Chinese",
"Latin","Luganda","Kiswahili","Ateso","Dhopadhola","Leb Acoli","Leblango","Lugbarati","Lumasaaba","Lusoga",
"Runyoro-Rutooro","Runyankore-Rukiga"]

# ================= DATABASE =================
def get_db():
    con = sqlite3.connect(DB, timeout=10, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

# ================= LOGIN SECURITY =================
def login_required(role=None):
    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            if "user" not in session: return redirect("/")
            if role and session.get("role")!= role: return "Access Denied"
            return function(*args, **kwargs)
        return wrapper
    return decorator

# ================= ACTIVITY LOG =================
def log_activity(user, action):
    con = get_db()
    cur = con.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS ActivityLog(id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, action TEXT, date TEXT)")
    cur.execute("INSERT INTO ActivityLog (user,action,date) VALUES(?,?,?)", (user, action, datetime.now()))
    con.commit()
    con.close()

# ================= ADMISSION NUMBER =================
def generate_admission(class_name):
    year = datetime.now().year
    con = get_db()
    cur = con.cursor()
    result = cur.execute("SELECT COUNT(*) FROM Students WHERE admission_no LIKE?", (f"{class_name}-{year}-%",)).fetchone()[0]
    con.close()
    return f"{class_name}-{year}-{result + 1:03d}"

# ================= GRADE SYSTEM =================
def get_grade(mark):
    mark = int(mark)
    if mark >= 80: return "D1"
    elif mark >= 75: return "D2"
    elif mark >= 70: return "C3"
    elif mark >= 65: return "C4"
    elif mark >= 60: return "C5"
    elif mark >= 55: return "C6"
    elif mark >= 50: return "P7"
    elif mark >= 45: return "P8"
    else: return "F9"

# ================= DATABASE INITIALIZATION =================
def init_db():
    con = get_db()
    cur = con.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS Users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS Students(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, admission_no TEXT UNIQUE, class TEXT, parent_phone TEXT, password TEXT DEFAULT '1234', status TEXT DEFAULT 'Active')")
    cur.execute("CREATE TABLE IF NOT EXISTS Parents(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, phone TEXT UNIQUE, password TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS Fees(id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, term TEXT, total_fee REAL, paid REAL DEFAULT 0, balance REAL)")
    cur.execute("CREATE TABLE IF NOT EXISTS Marks(id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, subject TEXT, marks INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS SubjectChoices(id INTEGER PRIMARY KEY AUTOINCREMENT, admission_no TEXT, subjects_chosen TEXT, status TEXT DEFAULT 'Pending')")
    cur.execute("CREATE TABLE IF NOT EXISTS LibraryBooks(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, author TEXT, status TEXT DEFAULT 'Available')")
    cur.execute("CREATE TABLE IF NOT EXISTS IssuedBooks(id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, book_id INTEGER, issue_date TEXT, due_date TEXT, return_date TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS Teachers(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, subject TEXT, phone TEXT, email TEXT)")

    users = [("admin","admin","Admin"),("sec","123","Secretary"),("bursar","123","Bursar"),("dos","123","DOS"),("librarian","123","Librarian"),("headteacher","123","Headteacher")]
    for user in users:
        cur.execute("INSERT OR IGNORE INTO Users (username,password,role) VALUES(?,?,?)", user)
    con.commit()
    con.close()

# ================= CSS =================
CSS = """<style>:root{--bg:#050505;--card:#111;--green:#00ff66;--text:#eaffea;}
body{background:var(--bg);color:var(--text);font-family:Consolas,monospace;margin:0;}
.header{padding:20px;background:#111;border-bottom:2px solid var(--green);text-align:center;font-size:22px;color:var(--green);}
.container{width:90%;max-width:1100px;margin:auto;padding:20px;}
.card{background:var(--card);padding:20px;border-radius:10px;border:1px solid var(--green);margin:20px 0;}
input,select{width:95%;padding:12px;margin:8px;background:#222;color:white;border:1px solid #333;border-radius:5px;}
button,.btn{background:#00ff66;color:black;padding:12px 20px;border:none;border-radius:5px;text-decoration:none;cursor:pointer;}
table{width:100%;border-collapse:collapse;}td,th{border:1px solid #333;padding:10px;}
th{background:#00ff66;color:black;}.success{color:#00ff66;}.error{color:red;}</style>"""
HEADER = """<div class="header">SPEAR SCHOOL V7.1<a href="/logout" style="float:right;color:#00ff66">Logout</a></div>"""

# ================= LOGIN =================
@app.route("/", methods=["GET","POST"])
def login():
    message=""
    if request.method=="POST":
        username=request.form["username"]; password=request.form["password"]; role=request.form["role"]
        con=get_db(); cur=con.cursor()
        user=None
        if role == "Student":
            user=cur.execute("SELECT * FROM Students WHERE admission_no=? AND password=? AND status='Active'",(username,password)).fetchone()
        else:
            user=cur.execute("SELECT * FROM Users WHERE username=? AND password=? AND role=?",(username,password,role)).fetchone()
        con.close()
        if user:
            session["user"]=username; session["role"]=role
            log_activity(username,"Logged in"); return redirect("/dashboard")
        else: message="Invalid login"
    return render_template_string(CSS+HEADER+"""<div class="container"><div class="card"><h2>SPEAR SCHOOL LOGIN</h2><p class="error">{{msg}}</p>
    <form method="post"><input name="username" placeholder="Username/Adm No" required>
    <input type="password" name="password" placeholder="Password" required><select name="role" required>
    <option>Admin</option><option>Secretary</option><option>Bursar</option><option>DOS</option>
    <option>Librarian</option><option>Headteacher</option><option>Student</option></select><button>Login</button></form></div></div>""",msg=message)

# ================= DASHBOARD =================
@app.route("/dashboard")
@login_required()
def dashboard():
    con = get_db(); cur = con.cursor()
    students = cur.execute("SELECT COUNT(*) FROM Students").fetchone()[0]
    fees = cur.execute("SELECT SUM(paid) FROM Fees WHERE term=?",(CURRENT_TERM,)).fetchone()[0] or 0
    unpaid = cur.execute("SELECT COUNT(*) FROM Fees WHERE term=? AND balance>0",(CURRENT_TERM,)).fetchone()[0]
    books = cur.execute("SELECT COUNT(*) FROM IssuedBooks WHERE return_date IS NULL").fetchone()[0]
    con.close(); role=session["role"]; buttons=""
    if role in ["Admin","Secretary"]: buttons += """<a class="btn" href="/add_student">Register Student</a><a class="btn" href="/student_records">Student Records</a><a class="btn" href="/import_students">Import CSV</a><a class="btn" href="/export_students">Export CSV</a><a class="btn" href="/registration_fee">Registration Fee</a>"""
    if role=="DOS": buttons += """<a class="btn" href="/enter_marks">Enter Marks</a><a class="btn" href="/view_marks">View Results</a><a class="btn" href="/exam_permit">Exam Permit</a><a class="btn" href="/print_report">Report Card</a><a class="btn" href="/approve_subjects">Approve Subjects</a>"""
    if role=="Bursar": buttons += """<a class="btn" href="/fees">Fees Management</a><a class="btn" href="/whatsapp_fees">WhatsApp Reminders</a>"""
    if role=="Librarian": buttons += """<a class="btn" href="/library">Library</a><a class="btn" href="/issue_book">Issue Book</a><a class="btn" href="/overdue">Overdue Books</a>"""
    if role=="Student": buttons += """<a class="btn" href="/student_portal">My Portal</a><a class="btn" href="/select_subjects">Select Subjects</a><a class="btn" href="/change_password">Change Password</a>"""
    return render_template_string(CSS+HEADER+f"""<div class="container"><div class="card"><h2>Welcome {session['user']}</h2><p>Role: {role} | Term: {CURRENT_TERM}</p>
    <table><tr><th>Students</th><th>Fees Collected</th><th>Defaulters</th><th>Issued Books</th></tr>
    <tr><td>{students}</td><td>UGX {fees:,}</td><td>{unpaid}</td><td>{books}</td></tr></table><br>{buttons}</div></div>""")

# ================= ADD STUDENT =================
@app.route("/add_student",methods=["GET","POST"])
@login_required()
def add_student():
    if session["role"] not in ["Admin","Secretary"]: return "Access Denied"
    if request.method=="POST":
        name=request.form["name"]; class_name=request.form["class"]; phone=request.form["phone"]
        adm=generate_admission(class_name); fee=FEE_STRUCTURE.get(class_name,850000)
        con=get_db(); cur=con.cursor()
        cur.execute("INSERT INTO Students (name,admission_no,class,parent_phone) VALUES(?,?,?,?)",(name,adm,class_name,phone))
        student_id=cur.lastrowid
        cur.execute("INSERT INTO Fees (student_id,term,total_fee,balance) VALUES(?,?,?,?)",(student_id,CURRENT_TERM,fee,fee))
        cur.execute("INSERT OR IGNORE INTO Parents (name,phone,password) VALUES(?,?,?)",(name+" Parent",phone,"1234"))
        con.commit(); con.close()
        log_activity(session["user"],f"Added {adm}")
        return render_template_string(CSS+HEADER+f"""<div class="container"><div class="card"><h2 class="success">Student Registered Successfully</h2>
        <p>Admission Number: <b>{adm}</b></p><a class="btn" href="/dashboard">Dashboard</a></div></div>""")
    return render_template_string(CSS+HEADER+"""<div class="container"><div class="card"><h2>Register Student</h2><form method="post">
    <input name="name" placeholder="Full Name" required><select name="class"><option>S.1</option><option>S.2</option><option>S.3</option><option>S.4</option><option>S.5</option><option>S.6</option></select>
    <input name="phone" placeholder="Parent Phone" required><button>Register</button></form></div></div>""")

# ================= STUDENT RECORDS =================
@app.route("/student_records")
@login_required()
def student_records():
    if session["role"] not in ["Admin","Secretary"]: return "Access Denied"
    con=get_db(); students=con.execute("SELECT id,name,admission_no,class,parent_phone,status FROM Students ORDER BY class,name").fetchall(); con.close()
    rows="";
    for s in students: rows += f"<tr><td>{s['name']}</td><td>{s['admission_no']}</td><td>{s['class']}</td><td>{s['parent_phone']}</td><td>{s['status']}</td><td><a class='btn' href='/deactivate/{s['id']}'>Deactivate</a></td></tr>"
    return render_template_string(CSS+HEADER+f"""<div class="container"><div class="card"><h2>Student Records</h2><table><tr><th>Name</th><th>Admission</th><th>Class</th><th>Phone</th><th>Status</th><th>Action</th></tr>{rows}</table></div></div>""")

@app.route("/deactivate/<int:id>")
@login_required()
def deactivate_student(id):
    if session["role"] not in ["Admin","Secretary"]: return "Access Denied"
    con=get_db(); con.execute("UPDATE Students SET status='Inactive' WHERE id=?",(id,)); con.commit(); con.close()
    log_activity(session["user"],f"Deactivated student {id}"); return redirect("/student_records")

# ================= FEES =================
@app.route("/fees")
@login_required("Bursar")
def fees():
    con=get_db(); data=con.execute("SELECT s.id,s.name,s.admission_no,s.class,f.total_fee,f.paid,f.balance FROM Students s JOIN Fees f ON s.id=f.student_id WHERE f.term=?",(CURRENT_TERM,)).fetchall(); con.close()
    rows="";
    for f in data: rows += f"<tr><td>{f['name']}</td><td>{f['admission_no']}</td><td>{f['class']}</td><td>UGX {f['total_fee']:,}</td><td>UGX {f['paid']:,}</td><td>UGX {f['balance']:,}</td><td><a class='btn' href='/pay_fee/{f['id']}'>Pay</a></td></tr>"
    return render_template_string(CSS+HEADER+f"""<div class="container"><div class="card"><h2>Fee Management</h2><table><tr><th>Name</th><th>Admission</th><th>Class</th><th>Total</th><th>Paid</th><th>Balance</th><th>Action</th></tr>{rows}</table></div></div>""")

@app.route("/pay_fee/<int:id>",methods=["GET","POST"])
@login_required("Bursar")
def pay_fee(id):
    con=get_db(); cur=con.cursor()
    if request.method=="POST":
        amount=float(request.form["amount"])
        fee=cur.execute("SELECT paid,total_fee FROM Fees WHERE student_id=? AND term=?",(id,CURRENT_TERM)).fetchone()
        new_paid=fee["paid"]+amount; balance=fee["total_fee"]-new_paid
        cur.execute("UPDATE Fees SET paid=?,balance=? WHERE student_id=? AND term=?",(new_paid,balance,id,CURRENT_TERM))
        con.commit(); con.close(); return redirect("/fees")
    con.close()
    return render_template_string(CSS+HEADER+"""<div class="container"><div class="card"><h2>Record Payment</h2><form method="post"><input type="number" name="amount" placeholder="Amount UGX" required><button>Save Payment</button></form></div></div>""")

@app.route("/registration_fee",methods=["GET","POST"])
@login_required()
def registration_fee():
    if session["role"] not in ["Secretary","Bursar","Admin"]: return "Access Denied"
    message=""
    if request.method=="POST":
        adm=request.form["adm"]; amount=float(request.form["amount"])
        con=get_db(); cur=con.cursor(); student=cur.execute("SELECT id,name FROM Students WHERE admission_no=?",(adm,)).fetchone()
        if student:
            cur.execute("INSERT INTO Fees (student_id,term,total_fee,paid,balance) VALUES(?,?,?,?,?)",(student["id"],"Registration",amount,amount,0))
            con.commit(); message=f"<p class='success'>Payment received from {student['name']}</p>"
        else: message="<p class='error'>Student not found</p>"
        con.close()
    return render_template_string(CSS+HEADER+f"""<div class="container"><div class="card"><h2>Registration Fee</h2>{message}<form method="post"><input name="adm" placeholder="Admission Number" required><input name="amount" type="number" placeholder="Amount UGX" required><button>Save Payment</button></form></div></div>""")

# ================= ACADEMICS =================
@app.route("/enter_marks",methods=["GET","POST"])
@login_required("DOS")
def enter_marks():
    con=get_db(); cur=con.cursor(); message=""
    if request.method=="POST":
        student=request.form["student"]; subject=request.form["subject"]; marks=int(request.form["marks"])
        old=cur.execute("SELECT id FROM Marks WHERE student_id=? AND subject=?",(student,subject)).fetchone()
        if old: cur.execute("UPDATE Marks SET marks=? WHERE id=?",(marks,old["id"]))
        else: cur.execute("INSERT INTO Marks (student_id,subject,marks) VALUES(?,?,?)",(student,subject,marks))
        con.commit(); message="<p class='success'>Marks saved successfully</p>"
    students=cur.execute("SELECT id,name,class FROM Students WHERE status='Active'").fetchall(); con.close()
    student_options="".join([f"<option value='{s['id']}'>{s['name']} - {s['class']}</option>" for s in students])
    subject_options="".join([f"<option>{s}</option>" for s in COMPULSORY_SUBJECTS+ELECTIVE_SUBJECTS])
    return render_template_string(CSS+HEADER+f"""<div class="container"><div class="card"><h2>Enter Student Marks</h2>{message}<form method="post">
    <select name="student">{student_options}</select><select name="subject">{subject_options}</select>
    <input type="number" name="marks" max="100" min="0" placeholder="Marks" required><button>Save Marks</button></form></div></div>""")

@app.route("/view_marks")
@login_required("DOS")
def view_marks():
    con=get_db(); results=con.execute("SELECT s.admission_no,s.name,s.class,m.subject,m.marks FROM Marks m JOIN Students s ON s.id=m.student_id ORDER BY s.class,s.name").fetchall(); con.close()
    rows="";
    for r in results: rows += f"<tr><td>{r['admission_no']}</td><td>{r['name']}</td><td>{r['class']}</td><td>{r['subject']}</td><td>{r['marks']}</td><td><b>{get_grade(r['marks'])}</b></td></tr>"
    return render_template_string(CSS+HEADER+f"""<div class="container"><div class="card"><h2>UNEB Results</h2><table><tr><th>Admission</th><th>Name</th><th>Class</th><th>Subject</th><th>Marks</th><th>Grade</th></tr>{rows}</table><a class="btn" href="/dashboard">Back</a></div></div>""")

@app.route("/exam_permit")
@login_required("DOS")
def exam_permit():
    con=get_db(); students=con.execute("SELECT s.name,s.class,f.total_fee,f.paid FROM Students s JOIN Fees f ON s.id=f.student_id WHERE f.term=?",(CURRENT_TERM,)).fetchall(); con.close()
    rows=""
    for s in students:
        percentage = (s["paid"]/s["total_fee"]*100) if s["total_fee"]>0 else 0
        status = "CLEARED" if percentage >= 90 else "BLOCKED"
        rows += f"<tr><td>{s['name']}</td><td>{s['class']}</td><td>{percentage:.1f}%</td><td>{status}</td></tr>"
    return render_template_string(CSS+HEADER+f"""<div class="container"><div class="card"><h2>Exam Permit</h2><table><tr><th>Name</th><th>Class</th><th>Fees Paid</th><th>Status</th></tr>{rows}</table><a class="btn" href="/dashboard">Back</a></div></div>""")

@app.route("/print_report",methods=["GET","POST"])
@login_required("DOS")
def print_report():
    con=get_db(); cur=con.cursor(); students=cur.execute("SELECT admission_no,name,class FROM Students ORDER BY name").fetchall()
    if request.method=="POST":
        adm=request.form["student"]; student=cur.execute("SELECT * FROM Students WHERE admission_no=?",(adm,)).fetchone()
        marks=cur.execute("SELECT subject,marks FROM Marks WHERE student_id=?",(student["id"],)).fetchall(); con.close()
        pdf=FPDF(); pdf.add_page(); pdf.set_font("Arial","B",16); pdf.cell(0,10,"SPEAR SCHOOL REPORT CARD",ln=True,align="C")
        pdf.set_font("Arial","",12); pdf.cell(0,10,f"Name: {student['name']}",ln=True); pdf.cell(0,10,f"Admission: {student['admission_no']}",ln=True); pdf.cell(0,10,f"Class: {student['class']}",ln=True)
        total=0
        for m in marks: total+=m["marks"]; pdf.cell(0,8,f"{m['subject']} : {m['marks']} Grade {get_grade(m['marks'])}",ln=True)
        average=total/len(marks) if marks else 0; pdf.cell(0,10,f"Average: {average:.2f}",ln=True); pdf.cell(0,10,"DOS Signature: ______________",ln=True)
        filename=f"Report_{adm}.pdf"; pdf.output(filename); return send_file(filename,as_attachment=True)
    options="".join([f"<option value='{s['admission_no']}'>{s['name']} - {s['class']}</option>" for s in students]); con.close()
    return render_template_string(CSS+HEADER+f"""<div class="container"><div class="card"><h2>Print Report Card</h2><form method="post"><select name="student">{options}</select><button>Generate PDF</button></form></div></div>""")

# ================= NEW: SUBJECT SELECTION =================
@app.route("/select_subjects",methods=["GET","POST"])
@login_required("Student")
def select_subjects():
    con=get_db(); cur=con.cursor(); message=""
    student=cur.execute("SELECT * FROM Students WHERE admission_no=?",(session["user"],)).fetchone()
    if not student or student['class'] not in ['S.5','S.6']: con.close(); return "Only S.5 and S.6 can select subjects"
    if request.method=="POST":
        chosen=", ".join(request.form.getlist("subjects"))
        cur.execute("INSERT OR REPLACE INTO SubjectChoices(admission_no,subjects_chosen,status) VALUES(?,?,?)",(session["user"],chosen,"Pending"))
        con.commit(); message="<p class='success'>Subjects Submitted. Waiting for DOS Approval</p>"
    con.close()
    elective_options="".join([f"<label><input type='checkbox' name='subjects' value='{s}'> {s}</label><br>" for s in ELECTIVE_SUBJECTS])
    return render_template_string(CSS+HEADER+f"""<div class="container"><div class="card"><h2>Select Elective Subjects</h2><p>Choose 2-4 Electives. Compulsory: {', '.join(COMPULSORY_SUBJECTS)}</p>{message}<form method="post">{elective_options}<button>Submit</button></form></div></div>""")

@app.route("/approve_subjects")
@login_required("DOS")
def approve_subjects():
    con=get_db(); cur=con.cursor()
    if request.args.get("approve"):
        cur.execute("UPDATE SubjectChoices SET status='Approved' WHERE admission_no=?",(request.args.get("approve"),)); con.commit()
    pending=cur.execute("SELECT s.name,s.class,sc.admission_no,sc.subjects_chosen FROM SubjectChoices sc JOIN Students s ON s.admission_no=sc.admission_no WHERE sc.status='Pending'").fetchall(); con.close()
    rows="".join([f"<tr><td>{p['name']}</td><td>{p['class']}</td><td>{p['subjects_chosen']}</td><td><a class='btn' href='/approve_subjects?approve={p['admission_no']}'>Approve</a></td></tr>" for p in pending])
    return render_template_string(CSS+HEADER+f"""<div class="container"><div class="card"><h2>Approve Subject Choices</h2><table><tr><th>Name</th><th>Class</th><th>Subjects</th><th>Action</th></tr>{rows}</table></div></div>""")

# ================= NEW: LIBRARY ISSUE/RETURN =================
@app.route("/issue_book",methods=["GET","POST"])
@login_required("Librarian")
def issue_book():
    con=get_db(); cur=con.cursor(); message=""
    if request.method=="POST":
        student_id=request.form["student"]; book_id=request.form["book"]
        issue_date=datetime.now().date(); due_date=issue_date + timedelta(days=14)
        cur.execute("INSERT INTO IssuedBooks(student_id,book_id,issue_date,due_date) VALUES(?,?,?,?)",(student_id,book_id,issue_date,due_date))
        cur.execute("UPDATE LibraryBooks SET status='Issued' WHERE id=?",(book_id,)); con.commit(); message="<p class='success'>Book Issued</p>"
    students=cur.execute("SELECT id,name FROM Students WHERE status='Active'").fetchall()
    books=cur.execute("SELECT id,title FROM LibraryBooks WHERE status='Available'").fetchall(); con.close()
    student_opts="".join([f"<option value='{s['id']}'>{s['name']}</option>" for s in students])
    book_opts="".join([f"<option value='{b['id']}'>{b['title']}</option>" for b in books])
    return render_template_string(CSS+HEADER+f"""<div class="container"><div class="card"><h2>Issue Book</h2>{message}<form method="post">
    <select name="student">{student_opts}</select><select name="book">{book_opts}</select><button>Issue</button></form></div></div>""")

@app.route("/library",methods=["GET","POST"])
@login_required("Librarian")
def library():
    con=get_db(); cur=con.cursor()
    if request.method=="POST": cur.execute("INSERT INTO LibraryBooks(title,author) VALUES(?,?)",(request.form["title"],request.form["author"])); con.commit()
    books=cur.execute("SELECT * FROM LibraryBooks ORDER BY title").fetchall()
    issued=cur.execute("SELECT i.id,s.name,b.title FROM IssuedBooks i JOIN Students s ON s.id=i.student_id JOIN LibraryBooks b ON b.id=i.book_id WHERE i.return_date IS NULL").fetchall(); con.close()
    book_rows="".join([f"<tr><td>{b['title']}</td><td>{b['author']}</td><td>{b['status']}</td></tr>" for b in books])
    issued_rows="".join([f"<tr><td>{i['name']}</td><td>{i['title']}</td><td><a class='btn' href='/return_book/{i['id']}'>Return</a></td></tr>" for i in issued])
    return render_template_string(CSS+HEADER+f"""<div class="container"><div class="card"><h2>Library</h2><form method="post"><input name="title" placeholder="Book Title" required><input name="author" placeholder="Author" required><button>Add Book</button></form><h3>All Books</h3><table><tr><th>Book</th><th>Author</th><th>Status</th></tr>{book_rows}</table><h3>Issued Books</h3><table><tr><th>Student</th><th>Book</th><th>Action</th></tr>{issued_rows}</table></div></div>""")

@app.route("/return_book/<int:id>")
@login_required("Librarian")
def return_book(id):
    con=get_db(); cur=con.cursor()
    book_id=cur.execute("SELECT book_id FROM IssuedBooks WHERE id=?",(id,)).fetchone()['book_id']
    cur.execute("UPDATE IssuedBooks SET return_date=? WHERE id=?",(datetime.now().date(),id))
    cur.execute("UPDATE LibraryBooks SET status='Available' WHERE id=?",(book_id,)); con.commit(); con.close()
    return redirect("/library")

@app.route("/overdue")
@login_required("Librarian")
def overdue():
    con=get_db(); books=con.execute("SELECT s.name,b.title,i.due_date FROM IssuedBooks i JOIN Students s ON s.id=i.student_id JOIN LibraryBooks b ON b.id=i.book_id WHERE i.return_date IS NULL AND i.due_date <?",(datetime.now().date(),)).fetchall(); con.close()
    rows="".join([f"<tr><td>{b['name']}</td><td>{b['title']}</td><td>{b['due_date']}</td></tr>" for b in books])
    return render_template_string(CSS+HEADER+f"""<div class="container"><div class="card"><h2>Overdue Books</h2><table><tr><th>Student</th><th>Book</th><th>Due Date</th></tr>{rows}</table></div></div>""")

# ================= WHATSAPP =================
def send_whatsapp(phone,message):
    if not WHATSAPP_TOKEN or "PASTE" in WHATSAPP_TOKEN: return False
    if phone.startswith("0"): phone="256"+phone[1:]
    headers={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    data={"messaging_product":"whatsapp","to":phone,"type":"text","text":{"body":message}}
    try: return requests.post(WHATSAPP_URL,headers=headers,json=data).status_code==200
    except: return False

@app.route("/whatsapp_fees",methods=["GET","POST"])
@login_required("Bursar")
def whatsapp_fees():
    report=""
    if request.method=="POST":
        con=get_db(); students=con.execute("SELECT s.name,s.class,s.parent_phone,f.balance FROM Students s JOIN Fees f ON s.id=f.student_id WHERE f.term=? AND f.balance > 0",(CURRENT_TERM,)).fetchall(); sent=0
        for s in students:
            message=f"SPEAR SCHOOL\nDear Parent of {s['name']}\nClass: {s['class']}\nOutstanding Balance: UGX {s['balance']:,}\nPlease clear fees."
            if send_whatsapp(s["parent_phone"],message): sent+=1
        con.close(); report=f"<p class='success'>Messages Sent: {sent}</p>"
    return render_template_string(CSS+HEADER+f"""<div class="container"><div class="card"><h2>Fee Reminder</h2>{report}<form method="post"><button>Send Reminders</button></form></div></div>""")

# ================= IMPORT/EXPORT =================
@app.route("/export_students")
@login_required()
def export_students():
    if session["role"] not in ["Secretary","Admin"]: return "Access Denied"
    con=get_db(); students=con.execute("SELECT name,admission_no,class,parent_phone FROM Students").fetchall(); con.close()
    output=io.StringIO(); writer=csv.writer(output); writer.writerow(["Name","Admission","Class","Phone"])
    for s in students: writer.writerow([s["name"],s["admission_no"],s["class"],s["parent_phone"]])
    file=BytesIO(); file.write(output.getvalue().encode()); file.seek(0)
    return send_file(file,mimetype="text/csv",download_name="students.csv",as_attachment=True)

@app.route("/import_students",methods=["GET","POST"])
@login_required()
def import_students():
    if session["role"] not in ["Secretary","Admin"]: return "Access Denied"
    message=""
    if request.method=="POST":
        file=request.files["file"]; stream=io.StringIO(file.stream.read().decode("UTF-8")); reader=csv.reader(stream); next(reader)
        con=get_db(); cur=con.cursor()
        for row in reader:
            name=row[0]; class_name=row[1]; phone=row[2]
            adm=generate_admission(class_name)
            cur.execute("INSERT INTO Students (name,admission_no,class,parent_phone) VALUES(?,?,?,?)",(name,adm,class_name,phone))
        con.commit(); con.close(); message="<p class='success'>Students Imported Successfully</p>"
    return render_template_string(CSS+HEADER+f"""<div class="container"><div class="card"><h2>Import Students</h2>{message}<form method="post" enctype="multipart/form-data"><p>Format: Name,Class,Phone</p><input type="file" name="file" required><button>Upload CSV</button></form></div></div>""")

# ================= STUDENT PORTAL =================
@app.route("/student_portal")
@login_required("Student")
def student_portal():
    con=get_db(); cur=con.cursor(); student=cur.execute("SELECT * FROM Students WHERE admission_no=?",(session["user"],)).fetchone()
    if not student: con.close(); return "Student Not Found"
    subjects=cur.execute("SELECT subjects_chosen,status FROM SubjectChoices WHERE admission_no=?",(session["user"],)).fetchone(); con.close()
    subject_display="<div class='card'><h3>No Subjects Selected</h3></div>"
    if subjects:
        if subjects["status"]=="Approved": subject_display=f"<div class='card'><h3>Approved Subjects</h3><p class='success'>{subjects['subjects_chosen']}</p></div>"
        else: subject_display="<div class='card'><h3>Subject Approval</h3><p>Waiting for DOS approval</p></div>"
    return render_template_string(CSS+HEADER+f"""<div class="container"><div class="card"><h2>Student Portal</h2><h3>Welcome {student['name']}</h3><p>Admission: {student['admission_no']}</p><p>Class: {student['class']}</p></div>{subject_display}</div>""")

@app.route("/change_password",methods=["GET","POST"])
@login_required()
def change_password():
    message=""
    if request.method=="POST":
        old=request.form["old"]; new=request.form["new"]; con=get_db(); cur=con.cursor()
        if session["role"]=="Student":
            user=cur.execute("SELECT * FROM Students WHERE admission_no=? AND password=?",(session["user"],old)).fetchone()
            if user: 
                cur.execute("UPDATE Students SET password=? WHERE admission_no=?",(new,session["user"])); 
                message="<p class='success'>Password Changed</p>"
            else: 
                message="<p class='error'>Wrong Old Password</p>"
        else:
            user=cur.execute("SELECT * FROM Users WHERE username=? AND password=?",(session["user"],old)).fetchone()
            if user: 
                cur.execute("UPDATE Users SET password=? WHERE username=?",(new,session["user"])); 
                message="<p class='success'>Password Changed</p>"
            else: 
                message="<p class='error'>Wrong Old Password</p>"
        con.commit(); con.close()
    return render_template_string(CSS+HEADER+f"""<div class="container"><div class="card"><h2>🔑 Change Password</h2>{message}<form method="post">
    <input type="password" name="old" placeholder="Old Password" required>
    <input type="password" name="new" placeholder="New Password" required>
    <button>Update Password</button></form></div></div>""")

# ================= LOGOUT + ERRORS =================
@app.route("/logout")
def logout(): 
    user=session.get("user")
    if user: 
        log_activity(user,"Logout"); 
    session.clear(); 
    return redirect("/")

@app.errorhandler(404)
def page_not_found(error): 
    return render_template_string(CSS+HEADER+"""<div class="container"><div class="card"><h2>404 - Page Not Found</h2>
    <a class="btn" href="/dashboard">Dashboard</a></div></div>""")

# ================= APPLICATION START =================
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
