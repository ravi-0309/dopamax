from flask import Flask, render_template, request, redirect, jsonify, session, flash, url_for
import datetime
import hashlib
import os
import secrets
import db  # database compatibility layer (SQLite locally, Postgres via DATABASE_URL)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# =========================
# DATABASE
# =========================

def init_db():
    conn = db.connect()
    if db.IS_PG:
        conn.set_autocommit(True)   # so each DDL commits independently on Postgres
    cursor = conn.cursor()
    PK = db.pk_clause()
    TS = db.ts_default()

    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS users (
        id {PK},
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at {TS}
    )
    """)

    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS books (
        id {PK},
        user_id INTEGER DEFAULT 1,
        title TEXT,
        total_pages INTEGER,
        current_page INTEGER DEFAULT 0,
        dopamine_per_page REAL,
        completed INTEGER DEFAULT 0
    )
    """)

    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS courses (
        id {PK},
        user_id INTEGER DEFAULT 1,
        title TEXT,
        total_lectures INTEGER,
        completed_lectures INTEGER DEFAULT 0,
        dopamine_per_lecture REAL
    )
    """)

    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS research (
        id {PK},
        user_id INTEGER DEFAULT 1,
        title TEXT,
        dopamine_points REAL,
        completed INTEGER DEFAULT 0
    )
    """)

    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS custom_sections (
        id {PK},
        user_id INTEGER DEFAULT 1,
        name TEXT,
        icon TEXT DEFAULT '📁'
    )
    """)

    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS custom_tasks (
        id {PK},
        user_id INTEGER DEFAULT 1,
        section_name TEXT,
        title TEXT,
        dopamine_points REAL,
        completed INTEGER DEFAULT 0
    )
    """)

    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS daily_progress (
        id {PK},
        user_id INTEGER DEFAULT 1,
        date TEXT,
        source TEXT,
        dopamine_points REAL
    )
    """)

    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS settings (
        id {PK},
        user_id INTEGER DEFAULT 1,
        monday_goal INTEGER DEFAULT 50,
        tuesday_goal INTEGER DEFAULT 50,
        wednesday_goal INTEGER DEFAULT 50,
        thursday_goal INTEGER DEFAULT 50,
        friday_goal INTEGER DEFAULT 45,
        saturday_goal INTEGER DEFAULT 25,
        sunday_goal INTEGER DEFAULT 20,
        celebration_enabled INTEGER DEFAULT 1,
        daily_reminder_hour INTEGER DEFAULT 9,
        theme TEXT DEFAULT 'dark',
        book_bonus INTEGER DEFAULT 50,
        course_bonus INTEGER DEFAULT 100,
        research_bonus INTEGER DEFAULT 25
    )
    """)

    # Migration: add missing columns to existing tables
    migrations = [
        ("books", "user_id", "INTEGER DEFAULT 1"),
        ("courses", "user_id", "INTEGER DEFAULT 1"),
        ("research", "user_id", "INTEGER DEFAULT 1"),
        ("custom_sections", "user_id", "INTEGER DEFAULT 1"),
        ("custom_sections", "icon", "TEXT DEFAULT '📁'"),
        ("custom_tasks", "user_id", "INTEGER DEFAULT 1"),
        ("daily_progress", "user_id", "INTEGER DEFAULT 1"),
        ("settings", "user_id", "INTEGER DEFAULT 1"),
        ("settings", "book_bonus", "INTEGER DEFAULT 50"),
        ("settings", "course_bonus", "INTEGER DEFAULT 100"),
        ("settings", "research_bonus", "INTEGER DEFAULT 25"),
        ("books", "completed", "INTEGER DEFAULT 0"),
        ("users", "display_name", "TEXT"),
        # Rate-based / repeatable custom tasks + streaks
        ("custom_tasks", "task_type", "TEXT DEFAULT 'once'"),
        ("custom_tasks", "unit_name", "TEXT"),
        ("custom_tasks", "rate_dopamine", "REAL DEFAULT 0"),
        ("custom_tasks", "rate_units", "REAL DEFAULT 1"),
        ("custom_tasks", "completion_bonus", "REAL DEFAULT 0"),
        ("custom_tasks", "streak_days", "INTEGER DEFAULT 0"),
        ("custom_tasks", "streak_bonus", "REAL DEFAULT 0"),
        ("custom_tasks", "current_streak", "INTEGER DEFAULT 0"),
        ("custom_tasks", "last_log_date", "TEXT"),
        ("custom_tasks", "streak_awards", "INTEGER DEFAULT 0"),
        ("custom_tasks", "total_units", "REAL DEFAULT 0"),
        ("custom_tasks", "log_count", "INTEGER DEFAULT 0"),
    ]
    for table, col, typedef in migrations:
        try:
            if db.IS_PG:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {typedef}")
            else:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")
        except Exception:
            pass

    conn.commit()
    conn.close()

def ensure_user_settings(user_id):
    """Create settings row for user if missing."""
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM settings WHERE user_id=?", (user_id,))
    if cursor.fetchone() is None:
        cursor.execute("""
        INSERT INTO settings (user_id, monday_goal, tuesday_goal, wednesday_goal,
            thursday_goal, friday_goal, saturday_goal, sunday_goal,
            celebration_enabled, daily_reminder_hour, theme,
            book_bonus, course_bonus, research_bonus)
        VALUES (?,50,50,50,50,45,25,20,1,9,'dark',50,100,25)
        """, (user_id,))
        conn.commit()
    conn.close()

# =========================
# AUTH HELPERS
# =========================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def current_user():
    return session.get("user_id")

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user():
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated

# =========================
# HELPERS
# =========================

def add_dopamine(points, source):
    user_id = current_user() or 1
    today = str(datetime.date.today())
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO daily_progress (user_id, date, source, dopamine_points) VALUES (?,?,?,?)",
        (user_id, today, source, points)
    )
    conn.commit()
    conn.close()

def get_today_points(user_id=None):
    uid = user_id or current_user() or 1
    today = str(datetime.date.today())
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(dopamine_points) FROM daily_progress WHERE user_id=? AND date=?", (uid, today))
    result = cursor.fetchone()[0]
    conn.close()
    return round(result, 2) if result else 0

def get_today_breakdown(user_id=None):
    """Return today's dopamine grouped by source: list of (source, points), high to low."""
    uid = user_id or current_user() or 1
    today = str(datetime.date.today())
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT source, SUM(dopamine_points) FROM daily_progress
           WHERE user_id=? AND date=? GROUP BY source ORDER BY SUM(dopamine_points) DESC""",
        (uid, today)
    )
    rows = cursor.fetchall()
    conn.close()
    return [(r[0], round(r[1], 1)) for r in rows if r[1]]

def get_display_name(user_id=None):
    """Return the user's chosen display name, or None if not set yet."""
    uid = user_id or current_user() or 1
    conn = db.connect()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT display_name FROM users WHERE id=?", (uid,))
        row = cursor.fetchone()
    except Exception:
        row = None
    conn.close()
    return row[0] if row and row[0] else None

def get_today_goal(user_id=None):
    uid = user_id or current_user() or 1
    day_index = datetime.datetime.today().weekday()
    cols = ["monday_goal","tuesday_goal","wednesday_goal","thursday_goal",
            "friday_goal","saturday_goal","sunday_goal"]
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute(f"SELECT {cols[day_index]} FROM settings WHERE user_id=?", (uid,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 50

def get_streak(user_id=None):
    uid = user_id or current_user() or 1
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT date, SUM(dopamine_points) as total
    FROM daily_progress WHERE user_id=?
    GROUP BY date ORDER BY date DESC
    """, (uid,))
    rows = cursor.fetchall()
    conn.close()

    # Get goal for each day to check if met
    streak = 0
    today = datetime.date.today()
    for row in rows:
        try:
            row_date = datetime.date.fromisoformat(row[0])
        except:
            break
        # Allow today or yesterday to start streak
        expected = today - datetime.timedelta(days=streak)
        if row_date != expected:
            break
        if row[1] >= 30:  # at least 30dp to count
            streak += 1
        else:
            break
    return streak

def get_avg_daily_points(user_id=None):
    uid = user_id or current_user() or 1
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT AVG(daily_total) FROM (
        SELECT SUM(dopamine_points) as daily_total
        FROM daily_progress WHERE user_id=?
        GROUP BY date
    )
    """, (uid,))
    row = cursor.fetchone()
    conn.close()
    return round(row[0], 1) if row and row[0] else 0

def get_productivity_level(streak, avg_points):
    """Return (title, description, next_title, next_req, color) based on streak + avg."""
    levels = [
        (0,   0,   "🌱 Seedling",       "Just getting started", "#6b7280"),
        (3,   10,  "⚡ Spark",          "You're building momentum", "#f0c040"),
        (7,   20,  "🔥 Igniter",        "Consistent for a week", "#f08040"),
        (14,  35,  "💎 Crystal",        "Two weeks of focus", "#40c8f0"),
        (21,  50,  "🚀 Rocket",         "Three-week beast mode", "#c040f0"),
        (30,  60,  "🏆 Champion",       "A month of excellence", "#40e08a"),
        (60,  70,  "👑 Legend",         "Two months of dominance", "#f0c040"),
        (90,  80,  "⚡ Transcendent",   "Ninety days of mastery", "#ff6090"),
        (120, 90,  "🌌 Cosmic",         "Four months unbroken", "#8a7dff"),
        (180, 100, "☄️ Singularity",    "Half a year of mastery", "#00d4d4"),
        (270, 115, "🔱 Mythic",         "Nine months ascended", "#ff9f40"),
        (365, 130, "♾️ Eternal",        "A full year of dominance", "#ff4d6d"),
    ]

    current_level = levels[0]
    for i, (min_streak, min_avg, title, desc, color) in enumerate(levels):
        if streak >= min_streak and avg_points >= min_avg:
            current_level = (i, min_streak, min_avg, title, desc, color)

    idx = current_level[0]
    title = current_level[3]
    desc = current_level[4]
    color = current_level[5]

    # Next level
    if idx + 1 < len(levels):
        next_streak, next_avg, next_title, _, _ = levels[idx + 1]
        next_req = f"{next_streak}d streak + {next_avg} avg dp/day"
    else:
        next_title = "MAX LEVEL"
        next_req = "You've reached the peak!"

    return title, desc, next_title, next_req, color

def get_custom_sections(user_id=None):
    uid = user_id or current_user() or 1
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM custom_sections WHERE user_id=?", (uid,))
    sections = cursor.fetchall()
    conn.close()
    return sections

# =========================
# AUTH ROUTES
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect("/")
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = db.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT id, password_hash FROM users WHERE email=?", (email,))
        user = cursor.fetchone()
        conn.close()
        if user and user[1] == hash_password(password):
            session["user_id"] = user[0]
            session["user_email"] = email
            ensure_user_settings(user[0])
            return redirect("/")
        error = "Invalid email or password."
    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect("/")
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not email or not password:
            error = "Email and password are required."
        elif password != confirm:
            error = "Passwords do not match."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            try:
                conn = db.connect()
                cursor = conn.cursor()
                user_id = db.insert_returning_id(
                    cursor,
                    "INSERT INTO users (email, password_hash) VALUES (?,?)",
                    (email, hash_password(password))
                )
                conn.commit()
                conn.close()
                ensure_user_settings(user_id)
                session["user_id"] = user_id
                session["user_email"] = email
                return redirect("/")
            except db.IntegrityError:
                error = "An account with this email already exists."
    return render_template("register.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# =========================
# API
# =========================

@app.route("/api/today_points")
@login_required
def api_today_points():
    return jsonify({"points": get_today_points()})

@app.route("/api/set_name", methods=["POST"])
@login_required
def api_set_name():
    """Save the user's display name (used by the first-load name prompt)."""
    uid = current_user()
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or request.form.get("name") or "").strip()[:40]
    if not name:
        return jsonify({"ok": False, "error": "Name required"}), 400
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET display_name=? WHERE id=?", (name, uid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "name": name})

@app.route("/api/check_goal_just_crossed")
@login_required
def api_check_goal_just_crossed():
    """Returns True only once per day when goal is first crossed."""
    uid = current_user()
    today = str(datetime.date.today())
    points = get_today_points(uid)
    goal = get_today_goal(uid)

    # Use session to track if confetti was already shown today
    key = f"confetti_shown_{today}_{uid}"
    already_shown = session.get(key, False)

    if points >= goal and not already_shown:
        session[key] = True
        return jsonify({"show_confetti": True})
    return jsonify({"show_confetti": False})

# =========================
# DASHBOARD
# =========================

@app.route("/")
@login_required
def dashboard():
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM books WHERE user_id=?", (uid,))
    books = cursor.fetchall()
    cursor.execute("SELECT * FROM courses WHERE user_id=?", (uid,))
    courses = cursor.fetchall()
    cursor.execute("SELECT * FROM research WHERE user_id=?", (uid,))
    research = cursor.fetchall()
    cursor.execute("SELECT * FROM custom_sections WHERE user_id=?", (uid,))
    custom_sections = cursor.fetchall()
    conn.close()

    today_points = get_today_points(uid)
    today_date = datetime.datetime.today().strftime("%A, %d %B %Y")
    goal = get_today_goal(uid)
    completion_percent = int((today_points / goal) * 100) if goal > 0 else 0
    streak = get_streak(uid)
    avg_points = get_avg_daily_points(uid)
    prod_level = get_productivity_level(streak, avg_points)
    today_breakdown = get_today_breakdown(uid)
    display_name = get_display_name(uid)

    return render_template(
        "dashboard.html",
        books=books, courses=courses, research=research,
        custom_sections=custom_sections,
        today_points=today_points, today_date=today_date,
        goal=goal, completion_percent=completion_percent,
        streak=streak, prod_level=prod_level, avg_points=avg_points,
        today_breakdown=today_breakdown, display_name=display_name,
        user_email=session.get("user_email", "")
    )

# =========================
# BOOKS
# =========================

@app.route("/books")
@login_required
def books_page():
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM books WHERE user_id=?", (uid,))
    books = cursor.fetchall()
    cursor.execute("SELECT * FROM custom_sections WHERE user_id=?", (uid,))
    custom_sections = cursor.fetchall()
    conn.close()
    return render_template("books.html", books=books, custom_sections=custom_sections)

@app.route("/add_book", methods=["POST"])
@login_required
def add_book():
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO books (user_id, title, total_pages, current_page, dopamine_per_page, completed) VALUES (?,?,?,?,?,?)",
        (uid, request.form["title"], int(request.form["total_pages"]), 0, float(request.form["dopamine_per_page"]), 0)
    )
    conn.commit()
    conn.close()
    return redirect("/books")

@app.route("/update_book/<int:id>", methods=["POST"])
@login_required
def update_book(id):
    uid = current_user()
    pages = int(request.form["pages"])
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT current_page, dopamine_per_page, total_pages, completed FROM books WHERE id=? AND user_id=?", (id, uid))
    book = cursor.fetchone()
    if not book:
        conn.close()
        return redirect("/books")

    current_page, dopamine_per_page, total_pages, _ = book
    new_page = current_page + pages
    if new_page > total_pages:
        conn.close()
        return redirect("/books")

    dopamine = pages * dopamine_per_page
    completed = 0
    if new_page >= total_pages:
        new_page = total_pages
        completed = 1
        cursor.execute("SELECT book_bonus FROM settings WHERE user_id=?", (uid,))
        r = cursor.fetchone()
        if r: dopamine += r[0]

    cursor.execute("UPDATE books SET current_page=?, completed=? WHERE id=? AND user_id=?", (new_page, completed, id, uid))
    conn.commit()
    conn.close()
    add_dopamine(dopamine, "Books")
    return redirect("/books")

@app.route("/delete_book/<int:id>")
@login_required
def delete_book(id):
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM books WHERE id=? AND user_id=?", (id, uid))
    conn.commit()
    conn.close()
    return redirect("/books")

@app.route("/edit_book/<int:id>")
@login_required
def edit_book(id):
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM books WHERE id=? AND user_id=?", (id, uid))
    book = cursor.fetchone()
    cursor.execute("SELECT * FROM custom_sections WHERE user_id=?", (uid,))
    custom_sections = cursor.fetchall()
    conn.close()
    return render_template("edit_book.html", book=book, custom_sections=custom_sections)

@app.route("/save_book/<int:id>", methods=["POST"])
@login_required
def save_book(id):
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE books SET title=?, total_pages=?, dopamine_per_page=? WHERE id=? AND user_id=?",
        (request.form["title"], int(request.form["total_pages"]), float(request.form["dopamine_per_page"]), id, uid)
    )
    conn.commit()
    conn.close()
    return redirect("/books")

# =========================
# COURSES
# =========================

@app.route("/courses")
@login_required
def courses_page():
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM courses WHERE user_id=?", (uid,))
    courses = cursor.fetchall()
    cursor.execute("SELECT * FROM custom_sections WHERE user_id=?", (uid,))
    custom_sections = cursor.fetchall()
    conn.close()
    return render_template("courses.html", courses=courses, custom_sections=custom_sections)

@app.route("/add_course", methods=["POST"])
@login_required
def add_course():
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO courses (user_id, title, total_lectures, dopamine_per_lecture) VALUES (?,?,?,?)",
        (uid, request.form["title"], int(request.form["total_lectures"]), float(request.form["dopamine_per_lecture"]))
    )
    conn.commit()
    conn.close()
    return redirect("/courses")

@app.route("/update_course/<int:id>", methods=["POST"])
@login_required
def update_course(id):
    uid = current_user()
    lectures = int(request.form["lectures"])
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT completed_lectures, dopamine_per_lecture, total_lectures FROM courses WHERE id=? AND user_id=?", (id, uid))
    course = cursor.fetchone()
    if not course:
        conn.close()
        return redirect("/courses")

    new_lectures = min(course[0] + lectures, course[2])
    dopamine = lectures * course[1]
    if new_lectures >= course[2]:
        cursor.execute("SELECT course_bonus FROM settings WHERE user_id=?", (uid,))
        r = cursor.fetchone()
        if r: dopamine += r[0]
    cursor.execute("UPDATE courses SET completed_lectures=? WHERE id=? AND user_id=?", (new_lectures, id, uid))
    conn.commit()
    conn.close()
    add_dopamine(dopamine, "Courses")
    return redirect("/courses")

@app.route("/edit_course/<int:id>")
@login_required
def edit_course(id):
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM courses WHERE id=? AND user_id=?", (id, uid))
    course = cursor.fetchone()
    cursor.execute("SELECT * FROM custom_sections WHERE user_id=?", (uid,))
    custom_sections = cursor.fetchall()
    conn.close()
    return render_template("edit_course.html", course=course, custom_sections=custom_sections)

@app.route("/save_course/<int:id>", methods=["POST"])
@login_required
def save_course(id):
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE courses SET title=?, total_lectures=?, dopamine_per_lecture=? WHERE id=? AND user_id=?",
        (request.form["title"], int(request.form["total_lectures"]), float(request.form["dopamine_per_lecture"]), id, uid)
    )
    conn.commit()
    conn.close()
    return redirect("/courses")

@app.route("/delete_course/<int:id>")
@login_required
def delete_course(id):
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM courses WHERE id=? AND user_id=?", (id, uid))
    conn.commit()
    conn.close()
    return redirect("/courses")

# =========================
# RESEARCH
# =========================

@app.route("/research")
@login_required
def research_page():
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM research WHERE user_id=?", (uid,))
    research = cursor.fetchall()
    cursor.execute("SELECT * FROM custom_sections WHERE user_id=?", (uid,))
    custom_sections = cursor.fetchall()
    conn.close()
    return render_template("research.html", research=research, custom_sections=custom_sections)

@app.route("/add_research", methods=["POST"])
@login_required
def add_research():
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO research (user_id, title, dopamine_points) VALUES (?,?,?)",
        (uid, request.form["title"], float(request.form["dopamine_points"]))
    )
    conn.commit()
    conn.close()
    return redirect("/research")

@app.route("/complete_research/<int:id>")
@login_required
def complete_research(id):
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT dopamine_points FROM research WHERE id=? AND user_id=?", (id, uid))
    task = cursor.fetchone()
    if task:
        cursor.execute("UPDATE research SET completed=1 WHERE id=? AND user_id=?", (id, uid))
        conn.commit()
        conn.close()
        add_dopamine(task[0], "Research")
    else:
        conn.close()
    return redirect("/research")

@app.route("/edit_research/<int:id>")
@login_required
def edit_research(id):
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM research WHERE id=? AND user_id=?", (id, uid))
    task = cursor.fetchone()
    cursor.execute("SELECT * FROM custom_sections WHERE user_id=?", (uid,))
    custom_sections = cursor.fetchall()
    conn.close()
    return render_template("edit_research.html", task=task, custom_sections=custom_sections)

@app.route("/save_research/<int:id>", methods=["POST"])
@login_required
def save_research(id):
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE research SET title=?, dopamine_points=? WHERE id=? AND user_id=?",
        (request.form["title"], float(request.form["dopamine_points"]), id, uid)
    )
    conn.commit()
    conn.close()
    return redirect("/research")

@app.route("/delete_research/<int:id>")
@login_required
def delete_research(id):
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM research WHERE id=? AND user_id=?", (id, uid))
    conn.commit()
    conn.close()
    return redirect("/research")

# =========================
# CUSTOM SECTIONS
# =========================

@app.route("/add_section", methods=["POST"])
@login_required
def add_section():
    uid = current_user()
    section_name = request.form["section_name"]
    section_icon = request.form.get("section_icon", "📁")
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO custom_sections (user_id, name, icon) VALUES (?,?,?)", (uid, section_name, section_icon))
    conn.commit()
    conn.close()
    return redirect(request.referrer or "/settings")

@app.route("/section/<section_name>")
@login_required
def custom_section(section_name):
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cols = ["id", "title", "dopamine_points", "completed", "task_type", "unit_name",
            "rate_dopamine", "rate_units", "completion_bonus", "streak_days", "streak_bonus",
            "current_streak", "last_log_date", "total_units", "log_count"]
    cursor.execute(
        f"SELECT {', '.join(cols)} FROM custom_tasks WHERE section_name=? AND user_id=?",
        (section_name, uid)
    )
    rows = cursor.fetchall()
    cursor.execute("SELECT * FROM custom_sections WHERE user_id=?", (uid,))
    custom_sections = cursor.fetchall()
    cursor.execute("SELECT icon FROM custom_sections WHERE user_id=? AND name=?", (uid, section_name))
    icon_row = cursor.fetchone()
    section_icon = icon_row[0] if icon_row else "📁"
    conn.close()

    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    tasks = []
    for r in rows:
        t = dict(zip(cols, r))
        # Live streak: counts only if last log was today or yesterday, otherwise broken (0)
        last = t.get("last_log_date")
        if last in (str(today), str(yesterday)):
            t["live_streak"] = t.get("current_streak") or 0
        else:
            t["live_streak"] = 0
        tasks.append(t)

    return render_template("custom_section.html", section_name=section_name,
                           tasks=tasks, custom_sections=custom_sections, section_icon=section_icon)

@app.route("/add_custom_task/<section_name>", methods=["POST"])
@login_required
def add_custom_task(section_name):
    uid = current_user()
    task_type = request.form.get("task_type", "once")
    title = request.form.get("title", "").strip()
    conn = db.connect()
    cursor = conn.cursor()

    if task_type == "rate":
        rate_dopamine = float(request.form.get("rate_dopamine") or 0)
        rate_units = float(request.form.get("rate_units") or 1) or 1
        unit_name = (request.form.get("unit_name") or "units").strip()
        completion_bonus = float(request.form.get("completion_bonus") or 0)
        streak_days = int(request.form.get("streak_days") or 0)
        streak_bonus = float(request.form.get("streak_bonus") or 0)
        cursor.execute(
            """INSERT INTO custom_tasks
               (user_id, section_name, title, dopamine_points, completed, task_type,
                unit_name, rate_dopamine, rate_units, completion_bonus, streak_days, streak_bonus)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (uid, section_name, title, 0, 0, "rate", unit_name, rate_dopamine, rate_units,
             completion_bonus, streak_days, streak_bonus)
        )
    else:
        dopamine_points = float(request.form.get("dopamine_points") or 0)
        completion_bonus = float(request.form.get("completion_bonus") or 0)
        cursor.execute(
            """INSERT INTO custom_tasks
               (user_id, section_name, title, dopamine_points, completed, task_type, completion_bonus)
               VALUES (?,?,?,?,?,?,?)""",
            (uid, section_name, title, dopamine_points, 0, "once", completion_bonus)
        )
    conn.commit()
    conn.close()
    return redirect(f"/section/{section_name}")

@app.route("/log_custom_task/<int:id>", methods=["POST"])
@login_required
def log_custom_task(id):
    """Log work on a repeatable rate-based task; awards dopamine, bonus, and streak rewards."""
    uid = current_user()
    units = float(request.form.get("units") or 0)
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT section_name, rate_dopamine, rate_units, completion_bonus, streak_days,
                  streak_bonus, current_streak, last_log_date, streak_awards, total_units, log_count
           FROM custom_tasks WHERE id=? AND user_id=?""",
        (id, uid)
    )
    row = cursor.fetchone()
    if not row or units <= 0:
        conn.close()
        return redirect(request.referrer or "/")

    (section_name, rate_dopamine, rate_units, completion_bonus, streak_days,
     streak_bonus, current_streak, last_log_date, streak_awards, total_units, log_count) = row
    rate_units = rate_units or 1

    earned = units * (rate_dopamine / rate_units)
    earned += (completion_bonus or 0)

    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    new_streak = current_streak or 0
    awards = streak_awards or 0

    if last_log_date != str(today):  # first log of a new day
        if last_log_date == str(yesterday):
            new_streak = (current_streak or 0) + 1
        else:
            new_streak = 1
        if streak_days and streak_days > 0 and new_streak % streak_days == 0:
            earned += (streak_bonus or 0)
            awards += 1

    cursor.execute(
        """UPDATE custom_tasks
           SET current_streak=?, last_log_date=?, streak_awards=?,
               total_units=?, log_count=?
           WHERE id=? AND user_id=?""",
        (new_streak, str(today), awards,
         (total_units or 0) + units, (log_count or 0) + 1, id, uid)
    )
    conn.commit()
    conn.close()
    add_dopamine(round(earned, 2), section_name)
    return redirect(f"/section/{section_name}")

@app.route("/complete_custom_task/<int:id>")
@login_required
def complete_custom_task(id):
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT dopamine_points, section_name, completion_bonus FROM custom_tasks WHERE id=? AND user_id=?", (id, uid))
    task = cursor.fetchone()
    if task:
        cursor.execute("UPDATE custom_tasks SET completed=1 WHERE id=? AND user_id=?", (id, uid))
        conn.commit()
        conn.close()
        add_dopamine((task[0] or 0) + (task[2] or 0), task[1])
        return redirect(f"/section/{task[1]}")
    conn.close()
    return redirect("/")

@app.route("/delete_custom_task/<int:id>")
@login_required
def delete_custom_task(id):
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT section_name FROM custom_tasks WHERE id=? AND user_id=?", (id, uid))
    task = cursor.fetchone()
    if task:
        cursor.execute("DELETE FROM custom_tasks WHERE id=? AND user_id=?", (id, uid))
        conn.commit()
        conn.close()
        return redirect(f"/section/{task[0]}")
    conn.close()
    return redirect("/")

@app.route("/edit_section/<section_name>")
@login_required
def edit_section(section_name):
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT name, icon FROM custom_sections WHERE name=? AND user_id=?", (section_name, uid))
    section = cursor.fetchone()
    cursor.execute("SELECT * FROM custom_sections WHERE user_id=?", (uid,))
    custom_sections = cursor.fetchall()
    conn.close()
    if not section:
        return redirect("/settings")
    return render_template("edit_section.html",
                           section_name=section[0],
                           section_icon=section[1] if section[1] else "📁",
                           custom_sections=custom_sections)

@app.route("/save_section/<old_name>", methods=["POST"])
@login_required
def save_section(old_name):
    uid = current_user()
    new_name = (request.form.get("section_name") or "").strip()
    new_icon = (request.form.get("section_icon") or "📁").strip()
    if not new_name:
        return redirect(f"/edit_section/{old_name}")
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE custom_sections SET name=?, icon=? WHERE name=? AND user_id=?",
                   (new_name, new_icon, old_name, uid))
    if new_name != old_name:
        # Cascade the rename so tasks and analytics stay linked
        cursor.execute("UPDATE custom_tasks SET section_name=? WHERE section_name=? AND user_id=?",
                       (new_name, old_name, uid))
        cursor.execute("UPDATE daily_progress SET source=? WHERE source=? AND user_id=?",
                       (new_name, old_name, uid))
    conn.commit()
    conn.close()
    return redirect(f"/section/{new_name}")

@app.route("/delete_section/<section_name>")
@login_required
def delete_section(section_name):
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM custom_sections WHERE name=? AND user_id=?", (section_name, uid))
    cursor.execute("DELETE FROM custom_tasks WHERE section_name=? AND user_id=?", (section_name, uid))
    conn.commit()
    conn.close()
    return redirect("/")

# =========================
# ANALYTICS
# =========================

@app.route("/analytics")
@login_required
def analytics():
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT date, SUM(dopamine_points)
    FROM daily_progress WHERE user_id=?
    GROUP BY date ORDER BY date ASC
    """, (uid,))
    daily_data = cursor.fetchall()

    cursor.execute("""
    SELECT source, SUM(dopamine_points)
    FROM daily_progress WHERE user_id=?
    GROUP BY source
    """, (uid,))
    section_data = cursor.fetchall()

    # Per-day source breakdown -> { "2026-06-03": {"Books": 12.0, "Courses": 30.0}, ... }
    cursor.execute("""
    SELECT date, source, SUM(dopamine_points)
    FROM daily_progress WHERE user_id=?
    GROUP BY date, source
    """, (uid,))
    per_day_rows = cursor.fetchall()

    cursor.execute("SELECT * FROM custom_sections WHERE user_id=?", (uid,))
    custom_sections = cursor.fetchall()
    conn.close()

    dates = [row[0] for row in daily_data]
    points = [round(row[1], 1) if row[1] else 0 for row in daily_data]
    sources = [row[0] for row in section_data]
    source_points = [round(row[1], 1) if row[1] else 0 for row in section_data]

    # Build per-day breakdown map for the JS (selected-day pie + table)
    daily_breakdown = {}
    for d, src, pts in per_day_rows:
        if not pts:
            continue
        daily_breakdown.setdefault(d, {})[src] = round(pts, 1)

    # ---- Summary stats ----
    total = round(sum(points), 1)
    daily_avg = round(total / len(points), 1) if points else 0

    today = datetime.date.today()
    def _avg_last(n):
        cutoff = today - datetime.timedelta(days=n)
        vals = [p for dt, p in zip(dates, points)
                if _safe_date(dt) and _safe_date(dt) >= cutoff]
        return round(sum(vals) / n, 1) if vals else 0

    weekly_avg = _avg_last(7)
    monthly_avg = _avg_last(30)

    best_day_points = best_day_date = worst_day_points = worst_day_date = None
    if points:
        best_i = max(range(len(points)), key=lambda i: points[i])
        worst_i = min(range(len(points)), key=lambda i: points[i])
        best_day_points, best_day_date = points[best_i], dates[best_i]
        worst_day_points, worst_day_date = points[worst_i], dates[worst_i]

    return render_template(
        "analytics.html",
        dates=dates, points=points,
        sources=sources, source_points=source_points,
        daily_breakdown=daily_breakdown,
        total=total, daily_avg=daily_avg,
        weekly_avg=weekly_avg, monthly_avg=monthly_avg,
        best_day_points=best_day_points, best_day_date=best_day_date,
        worst_day_points=worst_day_points, worst_day_date=worst_day_date,
        custom_sections=custom_sections
    )

def _safe_date(s):
    try:
        return datetime.date.fromisoformat(s)
    except Exception:
        return None

# =========================
# SETTINGS
# =========================

@app.route("/settings")
@login_required
def settings_page():
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM settings WHERE user_id=?", (uid,))
    settings = cursor.fetchone()
    cursor.execute("SELECT * FROM custom_sections WHERE user_id=?", (uid,))
    custom_sections = cursor.fetchall()
    conn.close()
    streak = get_streak(uid)
    avg_points = get_avg_daily_points(uid)
    prod_level = get_productivity_level(streak, avg_points)
    return render_template("settings.html", settings=settings,
                           custom_sections=custom_sections,
                           streak=streak, avg_points=avg_points,
                           prod_level=prod_level)

@app.route("/update_settings", methods=["POST"])
@login_required
def update_settings():
    uid = current_user()
    conn = db.connect()
    cursor = conn.cursor()

    def _int(name, default):
        try:
            return int(float(request.form.get(name, default)))
        except (TypeError, ValueError):
            return default

    celebration = _int("celebration_enabled", 0)
    cursor.execute("""
    UPDATE settings SET
        monday_goal=?, tuesday_goal=?, wednesday_goal=?, thursday_goal=?,
        friday_goal=?, saturday_goal=?, sunday_goal=?,
        celebration_enabled=?, daily_reminder_hour=?, theme=?,
        book_bonus=?, course_bonus=?, research_bonus=?
    WHERE user_id=?
    """, (
        _int("monday", 50), _int("tuesday", 50),
        _int("wednesday", 50), _int("thursday", 50),
        _int("friday", 45), _int("saturday", 25),
        _int("sunday", 20),
        celebration,
        _int("daily_reminder_hour", 9),
        request.form.get("theme", "dark"),
        _int("book_bonus", 50),
        _int("course_bonus", 100),
        _int("research_bonus", 25),
        uid
    ))
    conn.commit()
    conn.close()
    return redirect("/settings")

# =========================
# RUN
# =========================

# Ensure tables exist on startup. This runs both locally and under a WSGI
# server like gunicorn (Render), where the __main__ block below is NOT executed.
try:
    init_db()
except Exception as _e:
    print("init_db() warning:", _e)

if __name__ == "__main__":
    app.run(debug=True)
