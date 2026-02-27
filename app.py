"""
KVR Database Server
A simple Flask REST API for managing KingdomVR user accounts.
"""

import os
import functools
from flask import Flask, request, jsonify, abort
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
# Admin app (serves a small web UI on port 1212)
from flask import render_template_string
import threading
admin_app = Flask("admin")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
app.config["DATABASE"] = os.environ.get("DATABASE", "kvr_database.db")
# Trim surrounding whitespace to avoid accidental trailing/leading spaces in .env
API_KEY = os.environ.get("API_KEY", "").strip()

# ---------------------------------------------------------------------------
# Database helpers (sqlite3 – no ORM needed, easy to extend)
# ---------------------------------------------------------------------------
import sqlite3


def get_db():
    """Open a new database connection for the current request."""
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    # Enable foreign-key enforcement
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_user_columns(conn=None):
    """Return the list of column names for the `users` table."""
    close = conn is None
    if conn is None:
        conn = get_db()
    try:
        rows = conn.execute("PRAGMA table_info(users)").fetchall()
        cols = [r[1] for r in rows]
        return cols
    finally:
        if close:
            conn.close()


def init_db(conn=None):
    """Create the users table if it does not already exist."""
    close = conn is None
    if conn is None:
        conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT    NOT NULL UNIQUE,
            pin         TEXT    NOT NULL UNIQUE,
            kvrcoin     REAL    NOT NULL DEFAULT 0,
            chess_points REAL   NOT NULL DEFAULT 0
        )
        """
    )
    conn.commit()
    # Create admin table to store password hash (single-row table)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY,
            password_hash TEXT
        )
        """
    )
    conn.commit()
    if close:
        conn.close()


def get_admin_hash(conn=None):
    close = conn is None
    if conn is None:
        conn = get_db()
    try:
        row = conn.execute("SELECT password_hash FROM admin WHERE id = 1").fetchone()
        return row[0] if row is not None else None
    finally:
        if close:
            conn.close()


def set_admin_hash(password_hash, conn=None):
    close = conn is None
    if conn is None:
        conn = get_db()
    try:
        # Insert or replace single-row (id=1)
        conn.execute("INSERT OR REPLACE INTO admin (id, password_hash) VALUES (1, ?)", (password_hash,))
        conn.commit()
    finally:
        if close:
            conn.close()


def user_to_dict(row):
    """Convert a sqlite3.Row to a plain dict (skipping internal 'id')."""
    # Include all columns returned by the query except the internal `id`.
    # This makes the API forward-compatible with new columns added to the
    # `users` table (e.g. via `scripts/add_field.py`).
    result = {}
    for key in row.keys():
        if key == "id":
            continue
        result[key] = row[key]
    return result


# ---------------------------------------------------------------------------
# Authentication decorator
# ---------------------------------------------------------------------------
def require_api_key(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not API_KEY:
            abort(500, description="API_KEY is not configured on the server.")
        provided = request.headers.get("X-API-Key", "")
        if provided != API_KEY:
            abort(401, description="Invalid or missing API key.")
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/users", methods=["POST"])
@require_api_key
def create_user():
    """Create a new user."""
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    pin = data.get("pin")

    if not username or pin is None:
        abort(400, description="'username' and 'pin' are required.")

    kvrcoin = data.get("kvrcoin", 0)
    chess_points = data.get("chess_points", 0)

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, pin, kvrcoin, chess_points) VALUES (?, ?, ?, ?)",
            (username, pin, kvrcoin, chess_points),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return jsonify(user_to_dict(row)), 201
    except sqlite3.IntegrityError as exc:
        abort(409, description=f"Conflict: {exc}")
    finally:
        conn.close()


@app.route("/users/<username>", methods=["GET"])
@require_api_key
def get_user_by_username(username):
    """Return a user looked up by username."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        abort(404, description=f"No user with username '{username}'.")
    return jsonify(user_to_dict(row))


@app.route("/users/pin/<pin>", methods=["GET"])
@require_api_key
def get_user_by_pin(pin):
    """Return a user looked up by PIN (PINs are stored as TEXT)."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE pin = ?", (pin,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        abort(404, description=f"No user with pin '{pin}'.")
    return jsonify(user_to_dict(row))


@app.route("/leaderboard/chess", methods=["GET"])
@require_api_key
def chess_leaderboard():
    """Return users and their `chess_points` for a leaderboard.

    Query params:
    - `limit` (int, optional): maximum number of rows to return
    - `order` (asc|desc, default desc): sort order by `chess_points`
    """
    limit = request.args.get("limit", type=int)
    order = (request.args.get("order", "desc") or "desc").lower()
    if order not in ("asc", "desc"):
        order = "desc"

    conn = get_db()
    try:
        base_sql = f"SELECT username, chess_points FROM users ORDER BY chess_points {order.upper()}"
        if limit:
            rows = conn.execute(base_sql + " LIMIT ?", (limit,)).fetchall()
        else:
            rows = conn.execute(base_sql).fetchall()
    finally:
        conn.close()

    result = [
        {"username": r["username"], "chess_points": r["chess_points"]}
        for r in rows
    ]
    return jsonify(result)


@app.route("/users/<username>", methods=["PATCH"])
@require_api_key
def update_user(username):
    """Update one or more fields for an existing user."""
    data = request.get_json(silent=True) or {}

    # Only allow known, mutable fields to be updated
    allowed_fields = {"pin", "kvrcoin", "chess_points"}
    updates = {k: v for k, v in data.items() if k in allowed_fields}

    if not updates:
        abort(400, description="No valid fields provided for update.")

    set_clause = ", ".join(f"{field} = ?" for field in updates)
    values = list(updates.values()) + [username]

    conn = get_db()
    try:
        cursor = conn.execute(
            f"UPDATE users SET {set_clause} WHERE username = ?", values
        )
        conn.commit()
        if cursor.rowcount == 0:
            abort(404, description=f"No user with username '{username}'.")
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return jsonify(user_to_dict(row))
    except sqlite3.IntegrityError as exc:
        abort(409, description=f"Conflict: {exc}")
    finally:
        conn.close()


@app.route("/users/<username>", methods=["DELETE"])
@require_api_key
def delete_user(username):
    """Delete a user."""
    conn = get_db()
    try:
        cursor = conn.execute(
            "DELETE FROM users WHERE username = ?", (username,)
        )
        conn.commit()
        if cursor.rowcount == 0:
            abort(404, description=f"No user with username '{username}'.")
    finally:
        conn.close()
    return jsonify({"message": f"User '{username}' deleted."})


# --------------------------
# Admin app routes (UI)
# --------------------------


@admin_app.route("/")
def admin_index():
        html = """
        <!doctype html>
        <html>
        <head>
            <meta charset="utf-8" />
            <title>KVR Go Admin</title>
            <style>body{font-family:sans-serif;padding:20px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:8px} .hidden{display:none}</style>
        </head>
        <body>
            <h1>KVR Admin</h1>
            <section id="setPasswordSection" class="hidden">
                <h2>Set Admin Password</h2>
                <form id="setPasswordForm">
                    <input type="password" id="newPass" placeholder="New password" />
                    <input type="password" id="newPass2" placeholder="Confirm password" />
                    <button type="submit">Set Password</button>
                </form>
            </section>

            <section id="loginSection" class="hidden">
                <h2>Admin Login</h2>
                <button id="loginBtn">Enter password</button>
            </section>

            <section id="adminUI" class="hidden">
                <section>
                    <h2>Create user</h2>
                    <form id="createForm">
                        <div id="createInputs"></div>
                        <button type="submit">Create</button>
                    </form>
                </section>

                <section>
                    <h2>Users</h2>
                    <div id="users"></div>
                </section>
            </section>

            <script>
            let authHeader = null;

            async function fetchJSON(path, opts={}){
                opts.headers = opts.headers || {};
                if(authHeader){ opts.headers['Authorization'] = authHeader; }
                const res = await fetch(path, opts);
                if(!res.ok){ const txt = await res.text(); throw {status: res.status, text: txt}; }
                return res.json();
            }

            function show(id){ document.getElementById(id).classList.remove('hidden'); }
            function hide(id){ document.getElementById(id).classList.add('hidden'); }

            async function promptForPassword(){
                while(true){
                    const pwd = prompt('Enter admin password (cancel to abort):');
                    if(pwd === null) throw 'cancelled';
                    authHeader = 'Basic ' + btoa('admin:' + pwd);
                    try{
                        const r = await fetch('/api/fields', {headers: {'Authorization': authHeader}});
                        if(r.status === 200) return;
                        if(r.status === 401){ alert('Invalid password'); continue; }
                        throw 'error';
                    }catch(e){
                        if(e && e.status === 401) { alert('Invalid password'); continue; }
                        throw e;
                    }
                }
            }

            async function loadAdminUI(){
                const fields = await fetchJSON('/api/fields');
                const users = await fetchJSON('/api/users');

                // build create form inputs
                const createInputs = document.getElementById('createInputs');
                createInputs.innerHTML = '';
                for(const f of fields){
                    if(f === 'id') continue;
                    const inp = document.createElement('input'); inp.name = f; inp.placeholder = f; inp.style.marginRight='8px';
                    createInputs.appendChild(inp);
                }

                // build users table
                const usersDiv = document.getElementById('users');
                usersDiv.innerHTML = '';
                const table = document.createElement('table');
                const thead = document.createElement('thead');
                const tr = document.createElement('tr');
                for(const f of fields){ const th = document.createElement('th'); th.textContent = f; tr.appendChild(th); }
                tr.appendChild(document.createElement('th'));
                thead.appendChild(tr); table.appendChild(thead);
                const tbody = document.createElement('tbody');

                for(const u of users){
                    const row = document.createElement('tr');
                    for(const f of fields){
                        const td = document.createElement('td');
                        if(f === 'id'){
                            td.textContent = u[f] ?? '';
                        } else if(f === 'username'){
                            const span = document.createElement('span'); span.textContent = u[f]; td.appendChild(span);
                        } else {
                            const inp = document.createElement('input'); inp.value = u[f] ?? ''; inp.dataset.field = f; inp.style.width='100%'; td.appendChild(inp);
                        }
                        row.appendChild(td);
                    }
                    const tdActions = document.createElement('td');
                    const save = document.createElement('button'); save.textContent='Save';
                    save.onclick = async ()=>{
                        const updates = {};
                        for(const inp of row.querySelectorAll('input')){
                            updates[inp.dataset.field] = isNaN(inp.value) ? inp.value : (inp.value === '' ? null : Number(inp.value));
                        }
                        await fetchJSON('/api/users/'+encodeURIComponent(u.username), {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(updates)});
                        await refresh();
                    };
                    const del = document.createElement('button'); del.textContent='Delete'; del.style.marginLeft='8px';
                    del.onclick = async ()=>{ if(confirm('Delete '+u.username+'?')){ await fetchJSON('/api/users/'+encodeURIComponent(u.username), {method:'DELETE'}); await refresh(); } };
                    tdActions.appendChild(save); tdActions.appendChild(del); row.appendChild(tdActions);
                    tbody.appendChild(row);
                }
                table.appendChild(tbody); usersDiv.appendChild(table);
            }

            async function refresh(){ await loadAdminUI(); }

            document.getElementById('createForm').onsubmit = async (ev)=>{
                ev.preventDefault();
                const form = ev.target; const data = {};
                for(const inp of form.querySelectorAll('input')){ if(inp.value !== ''){ const num = Number(inp.value); data[inp.name] = isNaN(num) ? inp.value : num; } }
                await fetchJSON('/api/users', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
                form.reset(); await refresh();
            }

            document.getElementById('setPasswordForm').onsubmit = async (ev)=>{
                ev.preventDefault();
                const p1 = document.getElementById('newPass').value;
                const p2 = document.getElementById('newPass2').value;
                if(p1 !== p2){ alert('Passwords do not match'); return; }
                if(p1.length < 4){ alert('Password too short'); return; }
                await fetch('/api/admin/set', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({password: p1})});
                authHeader = 'Basic ' + btoa('admin:' + p1);
                hide('setPasswordSection'); show('adminUI'); await refresh();
            }

            document.getElementById('loginBtn').onclick = async ()=>{
                try{ await promptForPassword(); hide('loginSection'); show('adminUI'); await refresh(); }catch(e){ alert('Login cancelled'); }
            }

            async function init(){
                try{
                    const s = await fetchJSON('/api/admin/status');
                    if(!s.has_password){ show('setPasswordSection'); }
                    else { show('loginSection'); }
                }catch(e){ alert('Error initializing admin UI'); }
            }

            init();
            </script>
        </body>
        </html>
        """
        return render_template_string(html)


@admin_app.route('/api/fields', methods=['GET'])
def admin_fields():
    if not _admin_is_authorized():
        return _unauthorized()
    conn = get_db()
    try:
        cols = get_user_columns(conn)
        return jsonify(cols)
    finally:
        conn.close()


@admin_app.route('/api/users', methods=['GET'])
def admin_list_users():
    if not _admin_is_authorized():
        return _unauthorized()
    conn = get_db()
    try:
        rows = conn.execute('SELECT * FROM users').fetchall()
        result = [ {k: row[k] for k in row.keys()} for row in rows ]
        return jsonify(result)
    finally:
        conn.close()


@admin_app.route('/api/users', methods=['POST'])
def admin_create_user():
    if not _admin_is_authorized():
        return _unauthorized()
    data = request.get_json(silent=True) or {}
    username = data.get('username')
    pin = data.get('pin')
    if not username or pin is None:
        abort(400, description="'username' and 'pin' are required.")
    conn = get_db()
    try:
        # accept arbitrary other fields present in the table
        cols = get_user_columns(conn)
        insert_cols = ['username', 'pin']
        values = [username, pin]
        for c in cols:
            if c in ('id', 'username', 'pin'):
                continue
            if c in data:
                insert_cols.append(c)
                values.append(data[c])
        q = f"INSERT INTO users ({', '.join(insert_cols)}) VALUES ({', '.join(['?']*len(values))})"
        conn.execute(q, tuple(values))
        conn.commit()
        row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        return jsonify({k: row[k] for k in row.keys()}), 201
    except sqlite3.IntegrityError as exc:
        abort(409, description=str(exc))
    finally:
        conn.close()


@admin_app.route('/api/users/<username>', methods=['PATCH'])
def admin_update_user(username):
    if not _admin_is_authorized():
        return _unauthorized()
    data = request.get_json(silent=True) or {}
    if not data:
        abort(400, description='No data provided')
    conn = get_db()
    try:
        cols = get_user_columns(conn)
        updates = {k: v for k, v in data.items() if k in cols and k != 'id' and k != 'username'}
        if not updates:
            abort(400, description='No valid fields to update')
        set_clause = ', '.join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [username]
        cur = conn.execute(f"UPDATE users SET {set_clause} WHERE username = ?", values)
        conn.commit()
        if cur.rowcount == 0:
            abort(404, description=f"No user with username '{username}'.")
        row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        return jsonify({k: row[k] for k in row.keys()})
    except sqlite3.IntegrityError as exc:
        abort(409, description=str(exc))
    finally:
        conn.close()


@admin_app.route('/api/users/<username>', methods=['DELETE'])
def admin_delete_user(username):
    if not _admin_is_authorized():
        return _unauthorized()
    conn = get_db()
    try:
        cur = conn.execute('DELETE FROM users WHERE username = ?', (username,))
        conn.commit()
        if cur.rowcount == 0:
            abort(404, description=f"No user with username '{username}'.")
        return jsonify({'message': 'deleted'})
    finally:
        conn.close()



# --------------------------
# Admin password management + helpers
# --------------------------


def _unauthorized():
    # Basic auth challenge
    return (jsonify({'error': 'Unauthorized'}), 401, {'WWW-Authenticate': 'Basic realm="KVR Admin"'})


def _admin_is_authorized():
    # Check Authorization header for Basic auth and validate password
    auth = request.authorization
    if not auth or not auth.password:
        return False
    stored = get_admin_hash()
    if not stored:
        return False
    return check_password_hash(stored, auth.password)


@admin_app.route('/api/admin/status', methods=['GET'])
def admin_status():
    # Returns if admin password is set
    stored = get_admin_hash()
    return jsonify({'has_password': bool(stored)})


@admin_app.route('/api/admin/set', methods=['POST'])
def admin_set():
    # Allow setting password only if none exists yet, otherwise require auth
    stored = get_admin_hash()
    if stored:
        if not _admin_is_authorized():
            return _unauthorized()
    data = request.get_json(silent=True) or {}
    pwd = data.get('password')
    if not pwd or not isinstance(pwd, str) or len(pwd) < 4:
        abort(400, description='Password must be provided and be at least 4 characters')
    h = generate_password_hash(pwd)
    set_admin_hash(h)
    return jsonify({'message': 'admin password set'})



# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(400)
@app.errorhandler(401)
@app.errorhandler(404)
@app.errorhandler(409)
@app.errorhandler(500)
def handle_error(exc):
    return jsonify({"error": exc.description}), exc.code


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    with app.app_context():
        init_db()
    # start the admin UI on port 1212 in a background thread
    def _run_admin():
        admin_app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("ADMIN_PORT", 1212)))

    t = threading.Thread(target=_run_admin, daemon=True)
    t.start()

    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
