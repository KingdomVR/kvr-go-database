"""
KVR Database Server
A simple Flask REST API for managing KingdomVR user accounts.
"""

import os
import functools
from flask import Flask, request, jsonify, abort
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
app.config["DATABASE"] = os.environ.get("DATABASE", "kvr_database.db")
API_KEY = os.environ.get("API_KEY", "")

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
            pin         INTEGER NOT NULL UNIQUE,
            kvrcoin     REAL    NOT NULL DEFAULT 0,
            chess_points REAL   NOT NULL DEFAULT 0
        )
        """
    )
    conn.commit()
    if close:
        conn.close()


def user_to_dict(row):
    """Convert a sqlite3.Row to a plain dict (skipping internal 'id')."""
    return {
        "username": row["username"],
        "pin": row["pin"],
        "kvrcoin": row["kvrcoin"],
        "chess_points": row["chess_points"],
    }


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
    if not isinstance(pin, int):
        abort(400, description="'pin' must be an integer.")

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


@app.route("/users/pin/<int:pin>", methods=["GET"])
@require_api_key
def get_user_by_pin(pin):
    """Return a user looked up by PIN."""
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
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
