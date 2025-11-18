from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
import os
import time
import random
import string
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'supersecretkey123'

# ================================
# DATABASE
# ================================
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="fahu087",
    database="safecity"
)
cursor = db.cursor()

# ================================
# FILE UPLOADS
# ================================
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ================================
# HOME / CITIZEN LOGIN
# ================================
@app.route('/', methods=['GET', 'POST'])
def home():

    # TEMPORARILY TURN OFF CAPTCHA COMPLETELY
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')

        # Direct login without checking captcha
        session['citizen'] = {'name': name, 'phone': phone}
        return redirect(url_for('citizen_home'))

    return render_template('index.html', captcha="", error=None)


    session['captcha'] = generate_captcha()
    return render_template('index.html', captcha=session['captcha'], error=error)

# ================================
# CITIZEN HOME
# ================================
@app.route('/citizen/home')
def citizen_home():
    if 'citizen' not in session:
        return redirect(url_for('home'))
    return render_template('citizen_home.html', citizen=session['citizen'])

# ================================
# CITIZEN REPORT LIST
# ================================
@app.route('/citizen/reports')
def citizen_reports():
    if 'citizen' not in session:
        return redirect(url_for('home'))

    citizen = session['citizen']

    cursor2 = db.cursor(dictionary=True)   # <-- IMPORTANT FIX

    cursor2.execute("""
        SELECT id, victim_name, victim_age, victim_gender, location, description,
               image_path, status, assigned_to, solved_by, created_at
        FROM reports
        WHERE citizen_name = %s AND citizen_phone = %s
        ORDER BY id DESC
    """, (citizen['name'], citizen['phone']))

    reports = cursor2.fetchall()
    cursor2.close()

    return render_template('citizen_reports.html', citizen=citizen, reports=reports)

# ================================
# REPORT PAGE
# ================================
@app.route('/report', methods=['GET', 'POST'])
def report():
    if request.method == 'POST':
        victim_name = request.form['victim_name']
        victim_age = request.form['victim_age']
        victim_gender = request.form['victim_gender']
        location = request.form['location']
        description = request.form['description']

        # Save images
        images = request.files.getlist('images')
        image_paths = []

        for img in images:
            if img and img.filename != '':
                filename = secure_filename(img.filename)
                unique_name = str(int(time.time())) + "_" + filename
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
                img.save(save_path)
                image_paths.append(f"uploads/{unique_name}")

        image_path = ",".join(image_paths) if image_paths else None

        citizen = session.get('citizen')
        citizen_name = citizen['name'] if citizen else None
        citizen_phone = citizen['phone'] if citizen else None

        cursor.execute("""
            INSERT INTO reports 
            (victim_name, victim_age, victim_gender, location, description, image_path,
             citizen_name, citizen_phone)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (victim_name, victim_age, victim_gender, location, description, image_path,
              citizen_name, citizen_phone))

        db.commit()
        return render_template('success.html')

    return render_template('report.html')

# ================================
# POLICE LOGIN
# ================================
@app.route('/police', methods=['GET', 'POST'])
def police_login():
    if request.method == 'POST':
        role = request.form['role']
        password = request.form['password']

        # Officer Login
        if role == "officer":
            officer_name = request.form['officer_name']

            if password == "police123":
                session['police'] = True
                session['role'] = "officer"
                session['officer_name'] = officer_name
                return redirect(url_for('police_dashboard'))

            return render_template('police_login.html', error="Invalid Officer Password")

        # Admin Login
        else:
            if password == "admin123":
                session['police'] = True
                session['role'] = "admin"
                session['officer_name'] = None
                return redirect(url_for('police_dashboard'))

            return render_template('police_login.html', error="Invalid Admin Password")

    return render_template('police_login.html')

# ================================
# POLICE DASHBOARD
# ================================
@app.route('/police/dashboard')
def police_dashboard():
    if 'police' not in session:
        return redirect(url_for('police_login'))

    cursor2 = db.cursor(dictionary=True)

    if session['role'] == "admin":
        cursor2.execute("SELECT * FROM reports ORDER BY id DESC")
    else:
        cursor2.execute("""
            SELECT * FROM reports 
            WHERE assigned_to=%s 
            ORDER BY id DESC
        """, (session['officer_name'],))

    reports = cursor2.fetchall()
    cursor2.close()

    return render_template('view.html', reports=reports)

# ================================
# SEARCH VIEW (ADMIN OR OFFICER)
# ================================
@app.route('/view', methods=['GET', 'POST'])
def view_reports():
    if 'police' not in session:
        return redirect(url_for('police_login'))

    keyword = ""

    if request.method == 'POST':
        keyword = request.form.get('keyword', "").strip()

        cursor2 = db.cursor(dictionary=True)

        cursor2.execute("""
            SELECT * FROM reports
            WHERE citizen_name LIKE %s 
               OR location LIKE %s
               OR description LIKE %s
            ORDER BY id DESC
        """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"))

        reports = cursor2.fetchall()
        cursor2.close()

        return render_template("view.html", reports=reports, keyword=keyword)

    # If GET request → show all
    return redirect(url_for('police_dashboard'))


# ================================
# VIEW SINGLE REPORT
# ================================
@app.route('/report/<int:report_id>')
def view_report(report_id):

    cursor = db.cursor(dictionary=True)

    # ============================
    # Assign case ONLY if unassigned
    # ============================
    if "officer_name" in session:
        cursor2 = db.cursor()

        # Check current assignment
        cursor2.execute("SELECT assigned_to FROM reports WHERE id=%s", (report_id,))
        row = cursor2.fetchone()
        current_assigned = row[0] if row else None

        # Assign only if empty
        if not current_assigned or current_assigned.strip() == "":
            cursor2.execute("""
                UPDATE reports 
                SET assigned_to=%s 
                WHERE id=%s
            """, (session["officer_name"], report_id))
            db.commit()

        cursor2.close()

    # ============================
    # Serial number calculation
    # ============================
    cursor.execute("SELECT id FROM reports ORDER BY id ASC")
    all_reports = cursor.fetchall()

    cursor.execute("SELECT * FROM reports WHERE id=%s", (report_id,))
    report = cursor.fetchone()
    cursor.close()

    serial = next((i+1 for i, r in enumerate(all_reports) if r["id"] == report_id), report_id)

    return render_template("report_details.html", report=report, serial=serial)



# ================================
# MARK REPORT AS SOLVED
# ================================
@app.route('/solve/<int:report_id>', methods=['POST'])
def solve(report_id):
    officer = session.get('officer_name', 'Unknown')

    cursor.execute("""
        UPDATE reports 
        SET status='Solved', solved_by=%s 
        WHERE id=%s
    """, (officer, report_id))

    db.commit()
    return redirect(url_for('police_dashboard'))
# ================================
# DELETE REPORT (ADMIN ONLY)
# ================================
@app.route('/delete/<int:report_id>', methods=['POST'])
def delete_report(report_id):
    if session.get('role') != "admin":
        return "Unauthorized", 403

    cursor.execute("DELETE FROM reports WHERE id=%s", (report_id,))
    db.commit()

    return redirect(url_for('police_dashboard'))

# ================================
# LOGOUT
# ================================
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))
@app.route('/assign/<int:report_id>', methods=['POST'])
def assign_case(report_id):
    if session.get('role') != "admin":
        return "Unauthorized", 403

    officer_name = request.form['officer_name']

    cursor.execute("""
        UPDATE reports 
        SET assigned_to=%s 
        WHERE id=%s
    """, (officer_name, report_id))
    
    db.commit()
    return redirect(url_for('police_dashboard'))

# ================================
# RUN APP
# ================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
