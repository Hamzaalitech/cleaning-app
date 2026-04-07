from flask import Flask, render_template, request
from datetime import datetime, timedelta
import json
import os
import time
from werkzeug.utils import secure_filename
import psycopg2
app = Flask(__name__)
app.secret_key = "change-this-to-a-long-random-secret-key"

DATA_FILE = "checklists.json"
STAFF_NAMES_FILE = "staff_names.json"
UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MASTER_UNLOCK_CODE = "2468"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

conn = None

def get_db_connection():
    global conn
    if conn is None or conn.closed != 0:
        print("NEW DB CONNECTION CREATED") 
        conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
    return conn

DEFAULT_TASKS = [
    "Cutlery",
    "Cutlery containers - inside & out",
    "Ketchup & Mayo bottles - remove lids & give to dishwasher",
    "Salt & Pepper shakers",
    "WAITER STATION: All top surfaces, ramekin shelves",
    "All storage shelves underneath",
    "Behind & under monitor and printer",
    "All baby chairs",
    "STAIRCASE: Steps hoover & dry mop",
    "Sides of steps",
    "TABLES: All table tops",
    "Pull tables apart and wipe sides",
    "Base of tables",
    "SOFAS: Top surfaces",
    "Inside of grooves (joints between sofas) and gaps",
    "Chairs",
    "PLANTERS (wipe sides and top): Table 10",
    "Table 19-20",
    "Table 21-22",
    "DOORS & FIXTURES: Door leading to toilet",
    "Door leading to fire exit by T23",
    "Copper ledge above T23",
    "TOOLS: Dust pan and brush",
    "HOOVER: All corners, sides & under staircase",
    "Under table bases (move tables to one side)",
    "MOP: All areas including corners",
    "Under table bases (move tables to one side)",
    "SWITCH OFF: AC above T15",
    "AC above T23",
    "AC in grill section",
    "AC in back section",
    "Heater above T19",
    "Heater above T21",
    "ROBOT: All surfaces"
]

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def build_tasks(task_names):
    return [
        {
            "task": task_name,
            "staff": "",
            "done": False,
            "task_time": "",
            "manager_check": "",
            "manager_time": "",
            "comment": "",
            "photo": ""
        }
        for task_name in task_names
    ]

def normalize_all_tasks(data):
    for date_key, tasks in data.items():
        for item in tasks:
            if "staff" not in item:
                item["staff"] = ""
            if "done" not in item:
                item["done"] = False
            if "task_time" not in item:
                item["task_time"] = ""
            if "manager_check" not in item:
                item["manager_check"] = ""
            if "manager_time" not in item:
                item["manager_time"] = ""
            if "comment" not in item:
                item["comment"] = ""
            if "photo" not in item:
                item["photo"] = ""
    return data

def load_all_tasks():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            return normalize_all_tasks(data)
    return {}

def load_staff_names():
    if os.path.exists(STAFF_NAMES_FILE):
        with open(STAFF_NAMES_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            if isinstance(data, list):
                return data
    return []

def save_staff_names():
    with open(STAFF_NAMES_FILE, "w", encoding="utf-8") as file:
        json.dump(staff_names, file, indent=4)

def remember_staff_name(name):
    cleaned_name = name.strip()
    if not cleaned_name:
        return

    existing_lower = {item.lower() for item in staff_names}
    if cleaned_name.lower() not in existing_lower:
        staff_names.append(cleaned_name)
        staff_names.sort(key=lambda value: value.lower())
        save_staff_names()

def prune_old_tasks():
    global all_tasks

    valid_dates = []
    for date_key in all_tasks.keys():
        try:
            date_obj = datetime.strptime(date_key, "%Y-%m-%d")
            valid_dates.append((date_obj, date_key))
        except ValueError:
            continue

    valid_dates.sort(reverse=True)
    keep_keys = {date_key for _, date_key in valid_dates[:28]}

    all_tasks = {
        date_key: tasks
        for date_key, tasks in all_tasks.items()
        if date_key in keep_keys
    }

def save_all_tasks():
    prune_old_tasks()
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(all_tasks, file, indent=4)

all_tasks = load_all_tasks()
staff_names = load_staff_names()
prune_old_tasks()

def get_current_date_key():
    now = datetime.now()
    if now.hour < 5:
        now = now - timedelta(days=1)
    return now.strftime("%Y-%m-%d")

def is_valid_date_key(date_key):
    try:
        datetime.strptime(date_key, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False

def has_valid_unlock(unlock_code):
    return unlock_code == MASTER_UNLOCK_CODE

def is_past_date_locked(date_key, unlock_code=""):
    if date_key >= get_current_date_key():
        return False
    return not has_valid_unlock(unlock_code)

def get_tasks_for_date(date_key):
    base_tasks = build_tasks(DEFAULT_TASKS)

    db_tasks = get_tasks_from_db(date_key)
    if db_tasks:
        db_task_map = {}
        for item in db_tasks:
            if item["task"] not in db_task_map or item.get("manager_check_date"):
                db_task_map[item["task"]] = item

        for task in base_tasks:
            if task["task"] in db_task_map:
                saved_task = db_task_map[task["task"]]
                task["staff"] = saved_task["staff"]
                task["done"] = saved_task["done"]
                task["task_time"] = saved_task["task_time"]
                task["manager_check"] = saved_task["manager_check"]
                task["manager_time"] = saved_task["manager_time"]
                task["manager_check_date"] = saved_task["manager_check_date"]
                task["comment"] = saved_task["comment"]
                task["photo"] = saved_task["photo"]

        return base_tasks

    if date_key not in all_tasks:
        all_tasks[date_key] = build_tasks(DEFAULT_TASKS)
        save_all_tasks()

    return all_tasks[date_key]

def get_tasks_from_db(date_key):
    read_start = time.time()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT task_name, staff_name, done, task_time, manager_check, manager_time, manager_check_date, comment, photo FROM checklists WHERE date_key = %s;",
            (date_key,)
        )

        rows = cursor.fetchall()
        read_end = time.time()
        print("DB READ TIME:", read_end - read_start)
        
        cursor.close()

        tasks = []
        for row in rows:
            tasks.append({
                "task": row[0],
                "staff": row[1] or "",
                "done": row[2],
                "task_time": row[3] or "",
                "manager_check": row[4] or "",
                "manager_time": row[5] or "",
                "manager_check_date": row[6] if row[6] else None,
                "comment": row[7] or "",
                "photo": row[8] or ""
            })

        return tasks

    except Exception as e:
        print("DB READ ERROR:", e)
        return []
    
def upsert_task_to_db(date_key, task):
    db_start = time.time()
    print("UPSERT CALLED:", date_key, task)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO checklists
            (task_name, staff_name, done, task_time, manager_check, manager_time, manager_check_date, comment, photo, date_key)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (date_key, task_name)
            DO UPDATE SET
                staff_name = EXCLUDED.staff_name,
                done = CASE
                    WHEN EXCLUDED.done IS DISTINCT FROM checklists.done THEN EXCLUDED.done
                    ELSE checklists.done
                END,
                task_time = EXCLUDED.task_time,
                manager_check = COALESCE(NULLIF(EXCLUDED.manager_check, ''), checklists.manager_check),
                manager_time = COALESCE(NULLIF(EXCLUDED.manager_time, ''), checklists.manager_time),
                manager_check_date = COALESCE(EXCLUDED.manager_check_date, checklists.manager_check_date),
                comment = COALESCE(NULLIF(EXCLUDED.comment, ''), checklists.comment),
                photo = COALESCE(NULLIF(EXCLUDED.photo, ''), checklists.photo);
            """,
            (
                task["task"],
                task["staff"],
                task["done"],
                task["task_time"],
                task["manager_check"],
                task["manager_time"],
                task.get("manager_check_date"),
                task["comment"],
                task["photo"],
                date_key
            )
        )

        conn.commit()
        db_end = time.time()
        print("DB FUNCTION TIME:", db_end - db_start)
        print("DB COMMIT SUCCESS")
        cursor.close()
        return True

    except Exception as e:
        print("DB UPSERT ERROR FULL:", repr(e))
        return False
        
@app.route("/")
def home():
    date_param = request.args.get("date", "").strip()

    if is_valid_date_key(date_param):
        date_key = date_param
    else:
        date_key = get_current_date_key()

    selected_date_obj = datetime.strptime(date_key, "%Y-%m-%d")
    previous_date = (selected_date_obj - timedelta(days=1)).strftime("%Y-%m-%d")

    current_date_key = get_current_date_key()
    if date_key < current_date_key:
        next_date = (selected_date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        next_date = None

    
    tasks = get_tasks_for_date(date_key)

    dates = [item["manager_check_date"] for item in tasks if item.get("manager_check_date")]

    if dates:
        latest_date = max(dates)
        manager_check_date = latest_date.strftime("%d %B")
    else:
        manager_check_date = None
    
    is_locked = is_past_date_locked(date_key)

    return render_template(
        "index.html",
        tasks=tasks,
        manager_check_date=manager_check_date,
        selected_date=date_key,
        previous_date=previous_date,
        next_date=next_date,
        is_locked=is_locked,
        staff_names=staff_names
    )

@app.route("/unlock", methods=["POST"])
def unlock_date():
    date_key = request.form.get("date", "").strip()
    code = request.form.get("code", "").strip()

    if not is_valid_date_key(date_key):
        return {"success": False}, 400

    if not has_valid_unlock(code):
        return {"success": False}, 403

    return {"success": True}

@app.route("/done", methods=["POST"])
def mark_done():
    start_time = time.time()
    task_name = request.form.get("task")
    staff = request.form.get("staff", "")
    checked = request.form.get("checked", "false")
    date_key = request.form.get("date", "").strip()
    unlock_code = request.form.get("unlock_code", "").strip()

    if not is_valid_date_key(date_key):
        date_key = get_current_date_key()

    # LOCKED CASE
    if is_past_date_locked(date_key, unlock_code):
        tasks = get_tasks_for_date(date_key)
        for item in tasks:
            if item["task"] == task_name:
                return {
                    "staff": item["staff"],
                    "task_time": item["task_time"]
                }
        return {"staff": "", "task_time": ""}

    # NORMAL CASE
    tasks = get_tasks_for_date(date_key)
    item = next((t for t in tasks if t["task"] == task_name), None)

    if not item:
        item = {
            "task": task_name,
            "staff": "",
            "done": False,
            "task_time": "",
            "manager_check": "",
            "manager_time": "",
            "manager_check_date": None,
            "comment": "",
            "photo": ""
        }

    if checked == "true":
        item["staff"] = staff
        item["done"] = True
        item["task_time"] = datetime.now().strftime("%H:%M:%S")
        remember_staff_name(staff)
    else:
        item["staff"] = ""
        item["done"] = False
        item["task_time"] = ""

    upsert_task_to_db(date_key, item)

    end_time = time.time()
    print("TOTAL REQUEST TIME:", end_time - start_time)

    return {
    "staff": item["staff"],
    "task_time": item["task_time"]
    }

@app.route("/manager-check", methods=["POST"])
def manager_check():
    task_name = request.form.get("task")
    status = request.form.get("status", "").strip()
    date_key = request.form.get("date", "").strip()
    unlock_code = request.form.get("unlock_code", "").strip()

    if not is_valid_date_key(date_key):
        date_key = get_current_date_key()

    if is_past_date_locked(date_key, unlock_code):
        tasks = get_tasks_for_date(date_key)
        for item in tasks:
            if item["task"] == task_name:
                return {
                    "manager_check": item["manager_check"],
                    "manager_time": item["manager_time"]
                }
        return {"manager_check": "", "manager_time": ""}

    tasks = get_tasks_for_date(date_key)
    item = next((t for t in tasks if t["task"] == task_name), None)

    if not item:
        item = {
            "task": task_name,
            "staff": "",
            "done": False,
            "task_time": "",
            "manager_check": "",
            "manager_time": "",
            "manager_check_date": None,
            "comment": "",
            "photo": ""
        }

    item["manager_check"] = status
    item["manager_time"] = datetime.now().strftime("%H:%M:%S")
    item["manager_check_date"] = datetime.now().strftime("%Y-%m-%d")

    upsert_task_to_db(date_key, item)

    return {
        "manager_check": item["manager_check"],
        "manager_time": item["manager_time"],
        "manager_check_date": datetime.now().strftime("%d %B")
    }

@app.route("/comment", methods=["POST"])
def save_comment():
    task_name = request.form.get("task")
    comment = request.form.get("comment", "").strip()
    date_key = request.form.get("date", "").strip()
    unlock_code = request.form.get("unlock_code", "").strip()

    if not is_valid_date_key(date_key):
        date_key = get_current_date_key()

    if is_past_date_locked(date_key, unlock_code):
        tasks = get_tasks_for_date(date_key)
        for item in tasks:
            if item["task"] == task_name:
                return {"comment": item["comment"]}
        return {"comment": ""}

    tasks = get_tasks_for_date(date_key)
    item = next((t for t in tasks if t["task"] == task_name), None)

    if not item:
        item = {
            "task": task_name,
            "staff": "",
            "done": False,
            "task_time": "",
            "manager_check": "",
            "manager_time": "",
            "manager_check_date": None,
            "comment": "",
            "photo": ""
        }

    item["comment"] = comment

    upsert_task_to_db(date_key, item)

    return {"comment": item["comment"]}




@app.route("/upload-photo", methods=["POST"])
def upload_photo():
    task_name = request.form.get("task", "").strip()
    date_key = request.form.get("date", "").strip()
    unlock_code = request.form.get("unlock_code", "").strip()
    photo = request.files.get("photo")

    if not is_valid_date_key(date_key):
        date_key = get_current_date_key()

    if is_past_date_locked(date_key, unlock_code):
        tasks = get_tasks_for_date(date_key)
        for item in tasks:
            if item["task"] == task_name:
                return {
                    "success": True,
                    "photo": item["photo"]
                }
        return {"success": False, "photo": ""}, 400

    if not photo or photo.filename == "":
        return {"success": False, "photo": "", "message": "No file selected"}, 400

    if not allowed_file(photo.filename):
        return {"success": False, "photo": "", "message": "Invalid file type"}, 400

    tasks = get_tasks_for_date(date_key)

    for item in tasks:
        if item["task"] == task_name:
            if item.get("photo"):
                old_path = os.path.join(app.config["UPLOAD_FOLDER"], item["photo"])
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except Exception:
                        pass

            original_name = secure_filename(photo.filename)
            extension = original_name.rsplit(".", 1)[1].lower()
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            safe_task_name = secure_filename(task_name).replace("-", "_")
            stored_filename = f"{date_key}_{safe_task_name}_{timestamp}.{extension}"
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], stored_filename)

            photo.save(file_path)

            item["photo"] = stored_filename
            upsert_task_to_db(date_key, item)
            save_all_tasks()

            return {
                "success": True,
                "photo": item["photo"]
            }

    return {"success": False, "photo": "", "message": "Task not found"}, 404

@app.route("/test-data")
def test_data():
    try:
        rows = get_tasks_from_db("2026-04-02")
        return str(rows)

    except Exception as e:
        return str(e)
    
@app.route("/test-db")
def test_db():
    try:
        conn = get_db_connection()
        conn.close()
        return "Database connected successfully!"
    except Exception as e:
        return f"Database connection failed: {e}"
    
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")