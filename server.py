from flask import Flask, redirect, url_for, render_template, request, session, flash, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import os
import sqlite3

app = Flask(__name__)

# ------------------- Config -------------------
app.secret_key = 'kapikapi123'
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ------------------- Veritabanı Fonksiyonları -------------------
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fullname TEXT,
        email TEXT UNIQUE,
        password TEXT,
        phone TEXT,
        user_type TEXT,
        profile_image TEXT,
        user_plate TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT,
        text TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

init_db()

# ------------------- Rotalar -------------------
@app.route("/")
def home():
    return render_template('index.html')

@app.route("/gonder")
def send():
    return render_template('send.html')

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        msg_text = request.form.get('message')
        if msg_text:
            conn = get_db_connection()
            conn.execute('INSERT INTO messages (sender, text) VALUES (?, ?)',
                         (session['user_name'], msg_text))
            conn.commit()
            conn.close()
            
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
             return "OK", 200 
        
        return redirect(url_for('chat'))

    conn = get_db_connection()
    messages = conn.execute('SELECT * FROM messages ORDER BY timestamp ASC').fetchall()
    conn.close()
    return render_template('chat.html', messages=messages)

@app.route('/get_messages')
def get_messages():
    conn = get_db_connection()
    db_messages = conn.execute('SELECT sender, text FROM messages ORDER BY timestamp ASC').fetchall()
    conn.close()
    output = [{'sender': m['sender'], 'text': m['text']} for m in db_messages]
    return jsonify({"messages": output})

# ------------------- Login -------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        sifre = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()

        if not user or not check_password_hash(user['password'], sifre):
            flash("Email veya şifre yanlış!", "error")
            return redirect(url_for('login'))

        # Session Bilgilerini Doldur
        session['user_id'] = user['email']
        session['user_name'] = user['fullname']
        session['email'] = user['email']
        session['phone'] = user['phone']
        session['user_type'] = user['user_type']
        session['profile_image'] = user['profile_image'] or 'static/uploads/default.jpg'
        session['user_plate'] = user['user_plate']
        
        flash(f"Hoş geldin, {user['fullname']}!", "success")
        return redirect(url_for('home')) # Girişten sonra ANA SAYFAYA yönlendir

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()  
    flash("Başarıyla çıkış yapıldı.", "info")
    return redirect(url_for('login')) 

# ------------------- Register -------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        ad = request.form['fullname']
        email = request.form['email']
        sifre = request.form['password']
        sifre_tekrar = request.form['password_repeat']
        tel = request.form['phone']
        user_type = request.form['user_type'] 
        plate = request.form.get('plate') if user_type == 'kurye' else None
    
        if sifre != sifre_tekrar:
            flash("Şifreler eşleşmiyor!", "error")
            return redirect(url_for('register'))

        profile_image = 'static/uploads/default.jpg'
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(save_path)
                profile_image = save_path

        hashed_password = generate_password_hash(sifre, method='pbkdf2:sha256')

        conn = get_db_connection()
        try:
            conn.execute('''INSERT INTO users 
                (fullname, email, password, phone, user_type, profile_image, user_plate) 
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (ad, email, hashed_password, tel, user_type, profile_image, plate))
            conn.commit()
            flash("Kayıt başarılı! Lütfen giriş yapın.", "success")
            return redirect(url_for('login')) # Kayıt sonrası LOGIN sayfasına yönlendir
        except sqlite3.IntegrityError:
            flash("Bu email adresi zaten kullanımda!", "error")
            return redirect(url_for('register'))
        finally:
            conn.close()

    return render_template('register.html')

# ------------------- Profile & Edit -------------------
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = {
        'user_name': session.get('user_name'),
        'user_email': session.get('email'),
        'user_phone': session.get('phone'),
        'user_image': session.get('profile_image'),
        'user_plate': session.get('user_plate'),
    }
    user_type = session.get('user_type', 'customer')
    past_orders = [
        {"id": 1, "date": "2025-11-15", "status": "Teslim Edilecek" if user_type != 'kurye' else "Teslimatlar"},
        {"id": 2, "date": "2025-12-01", "status": "Teslim Edilecek" if user_type != 'kurye' else "Teslimatlar"}
    ]
    return render_template('profile.html', user=user, past_orders=past_orders, user_type=user_type)

@app.route("/edit_profile", methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == "POST":
        new_name = request.form['fullname']
        new_phone = request.form['phone']
        
        conn = get_db_connection()
        conn.execute('UPDATE users SET fullname = ?, phone = ? WHERE email = ?',
                     (new_name, new_phone, session['email']))
        
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(save_path)
                conn.execute('UPDATE users SET profile_image = ? WHERE email = ?',
                             (save_path, session['email']))
                session['profile_image'] = save_path

        conn.commit()
        conn.close()
        
        session['user_name'] = new_name
        session['phone'] = new_phone
        flash("Profil başarıyla güncellendi.", "success")
        return redirect(url_for('profile'))

    user = {
        'fullname': session.get('user_name'),
        'email': session.get('email'),
        'phone': session.get('phone'),
        'profile_image': session.get('profile_image')
    }
    return render_template('edit_profile.html', user=user)

@app.route("/takip")
def track(): return render_template('track.html')

@app.route("/kurye-ol")
def courier(): return render_template('courier.html')

if __name__ == "__main__":
    app.run(debug=True)