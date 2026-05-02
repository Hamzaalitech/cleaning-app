from flask import Flask, render_template, request, redirect, session
from datetime import datetime, timedelta
import json
import os
import time
from werkzeug.utils import secure_filename
import psycopg2
app = Flask(__name__)
app.secret_key = "change-this-to-a-long-random-secret-key"

APP_PIN = os.environ.get("APP_PIN", "36912")

MANAGER_WARNING_TASK = "__MANAGER_WARNING_STAMP__"

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

def get_manager_warning_stamp(date_key, area):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT comment FROM checklists WHERE date_key = %s AND task_name = %s AND area = %s LIMIT 1;",
            (date_key, MANAGER_WARNING_TASK, area)
        )

        row = cursor.fetchone()
        cursor.close()

        if row and row[0]:
            return row[0]

        return ""

    except Exception as e:
        print("GET MANAGER WARNING STAMP ERROR:", e)
        return ""


def set_manager_warning_stamp(date_key, area, message="CHECKLIST NOT USED - £10 FINE"):
    try:
        task = {
            "task": MANAGER_WARNING_TASK,
            "staff": "",
            "done": False,
            "task_time": "",
            "manager_check": "",
            "manager_time": "",
            "manager_check_date": None,
            "comment": message,
            "photo": ""
        }

        return upsert_task_to_db(date_key, task, area)

    except Exception as e:
        print("SET MANAGER WARNING STAMP ERROR:", e)
        return False

DEFAULT_TASKS = [
    "Cutlery",
    "Cutlery container - inside & out",
    "Ketchup / Mayo bottles & Inside lids",
    "Salt & Pepper shakers",
    "Waiter Station: Top surfaces, ramekin shelves",
    "Waiter Station: Storage shelves underneath",
    "Behind & under monitor and printer",
    "All baby chairs", 
    "Staircase: Steps, hoover & dry mop",
    "Staircase: Sides of steps",
    "All table tops",
    "Pull tables apart and wipe sides",
    "Base of tables",
    "Sofas: Top surfaces",
    "Sofas: Inside of grooves (joints between sofas) and gaps",
    "Chairs",
    "Planter(top & sides): Table 10",
    "Planter(top & sides): Table 19-20",
    "Planter(top & sides): Table 21-22",
    "Door leading to toilet",
    "Door leading to fire exit by T23",
    "Copper ledge above T23",
    "Dust pan and brush",
    "Hoover: All corners, sides & under staircase",
    "Hoover: Under table bases (move tables to one side)",
    "Mop: All areas including corners",
    "Mop: Under table bases (move tables to one side)",
    "Off: AC above T15",
    "Off: AC above T23",
    "Off: AC in grill section",
    "Off: AC in back section",
    "Off: Heater above T19",
    "Off: Heater above T21",
    "ROBOT: All surfaces",
    "Grill section cleaned, hoovered & mopped",
]

AREA_TASKS = {
    "main": DEFAULT_TASKS,
    "bar": [
    "Epos screen: including underneath and behind",
    "Till: including underneath and behind",
    "Printer",
    "Phone",
    "Card machine",
    "Blenders",
    "Area under & behind blender",
    "Ticket holder",
    "Sugar container",
    "Frappe powder tin",
    "Rubber mats",
    "Desserts freezer: all inner & outer areas",
    "Counter top",
    "Sink and surrounding area",
    "Tap",
    "Storage area under sink",
    "Orange juice machine",
    "Ice machine: outer surfaces",
    "Ice machine: inner surfaces",
    "Serving trays",
    "Drinks fridge: Doors-inside and out",
    "Drinks fridge: bottom shelves",
    "Drinks fridge: everything covered",
    "Drinks fridge: fill up all drinks",
    "Drinks seal machine, turn off, clean all surfaces",
    "Drinks seal machine, circular cup holding part",
    "Wipe & polish all drinking glasses",
    "Stainless steel surface including under drinks seal machine",
    "Switch off AC units above light switch",
    "Bin by till: empty out & put new bin bag, clean all surfaces",
    "Bin under counter: empty out & put new bin bag, clean all surfaces",
    "Mop & hoover whole area",
    "Mop & hoover under ice-machine"
    ],

    "upstairs": [
    "Maître D station including ledges",
    "Both phones",
    "Laptop including security strap",
    "Barriers including red rope",
    "Epos screen",
    "Printer",
    "Wipe down all stainless steel surfaces of bar",
    "Dumb waiter area",
    "Planter",
    "Tables",
    "Sofas including inside gaps/grooves",
    "Grooves of counter",
    "Shelf above sink",
    "Sink and surrounding area",
    "Taps",
    "Soap dispenser above sink",
    "Area below sink",
    "Black fridge: outer & inner surfaces",
    "OJ machine",
    "Blender",
    "Ice machine",
    "Grey fridge: outer & inner surfaces",
    "Drinks fridge: outer & inner surfaces",
    "Cutlery container",
    "All stainless-steel surfaces",
    "Bin-Inside & Out",
    "Hoover all areas including under table bases",
    "Hoover hotel reception",
    "Hoover store room",
    "Mop all areas including store room & reception"
    ],

    "back": [
    "Cutlery container - inside & out",
    "Ketchup / mayo bottles, including inside lids",
    "Salt & pepper shakers",
    "Waiter station: all top surfaces, tidy",
    "Waiter station: storage shelves underneath",
    "Monitor, including under & behind",
    "Printer, including under & behind",
    "All table tops",
    "Pull tables apart and wipe sides",
    "Base of tables",
    "Sofas: top surfaces",
    "Sofas: inside grooves (joints between sofas) and gaps",
    "Chairs",
    "Planter (top & sides): Table 28",
    "Planter (top & sides): Table 31",
    "Door leading to fire exit",
    "AC ledge above opposite T31",
    "Dustpan and brush",
    "Hoover, including corners",
    "Hoover: under table bases (move tables to one side)",
    "Mop: all areas, including corners",
    "Mop: under table bases (move tables to one side)",
    "AC above T30 (switch off)",
    "Bin: empty, replace bag, clean all surfaces"
    ],

    "grill": [
    "3 stainless-steel shelves, including under all objects and walls",
    "Probe wipes container",
    "Blue roll holder and surrounding stainless-steel area",
    "Fire blanket and surrounding stainless-steel area",
    "Gantry: 2 shelves",
    "Gantry: area around bulb, sides, and poles",
    "Bain Marie: all surfaces, including pots",
    "Chip scuttle",
    "Pull-out chips freezer",
    "Fryer baskets",
    "Fryer: clean oil surface and area just above oil",
    "Fryer: front and back surfaces",
    "Fryer: storage area below",
    "Montague: all outer surfaces, including control knobs",
    "Montague: area under grill bars",
    "Montague: drip trays, legs, and wheels",
    "Grill: grill bars",
    "Grill: exposed sides, drip trays, and control knobs",
    "Grill: storage area, legs, and wheels",
    "Table next to grill: top surface and shelves below",
    "Table next to grill: legs and wheels",
    "Canopy: front and sides",
    "Glass splash back: both sides, including brackets",
    "Tabletop meat fridge, including containers and lids",
    "Shelves above fridge",
    "Both ticket holders",
    "Adande meat fridge, including inside both drawers",
    "Plate warmer",
    "Bun toaster, including crumb tray and control knobs",
    "Salad display and surrounding area",
    "Plate shelves, including legs",
    "Alto-Shaam grill side: all surfaces, including inside door and wheels",
    "Utensil holders",
    "Bin",
    "Oil tray ceiling: remove oil and clean",
    "Sweep all areas, including deep under machinery",
    "Mop all areas, including deep under machinery"
    ],

    "back_kitchen": [
    "Door leading to till area: both sides",
    "Fire extinguisher",
    "Fire blanket and surrounding area",
    "Ticket holder and surrounding area",
    "Dumb waiter",
    "Mobile shelves below, including legs and wheels",
    "Stainless-steel doors",
    "Blue roll holder and surrounding area",
    "Microwaves",
    "Shelf above microwave, including sides and legs",
    "Canopy control and socket above",
    "Knives and knife holder",
    "Countertop fridge",
    "Area either side of countertop fridge, including under crockery",
    "Pull-out fridge",
    "Pull-out freezer",
    "Small sink, including taps and surrounding area",
    "Small sink: area below, including legs and waste pipe",
    "Tin opener",
    "Bin",
    "Cooker, including splash back and vent",
    "Cooker: storage area below, legs, and base of legs",
    "Shelf above cooker",
    "Fryer baskets",
    "Fryer: clean oil surface and area just above oil",
    "Fryer: front and back surfaces",
    "Fryer: storage area below",
    "Combi: door, including inside surfaces",
    "Combi: area under",
    "Combi: top and side surfaces",
    "Combi: use cleaning tablets to clean inside, guided by combi system",
    "Pull-out fridges below combi",
    "Pull-out freezers below combi, including legs"
    ],

    "dishwasher": [
    "Stainless-steel dishwasher rack area, including frame and legs",
    "Dishwasher, including inner components",
    "Dishwasher: legs and frame",
    "Sink and surrounding area, including splash back",
    "Storage area under sink, including stainless-steel backing, frames, and legs",
    "Taps and sprayer",
    "Stainless-steel shelves, including brackets and walls",
    "Control switch above",
    "Set-down table, including shelves below and legs",

    "Door leading to toilets",

    "White fridge and freezer door",
    "Front side of cold room only",
    "Put all washed items back in their original places",
    "Black mats",
    "Bin",
    "Sweep all areas, including deep under machinery",
    "Mop all areas, including deep under machinery"
    ],

    "toilet": [
    "Hallway: all doors, including fire exit, handles",
    "Each toilet: Sink",
    "Taps",
    "Drain out the water from the sides of the tap area",
    "Soap dispenser including filling with liquid",
    "Ceiling light, extractor, fire alarm",
    "Mirror",
    "Baby changer",
    "Hand dryer",
    "Bin",
    "Sanitary towel bins (don’t empty)",
    "Toilet roll holder- including fill up with toilet roll",
    "Toilet seat",
    "Toilet basin",
    "Toilet flush and the back wall",
    "Sweep- all areas including corners",
    "Mop- all areas including corners",
    "Sweep & mop fire exit"
    ],

}

def get_task_names_for_area(area):
    return AREA_TASKS.get(area, DEFAULT_TASKS)

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
    for storage_key in all_tasks.keys():
        try:
            date_part = storage_key.split("__")[0]
            date_obj = datetime.strptime(date_part, "%Y-%m-%d")
            valid_dates.append((date_obj, storage_key))
        except ValueError:
            continue

    valid_dates.sort(reverse=True)
    keep_keys = {key for _, key in valid_dates[:28]}

    all_tasks = {
        key: tasks
        for key, tasks in all_tasks.items()
        if key in keep_keys
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

def get_tasks_for_date(date_key, area="main"):
    base_tasks = build_tasks(get_task_names_for_area(area))
    db_tasks = get_tasks_from_db(date_key, area)
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
                task["issue_rectified"] = saved_task.get("issue_rectified", False)

        return base_tasks
    
    return base_tasks

def get_weekly_tasks(week_key, area):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT task_name, responsible, staff_photo, done, manager_check, manager_photo
            FROM weekly_checklists
            WHERE week_key = %s AND area = %s
            ORDER BY id ASC
        """, (week_key, area))

        rows = cur.fetchall()

        tasks = []
        for row in rows:
            tasks.append({
                "task_name": row[0],
                "responsible": row[1],
                "staff_photo": row[2],
                "done": row[3],
                "manager_check": row[4],
                "manager_photo": row[5],
            })

        return tasks

    except Exception as e:
        print("GET WEEKLY TASKS ERROR:", e)
        return []
    
def get_current_week_key():
    from datetime import datetime
    year, week, _ = datetime.now().isocalendar()
    return f"{year}-W{week}"

def initialize_week_if_empty(week_key, area):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if any rows already exist
        cur.execute("""
            SELECT 1 FROM weekly_checklists
            WHERE week_key = %s AND area = %s
            LIMIT 1
        """, (week_key, area))

        exists = cur.fetchone()

        if exists:
            return  # already initialized

        # Get base tasks (same as daily)
        base_tasks = build_tasks(get_task_names_for_area(area))

        for task in base_tasks:
            cur.execute("""
                INSERT INTO weekly_checklists (week_key, area, task_name)
                VALUES (%s, %s, %s)
            """, (week_key, area, task["task"]))

        conn.commit()

    except Exception as e:
        print("INITIALIZE WEEK ERROR:", e)

def get_tasks_from_db(date_key, area):
    read_start = time.time()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT task_name, staff_name, done, task_time, manager_check, manager_time, manager_check_date, comment, photo, issue_rectified FROM checklists WHERE date_key = %s AND area = %s;",
            (date_key, area)
        )

        rows = cursor.fetchall()
        read_end = time.time()
        print("DB READ TIME:", read_end - read_start)
        
        cursor.close()

        tasks = []
        for row in rows:
            if row[0] == MANAGER_WARNING_TASK:
                continue

            tasks.append({
                "task": row[0],
                "staff": row[1] or "",
                "done": row[2],
                "task_time": row[3] or "",
                "manager_check": row[4] or "",
                "manager_time": row[5] or "",
                "manager_check_date": row[6] if row[6] else None,
                "comment": row[7] or "",
                "photo": row[8] or "",
                "issue_rectified": row[9] if row[9] is not None else False
            })

        return tasks

    except Exception as e:
        print("DB READ ERROR:", e)
        return []
    
def upsert_task_to_db(date_key, task, area):
    db_start = time.time()
    print("UPSERT CALLED:", date_key, task)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO checklists
            (task_name, staff_name, done, task_time, manager_check, manager_time, manager_check_date, comment, photo, date_key, area, issue_rectified)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            comment = EXCLUDED.comment,
            photo = EXCLUDED.photo,
            area = EXCLUDED.area,
            issue_rectified = EXCLUDED.issue_rectified;
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
                date_key,
                area,
                task.get("issue_rectified", False)
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
        
@app.route("/pin", methods=["GET", "POST"])
def pin_entry():
    error = ""

    if request.method == "POST":
        entered_pin = request.form.get("pin", "").strip()

        if entered_pin == APP_PIN:
            session["pin_unlocked"] = True
            return redirect("/select-area")
        else:
            error = "Incorrect PIN"

    return render_template("pin.html", error=error)

@app.route("/select-area")
def select_area():
    if not session.get("pin_unlocked"):
        return redirect("/pin")

    return render_template("select_area.html")

@app.route("/weekly-select-area")
def weekly_select_area():
    if not session.get("pin_unlocked"):
        return redirect("/pin")

    return render_template("weekly_select_area.html")

@app.route("/weekly")
def weekly_home():
    if not session.get("pin_unlocked"):
        return redirect("/pin")

    area = request.args.get("area", "").strip().lower()

    if not area:
        return redirect("/weekly?area=main")

    week_key = get_current_week_key()

    initialize_week_if_empty(week_key, area)

    tasks = get_weekly_tasks(week_key, area)
    
    return render_template(
    "weekly.html",
    area=area,
    week_key=week_key,
    tasks=tasks
)

@app.route("/lock")
def lock_app():
    print("LOCK BEFORE:", dict(session))
    session.pop("pin_unlocked", None)
    print("LOCK AFTER:", dict(session))
    return redirect("/pin")

@app.route("/lock-session", methods=["POST"])
def lock_session():
    session.pop("pin_unlocked", None)
    return ("", 204)

@app.route("/")
def home():
    print("HOME SESSION:", dict(session))
    if not session.get("pin_unlocked"):
        return redirect("/pin")
    area = request.args.get("area", "").strip().lower()

    if area not in ["main", "bar", "upstairs", "back", "grill", "back_kitchen", "dishwasher", "toilet"]:
        return redirect("/?area=main")
    
    date_param = request.args.get("date", "").strip()
    
    if is_valid_date_key(date_param):
        date_key = date_param
    else:
        date_key = get_current_date_key()

    selected_date_obj = datetime.strptime(date_key, "%Y-%m-%d")
    previous_date = (selected_date_obj - timedelta(days=1)).strftime("%Y-%m-%d")
    warning_stamp = get_manager_warning_stamp(date_key, area)

    current_date_key = get_current_date_key()
    if date_key < current_date_key:
        next_date = (selected_date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        next_date = None

    tasks = get_tasks_for_date(date_key, area)

    yesterday_tasks = get_tasks_for_date(previous_date, area)
    yesterday_issues = [
        {
            "task": item.get("task") or item.get("task_name"),
            "comment": item.get("comment", ""),
            "photo": item.get("photo", ""),
            "issue_rectified": item.get("issue_rectified", False)
        }
    for item in yesterday_tasks
    if item.get("manager_check") == "not_cleaned"
    ]
    dates = [item["manager_check_date"] for item in tasks if item.get("manager_check_date")]

    if dates:
        latest_date = max(dates)

        if isinstance(latest_date, str):
            latest_date = datetime.strptime(latest_date, "%Y-%m-%d")

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
        yesterday_issues=yesterday_issues,
        staff_names=staff_names,
        warning_stamp=warning_stamp,
        area=area,
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
    area = request.form.get("area", "main").strip().lower()
    unlock_code = request.form.get("unlock_code", "").strip()

    if not is_valid_date_key(date_key):
        date_key = get_current_date_key()

    # LOCKED CASE
    if is_past_date_locked(date_key, unlock_code):
        tasks = get_tasks_for_date(date_key, area)
        for item in tasks:
            if item["task"] == task_name:
                return {
                    "staff": item["staff"],
                    "task_time": item["task_time"]
                }
        return {"staff": "", "task_time": ""}

    # NORMAL CASE
    tasks = get_tasks_for_date(date_key, area)
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
            "photo": "",
            "issue_rectified": False
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

    upsert_task_to_db(date_key, item, area)

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
    area = request.form.get("area", "main").strip().lower()
    unlock_code = request.form.get("unlock_code", "").strip()

    if not is_valid_date_key(date_key):
        date_key = get_current_date_key()

    if is_past_date_locked(date_key, unlock_code):
        tasks = get_tasks_for_date(date_key, area)
        for item in tasks:
            if item["task"] == task_name:
                return {
                    "manager_check": item["manager_check"],
                    "manager_time": item["manager_time"]
                }
        return {"manager_check": "", "manager_time": ""}

    tasks = get_tasks_for_date(date_key, area)
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

    upsert_task_to_db(date_key, item, area)

    return {
        "manager_check": item["manager_check"],
        "manager_time": item["manager_time"],
        "manager_check_date": datetime.now().strftime("%d %B")
    }

@app.route("/weekly-done", methods=["POST"])
def weekly_done():
    if not session.get("pin_unlocked"):
        return {"success": False, "message": "Locked"}, 403

    task_name = request.form.get("task", "").strip()
    area = request.form.get("area", "").strip().lower()
    week_key = get_current_week_key()

    if not task_name or not area:
        return {"success": False, "message": "Missing data"}, 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        done_value = request.form.get("done", "false") == "true"

        if done_value:
            cur.execute("""
                UPDATE weekly_checklists
                SET done = TRUE,
                    done_time = NOW(),
                    updated_at = NOW()
                WHERE week_key = %s
                AND area = %s
                AND task_name = %s
            """, (week_key, area, task_name))
        else:
            cur.execute("""
                UPDATE weekly_checklists
                SET done = FALSE,
                    done_time = NULL,
                    updated_at = NOW()
                WHERE week_key = %s
                AND area = %s
                AND task_name = %s
            """, (week_key, area, task_name))

        conn.commit()

        return {"success": True}

    except Exception as e:
        print("WEEKLY DONE ERROR:", e)
        return {"success": False, "message": "Server error"}, 500

@app.route("/weekly-upload-staff-photo", methods=["POST"])
def weekly_upload_staff_photo():
    if not session.get("pin_unlocked"):
        return {"success": False, "message": "Locked"}, 403

    task_name = request.form.get("task", "").strip()
    area = request.form.get("area", "").strip().lower()
    photo = request.files.get("photo")
    week_key = get_current_week_key()

    if not task_name or not area:
        return {"success": False, "message": "Missing data"}, 400

    if not photo or photo.filename == "":
        return {"success": False, "message": "No file"}, 400

    if not allowed_file(photo.filename):
        return {"success": False, "message": "Invalid file type"}, 400

    try:
        from werkzeug.utils import secure_filename
        import os
        from datetime import datetime

        conn = get_db_connection()
        cur = conn.cursor()

        # Create safe filename
        original_name = secure_filename(photo.filename)
        extension = original_name.rsplit(".", 1)[1].lower()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        safe_task = secure_filename(task_name).replace("-", "_")

        filename = f"{week_key}_{safe_task}_{timestamp}.{extension}"
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

        photo.save(file_path)

        cur.execute("""
            UPDATE weekly_checklists
            SET staff_photo = %s,
                staff_photo_time = NOW(),
                updated_at = NOW()
            WHERE week_key = %s
              AND area = %s
              AND task_name = %s
        """, (filename, week_key, area, task_name))

        conn.commit()

        return {"success": True, "photo": filename}

    except Exception as e:
        print("WEEKLY STAFF PHOTO ERROR:", e)
        return {"success": False, "message": "Server error"}, 500

@app.route("/weekly-delete-staff-photo", methods=["POST"])
def weekly_delete_staff_photo():
    if not session.get("pin_unlocked"):
        return {"success": False}, 403

    data = request.get_json()
    task_name = data.get("task", "").strip()
    area = data.get("area", "").strip().lower()
    week_key = get_current_week_key()

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            UPDATE weekly_checklists
            SET staff_photo = NULL,
                staff_photo_time = NULL,
                updated_at = NOW()
            WHERE week_key = %s
              AND area = %s
              AND task_name = %s
        """, (week_key, area, task_name))

        conn.commit()

        return {"success": True}

    except Exception as e:
        print("WEEKLY DELETE PHOTO ERROR:", e)
        return {"success": False}, 500

@app.route("/rectify-issue", methods=["POST"])
def rectify_issue():
    data = request.get_json()

    task_name = data.get("task")
    date_key = data.get("date", "").strip()
    area = data.get("area", "main").strip().lower()

    if not task_name or not is_valid_date_key(date_key):
        return {"success": False, "error": "Invalid task or date"}, 400

    tasks = get_tasks_for_date(date_key, area)
    item = next((t for t in tasks if t["task"] == task_name), None)

    if not item:
        return {"success": False, "error": "Task not found"}, 404

    item["issue_rectified"] = True
    upsert_task_to_db(date_key, item, area)

    return {"success": True}

@app.route("/set-warning-stamp", methods=["POST"])
def set_warning_stamp():
    date_key = request.form.get("date", "").strip()
    area = request.form.get("area", "main").strip().lower()

    if not is_valid_date_key(date_key):
        date_key = get_current_date_key()

    set_manager_warning_stamp(date_key, area)
    return redirect(f"/?date={date_key}&area={area}")

@app.route("/upload-photo", methods=["POST"])
def upload_photo():
    task_name = request.form.get("task", "").strip()
    date_key = request.form.get("date", "").strip()
    area = request.form.get("area", "main").strip().lower()
    print("UPLOAD AREA:", area)
    unlock_code = request.form.get("unlock_code", "").strip()
    photo = request.files.get("photo")

    if not is_valid_date_key(date_key):
        date_key = get_current_date_key()

    if is_past_date_locked(date_key, unlock_code):
        tasks = get_tasks_for_date(date_key, area)
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

    tasks = get_tasks_for_date(date_key, area)
    print("UPLOAD TASK:", task_name)
    print("AVAILABLE TASKS:", [t["task"] for t in tasks])

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
            upsert_task_to_db(date_key, item, area)
            save_all_tasks()

            return {
                "success": True,
                "photo": item["photo"]
            }

    return {"success": False, "photo": "", "message": "Task not found"}, 404

@app.route("/delete-photo", methods=["POST"])
def delete_photo():
    task = request.form.get("task", "")
    area = request.form.get("area", "main").strip().lower()
    date_key = request.form.get("date", "")
    unlock_code = request.form.get("unlock_code", "")

    if not is_valid_date_key(date_key):
        return {"success": False}, 400

    if is_past_date_locked(date_key, unlock_code):
        return {"success": False}, 403

    tasks = get_tasks_for_date(date_key, area)

    for item in tasks:
        if item["task"] == task and item.get("photo"):
            photo_filename = item["photo"]

            try:
                import os
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], photo_filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass

            item["photo"] = ""

            upsert_task_to_db(date_key, item, area)
            save_all_tasks()

            return {"success": True}

    return {"success": False}

@app.route("/test-data")
def test_data():
    try:
        rows = get_tasks_from_db("2026-04-02")
        return str(rows)

    except Exception as e:
        return str(e)

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route("/comment", methods=["POST"])
def save_comment():
    task_name = request.form.get("task")
    comment = request.form.get("comment", "").strip()
    date_key = request.form.get("date", "").strip()
    area = request.form.get("area", "main").strip().lower()
    unlock_code = request.form.get("unlock_code", "").strip()

    if not is_valid_date_key(date_key):
        date_key = get_current_date_key()

    if is_past_date_locked(date_key, unlock_code):
        tasks = get_tasks_for_date(date_key, area)
        for item in tasks:
            if item["task"] == task_name:
                return {"comment": item["comment"]}
        return {"comment": ""}

    tasks = get_tasks_for_date(date_key, area)
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

    upsert_task_to_db(date_key, item, area)

    return {"comment": item["comment"]}
       
@app.route("/photo-checklist")
def photo_checklist():
    return render_template("photo_checklist.html")

@app.route("/test-db")
def test_db():
    try:
        conn = get_db_connection()
        conn.close()
        return "Database connected successfully!"
    except Exception as e:
        return f"Database connection failed: {e}"

# ══════════════════════════════════════
# SGW NEW ROUTES — photo checklist system
# ══════════════════════════════════════

@app.route("/sgw/checklist")
def sgw_checklist():
    if not session.get("pin_unlocked"):
        return redirect("/pin")
    area = request.args.get("area", "main").strip().lower()
    return render_template("sgw_checklist.html", area=area)

@app.route("/sgw/load")
def sgw_load():
    if not session.get("pin_unlocked"):
        return {"error": "locked"}, 403
    area = request.args.get("area", "main").strip().lower()
    date_key = request.args.get("date", "").strip()
    if not is_valid_date_key(date_key):
        date_key = get_current_date_key()
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT task_name, done, done_ts, done_by, mgr, mgr_ts, mgr_comment, photo_path
            FROM sgw_checklists
            WHERE area = %s AND date_key = %s
        """, (area, date_key))
        rows = cur.fetchall()
        cur.close()
        data = {}
        for row in rows:
            data[row[0]] = {
                "done": row[1],
                "done_ts": row[2] or "",
                "done_by": row[3] or "",
                "mgr": row[4],
                "mgr_ts": row[5] or "",
                "mgr_comment": row[6] or "",
                "photo_path": row[7] or ""
            }
        return {"date_key": date_key, "tasks": data}
    except Exception as e:
        print("SGW LOAD ERROR:", e)
        return {"error": str(e)}, 500

@app.route("/sgw/done", methods=["POST"])
def sgw_done():
    if not session.get("pin_unlocked"):
        return {"error": "locked"}, 403
    data = request.get_json()
    area = data.get("area", "main")
    date_key = data.get("date_key", get_current_date_key())
    task_name = data.get("task_name")
    done = data.get("done", False)
    done_ts = data.get("done_ts", "")
    done_by = data.get("done_by", "")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sgw_checklists (area, date_key, task_name, done, done_ts, done_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (area, date_key, task_name)
            DO UPDATE SET done = EXCLUDED.done, done_ts = EXCLUDED.done_ts, done_by = EXCLUDED.done_by
        """, (area, date_key, task_name, done, done_ts, done_by))
        conn.commit()
        cur.close()
        return {"success": True}
    except Exception as e:
        print("SGW DONE ERROR:", e)
        return {"error": str(e)}, 500

@app.route("/sgw/manager", methods=["POST"])
def sgw_manager():
    if not session.get("pin_unlocked"):
        return {"error": "locked"}, 403
    data = request.get_json()
    area = data.get("area", "main")
    date_key = data.get("date_key", get_current_date_key())
    task_name = data.get("task_name")
    mgr = data.get("mgr")        # will be True, False, or None
    mgr_ts = data.get("mgr_ts", "")

    # Convert to string for TEXT column
    if mgr is True:
        mgr_val = "true"
    elif mgr is False:
        mgr_val = "false"
    else:
        mgr_val = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sgw_checklists (area, date_key, task_name, mgr, mgr_ts)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (area, date_key, task_name)
            DO UPDATE SET mgr = EXCLUDED.mgr, mgr_ts = EXCLUDED.mgr_ts
        """, (area, date_key, task_name, mgr_val, mgr_ts))
        conn.commit()
        cur.close()
        return {"success": True}
    except Exception as e:
        print("SGW MANAGER ERROR:", e)
        return {"error": str(e)}, 500

@app.route("/sgw/comment", methods=["POST"])
def sgw_comment():
    if not session.get("pin_unlocked"):
        return {"error": "locked"}, 403
    data = request.get_json()
    area = data.get("area", "main")
    date_key = data.get("date_key", get_current_date_key())
    task_name = data.get("task_name")
    mgr_comment = data.get("mgr_comment", "")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sgw_checklists (area, date_key, task_name, mgr_comment)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (area, date_key, task_name)
            DO UPDATE SET mgr_comment = EXCLUDED.mgr_comment
        """, (area, date_key, task_name, mgr_comment))
        conn.commit()
        cur.close()
        return {"success": True}
    except Exception as e:
        print("SGW COMMENT ERROR:", e)
        return {"error": str(e)}, 500

def _init_db_schema():
    try:
        c = get_db_connection()
        cur = c.cursor()
        cur.execute("ALTER TABLE sgw_pin_positions ADD COLUMN IF NOT EXISTS w INTEGER")
        cur.execute("ALTER TABLE sgw_pin_positions ADD COLUMN IF NOT EXISTS side TEXT")
        c.commit()
        cur.close()
        print("DB SCHEMA INIT OK")
    except Exception as e:
        try:
            get_db_connection().rollback()
        except Exception:
            pass
        print("DB SCHEMA INIT ERROR:", e)

_init_db_schema()

@app.route("/sgw/positions")
def sgw_positions_load():
    area = request.args.get("area", "main").strip().lower()
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT task_id, x, y, w, side FROM sgw_pin_positions WHERE area = %s", (area,))
        rows = cur.fetchall()
        cur.close()
        positions = {}
        for row in rows:
            entry = {"x": row[1], "y": row[2]}
            if row[3] is not None:
                entry["w"] = row[3]
            if row[4] is not None:
                entry["side"] = row[4]
            positions[row[0]] = entry
        return {"positions": positions}
    except Exception as e:
        try:
            get_db_connection().rollback()
        except Exception:
            pass
        print("SGW POSITIONS LOAD ERROR:", e)
        return {"error": str(e)}, 500

@app.route("/sgw/positions", methods=["POST"])
def sgw_positions_save():
    if not session.get("pin_unlocked"):
        return {"error": "locked"}, 403
    data = request.get_json()
    area = data.get("area", "main")
    task_id = data.get("task_id")
    x = data.get("x")
    y = data.get("y")
    w = data.get("w")
    side = data.get("side")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sgw_pin_positions (area, task_id, x, y, w, side)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (area, task_id)
            DO UPDATE SET x = EXCLUDED.x, y = EXCLUDED.y,
                          w = COALESCE(EXCLUDED.w, sgw_pin_positions.w),
                          side = COALESCE(EXCLUDED.side, sgw_pin_positions.side)
        """, (area, task_id, x, y, w, side))
        conn.commit()
        cur.close()
        return {"success": True}
    except Exception as e:
        try:
            get_db_connection().rollback()
        except Exception:
            pass
        print("SGW POSITIONS SAVE ERROR:", e)
        return {"error": str(e)}, 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")

