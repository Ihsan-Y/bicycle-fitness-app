from flask import Flask, render_template_string, request, flash, redirect, url_for
import datetime
import os
import re
import sqlite3

app = Flask(__name__)
app.secret_key = "bisiklet_fitness_gizli_anahtar"

# --- VERİTABANI AYARLARI ---
def get_db_connection():
    conn = sqlite3.connect('veritabani.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS kullanicilar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad TEXT, soyad TEXT, kullanici_adi TEXT UNIQUE,
            sifre TEXT, eposta TEXT UNIQUE, telefon TEXT UNIQUE,
            kayit_tarihi TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- DOĞRULAMA FONKSİYONLARI ---
def validate_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) if email else False

def validate_phone(tel):
    if not tel: return False
    nums = re.sub(r"\D", "", tel)
    return len(nums) == 10 and not nums.startswith('0')

def validate_password(pw):
    if not pw or len(pw) < 8: return False
    if not re.search(r"[a-z]", pw): return False
    if not re.search(r"[A-Z]", pw): return False
    if not re.search(r"[0-9]", pw): return False
    return True

# --- ANTRENMAN VERİLERİ ---
WORKOUTS = {
    'aletsiz': [
        {'isim': 'Squat', 'set': '3x15', 'detay': 'Bacak ve kalça gücü için temel hareket.'},
        {'isim': 'Plank', 'set': '3x45sn', 'detay': 'Core bölgesi ve denge sağlar.'},
        {'isim': 'Şınav', 'set': '3x12', 'detay': 'Üst vücut ve göğüs kasları.'}
    ],
    'aletli': [
        {'isim': 'Leg Press', 'set': '4x10', 'detay': 'Alt vücut kuvvet patlaması.'},
        {'isim': 'Kettlebell Swing', 'set': '3x20', 'detay': 'Kardiyo ve kalça kuvveti.'},
        {'isim': 'Lat Pulldown', 'set': '3x12', 'detay': 'Sırt ve çekiş gücü.'}
    ]
}

# --- HTML ŞABLONLARI ---

HOME_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <title>Bisikletçi Fitness</title>
    <style>
        body { background-color: #f4f7f6; font-family: sans-serif; }
        .auth-card { border-radius: 15px; border: none; max-width: 600px; margin: auto; }
        .hint-text { font-size: 0.75rem; color: #6c757d; margin-top: -8px; margin-bottom: 10px; display: block; }
        .hidden-trap { display: none !important; }
        .modal-body { max-height: 350px; overflow-y: auto; font-size: 0.9rem; line-height: 1.5; }
    </style>
</head>
<body onload="checkStatus()">
    <nav class="navbar navbar-light bg-white shadow-sm mb-4">
        <div class="container">
            <a class="navbar-brand fw-bold text-primary" href="/">Bisikletçi Fitness</a>
            <button class="btn btn-outline-success btn-sm" data-bs-toggle="modal" data-bs-target="#modalLogin">Üye Girişi</button>
        </div>
    </nav>

    <div class="container">
        <h2 class="text-center mb-4 fw-bold text-primary">Performans Yolculuğuna Başla</h2>
        <div class="card auth-card shadow-sm p-4 border-top border-primary border-5">
            <h4 class="mb-4 text-primary text-center">Yeni Kayıt Formu</h4>
            {% with messages = get_flashed_messages(category_filter=["reg_err"]) %}
              {% if messages %}{% for m in messages %}<div class="alert alert-danger small">{{ m }}</div>{% endfor %}{% endif %}
            {% endwith %}
            
            <form id="regForm" action="/check_and_open_modals" method="POST" autocomplete="off">
                <div class="hidden-trap"><input type="text"><input type="password"></div>
                <input type="hidden" name="saved_pass" id="saved_pass" value="{{ d.saved_pass or '' }}">

                <div class="row">
                    <div class="col-md-6 mb-2"><input type="text" name="ad" class="form-control" placeholder="Ad" required value="{{ d.ad or '' }}"></div>
                    <div class="col-md-6 mb-2"><input type="text" name="soyad" class="form-control" placeholder="Soyad" required value="{{ d.soyad or '' }}"></div>
                </div>
                
                <input type="text" name="user" class="form-control mb-2" placeholder="Kullanıcı Adı" required value="{{ d.user or '' }}">
                <input type="password" id="display_pass" name="pass" class="form-control mb-2" placeholder="Şifre" {% if not d.saved_pass %}required{% endif %} autocomplete="new-password">
                <span class="hint-text text-start">En az 8 karakter (Büyük/Küçük harf ve Sayı)</span>
                
                <input type="email" name="email" class="form-control mb-2" placeholder="E-posta" required value="{{ d.email or '' }}">
                <input type="tel" name="tel" class="form-control mb-3" placeholder="Telefon (5xx...)" required value="{{ d.tel or '' }}">
                
                <button type="submit" class="btn btn-primary w-100 py-2 fw-bold" onclick="syncPass()">HEMEN KAYIT OL</button>
            </form>
        </div>
    </div>

    <div class="modal fade" id="modalLogin" tabindex="-1">
        <div class="modal-dialog modal-sm modal-dialog-centered">
            <div class="modal-content p-4">
                <h5 class="text-center mb-3 text-success">Giriş Yap</h5>
                {% with messages = get_flashed_messages(category_filter=["login_err"]) %}
                  {% if messages %}{% for m in messages %}<div class="alert alert-warning small">{{ m }}</div>{% endfor %}{% endif %}
                {% endwith %}
                <form action="/login" method="POST">
                    <input type="text" name="login_user" class="form-control mb-2" placeholder="Kullanıcı Adı" required>
                    <input type="password" name="login_pass" class="form-control mb-3" placeholder="Şifre" required>
                    <button type="submit" class="btn btn-success w-100">Antrenmana Başla</button>
                </form>
            </div>
        </div>
    </div>

    <div class="modal fade" id="modalContract" data-bs-backdrop="static" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered"><div class="modal-content">
            <div class="modal-header bg-primary text-white"><h5>Kullanıcı Sözleşmesi</h5></div>
            <div class="modal-body">
                <h6>1. Taraflar</h6>
                <p>İşbu sözleşme Bisikletçi Fitness ve Uygulama'yı kullanan Kullanıcı arasında akdedilmiştir.</p>
                <h6>2. Hizmet Kapsamı</h6>
                <p>Uygulama, bisiklet odaklı fitness programları sunar. Egzersizlerin uygulanması sırasında doğabilecek sağlık sorunlarından kullanıcı sorumludur.</p>
                <h6>3. Fikri Mülkiyet</h6>
                <p>Tasarım ve içerikler Bisikletçi Fitness'a aittir, izinsiz kopyalanamaz.</p>
            </div>
            <div class="modal-footer"><button type="button" class="btn btn-primary" onclick="showKVKK()">Okudum, Onaylıyorum</button></div>
        </div></div>
    </div>
    <div class="modal fade" id="modalKVKK" data-bs-backdrop="static" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered"><div class="modal-content">
            <div class="modal-header bg-dark text-white"><h5>KVKK Rıza Metni</h5></div>
            <div class="modal-body">
                <p><strong>6698 Sayılı Kanun Uyarınca:</strong></p>
                <p>Ad, soyad, e-posta ve telefon verileriniz sadece üyeliğinizin oluşturulması ve antrenman takibi amacıyla güvenli arşivimizde saklanmaktadır. Verileriniz üçüncü taraflarla paylaşılmaz.</p>
                <p>Kabul ederek verilerinizin işlenmesine rıza göstermektesiniz.</p>
            </div>
            <div class="modal-footer"><button type="button" class="btn btn-success" onclick="submitFinal()">Kabul Ediyorum</button></div>
        </div></div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function syncPass() { const p = document.getElementById('display_pass').value; if(p) document.getElementById('saved_pass').value = p; }
        function checkStatus() {
            {% if open_modals %} new bootstrap.Modal(document.getElementById('modalContract')).show(); {% endif %}
            {% if get_flashed_messages(category_filter=["login_err"]) %} new bootstrap.Modal(document.getElementById('modalLogin')).show(); {% endif %}
        }
        function showKVKK() { 
            bootstrap.Modal.getInstance(document.getElementById('modalContract')).hide();
            new bootstrap.Modal(document.getElementById('modalKVKK')).show(); 
        }
        function submitFinal() { const f = document.getElementById('regForm'); f.action = "/register"; f.submit(); }
    </script>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body { background-color: #f8f9fa; }
        .welcome-section { background: linear-gradient(135deg, #0d6efd, #0a58ca); color: white; padding: 60px 0; border-radius: 0 0 40px 40px; }
        .workout-card { border: none; border-radius: 20px; transition: 0.3s; cursor: pointer; text-decoration: none; color: black; height: 100%; display: block; }
        .workout-card:hover { transform: translateY(-10px); box-shadow: 0 15px 30px rgba(0,0,0,0.1); color: inherit; }
        .icon-box { width: 70px; height: 70px; display: flex; align-items: center; justify-content: center; margin: 0 auto 15px; border-radius: 50%; }
    </style>
</head>
<body>
<div class="welcome-section text-center mb-5 shadow">
    <h1 class="fw-bold">Hoş Geldin, {{ username }}!</h1>
    <p class="lead">Bugün limitlerini zorlamaya hazır mısın?</p>
</div>
<div class="container">
    <div class="row justify-content-center g-4 text-center">
        <div class="col-md-5">
            <a href="/antrenman/aletsiz" class="card workout-card shadow-sm p-5">
                <div class="icon-box bg-success bg-opacity-10 text-success"><i class="fa-solid fa-person-running fa-3x"></i></div>
                <h3 class="fw-bold">Aletsiz Program</h3>
                <p class="text-muted">Kendi vücut ağırlığınla her yerde antrenman yap.</p>
            </a>
        </div>
        <div class="col-md-5">
            <a href="/antrenman/aletli" class="card workout-card shadow-sm p-5">
                <div class="icon-box bg-primary bg-opacity-10 text-primary"><i class="fa-solid fa-dumbbell fa-3x"></i></div>
                <h3 class="fw-bold">Aletli Program</h3>
                <p class="text-muted">Maksimum güç için ekipmanlı egzersizler.</p>
            </a>
        </div>
    </div>
    <div class="text-center mt-5 mb-5"><a href="/logout" class="btn btn-outline-danger px-5 py-2 fw-bold">GÜVENLİ ÇIKIŞ</a></div>
</div>
</body>
</html>
"""

WORKOUT_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f0f2f5; }
        .list-container { max-width: 600px; margin: 50px auto; }
        .exercise-card { border: none; border-radius: 15px; border-left: 5px solid #0d6efd; transition: 0.2s; }
    </style>
</head>
<body class="p-3">
    <div class="list-container">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2 class="fw-bold text-primary text-capitalize">{{ tip }} Antrenmanı</h2>
            <a href="javascript:history.back()" class="btn btn-secondary">Geri Dön</a>
        </div>
        {% for h in hareketler %}
        <div class="card exercise-card shadow-sm p-3 mb-3">
            <div class="d-flex justify-content-between align-items-center">
                <h5 class="mb-0 fw-bold text-dark">{{ h.isim }}</h5>
                <span class="badge bg-primary px-3 py-2">{{ h.set }}</span>
            </div>
            <p class="text-muted small mt-2 mb-0">{{ h.detay }}</p>
        </div>
        {% endfor %}
    </div>
</body>
</html>
"""

# --- ROUTES ---

@app.route('/')
def home():
    return render_template_string(HOME_HTML, d={}, err=None, open_modals=False)

@app.route('/check_and_open_modals', methods=['POST'])
def check_modals():
    # Şifre alanını hem normalden hem de gizli alandan kontrol ediyoruz
    pass_val = request.form.get('pass')
    saved_pass = request.form.get('saved_pass')
    final_pass = pass_val if pass_val else saved_pass

    data = {
        'ad': request.form.get('ad'),
        'soyad': request.form.get('soyad'),
        'user': request.form.get('user'),
        'email': request.form.get('email'),
        'tel': request.form.get('tel'),
        'saved_pass': final_pass
    }
    
    # Şifre None hatasını engellemek için kontrol
    if not final_pass or not validate_password(final_pass): 
        flash("Şifre zayıf veya boş! (8 karakter, Büyük/Küçük harf, Sayı)", "reg_err")
        return render_template_string(HOME_HTML, d=data, err='pass')

    if not validate_email(data['email']): 
        flash("E-posta geçersiz!", "reg_err")
        return render_template_string(HOME_HTML, d=data, err='email')

    # SQLite Mükerrer Kontrolü
    conn = get_db_connection()
    existing = conn.execute('SELECT * FROM kullanicilar WHERE kullanici_adi = ? OR eposta = ? OR telefon = ?', 
                            (data['user'], data['email'], data['tel'])).fetchone()
    conn.close()

    if existing:
        flash("Bu kullanıcı adı, e-posta veya telefon zaten kayıtlı!", "reg_err")
        return render_template_string(HOME_HTML, d=data, err='duplicate')
    
    return render_template_string(HOME_HTML, d=data, err=None, open_modals=True)

@app.route('/register', methods=['POST'])
def register():
    p = request.form.get('saved_pass')
    ad = request.form.get('ad')
    soyad = request.form.get('soyad')
    user = request.form.get('user')
    email = request.form.get('email')
    tel = request.form.get('tel')
    
    tarih = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO kullanicilar (ad, soyad, kullanici_adi, sifre, eposta, telefon, kayit_tarihi) VALUES (?, ?, ?, ?, ?, ?, ?)',
                     (ad, soyad, user, p, email, tel, tarih))
        conn.commit()
        return render_template_string(DASHBOARD_HTML, username=user)
    except Exception as e:
        flash(f"Kayıt hatası: {str(e)}", "reg_err")
        return redirect(url_for('home'))
    finally:
        conn.close()

@app.route('/login', methods=['POST'])
def login():
    u = request.form.get('login_user')
    p = request.form.get('login_pass')
    
    conn = get_db_connection()
    user_row = conn.execute('SELECT * FROM kullanicilar WHERE kullanici_adi = ? AND sifre = ?', (u, p)).fetchone()
    conn.close()
    
    if user_row:
        return render_template_string(DASHBOARD_HTML, username=u)
    
    flash("Hatalı kullanıcı adı veya şifre!", "login_err")
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    return redirect(url_for('home'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)