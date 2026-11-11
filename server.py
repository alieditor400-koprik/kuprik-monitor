import argparse
import datetime as dt
import hashlib
import hmac
import json
import os
import time
from threading import Lock
import secrets
import sqlite3
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get("BRIDGE_DB", ROOT / "monitoring.sqlite3"))
CLOUD = os.environ.get("BRIDGE_HTTPS") == "1"
SESSIONS = {}
SESSION_LOCK = Lock()
SESSION_SECONDS = 12 * 60 * 60
COOKIE_FLAGS = "; Path=/; HttpOnly; SameSite=Strict" + ("; Secure" if CLOUD else "")
STATUSES = ("Yaxshi", "Kuzatuvda", "Jiddiy nuqson")
EVENTS = ("Tekshiruv", "Ta’mirlash", "Mustahkamlash", "Hodisa", "Diagnostika")

def connect():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init():
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS bridges (
            id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
            region TEXT NOT NULL, category TEXT NOT NULL, year INTEGER NOT NULL,
            lat REAL NOT NULL, lon REAL NOT NULL, length REAL,
            equipment INTEGER NOT NULL, online INTEGER NOT NULL,
            bim TEXT NOT NULL, bio TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS staff (
            username TEXT PRIMARY KEY, name TEXT NOT NULL, salt TEXT NOT NULL,
            digest TEXT NOT NULL, can_edit INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bridge_audit (
            id INTEGER PRIMARY KEY, bridge INTEGER NOT NULL REFERENCES bridges(id),
            action TEXT NOT NULL, username TEXT NOT NULL, name TEXT NOT NULL,
            changes TEXT NOT NULL, created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS bridge_audit_bridge ON bridge_audit(bridge,id);
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY, bridge INTEGER NOT NULL REFERENCES bridges(id),
            kind TEXT NOT NULL, day TEXT NOT NULL, author TEXT NOT NULL,
            status TEXT NOT NULL, element TEXT NOT NULL, notes TEXT NOT NULL,
            action TEXT NOT NULL, photo TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)

        conn.execute("BEGIN IMMEDIATE")
        additions = {
            "staff": {"department": "TEXT NOT NULL DEFAULT ''", "title": "TEXT NOT NULL DEFAULT ''",
                      "phone": "TEXT NOT NULL DEFAULT ''", "email": "TEXT NOT NULL DEFAULT ''"},
            "bridges": {"photo": "TEXT NOT NULL DEFAULT ''"},
            "events": {"account_username": "TEXT", "performed_at": "TEXT"},
        }
        for table, columns in additions.items():
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            for column, definition in columns.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

def field(data, key, required=True, limit=250):
    value = data.get(key, "")
    if not isinstance(value, str):
        raise ValueError("Matn maydonini tekshiring.")
    value = value.strip()
    if (required and not value) or len(value) > limit:
        raise ValueError("Majburiy maydonlarni va matn uzunligini tekshiring.")
    return value

def number(data, key, low, high, integer=False):
    value = (int if integer else float)(field(data, key))
    if not low <= value <= high:
        raise ValueError("Raqamli maydonlar chegarasini tekshiring.")
    return value

def password_digest(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600_000).hex()

def get_account(username, conn):
    row = conn.execute("SELECT * FROM staff WHERE username=?", (username,)).fetchone()
    if username in ACCOUNTS:
        base = ACCOUNTS[username]
        return {**base, "name": row["name"] if row else base["name"], "username": username, "can_edit": base["role"] == "admin" or bool(row and row["can_edit"])}
    return {**dict(row), "role": "inspector"} if row and row["salt"] else None

def staff_list(conn):
    managed = {row["username"]: dict(row) for row in
               conn.execute("SELECT username,name,can_edit,department,title,phone,email FROM staff ORDER BY name")}
    for username, user in ACCOUNTS.items():
        if user["role"] == "inspector":
            managed.setdefault(username, {"username": username, "name": user["name"], "can_edit": False})
    return [{**item, "role": "employee"} for item in managed.values()]

class App(BaseHTTPRequestHandler):
    def reply(self, code, content, mime="application/json; charset=utf-8", cookie=None):
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(content)

    def json(self, data, code=200, cookie=None):
        self.reply(code, json.dumps(data, ensure_ascii=False).encode(), cookie=cookie)

    def session_id(self):
        for item in self.headers.get("Cookie", "").split(";"):
            key, _, value = item.strip().partition("=")
            if key == "koprik":
                return value
        return ""

    def account(self, conn):
        with SESSION_LOCK:
            account = SESSIONS.get(self.session_id())
        if account and account[1] > time.monotonic():
            return get_account(account[0], conn)
        return None

    def do_GET(self):
        if self.path == "/":
            page = (ROOT / "app.html").read_text(encoding="utf-8-sig")
            self.reply(200, page.replace("MODE_PLACEHOLDER", "cloud" if "" not in ACCOUNTS else "local").encode(),
                       "text/html; charset=utf-8")
            return
        if self.path != "/api/data":
            self.json({"error": "Sahifa topilmadi."}, 404)
            return
        with connect() as conn:
            conn.execute("BEGIN")
            account = self.account(conn)
            bridges = [dict(row) for row in conn.execute("SELECT * FROM bridges ORDER BY name")]
            events = [dict(row) for row in conn.execute("SELECT * FROM events ORDER BY day DESC, id DESC")]
            for event in events:
                username = event.pop("account_username")
                event["account_verified"] = username is not None
            audit = [dict(row) for row in conn.execute("SELECT * FROM bridge_audit ORDER BY id DESC")]
            if account is None:
                for entry in audit:
                    entry.pop("username", None)
            staff = staff_list(conn) if account and account["role"] == "admin" else []
        profile = ({"role": account["role"], "name": account["name"] or "Administrator", "can_edit": bool(account["can_edit"])}
                   if account else {"role": "viewer", "name": "", "can_edit": False})
        self.json({"bridges": bridges, "events": events, "audit": audit, "staff": staff,
                   "profile": profile})

    def do_POST(self):
        try:
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.json({"error": "So‘rov formati xato."}, 415)
                return
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 1_600_000:
                self.json({"error": "So‘rov hajmi chegaradan oshdi."}, 413)
                return
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("So‘rov formati xato.")
            if self.path == "/api/login":
                username = field(data, "username", "" not in ACCOUNTS)
                supplied = field(data, "password")
                with connect() as conn:
                    user = get_account(username, conn)
                if user and "password" in user:
                    valid = hmac.compare_digest(supplied.encode(), user["password"].encode())
                elif user:
                    valid = hmac.compare_digest(password_digest(supplied, user["salt"]), user["digest"])
                else:
                    valid = False
                if not valid:
                    self.json({"error": "Login yoki kirish kodi xato."}, 401)
                    return
                now = time.monotonic()
                session = secrets.token_urlsafe(32)
                with SESSION_LOCK:
                    for key in tuple(SESSIONS):
                        if SESSIONS[key][1] <= now:
                            del SESSIONS[key]
                    SESSIONS.pop(self.session_id(), None)
                    SESSIONS[session] = (username, now + SESSION_SECONDS)
                self.json({}, cookie=f"koprik={session}; Max-Age={SESSION_SECONDS}" + COOKIE_FLAGS)
                return
            with connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                account = self.account(conn)
                if account is None:
                    self.json({"error": "Qaytadan kiring."}, 401)
                    return
                if self.path == "/api/logout":
                    with SESSION_LOCK:
                        SESSIONS.pop(self.session_id(), None)
                    self.json({}, cookie="koprik=; Max-Age=0" + COOKIE_FLAGS)
                    return
                if self.path == "/api/staff":
                    if account["role"] != "admin":
                        self.json({"error": "Bu amal uchun administrator huquqi kerak."}, 403)
                        return
                    username = field(data, "username", limit=80)
                    edit = data.get("can_edit")
                    if not isinstance(edit, bool):
                        raise ValueError("Ruxsat qiymati xato.")
                    operation = data.get("operation")
                    if operation in ("create", "profile"):
                        details = tuple(field(data, key, False) for key in ("department","title","phone","email"))
                        name = field(data,"name")
                    if operation == "create":
                        if username in ACCOUNTS:
                            raise ValueError("Login band.")
                        password = field(data, "password")
                        if len(password) < 16:
                            raise ValueError("Parol kamida 16 belgidan iborat bo‘lsin.")
                        salt = secrets.token_hex(16)
                        conn.execute("""INSERT INTO staff
                            (username,name,salt,digest,can_edit,department,title,phone,email)
                            VALUES (?,?,?,?,?,?,?,?,?)""",
                            (username,name,salt,password_digest(password,salt),edit,*details))
                    elif operation == "profile":
                        existing = get_account(username,conn)
                        if not existing or existing["role"] == "admin":
                            raise ValueError("Xodim topilmadi.")
                        conn.execute("""INSERT INTO staff
                            (username,name,salt,digest,can_edit,department,title,phone,email)
                            VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(username) DO UPDATE SET
                            name=excluded.name, department=excluded.department,title=excluded.title,
                            phone=excluded.phone,email=excluded.email""",
                            (username,name,"","",existing["can_edit"],*details))
                    elif operation == "access":
                        existing = get_account(username,conn)
                        if not existing or existing["role"] == "admin":
                            raise ValueError("Mutaxassis topilmadi.")
                        conn.execute("""INSERT INTO staff (username,name,salt,digest,can_edit) VALUES (?,?,?,?,?)
                            ON CONFLICT(username) DO UPDATE SET can_edit=excluded.can_edit""",
                            (username,existing["name"],"", "", edit))
                    else:
                        raise ValueError("Amal xato.")
                    result_id = username
                elif self.path == "/api/bridge":
                    if not account["can_edit"]:
                        self.json({"error": "Pasportni o‘zgartirishga ruxsat yo‘q."}, 403)
                        return
                    equipment = number(data, "equipment", 0, 100000, True)
                    bim = field(data, "bim", False, 1000)
                    if bim and not bim.startswith(("https://", "http://")):
                        raise ValueError("BIM havolasi http yoki https bilan boshlanishi kerak.")
                    values = (
                        field(data, "code"), field(data, "name"), field(data, "region"),
                        field(data, "category"), number(data, "year", 1, dt.date.today().year, True),
                        number(data, "lat", -85, 85), number(data, "lon", -180, 180),
                        number(data, "length", 0, 100000) if field(data, "length", False) else None,
                        equipment, number(data, "online", 0, equipment, True), bim,
                        field(data, "bio", False, 5000),
                    )
                    photo = field(data,"photo",False,1_500_000)
                    if photo and not photo.startswith("data:image/jpeg;base64,"):
                        raise ValueError("Rasm formati xato.")
                    remove_photo = data.get("remove_photo") is True
                    before = None
                    if data.get("id"):
                        bridge_id = number(data, "id", 1, 2**53-1, True)
                        before = conn.execute("SELECT * FROM bridges WHERE id=?", (bridge_id,)).fetchone()
                        result = conn.execute("""UPDATE bridges SET code=?,name=?,region=?,category=?,
                        year=?,lat=?,lon=?,length=?,equipment=?,online=?,bim=?,bio=? WHERE id=?""",
                                              (*values, bridge_id))
                        if not result.rowcount:
                            raise ValueError("Ko‘prik topilmadi.")
                    else:
                        bridge_id = conn.execute("INSERT INTO bridges (code,name,region,category,year,lat,lon,length,equipment,online,bim,bio) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", values).lastrowid
                    if photo or remove_photo:
                        conn.execute("UPDATE bridges SET photo=? WHERE id=?", (photo,bridge_id))
                    after = dict(conn.execute("SELECT * FROM bridges WHERE id=?", (bridge_id,)).fetchone())
                    if before is None:
                        changes = {}
                    else:
                        changes = {key: [before[key], value] for key, value in after.items() if before[key] != value}
                    if "photo" in changes:
                        changes["photo"] = ["Rasm mavjud" if value else "—" for value in changes["photo"]]
                    if before is None or changes:
                        conn.execute("""INSERT INTO bridge_audit (bridge,action,username,name,changes)
                            VALUES (?,?,?,?,?)""", (bridge_id, "create" if before is None else "update",
                            account["username"], account["name"] or "Administrator", json.dumps(changes,ensure_ascii=False)))
                    result_id = bridge_id
                elif self.path == "/api/event":
                    if not account["can_edit"]:
                        self.json({"error": "Jurnalga yozishga ruxsat yo‘q."}, 403)
                        return
                    kind = field(data, "kind")
                    status = field(data, "status", False)
                    if kind not in EVENTS or (status and status not in STATUSES) or (kind == "Tekshiruv" and not status):
                        raise ValueError("Yozuv turi va holatini tekshiring.")
                    day = dt.date.fromisoformat(field(data, "day")).isoformat()
                    performed = field(data,"performed_time",False)
                    if performed:
                        clock = dt.time.fromisoformat(performed)
                        if clock.tzinfo or clock.second or clock.microsecond:
                            raise ValueError("Tekshiruv vaqtini soat va daqiqada kiriting.")
                        performed = dt.datetime.combine(dt.date.fromisoformat(day),clock).isoformat(timespec="minutes")
                    if day > dt.date.today().isoformat():
                        raise ValueError("Kelajak sanasini kiritib bo‘lmaydi.")
                    photo = field(data, "photo", False, 1_500_000)
                    if photo and not photo.startswith("data:image/jpeg;base64,"):
                        raise ValueError("Rasm formati xato.")
                    result_id = conn.execute("""INSERT INTO events
                        (bridge,kind,day,author,status,element,notes,action,photo,account_username,performed_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (number(data, "bridge", 1, 2**53-1, True), kind, day,
                         (account["name"] or "Administrator"), status, field(data, "element", False),
                         field(data, "notes", True, 5000), field(data, "action", False, 3000), photo, account["username"], performed or None)).lastrowid
                else:
                    self.json({"error": "Sahifa topilmadi."}, 404)
                    return
            self.json({"id": result_id})
        except (ValueError, TypeError, OverflowError) as exc:
            self.json({"error": str(exc)}, 400)
        except sqlite3.IntegrityError:
            self.json({"error": "Kod yoki login band, yoxud ko‘prik topilmadi."}, 409)
        except sqlite3.Error:
            self.json({"error": "Bazaga yozishda xato. Qaytadan urinib ko‘ring."}, 503)

def main():
    global ACCOUNTS
    parser = argparse.ArgumentParser()
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    accounts_file = os.environ.get("BRIDGE_ACCOUNTS_FILE")
    if CLOUD and not accounts_file:
        parser.error("BRIDGE_ACCOUNTS_FILE kerak.")
    if accounts_file:
        raw = json.loads(Path(accounts_file).read_text(encoding="utf-8-sig"))
        if not isinstance(raw, list) or not raw:
            parser.error("Kamida bitta hisob kerak.")
        ACCOUNTS = {}
        for user in raw:
            username = user["username"].strip()
            if (not username or username in ACCOUNTS or len(username) > 250
                    or not user["name"].strip() or user["role"] not in ("admin", "inspector")
                    or not 16 <= len(user["password"]) <= 250):
                parser.error("Hisob ma’lumotlari xato. Parol 16–250 belgi bo‘lishi kerak.")
            ACCOUNTS[username] = user
        if not any(user["role"] == "admin" for user in ACCOUNTS.values()):
            parser.error("Administrator hisobi kerak.")
    else:
        password = secrets.token_hex(5)
        ACCOUNTS = {"": {"password": password, "role": "admin", "name": ""}}
    DB.parent.mkdir(parents=True, exist_ok=True)
    init()
    server = ThreadingHTTPServer(("0.0.0.0" if args.lan else "127.0.0.1", args.port), App)
    address = f"http://localhost:{args.port}"
    print(f"Ko‘prik monitoringi — {address}", flush=True)
    if "" in ACCOUNTS:
        print(f"Kirish kodi: {password}", flush=True)
    if args.lan:
        print(f"Telefon: shu Wi-Fi tarmog‘idagi kompyuterning IPv4 manzilini :{args.port} porti bilan oching.", flush=True)
    if not args.no_browser:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
