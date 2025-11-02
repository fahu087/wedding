from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
import os
import time
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'supersecretkey123'

# ✅ Connect to MySQL
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="fahu087",
    database="safecity"
)
cursor = db.cursor()

# ✅ Folder to store uploaded images
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# ✅ Homepage
@app.route('/')
def home():
    return render_template('index.html')


# ✅ Report page (with multiple image upload + location)
@app.route('/report', methods=['GET', 'POST'])
def report():
    if request.method == 'POST':
        name = request.form['name']
        location = request.form['location']
        description = request.form['description']

        # ✅ Save multiple images safely
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

        # ✅ Save with citizen info (if logged in)
        citizen = session.get('citizen')
        citizen_name = citizen['name'] if citizen else None
        citizen_phone = citizen['phone'] if citizen else None

        cursor.execute("""
            INSERT INTO reports (name, location, description, image_path, citizen_name, citizen_phone)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name, location, description, image_path, citizen_name, citizen_phone))
        db.commit()

        return render_template('success.html')

    return render_template('report.html')

# ✅ View Reports (Citizen view)
@app.route('/view', methods=['GET', 'POST'])
def view_reports():
    keyword = request.form.get('keyword', '')

    if keyword:
        cursor.execute("""
            SELECT * FROM reports
            WHERE (name LIKE %s OR location LIKE %s)
            ORDER BY id DESC
        """, (f"%{keyword}%", f"%{keyword}%"))
    else:
        cursor.execute("SELECT * FROM reports ORDER BY id DESC")

    data = cursor.fetchall()
    return render_template('view.html', reports=data, keyword=keyword)


# ✅ Mark as Solved
@app.route('/solve/<int:report_id>', methods=['POST'])
def mark_as_solved(report_id):
    cursor.execute("UPDATE reports SET status = %s WHERE id = %s", ("Solved", report_id))
    db.commit()
    return redirect(url_for('police_dashboard'))


# ✅ Delete Report
@app.route('/delete/<int:report_id>', methods=['POST'])
def delete_report(report_id):
    cursor.execute("SELECT image_path FROM reports WHERE id = %s", (report_id,))
    result = cursor.fetchone()

    if result and result[0]:
        img_paths = result[0].split(',')
        for img_path in img_paths:
            full_path = os.path.join('static', img_path.strip())
            if os.path.exists(full_path):
                os.remove(full_path)

    cursor.execute("DELETE FROM reports WHERE id = %s", (report_id,))
    db.commit()
    return redirect(url_for('police_dashboard'))


# ✅ Citizen Login
@app.route('/citizen/login', methods=['GET', 'POST'])
def citizen_login():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        session['citizen'] = {'name': name, 'phone': phone}
        return redirect(url_for('citizen_home'))
    return render_template('citizen_login.html')


# ✅ Citizen Dashboard
@app.route('/citizen/home')
def citizen_home():
    if 'citizen' not in session:
        return redirect(url_for('citizen_login'))
    citizen = session['citizen']
    return render_template('citizen_home.html', citizen=citizen)


# ✅ Police Login
@app.route('/police', methods=['GET', 'POST'])
def police_login():
    if request.method == 'POST':
        password = request.form['password']
        if password == 'police123':  # Simple static password (you can change)
            session['police'] = True
            return redirect(url_for('police_dashboard'))
        else:
            return render_template('police_login.html', error="Invalid password")
    return render_template('police_login.html')


@app.route('/police/dashboard')
def police_dashboard():
    if 'police' not in session:
        return redirect(url_for('police_login'))
    cursor.execute("SELECT * FROM reports ORDER BY id DESC")
    reports = cursor.fetchall()
    return render_template('view.html', reports=reports)



# ✅ Logout (for both)
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))
@app.route('/citizen/reports')
def citizen_reports():
    if 'citizen' not in session:
        return redirect(url_for('citizen_login'))

    citizen = session['citizen']
    cursor.execute("""
        SELECT id, name, location, description, image_path, status
        FROM reports
        WHERE citizen_name = %s AND citizen_phone = %s
        ORDER BY id DESC
    """, (citizen['name'], citizen['phone']))
    reports = cursor.fetchall()

    return render_template('citizen_reports.html', citizen=citizen, reports=reports)


if __name__ == '__main__':
    app.run(debug=True)
