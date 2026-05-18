import json
import os
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, abort, send_from_directory
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = "pico_w_ry_water_quality_2026"

# ==========================
# 安全性與存儲 (自動建立必要資料夾與檔案)
# ==========================
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
app.config['UPLOAD_FOLDER'] = 'uploads/avatars'

USERS_FILE = "users.json"
BOATS_FILE = "boats.json"
HISTORY_DIR = "history"

def init_storage():
    # 建立資料夾
    for folder in [HISTORY_DIR, app.config['UPLOAD_FOLDER']]:
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
            print(f"已建立資料夾: {folder}")
    
    # 建立初始 JSON 檔案 (若不存在)
    for file in [USERS_FILE, BOATS_FILE]:
        if not os.path.exists(file):
            with open(file, "w", encoding="utf-8") as f:
                json.dump([], f)
            print(f"已建立初始檔案: {file}")

init_storage()

# ==========================
# 資料輔助函式
# ==========================
def load_json(filename):
    if not os.path.exists(filename): return []
    with open(filename, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return []

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_history_file(ip):
    return os.path.join(HISTORY_DIR, f"path_{ip.replace('.', '_')}.json")

def get_user(username):
    users = load_json(USERS_FILE)
    return next((u for u in users if u['username'] == username), None)

# ==========================
# 全域變數
# ==========================
boat_states = {}

def get_boat_state(ip):
    if ip not in boat_states:
        history = load_json(get_history_file(ip))
        boat_states[ip] = {
            "mode": "manual", "move": "stop", "pump": False,
            "lat": None, "lng": None, "gps_valid": False,
            "time": None, "track": history, "target_pos": None,      
            "cruise_path": [], "start_pos": None        
        }
    return boat_states[ip]

def ensure_boat_exists(ip):
    boats = load_json(BOATS_FILE)
    if not any(b['ip'] == ip for b in boats):
        new_boat = {
            "name": f"自動辨識設備 ({ip})",
            "ip": ip,
            "password": "123456789"
        }
        boats.append(new_boat)
        save_json(BOATS_FILE, boats)

# ==========================
# 權限裝飾器
# ==========================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "username" not in session: return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get("role") not in roles:
                return jsonify({"status": "error", "message": "權限不足"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def check_boat_auth(ip):
    if session.get("role") == "admin": return True
    if session.get("role") == "guest": return True 
    if ip in session.get("authorized_boats", []): return True
    return False

# ==========================
# 靜態資源路由
# ==========================
@app.route('/logo.png')
def serve_logo():
    return send_from_directory('.', 'logo.png')

@app.route('/uploads/avatars/<path:filename>')
def serve_avatar(filename):
    if not os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
        return send_from_directory('.', 'logo.png')
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ==========================
# 共享樣式
# ==========================
COMMON_STYLE = """
<style>
    :root { 
        --primary: #0284c7; --secondary: #10b981; --danger: #ef4444; --warning: #f59e0b; 
        --info: #0ea5e9; --bg: #f0f9ff; --card-bg: #ffffff; 
        --text-main: #0c4a6e; --text-muted: #64748b; 
    }
    * { box-sizing: border-box; }
    body { font-family: 'Inter', 'Microsoft JhengHei', system-ui, sans-serif; margin: 0; background: var(--bg); color: var(--text-main); }
    header { 
        background: #ffffff; color: var(--text-main); padding: 0.6rem 1rem; 
        display: flex; justify-content: space-between; align-items: center; 
        position: sticky; top: 0; z-index: 1000; border-bottom: 2px solid #e0f2fe;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .header-branding { display: flex; align-items: center; gap: 0.75rem; }
    .header-logo { height: 45px; width: 45px; border-radius: 8px; object-fit: cover; cursor: pointer; }
    .header-title { font-weight: 800; font-size: 1.25rem; color: var(--primary); letter-spacing: 0.05em; }
    
    .container { width: 100%; max-width: 1400px; margin: 0 auto; padding: 1rem; }
    .card { background: var(--card-bg); border-radius: 1rem; padding: 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 1rem; border: 1px solid #e2e8f0; }
    h2 { margin-top: 0; margin-bottom: 1rem; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem; color: var(--primary); }
    
    .grid { display: grid; grid-template-columns: 1fr; gap: 1rem; }
    @media (min-width: 1024px) { .grid { grid-template-columns: 400px 1fr; } }
    
    .btn { padding: 0.6rem 1rem; border: none; border-radius: 0.5rem; cursor: pointer; font-weight: 600; transition: 0.2s; display: inline-flex; align-items: center; justify-content: center; gap: 0.4rem; font-size: 0.9rem; }
    .btn-primary { background: var(--primary); color: white; }
    .btn-secondary { background: var(--secondary); color: white; }
    .btn-danger { background: var(--danger); color: white; }
    .btn-warning { background: var(--warning); color: white; }
    .btn-info { background: var(--info); color: white; }
    
    .mode-selector { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem; margin-bottom: 1rem; }
    .mode-btn { border: 2px solid #e0f2fe; background: white; padding: 0.8rem; border-radius: 0.75rem; text-align: center; cursor: pointer; transition: 0.2s; font-weight: 600; font-size: 0.85rem; }
    .mode-btn.active { border-color: var(--primary); background: #f0f9ff; color: var(--primary); box-shadow: 0 0 0 2px rgba(2, 132, 199, 0.1); }
    
    .control-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; }
    .btn-ctrl { aspect-ratio: 1; font-size: 1.2rem; border: 1px solid #e0f2fe; background: #fff; color: var(--primary); }
    .btn-ctrl:active { background: #f0f9ff; }
    .btn-ctrl.btn-danger { background: var(--danger); color: white; }
    
    .data-row { display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #f1f5f9; font-size: 0.9rem; }
    #map { height: 600px; width: 100%; border-radius: 1rem; border: 2px solid #e0f2fe; }
    
    input, select { width: 100%; padding: 0.75rem; border: 1px solid #cbd5e1; border-radius: 0.5rem; margin-bottom: 0.5rem; font-size: 0.95rem; }
    
    .badge-mode { padding: 0.2rem 0.6rem; border-radius: 2rem; font-size: 0.7rem; font-weight: 800; color: white; }
    .mode-manual { background: var(--text-muted); }
    .mode-sampling { background: var(--info); }
    .mode-cruise { background: var(--secondary); }
    .mode-return { background: var(--warning); }
    .mode-test { background: var(--danger); }

    .profile-avatar { width: 100px; height: 100px; border-radius: 50%; object-fit: cover; border: 4px solid var(--primary); margin-bottom: 1rem; }
    .friend-card { display: flex; align-items: center; gap: 1rem; padding: 0.75rem; border-bottom: 1px solid #f1f5f9; }
    .friend-avatar { width: 40px; height: 40px; border-radius: 50%; object-fit: cover; cursor: pointer; }
</style>
"""

HEAD_CONTENT = """
<meta charset='UTF-8'>
<meta name='viewport' content='width=device-width, initial-scale=1.0'>
<link rel="icon" type="image/png" href="/logo.png">
"""

# ==========================
# 路由邏輯
# ==========================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u, p = request.form.get("username"), request.form.get("password")
        users = load_json(USERS_FILE)
        user = next((x for x in users if x["username"] == u and x["password"] == p), None)
        if user:
            session.clear()
            session.permanent = True
            session.update({
                "username": u, 
                "role": user["role"], 
                "authorized_boats": user.get("owned_boats", [])
            })
            return redirect(url_for("index"))
        return "帳號或密碼錯誤", 401
    return render_template_string("""
<!DOCTYPE html><html><head>{{ head|safe }}{{ style|safe }}<title>登入 - 睿洋智慧水質網</title></head>
<body><div class='container'><div class='card' style='max-width:400px; margin: 5rem auto; text-align:center;'>
<img src="/logo.png" style="width:160px; margin-bottom:1.5rem; border-radius:20px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);">
<h2 style="justify-content:center; font-size: 1.5rem; margin-bottom: 1.5rem;">🔐 登入系統</h2>
<form action='/login' method='post'><input type='text' name='username' placeholder='帳號' required autofocus>
<input type='password' name='password' placeholder='密碼' required><button type='submit' class='btn btn-primary' style='width:100%; padding: 0.8rem;'>立即登入</button></form>
<p style='text-align:center; margin-top:1.5rem;'><a href='/register' style="color: var(--primary); text-decoration: none; font-weight: 600;">註冊帳號</a></p></div></div></body></html>
""", head=HEAD_CONTENT, style=COMMON_STYLE)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u, p, r = request.form.get("username"), request.form.get("password"), request.form.get("role")
        users = load_json(USERS_FILE)
        if any(x["username"] == u for x in users): return "帳號已存在", 400
        new_user = {
            "username": u, 
            "password": p, 
            "role": r,
            "avatar": "/uploads/avatars/default.png",
            "balance": 0.0,
            "owned_boats": [],
            "email": "",
            "friends": []
        }
        users.append(new_user)
        save_json(USERS_FILE, users)
        return redirect(url_for("login"))
    return render_template_string("""
<!DOCTYPE html><html><head>{{ head|safe }}{{ style|safe }}<title>註冊 - 睿洋智慧水質網</title></head>
<body><div class='container'><div class='card' style='max-width:400px; margin: 5rem auto;'>
<h2 style="justify-content:center;">📝 註冊帳號</h2>
<form action='/register' method='post'><input type='text' name='username' placeholder='帳號' required>
<input type='password' name='password' placeholder='密碼' required><select name='role'><option value='guest'>訪客</option><option value='user'>使用者</option></select>
<button type='submit' class='btn btn-primary' style='width:100%'>確認註冊</button></form>
<p style='text-align:center; margin-top:1rem;'><a href='/login'>回登入頁</a></p></div></div></body></html>
""", head=HEAD_CONTENT, style=COMMON_STYLE)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/profile/<username>")
@login_required
def profile(username):
    user = get_user(username)
    if not user: return "找不到該使用者", 404
    
    # Guest restriction: Guests cannot have profile data visible to others, 
    # and they themselves don't have personal data besides username/role.
    if user['role'] == 'guest':
        if session['username'] != username and session['role'] != 'admin':
            return "訪客資料不公開", 403
        # If it's the guest themselves, they only see limited info as per requirement "訪客沒有辦法有資料"
        is_own = (session['username'] == username)
        return render_template_string("""
<!DOCTYPE html><html><head>{{ head|safe }}{{ style|safe }}<title>{{ username }} 的資料 - 睿洋智慧水質網</title></head>
<body><header><div class="header-branding" onclick="location.href='/'"><img src="/logo.png" class="header-logo"><div class="header-title">睿洋智慧水質網</div></div>
<div><a href="/" style="color:var(--text-main); text-decoration:none; font-weight:700;">← 返回</a></div></header>
<div class="container"><div class="card" style="text-align:center;">
<img src="/logo.png" class="profile-avatar">
<h2 style="justify-content:center;">{{ username }} (訪客)</h2>
<p>訪客帳號不提供個人資料與社交功能。</p>
</div></div></body></html>
""", head=HEAD_CONTENT, style=COMMON_STYLE, username=username)
    
    is_own = (session['username'] == username)
    can_edit = is_own # user.role != 'guest' is already handled by above check
    
    friends_data = []
    users = load_json(USERS_FILE)
    for f_name in user.get('friends', []):
        f_user = next((u for u in users if u['username'] == f_name), None)
        if f_user:
            friends_data.append({
                "username": f_name,
                "avatar": f_user.get('avatar', '/uploads/avatars/default.png')
            })

    return render_template_string("""
<!DOCTYPE html><html><head>{{ head|safe }}{{ style|safe }}<title>{{ username }} 的資料 - 睿洋智慧水質網</title></head>
<body><header><div class="header-branding" onclick="location.href='/'"><img src="/logo.png" class="header-logo"><div class="header-title">睿洋智慧水質網</div></div>
<div><a href="/" style="color:var(--text-main); text-decoration:none; font-weight:700;">← 返回</a></div></header>
<div class="container"><div class="card" style="text-align:center;">
<img src="{{ user.avatar or '/uploads/avatars/default.png' }}" class="profile-avatar">
<h2 style="justify-content:center;">{{ username }} ({{ '管理員' if user.role == 'admin' else '使用者' }})</h2>
<div style="text-align:left; max-width:500px; margin: 0 auto;">
<div class="data-row"><span>帳號</span><span>{{ user.username }}</span></div>
<div class="data-row"><span>信箱</span><span>{{ user.email or '未填寫' }}</span></div>
<div class="data-row"><span>餘額</span><span>${{ user.balance or 0 }}</span></div>
<div class="data-row"><span>可使用船隻</span><span>{{ user.owned_boats|length }} 艘</span></div>
{% if is_own %}
<div style="margin-top:1.5rem; display:flex; gap:0.5rem;">
<a href="/profile/edit" class="btn btn-primary" style="flex:1;">編輯資料</a>
<a href="/profile/change_password" class="btn btn-warning" style="flex:1;">更改密碼</a>
</div>
{% endif %}
</div></div>

<div class="card"><h2>👥 好友列表 ({{ friends_data|length }})</h2>
{% if is_own %}
<form action="/api/friend/add" method="post" style="display:flex; gap:0.5rem; margin-bottom:1rem;">
<input type="text" name="friend_id" placeholder="輸入好友帳號 (ID)" required style="margin-bottom:0;">
<button type="submit" class="btn btn-primary">新增好友</button></form>
{% endif %}
<div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap:1rem;">
{% for friend in friends_data %}
<div class="card" style="display:flex; align-items:center; gap:1rem; padding:0.75rem; margin-bottom:0;">
<img src="{{ friend.avatar }}" class="friend-avatar" onclick="location.href='/profile/{{ friend.username }}'">
<div style="flex:1;"><strong>{{ friend.username }}</strong></div>
{% if is_own %}
<form action="/api/friend/remove" method="post" style="margin:0;">
<input type="hidden" name="friend_id" value="{{ friend.username }}">
<button type="submit" class="btn btn-danger" style="padding:0.2rem 0.5rem; font-size:0.7rem;">刪除</button></form>
{% endif %}
</div>
{% endfor %}
</div></div>
</div></body></html>
""", head=HEAD_CONTENT, style=COMMON_STYLE, user=user, username=username, is_own=is_own, friends_data=friends_data)

@app.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    if session['role'] == 'guest': return "訪客無法擁有資料", 403
    user = get_user(session['username'])
    if request.method == "POST":
        email = request.form.get("email")
        avatar = request.files.get("avatar")
        users = load_json(USERS_FILE)
        for u in users:
            if u['username'] == session['username']:
                u['email'] = email
                if avatar and avatar.filename:
                    ext = os.path.splitext(avatar.filename)[1]
                    filename = f"{session['username']}{ext}"
                    avatar.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    u['avatar'] = f"/uploads/avatars/{filename}"
                break
        save_json(USERS_FILE, users)
        return redirect(url_for("profile", username=session['username']))
    
    return render_template_string("""
<!DOCTYPE html><html><head>{{ head|safe }}{{ style|safe }}<title>編輯資料 - 睿洋智慧水質網</title></head>
<body><header><div class="header-branding" onclick="location.href='/'"><img src="/logo.png" class="header-logo"><div class="header-title">睿洋智慧水質網</div></div>
<div><a href="/profile/{{ session['username'] }}" style="color:var(--text-main); text-decoration:none; font-weight:700;">← 取消</a></div></header>
<div class="container"><div class="card" style="max-width:500px; margin: 2rem auto;">
<h2>📝 編輯個人資料</h2>
<form method="post" enctype="multipart/form-data">
<label>更換頭像</label><input type="file" name="avatar" accept="image/*">
<label>電子信箱</label><input type="email" name="email" value="{{ user.email or '' }}" placeholder="您的信箱">
<button type="submit" class="btn btn-primary" style="width:100%">儲存變更</button></form></div></div></body></html>
""", head=HEAD_CONTENT, style=COMMON_STYLE, user=user)

@app.route("/profile/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if session['role'] == 'guest': return "訪客無法擁有資料", 403
    if request.method == "POST":
        old_p, new_p = request.form.get("old_password"), request.form.get("new_password")
        users = load_json(USERS_FILE)
        for u in users:
            if u['username'] == session['username']:
                if u['password'] == old_p:
                    u['password'] = new_p
                    save_json(USERS_FILE, users)
                    return redirect(url_for("profile", username=session['username']))
                return "舊密碼錯誤", 400
        return "找不到使用者", 404
    
    return render_template_string("""
<!DOCTYPE html><html><head>{{ head|safe }}{{ style|safe }}<title>更改密碼 - 睿洋智慧水質網</title></head>
<body><header><div class="header-branding" onclick="location.href='/'"><img src="/logo.png" class="header-logo"><div class="header-title">睿洋智慧水質網</div></div>
<div><a href="/profile/{{ session['username'] }}" style="color:var(--text-main); text-decoration:none; font-weight:700;">← 取消</a></div></header>
<div class="container"><div class="card" style="max-width:500px; margin: 2rem auto;">
<h2>🔐 更改密碼</h2>
<form method="post"><input type="password" name="old_password" placeholder="輸入舊密碼" required>
<input type="password" name="new_password" placeholder="輸入新密碼" required>
<button type="submit" class="btn btn-primary" style="width:100%">確認更改</button></form></div></div></body></html>
""", head=HEAD_CONTENT, style=COMMON_STYLE)

@app.route("/api/friend/add", methods=["POST"])
@login_required
def add_friend():
    if session['role'] == 'guest': return "訪客無法加好友", 403
    friend_id = request.form.get("friend_id")
    if friend_id == session['username']: return "不能加自己為好友", 400
    
    users = load_json(USERS_FILE)
    friend_exists = any(u['username'] == friend_id for u in users)
    if not friend_exists: return "找不到該玩家", 404
    
    for u in users:
        if u['username'] == session['username']:
            if 'friends' not in u: u['friends'] = []
            if friend_id not in u['friends']:
                u['friends'].append(friend_id)
                save_json(USERS_FILE, users)
            break
    return redirect(url_for("profile", username=session['username']))

@app.route("/api/friend/remove", methods=["POST"])
@login_required
def remove_friend():
    friend_id = request.form.get("friend_id")
    users = load_json(USERS_FILE)
    for u in users:
        if u['username'] == session['username']:
            if 'friends' in u and friend_id in u['friends']:
                u['friends'].remove(friend_id)
                save_json(USERS_FILE, users)
            break
    return redirect(url_for("profile", username=session['username']))

@app.route("/")
@login_required
def index():
    boats = load_json(BOATS_FILE)
    user = get_user(session['username'])
    return render_template_string("""
<!DOCTYPE html><html><head>{{ head|safe }}{{ style|safe }}<title>船隻列表 - 睿洋智慧水質網</title></head>
<body><header><div class="header-branding" onclick="location.href='/'"><img src="/logo.png" class="header-logo"><div class="header-title">睿洋智慧水質網</div></div>
<div style="display:flex; align-items:center; gap:0.5rem;">
<img src="{{ user.avatar or '/uploads/avatars/default.png' }}" class="header-logo" style="border-radius:50%; width:35px; height:35px;" onclick="location.href='/profile/{{ session['username'] }}'">
<span onclick="location.href='/profile/{{ session['username'] }}'" style="cursor:pointer; font-weight:600;">{{ session['username'] }}</span> 
<a href="/logout" class="btn btn-danger" style="padding:0.3rem 0.6rem; font-size:0.75rem;">登出</a></div></header>
<div class="container"><div class="card"><h2>🛰️ 搜尋到以下設備</h2>
{% if boats %}{% for boat in boats %}
<div style="display:flex; justify-content:space-between; align-items:center; padding:1rem; border-bottom:1px solid #f1f5f9;">
<div><strong>{{ boat.name }}</strong><br><small style="color:var(--text-muted)">{{ boat.ip }}</small></div>
<a href="/control/{{ boat.ip }}" class="btn btn-primary">進入控制中心</a></div>
{% endfor %}{% else %}<p style="text-align:center; padding:2rem; color:var(--text-muted);">目前沒有連接中的船隻</p>{% endif %}
{% if session['role'] == 'admin' %}<div style="margin-top:1.5rem; text-align:right;"><a href="/admin" class="btn btn-warning">⚙️ 管理員後台</a></div>{% endif %}
</div></div></body></html>
""", head=HEAD_CONTENT, style=COMMON_STYLE, boats=boats, user=user)

@app.route("/control/<ip>", methods=["GET", "POST"])
@login_required
def control_boat(ip):
    boats = load_json(BOATS_FILE)
    boat = next((b for b in boats if b["ip"] == ip), None)
    if not boat: return "找不到船隻", 404
    
    if not check_boat_auth(ip):
        if request.method == "POST":
            if request.form.get("boat_password") == boat["password"]:
                auth_list = session.get("authorized_boats", [])
                auth_list.append(ip)
                session["authorized_boats"] = auth_list
                session.modified = True
                return redirect(url_for("control_boat", ip=ip))
            return "密碼錯誤", 403
        return render_template_string("""
<!DOCTYPE html><html><head>{{ head|safe }}{{ style|safe }}<title>驗證 - 睿洋智慧水質網</title></head>
<body><div class='container'><div class='card' style='max-width:400px; margin: 4rem auto;'><h2>🔐 存取驗證</h2>
<p>請輸入 <strong>{{ name }}</strong> 的控制密碼</p>
<form method='post'><input type='password' name='boat_password' required autofocus><button type='submit' class='btn btn-primary' style='width:100%'>驗證並連線</button></form></div></div></body></html>
""", head=HEAD_CONTENT, style=COMMON_STYLE, name=boat["name"])

    return render_template_string("""
<!DOCTYPE html><html><head>{{ head|safe }}{{ style|safe }}<title>{{ name }} - 控制中心</title><link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" /></head>
<body><header><div class="header-branding" onclick="location.href='/'"><img src="/logo.png" class="header-logo"><div class="header-title">睿洋智慧水質網</div></div>
<div><a href="/" style="color:var(--text-main); text-decoration:none; font-weight:700;">← 返回</a></div></header>
<div class="container">
    <div style="margin-bottom:1rem; display:flex; align-items:center; gap:0.5rem;">
        <span style="font-weight:700; font-size:1.1rem;">{{ name }}</span>
        <span id="current_mode_badge" class="badge-mode mode-manual">手動模式</span>
    </div>
    <div class="grid"><div class="panel-left"><div class="card"><h2>⚙️ 智慧模式切換</h2><div class="mode-selector">
<div class="mode-btn active" id="btn_m_manual" onclick="setMode('manual')">手動操控</div><div class="mode-btn" id="btn_m_test" onclick="setMode('test')">系統測試</div>
<div class="mode-btn" id="btn_m_sampling" onclick="setMode('sampling')">定點採水</div><div class="mode-btn" id="btn_m_cruise" onclick="setMode('cruise')">路徑巡航</div>
<div class="mode-btn" id="btn_m_return" onclick="setMode('return')">自動返航</div></div>
<div id="mode_instruction" style="font-size:0.85rem; color:var(--text-muted); background:#f0f9ff; padding:0.75rem; border-radius:0.5rem; margin-bottom:1rem;">手動模式：可進行即時遙控盤操作。</div>
<div id="mode_actions" style="display:none; margin-bottom:1rem;">
<button class="btn btn-info" id="btn_set_target" onclick="startPickingTarget()" style="width:100%">在地圖上選取目標</button>
<button class="btn btn-danger" id="btn_clear_path" onclick="clearCruisePath()" style="width:100%; display:none; margin-top:0.5rem; font-size:0.8rem;">清除巡航路線</button></div></div>
{% if role in ['user', 'admin'] %}
<div class="card" id="remote_control"><h2>🎮 即時遙控盤</h2><div class="control-grid">
<div></div><button class="btn btn-ctrl" onclick="sendMove('forward')">▲</button><div></div>
<button class="btn btn-ctrl" onclick="sendMove('left')">◀</button><button class="btn btn-ctrl btn-danger" onclick="sendMove('stop')">■</button><button class="btn btn-ctrl" onclick="sendMove('right')">▶</button>
<button class="btn btn-ctrl" onclick="sendMove('left_rotate')">⟲</button><button class="btn btn-ctrl" onclick="sendMove('backward')">▼</button><button class="btn btn-ctrl" onclick="sendMove('right_rotate')">⟳</button></div>
<button id="pumpBtn" class="btn btn-secondary" style="width:100%; margin-top:1rem; padding:1.2rem; font-size:1.1rem; border-radius:1rem;" onmousedown="setPump(true)" onmouseup="setPump(false)" ontouchstart="t_start(event)" ontouchend="t_end(event)">🌊 點擊採水 (按住)</button></div>
{% endif %}
<div class="card"><h2>📊 傳感器與 GPS 數據</h2><div class="data-row"><span class="data-label">座標位置</span><span class="data-value" id="pos_text">--</span></div><div class="data-row"><span class="data-label">GPS 鎖定</span><span id="gps_status">--</span></div>
<div class="data-row"><span class="data-label">移動指令</span><span id="move_status">--</span></div><div class="data-row"><span class="data-label">歷史紀錄點</span><span id="track_count">0 點</span></div>
{% if role == 'admin' %}<button onclick="clearHistory()" class="btn btn-danger" style="width:100%; margin-top:1rem; font-size:0.8rem; background:none; color:var(--danger); border:1px solid var(--danger);">清除軌跡檔案</button>{% endif %}
</div></div><div class="card" style="padding:0; overflow:hidden;"><div id="map"></div></div></div></div>
<script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
<script>
    const BOAT_IP = "{{ ip }}";
    let currentMode = 'manual';
    let isPicking = false;
    let map = L.map('map', { zoomControl: false }).setView([25.033, 121.565], 16);
    L.control.zoom({ position: 'bottomright' }).addTo(map);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
    let marker = null; let targetMarker = null;
    let polyline = L.polyline([], {color: '#0284c7', weight: 4, opacity: 0.6}).addTo(map);
    let cruisePolyline = L.polyline([], {color: '#10b981', weight: 3, dashArray: '5, 10'}).addTo(map);
    let cruiseMarkers = [];

    function t_start(e) { e.preventDefault(); setPump(true); }
    function t_end(e) { e.preventDefault(); setPump(false); }

    map.on('click', function(e) {
        if(!isPicking) return;
        if(currentMode === 'sampling') {
            setTargetPos(e.latlng.lat, e.latlng.lng);
            isPicking = false;
            document.getElementById('btn_set_target').innerText = '更換採水點';
        } else if(currentMode === 'cruise') {
            addToCruisePath(e.latlng.lat, e.latlng.lng);
        }
    });

    function setMode(mode) {
        currentMode = mode; isPicking = false;
        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
        document.getElementById('btn_m_' + mode).classList.add('active');
        let badge = document.getElementById('current_mode_badge');
        badge.className = 'badge-mode mode-' + mode;
        let modeNames = {'manual':'手動模式', 'test':'測試模式', 'sampling':'定點模式', 'cruise':'巡航模式', 'return':'返航模式'};
        badge.innerText = modeNames[mode];
        document.getElementById('mode_actions').style.display = (mode === 'sampling' || mode === 'cruise') ? 'block' : 'none';
        document.getElementById('btn_clear_path').style.display = (mode === 'cruise') ? 'block' : 'none';
        let instruct = document.getElementById('mode_instruction');
        if(mode === 'manual') instruct.innerText = '手動模式：可進行即時遙控。';
        if(mode === 'test') instruct.innerText = '測試模式：系統自動進行硬體校準測試。';
        if(mode === 'sampling') instruct.innerText = '定點模式：點選地圖位置後，船隻將自動前往並採水。';
        if(mode === 'cruise') instruct.innerText = '巡航模式：依照規劃路徑進行水質檢測巡邏。';
        if(mode === 'return') instruct.innerText = '返航模式：任務結束，船隻將自動駛回出發點。';
        fetch(`/api/mode/${BOAT_IP}`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({mode: mode}) });
    }

    function startPickingTarget() {
        isPicking = !isPicking;
        let btn = document.getElementById('btn_set_target');
        btn.innerText = isPicking ? '請在地圖上點擊位置...' : (currentMode === 'cruise' ? '新增巡航點' : '選取目標點');
    }

    function setTargetPos(lat, lng) {
        if(targetMarker) map.removeLayer(targetMarker);
        targetMarker = L.marker([lat, lng]).addTo(map);
        fetch(`/api/target/${BOAT_IP}`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lat: lat, lng: lng}) });
    }

    function addToCruisePath(lat, lng) {
        let cm = L.circleMarker([lat, lng], {radius: 5, color: '#10b981'}).addTo(map);
        cruiseMarkers.push(cm);
        fetch(`/api/cruise_add/${BOAT_IP}`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lat: lat, lng: lng}) })
        .then(r => r.json()).then(data => { cruisePolyline.setLatLngs(data.path.map(p => [p.lat, p.lng])); });
    }

    function clearCruisePath() {
        cruiseMarkers.forEach(m => map.removeLayer(m)); cruiseMarkers = [];
        cruisePolyline.setLatLngs([]);
        fetch(`/api/cruise_clear/${BOAT_IP}`, { method: 'POST' });
    }

    function clearHistory() {
        if(confirm("確定要清除所有軌跡資料嗎？")) { fetch(`/api/clear_history/${BOAT_IP}`, { method: 'POST' }).then(() => window.location.reload()); }
    }

    function sendMove(cmd) { fetch(`/api/move/${BOAT_IP}`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({move: cmd}) }); }
    function setPump(state) { fetch(`/api/pump/${BOAT_IP}`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({pump: state}) }); }

    function update() {
        fetch(`/api/data/${BOAT_IP}`).then(r => r.json()).then(data => {
            document.getElementById('move_status').innerText = data.move.toUpperCase();
            document.getElementById('gps_status').innerText = data.gps_valid ? '✅ 已鎖定' : '❌ 搜尋中';
            document.getElementById('pos_text').innerText = data.lat ? `${data.lat.toFixed(5)}, ${data.lng.toFixed(5)}` : '--';
            document.getElementById('track_count').innerText = data.track.length + ' 點';
            if(data.lat && data.lng) {
                let pos = [data.lat, data.lng];
                if(!marker) { marker = L.marker(pos).addTo(map); map.setView(pos, 18); }
                else marker.setLatLng(pos);
                polyline.setLatLngs(data.track.map(p => [p.lat, p.lng]));
            }
        });
    }
    setInterval(update, 1000);
</script></body></html>
""", head=HEAD_CONTENT, style=COMMON_STYLE, name=boat["name"], ip=ip, role=session["role"])

@app.route("/admin")
@login_required
@role_required(["admin"])
def admin():
    users = load_json(USERS_FILE)
    boats = load_json(BOATS_FILE)
    return render_template_string("""
<!DOCTYPE html><html><head>{{ head|safe }}{{ style|safe }}<title>後台管理 - 睿洋智慧水質網</title></head>
<body><header><div class="header-branding" onclick="location.href='/'"><img src="/logo.png" class="header-logo"><div class="header-title">系統管理員後台</div></div>
<div><a href="/" style="color:var(--text-main); text-decoration:none; font-weight:700;">← 返回</a></div></header>
<div class="container">
<div class="card" style="overflow-x: auto;"><h2>👥 玩家帳號管理</h2>
<table style="width:100%; border-collapse:collapse; min-width:600px;">
<tr style="text-align:left; color:var(--text-muted); border-bottom:2px solid #e0f2fe;"><th style="padding:1rem 0.5rem;">玩家</th><th>角色</th><th>餘額/船隻</th><th style="text-align:right;">操作</th></tr>
{% for u in users %}
<tr style="border-bottom: 1px solid #f1f5f9;">
<td style="padding:0.5rem; display:flex; align-items:center; gap:0.5rem;">
<img src="{{ u.avatar or '/uploads/avatars/default.png' }}" style="width:30px; height:30px; border-radius:50%; cursor:pointer;" onclick="location.href='/profile/{{ u.username }}'">
<span onclick="location.href='/profile/{{ u.username }}'" style="cursor:pointer; font-weight:600;">{{ u.username }}</span></td>
<td>{{ u.role }}</td>
<td>
    <div style="margin-bottom:0.5rem;">
    <form action="/admin/update_balance" method="post" style="display:flex; margin:0; align-items:center; gap:0.2rem;">
    <input type="hidden" name="username" value="{{ u.username }}">
    <input type="number" name="balance" value="{{ u.balance or 0 }}" style="width:80px; margin-bottom:0; padding:0.3rem;">
    <button type="submit" class="btn btn-primary" style="padding:0.3rem; font-size:0.7rem;">更新餘額</button></form>
    </div>
    <form action="/admin/update_boats" method="post" style="margin:0;">
    <input type="hidden" name="username" value="{{ u.username }}">
    <select name="boats" multiple style="font-size:0.7rem; height:60px; padding:0.2rem;">
        {% for boat in boats %}
        <option value="{{ boat.ip }}" {% if boat.ip in u.get('owned_boats', []) %}selected{% endif %}>{{ boat.name }}</option>
        {% endfor %}
    </select>
    <button type="submit" class="btn btn-secondary" style="padding:0.2rem; font-size:0.6rem; width:100%; margin-top:0.2rem;">更新船隻權限</button></form></td>
<td style="text-align:right;">
{% if u.username != session['username'] %}
<form action="/admin/del_user" method="post" style="display:inline;"><input type="hidden" name="username" value="{{ u.username }}"><button type="submit" class="btn btn-danger" style="padding:0.3rem 0.6rem; font-size:0.75rem;">刪除玩家</button></form>
{% endif %}</td></tr>
{% endfor %}</table></div>

<div class="card"><h2>➕ 手動新增設備</h2>
<form action="/admin/add_boat" method="post" style="display:grid; grid-template-columns: 1fr 1fr 1fr auto; gap:0.5rem; align-items:end;">
<div><label style="font-size:0.7rem; color:var(--text-muted)">設備名稱</label><input type="text" name="name" required placeholder="名稱" style="margin:0;"></div>
<div><label style="font-size:0.7rem; color:var(--text-muted)">IP 地址</label><input type="text" name="ip" required placeholder="IP" style="margin:0;"></div>
<div><label style="font-size:0.7rem; color:var(--text-muted)">控制密碼</label><input type="password" name="password" required placeholder="密碼" style="margin:0;"></div>
<button type="submit" class="btn btn-primary">確認新增</button></form></div>

<div class="card" style="overflow-x: auto;"><h2>📋 現有設備列表 (含自動偵測)</h2><table style="width:100%; border-collapse:collapse; min-width:600px;">
<tr style="text-align:left; color:var(--text-muted); border-bottom:2px solid #e0f2fe;"><th style="padding:1rem 0.5rem;">設備資訊</th><th>IP 地址</th><th>密碼管理</th><th style="text-align:right;">操作</th></tr>
{% for boat in boats %}
<tr style="border-bottom: 1px solid #f1f5f9;">
<form action="/admin/update_boat" method="post">
<input type="hidden" name="old_ip" value="{{ boat.ip }}">
<td style="padding:1rem 0.5rem;"><input type="text" name="name" value="{{ boat.name }}" style="margin:0; padding:0.4rem; font-size:0.85rem;"></td>
<td><input type="text" name="new_ip" value="{{ boat.ip }}" style="margin:0; padding:0.4rem; font-size:0.85rem; width:130px; font-family:monospace;"></td>
<td><input type="text" name="password" value="{{ boat.password }}" style="margin:0; padding:0.4rem; font-size:0.85rem; width:120px;"></td>
<td style="text-align:right; display:flex; gap:0.3rem; justify-content:flex-end; padding-top:1.2rem;">
<button type="submit" class="btn btn-primary" style="padding:0.3rem 0.6rem; font-size:0.75rem;">儲存</button>
</form>
<form action="/admin/del_boat" method="post" style="margin:0;"><input type="hidden" name="ip" value="{{ boat.ip }}"><button type="submit" class="btn btn-danger" style="padding:0.3rem 0.6rem; font-size:0.75rem;">刪除</button></form>
</td></tr>
{% endfor %}</table></div></div></body></html>
""", head=HEAD_CONTENT, style=COMMON_STYLE, boats=boats, users=users)

@app.route("/admin/update_balance", methods=["POST"])
@login_required
@role_required(["admin"])
def update_balance():
    u_name, bal = request.form.get("username"), request.form.get("balance")
    users = load_json(USERS_FILE)
    for u in users:
        if u['username'] == u_name:
            u['balance'] = float(bal)
            break
    save_json(USERS_FILE, users)
    return redirect(url_for("admin"))

@app.route("/admin/del_user", methods=["POST"])
@login_required
@role_required(["admin"])
def del_user():
    u_name = request.form.get("username")
    users = [u for u in load_json(USERS_FILE) if u['username'] != u_name]
    save_json(USERS_FILE, users)
    return redirect(url_for("admin"))

@app.route("/admin/update_boats", methods=["POST"])
@login_required
@role_required(["admin"])
def update_boats():
    u_name = request.form.get("username")
    selected_boats = request.form.getlist("boats")
    users = load_json(USERS_FILE)
    for u in users:
        if u['username'] == u_name:
            u['owned_boats'] = selected_boats
            break
    save_json(USERS_FILE, users)
    return redirect(url_for("admin"))

@app.route("/admin/add_boat", methods=["POST"])
@login_required
@role_required(["admin"])
def add_boat():
    name = request.form.get("name")
    ip = request.form.get("ip")
    password = request.form.get("password")
    if name and ip and password:
        boats = load_json(BOATS_FILE)
        if not any(b['ip'] == ip for b in boats):
            boats.append({"name": name, "ip": ip, "password": password})
            save_json(BOATS_FILE, boats)
    return redirect(url_for("admin"))

@app.route("/admin/update_boat", methods=["POST"])
@login_required
@role_required(["admin"])
def update_boat():
    old_ip = request.form.get("old_ip")
    new_ip = request.form.get("new_ip")
    name = request.form.get("name")
    pwd = request.form.get("password")
    
    boats = load_json(BOATS_FILE)
    for b in boats:
        if b['ip'] == old_ip:
            if name: b['name'] = name
            if pwd: b['password'] = pwd
            if new_ip: b['ip'] = new_ip
            break
    save_json(BOATS_FILE, boats)
    
    # Update active state if IP changed
    if old_ip != new_ip and old_ip in boat_states:
        boat_states[new_ip] = boat_states.pop(old_ip)
        
    return redirect(url_for("admin"))

@app.route("/admin/del_boat", methods=["POST"])
@login_required
@role_required(["admin"])
def del_boat():
    ip = request.form.get("ip")
    if ip:
        boats = load_json(BOATS_FILE)
        boats = [b for b in boats if b['ip'] != ip]
        save_json(BOATS_FILE, boats)
    return redirect(url_for("admin"))

@app.route("/api/mode/<ip>", methods=["POST"])
@login_required
def api_set_mode(ip):
    mode = request.json.get("mode", "manual")
    state = get_boat_state(ip)
    state["mode"] = mode
    return jsonify({"status": "ok", "mode": mode})

@app.route("/api/target/<ip>", methods=["POST"])
@login_required
def api_set_target(ip):
    lat, lng = request.json.get("lat"), request.json.get("lng")
    state = get_boat_state(ip)
    state["target_pos"] = {"lat": lat, "lng": lng}
    return jsonify({"status": "ok"})

@app.route("/api/cruise_add/<ip>", methods=["POST"])
@login_required
def api_cruise_add(ip):
    lat, lng = request.json.get("lat"), request.json.get("lng")
    state = get_boat_state(ip)
    state["cruise_path"].append({"lat": lat, "lng": lng})
    return jsonify({"status": "ok", "path": state["cruise_path"]})

@app.route("/api/cruise_clear/<ip>", methods=["POST"])
@login_required
def api_cruise_clear(ip):
    state = get_boat_state(ip)
    state["cruise_path"] = []
    return jsonify({"status": "ok"})

@app.route("/api/move/<ip>", methods=["POST"])
@login_required
def api_move(ip):
    get_boat_state(ip)["move"] = request.json.get("move", "stop")
    return jsonify({"status": "ok"})

@app.route("/api/pump/<ip>", methods=["POST"])
@login_required
def api_pump(ip):
    get_boat_state(ip)["pump"] = bool(request.json.get("pump", False))
    return jsonify({"status": "ok"})

@app.route("/api/data/<ip>", methods=["GET"])
@login_required
def api_data(ip):
    return jsonify(get_boat_state(ip))

@app.route("/api/clear_history/<ip>", methods=["POST"])
@login_required
@role_required(["admin"])
def api_clear_history(ip):
    filename = get_history_file(ip)
    if os.path.exists(filename): os.remove(filename)
    if ip in boat_states: boat_states[ip]["track"] = []
    return jsonify({"status": "ok"})

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

@app.route("/state", methods=["GET"])
def pico_state():
    boat_ip = get_client_ip()
    ensure_boat_exists(boat_ip)
    state = get_boat_state(boat_ip)
    return jsonify({
        "move": state.get("move", "stop"),
        "pump": state.get("pump", False)
    })

@app.route("/upload", methods=["POST"])
def pico_upload():
    boat_ip = get_client_ip()
    ensure_boat_exists(boat_ip)
    data = request.json
    state = get_boat_state(boat_ip)
    
    # 更新 GPS 與其他狀態
    lat, lng = data.get("lat"), data.get("lng")
    gps_valid = data.get("gps_valid", False)
    state.update({"lat": lat, "lng": lng, "gps_valid": gps_valid, "time": datetime.now().strftime("%H:%M:%S")})
    
    if gps_valid and lat and not state["start_pos"]: state["start_pos"] = {"lat": lat, "lng": lng}
    if gps_valid and lat and lat != 0:
        point = {"lat": lat, "lng": lng}
        if not state["track"] or (state["track"][-1]["lat"] != lat):
            state["track"].append(point)
            
    return jsonify({
        "status": "ok",
        "boat_ip": boat_ip
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
