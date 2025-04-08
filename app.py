from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_cors import CORS
import sqlite3

app = Flask(__name__)
CORS(app)

# إنشاء اتصال بقاعدة البيانات
def get_db_connection():
    conn = sqlite3.connect('Ourproject.db')
    conn.row_factory = sqlite3.Row
    return conn

# إنشاء الجداول إذا لم تكن موجودة
def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # جدول الأدوية
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medicines (
            medicine_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT
        )
    ''')

    # جدول الصيدليات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pharmacies (
            pharmacy_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            latitude REAL,
            longitude REAL
        )
    ''')

    # جدول العلاقة بين الأدوية والصيدليات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pharmacy_medicines (
            pharmacy_id INTEGER,
            medicine_id INTEGER,
            quantity INTEGER DEFAULT 0,
            FOREIGN KEY (pharmacy_id) REFERENCES pharmacies (pharmacy_id),
            FOREIGN KEY (medicine_id) REFERENCES medicines (medicine_id),
            PRIMARY KEY (pharmacy_id, medicine_id)
        )
    ''')
    
    conn.commit()
    conn.close()

def init_app():
    create_tables()

@app.route('/')
def index():
    conn = get_db_connection()
    medicines = conn.execute('SELECT * FROM medicines').fetchall()
    pharmacies = conn.execute('SELECT * FROM pharmacies').fetchall()
    conn.close()
    return render_template('index.html', medicines=medicines, pharmacies=pharmacies)

# إضافة صيدلية
@app.route('/add_pharmacy', methods=['POST'])
def add_pharmacy():
    name = request.form['name']
    latitude = request.form['latitude']
    longitude = request.form['longitude']
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO pharmacies (name, latitude, longitude) VALUES (?, ?, ?)',
        (name, latitude, longitude)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

# صفحة تعديل الصيدلية (GET) والدالة (POST)
@app.route('/edit_pharmacy/<int:pharmacy_id>', methods=['GET', 'POST'])
def edit_pharmacy(pharmacy_id):
    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form['name']
        latitude = request.form['latitude']
        longitude = request.form['longitude']
        conn.execute(
            'UPDATE pharmacies SET name = ?, latitude = ?, longitude = ? WHERE pharmacy_id = ?',
            (name, latitude, longitude, pharmacy_id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    else:
        pharmacy = conn.execute('SELECT * FROM pharmacies WHERE pharmacy_id = ?', (pharmacy_id,)).fetchone()
        conn.close()
        return render_template('edit_pharmacy.html', pharmacy=pharmacy)

# حذف صيدلية
@app.route('/delete_pharmacy/<int:pharmacy_id>', methods=['POST'])
def delete_pharmacy(pharmacy_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM pharmacies WHERE pharmacy_id = ?', (pharmacy_id,))
    conn.execute('DELETE FROM pharmacy_medicines WHERE pharmacy_id = ?', (pharmacy_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

# إضافة دواء
@app.route('/add_medicine', methods=['POST'])
def add_medicine():
    name = request.form['name']
    description = request.form['description']
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO medicines (name, description) VALUES (?, ?)',
        (name, description)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

# صفحة تعديل الدواء (GET) والدالة (POST)
@app.route('/edit_medicine/<int:medicine_id>', methods=['GET', 'POST'])
def edit_medicine(medicine_id):
    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        conn.execute(
            'UPDATE medicines SET name = ?, description = ? WHERE medicine_id = ?',
            (name, description, medicine_id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    else:
        medicine = conn.execute('SELECT * FROM medicines WHERE medicine_id = ?', (medicine_id,)).fetchone()
        conn.close()
        return render_template('edit_medicine.html', medicine=medicine)

# حذف دواء
@app.route('/delete_medicine/<int:medicine_id>', methods=['POST'])
def delete_medicine(medicine_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM medicines WHERE medicine_id = ?', (medicine_id,))
    conn.execute('DELETE FROM pharmacy_medicines WHERE medicine_id = ?', (medicine_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

# عرض الصيدليات التي تحتوي على دواء معين
@app.route('/pharmacies_with_medicine/<int:medicine_id>')
def pharmacies_with_medicine(medicine_id):
    conn = get_db_connection()
    pharmacies = conn.execute('''
        SELECT p.pharmacy_id, p.name, p.latitude, p.longitude, pm.quantity
        FROM pharmacies p
        JOIN pharmacy_medicines pm ON p.pharmacy_id = pm.pharmacy_id
        WHERE pm.medicine_id = ? AND pm.quantity > 0
    ''', (medicine_id,)).fetchall()
    medicine = conn.execute(
        'SELECT name FROM medicines WHERE medicine_id = ?', 
        (medicine_id,)
    ).fetchone()
    conn.close()
    return render_template('pharmacies_with_medicine.html', pharmacies=pharmacies, medicine=medicine)

# البحث عن الأدوية
@app.route('/medicines', methods=['GET'])
def search_medicines():
    query = request.args.get('query', '').strip().lower()
    conn = get_db_connection()
    medicines = conn.execute('''
        SELECT * FROM medicines
        WHERE LOWER(name) LIKE ? OR LOWER(description) LIKE ?
    ''', ('%' + query + '%', '%' + query + '%')).fetchall()
    conn.close()
    return jsonify([{
        'id': m['medicine_id'], 
        'name': m['name'], 
        'description': m['description']
    } for m in medicines])

# البحث عن الصيدليات القريبة
@app.route('/nearby_pharmacies', methods=['GET'])
def nearby_pharmacies():
    medicine_id = request.args.get('medicine_id', type=int)
    user_lat = request.args.get('lat', type=float)
    user_lng = request.args.get('lng', type=float)
    conn = get_db_connection()
    pharmacies = conn.execute('''
        SELECT p.*, pm.quantity,
        (6371 * acos(cos(radians(?)) * cos(radians(p.latitude)) 
        * cos(radians(p.longitude) - radians(?)) 
        + sin(radians(?)) * sin(radians(p.latitude)))) AS distance
        FROM pharmacies p
        JOIN pharmacy_medicines pm ON p.pharmacy_id = pm.pharmacy_id
        WHERE pm.medicine_id = ? AND pm.quantity > 0
        ORDER BY distance
        LIMIT 10
    ''', (user_lat, user_lng, user_lat, medicine_id)).fetchall()
    conn.close()
    return jsonify([dict(pharmacy) for pharmacy in pharmacies])

# إضافة دواء إلى صيدلية
@app.route('/add_medicine_to_pharmacy', methods=['POST'])
def add_medicine_to_pharmacy():
    pharmacy_id = request.form['pharmacy_id']
    medicine_id = request.form['medicine_id']
    quantity = request.form['quantity']
    conn = get_db_connection()
    conn.execute('''
        INSERT OR REPLACE INTO pharmacy_medicines (pharmacy_id, medicine_id, quantity)
        VALUES (?, ?, ?)
    ''', (pharmacy_id, medicine_id, quantity))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

# تهيئة التطبيق
init_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
