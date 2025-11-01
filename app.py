from flask import Flask, render_template, request, redirect, url_for
import mysql.connector, os, time
from werkzeug.utils import secure_filename

app = Flask(__name__)

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

# ✅ Report page (with image upload + auto location)
@app.route('/report', methods=['GET', 'POST'])
def report():
    if request.method == 'POST':
        name = request.form['name']
        location = request.form['location']
        description = request.form['description']

        # ✅ Save image safely with unique name
        image_file = request.files['image']
        image_path = None
        if image_file and image_file.filename != '':
            filename = secure_filename(image_file.filename)
            unique_name = str(int(time.time())) + "_" + filename  # make unique
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
            image_file.save(save_path)
            image_path = f"uploads/{unique_name}"  # only relative path stored

        # ✅ Insert data into database
        cursor.execute("""
            INSERT INTO reports (name, location, description, image_path)
            VALUES (%s, %s, %s, %s)
        """, (name, location, description, image_path))
        db.commit()

        return render_template('success.html')

    return render_template('report.html')

# ✅ View all reports (with search)
@app.route('/view', methods=['GET', 'POST'])
def view_reports():
    keyword = request.form.get('keyword', '')
    if keyword:
        cursor.execute("""
            SELECT * FROM reports
            WHERE name LIKE %s OR location LIKE %s
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
    return redirect(url_for('view_reports'))

if __name__ == '__main__':
    app.run(debug=True)
