# server.py (фикс: SHA-256 вместо bcrypt)
import os, sqlite3, datetime, hashlib
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel
import uvicorn

HOST = "0.0.0.0"
PORT = 8000
SECRET_KEY = "LOCAL_SCHEDULE_SECRET_KEY_REPLACE_ME"
TOKEN_EXPIRE_MINUTES = 480
SALT = "schedule_app_fixed_salt_v2"  # Соль для хеширования паролей

app = FastAPI(title="Schedule API v2")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
security = HTTPBearer()

def get_db():
    conn = sqlite3.connect("schedule.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, pwd_hash TEXT, role TEXT DEFAULT 'student');
            CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY, name TEXT UNIQUE);
            CREATE TABLE IF NOT EXISTS group_sched (id INTEGER PRIMARY KEY, grp TEXT, day TEXT, start_time TEXT, end_time TEXT, subj TEXT, teacher TEXT, room TEXT);
            CREATE TABLE IF NOT EXISTS teacher_sched (id INTEGER PRIMARY KEY, teacher TEXT, day TEXT, start_time TEXT, end_time TEXT, subj TEXT, grp TEXT, room TEXT);
            CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, date TEXT, name TEXT, desc TEXT);
        """)
init_db()

# 🔐 Простое хеширование: SHA-256 + соль
def hash_pwd(pwd: str) -> str:
    return hashlib.sha256((pwd + SALT).encode("utf-8")).hexdigest()

def make_token(user: str, role: str):
    exp = datetime.datetime.utcnow() + datetime.timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": user, "role": role, "exp": exp}, SECRET_KEY, algorithm="HS256")

def verify_token(auth: HTTPAuthorizationCredentials = Depends(security)):
    try:
        return jwt.decode(auth.credentials, SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")

class AuthIn(BaseModel): username: str; password: str; role: str = "student"
class ChangePwd(BaseModel): old_password: str; new_password: str
class Lesson(BaseModel): day: str; start_time: str; end_time: str; subj: str; teacher: str; room: str
class Event(BaseModel): date: str; name: str; desc: str

@app.post("/register")
def register(u: AuthIn, db=Depends(get_db)):
    if db.execute("SELECT 1 FROM users WHERE username=?", (u.username,)).fetchone():
        raise HTTPException(400, "User exists")
    # Хешируем пароль через SHA-256
    db.execute("INSERT INTO users (username, pwd_hash, role) VALUES (?,?,?)", 
               (u.username, hash_pwd(u.password), u.role))
    db.commit()
    return {"msg": "Registered"}

@app.post("/login")
def login(u: AuthIn, db=Depends(get_db)):
    row = db.execute("SELECT * FROM users WHERE username=?", (u.username,)).fetchone()
    # Сравниваем хеши
    if not row or row["pwd_hash"] != hash_pwd(u.password):
        raise HTTPException(401, "Wrong credentials")
    return {"token": make_token(row["username"], row["role"]), "role": row["role"]}

@app.post("/changepassword")
def change_pwd(data: ChangePwd, t: dict = Depends(verify_token), db=Depends(get_db)):
    row = db.execute("SELECT pwd_hash FROM users WHERE username=?", (t["sub"],)).fetchone()
    if not row or row["pwd_hash"] != hash_pwd(data.old_password):
        raise HTTPException(400, "Неверный старый пароль")
    if len(data.new_password) < 4:
        raise HTTPException(400, "Минимум 4 символа")
    db.execute("UPDATE users SET pwd_hash=? WHERE username=?", (hash_pwd(data.new_password), t["sub"]))
    db.commit()
    return {"msg": "Password changed"}

@app.get("/autocomplete")
def get_autocomplete(_=Depends(verify_token), db=Depends(get_db)):
    def col_vals(table, col):
        return list(set(r[col] for r in db.execute(f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL").fetchall() if r[col]))
    return {
        "teachers": col_vals("group_sched", "teacher"),
        "subjects": col_vals("group_sched", "subj"),
        "rooms": col_vals("group_sched", "room"),
        "groups": [r["name"] for r in db.execute("SELECT name FROM groups ORDER BY name").fetchall()]
    }

@app.get("/schedule/group/{name}")
def get_grp_sched(name: str, _=Depends(verify_token), db=Depends(get_db)):
    rows = db.execute("""SELECT id, day, start_time, end_time, subj, teacher, room FROM group_sched WHERE grp=? 
                         ORDER BY CASE day WHEN 'Пн' THEN 1 WHEN 'Вт' THEN 2 WHEN 'Ср' THEN 3 WHEN 'Чт' THEN 4 WHEN 'Пт' THEN 5 WHEN 'Сб' THEN 6 ELSE 7 END, start_time""", (name,)).fetchall()
    return [dict(r) for r in rows]

@app.post("/schedule/group/{name}")
def add_grp_lesson(name: str, le: Lesson, t=Depends(verify_token), db=Depends(get_db)):
    if t["role"] not in ("admin", "teacher"): raise HTTPException(403, "No permission")
    db.execute("INSERT INTO group_sched (grp, day, start_time, end_time, subj, teacher, room) VALUES (?,?,?,?,?,?,?)",
               (name, le.day, le.start_time, le.end_time, le.subj, le.teacher, le.room))
    db.commit()
    return {"msg": "Added"}

@app.delete("/schedule/group/{name}/{lid}")
def del_grp_lesson(name: str, lid: int, t=Depends(verify_token), db=Depends(get_db)):
    db.execute("DELETE FROM group_sched WHERE id=? AND grp=?", (lid, name))
    db.commit()
    return {"msg": "Deleted"}

@app.get("/events")
def get_events(_=Depends(verify_token), db=Depends(get_db)):
    return [dict(r) for r in db.execute("SELECT * FROM events ORDER BY date").fetchall()]

@app.post("/events")
def add_event(ev: Event, t=Depends(verify_token), db=Depends(get_db)):
    if t["role"] not in ("admin", "teacher"): raise HTTPException(403, "No permission")
    db.execute("INSERT INTO events (date, name, desc) VALUES (?,?,?)", (ev.date, ev.name, ev.desc))
    db.commit()
    return {"msg": "Added"}

@app.get("/schedule/teacher/{name}")
def get_teach_sched(name: str, _=Depends(verify_token), db=Depends(get_db)):
    rows = db.execute("""SELECT day, start_time, end_time, subj, grp as teacher, room FROM group_sched WHERE teacher=? 
                         ORDER BY CASE day WHEN 'Пн' THEN 1 WHEN 'Вт' THEN 2 WHEN 'Ср' THEN 3 WHEN 'Чт' THEN 4 WHEN 'Пт' THEN 5 WHEN 'Сб' THEN 6 ELSE 7 END, start_time""", (name,)).fetchall()
    return [dict(r) for r in rows]

if __name__ == "__main__":
    import sys, os
    # 🔧 Фикс PyInstaller: sys.stdout/stderr могут быть None
    if sys.stdout is None: sys.stdout = open(os.devnull, 'w')
    if sys.stderr is None: sys.stderr = open(os.devnull, 'w')

    print("[INFO] Initializing Schedule Server...")
    print(f"[SERVER] Running on: http://{HOST}:{PORT}")
    print(f"[DOCS]  API available at: http://127.0.0.1:{PORT}/docs")
    print("[READY] Press CTRL+C to stop")

    # 🔧 FIX: Передаём объект app напрямую, а не строку "server:app"
    # Это решает ошибку "Could not import module 'server'" в .exe
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
