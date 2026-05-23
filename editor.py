import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
import requests, threading, datetime, os, json, hashlib
from fpdf import FPDF

# ─── КОНФИГ ───
SERVER_IP = "127.0.0.1"
API = f"http://{SERVER_IP}:8000"
session = requests.Session()
token_headers = {}

# 🎨 ЦВЕТА И ШРИФТЫ
BG, SURFACE, ACCENT, TXT = "#0d1117", "#161b22", "#58a6ff", "#c9d1d9"
FONT, HDR = ("Consolas", 10), ("Consolas", 11, "bold")

# ─── УТИЛИТЫ ───
class AutocompleteCombobox(ttk.Combobox):
    def __init__(self, master, values=None, **kwargs):
        super().__init__(master, values=list(values or []), **kwargs)
        self._all = list(values or [])
        self.bind("<KeyRelease>", self._filter)
        self.bind("<FocusIn>", lambda e: self.config(values=self._all))
    def set_values(self, vals):
        self._all = list(vals)
        self.config(values=self._all)
    def _filter(self, e=None):
        typed = self.get().lower()
        self.config(values=[v for v in self._all if typed in v.lower()])

def apply_theme(r):
    r.configure(bg=BG)
    s = ttk.Style(); s.theme_use('clam')
    s.configure('.', background=BG, foreground=TXT, font=FONT)
    s.configure('TNotebook', background=BG)
    s.configure('TNotebook.Tab', background=SURFACE, foreground=TXT, padding=(12,6))
    s.configure('TButton', background='#21262d', foreground=ACCENT, font=FONT, padding=(8,4))
    s.configure('Treeview', background='#010409', foreground=TXT, fieldbackground='#010409', font=FONT)
    s.configure('Treeview.Heading', background=SURFACE, foreground=ACCENT, font=HDR)
    s.configure('TCombobox', background=SURFACE, foreground=TXT, fieldbackground=SURFACE, font=FONT)

class Toast:
    def __init__(self, parent, title, msg, color=ACCENT):
        self.win = tk.Toplevel(parent)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=SURFACE, highlightbackground=ACCENT, highlightthickness=1)
        w, h = 320, 70
        x = parent.winfo_rootx() + parent.winfo_width() - w - 20
        y = parent.winfo_rooty() + parent.winfo_height() - h - 60
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        tk.Label(self.win, text=f"🔔 {title}", bg=SURFACE, fg=color, font=HDR).pack(anchor='w', padx=10, pady=(8,0))
        tk.Label(self.win, text=msg, bg=SURFACE, fg=TXT, font=FONT).pack(anchor='w', padx=10, pady=(0,8))
        self.win.after(4000, self.win.destroy)

class ChangePwdDialog:
    def __init__(self, master):
        self.win = tk.Toplevel(master)
        self.win.title("Смена пароля")
        self.win.geometry("280x180")
        self.win.configure(bg=BG)
        self.win.resizable(False, False)
        self.win.transient(master)
        self.win.grab_set()
        frm = tk.Frame(self.win, bg=BG)
        frm.pack(fill='x', padx=20, pady=10)
        for i, lbl in enumerate(["Старый:", "Новый:", "Повтор:"]):
            tk.Label(frm, text=lbl, bg=BG, fg=TXT).grid(row=i, column=0, sticky='w')
        self.old = tk.Entry(frm, bg=SURFACE, fg=TXT, show='*'); self.old.grid(row=0, column=1, padx=5)
        self.new = tk.Entry(frm, bg=SURFACE, fg=TXT, show='*'); self.new.grid(row=1, column=1, padx=5)
        self.conf = tk.Entry(frm, bg=SURFACE, fg=TXT, show='*'); self.conf.grid(row=2, column=1, padx=5)
        tk.Button(self.win, text="СОХРАНИТЬ", command=self._change, bg=ACCENT, fg=BG, font=HDR).pack(fill='x', padx=20, pady=10)

    def _change(self):
        if self.new.get() != self.conf.get():
            return messagebox.showwarning("Ошибка", "Пароли не совпадают", parent=self.win)
        if len(self.new.get()) < 4:
            return messagebox.showwarning("Ошибка", "Минимум 4 символа", parent=self.win)
        old_p, new_p = self.old.get(), self.new.get()
        def _run():
            try:
                r = session.post(f"{API}/changepassword", json={"old_password": old_p, "new_password": new_p}, headers=token_headers, timeout=5)
                if r.ok:
                    self.win.after(0, lambda: [messagebox.showinfo("Успех", "Пароль изменён", parent=self.win), self.win.destroy()])
                else:
                    self.win.after(0, lambda: messagebox.showerror("Ошибка", r.json().get("detail", "Ошибка"), parent=self.win))
            except Exception as e:
                self.win.after(0, lambda: messagebox.showerror("Сеть", str(e), parent=self.win))
        threading.Thread(target=_run, daemon=True).start()

def export_pdf(rows, grp):
    if not rows: return messagebox.showwarning("Внимание", "Расписание пусто.")
    pdf = FPDF(); pdf.set_auto_page_break(auto=True, margin=15); pdf.add_page()
    font = None
    for p in [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\consola.ttf"]:
        if os.path.exists(p): font = p; break
    if not font: return messagebox.showerror("Ошибка", "Шрифт не найден.")
    pdf.add_font("Main", "", font, uni=True); pdf.add_font("Main", "B", font, uni=True)
    pdf.set_font("Main", "B", 16); pdf.cell(0, 10, f"Расписание: {grp}", align="C"); pdf.ln(10)
    pdf.set_font("Main", size=10); pdf.cell(0, 5, f"Дата: {datetime.datetime.now().strftime('%d.%m.%Y')}", align="C"); pdf.ln(10)
    headers = ["День", "Начало", "Конец", "Предмет", "Преподаватель", "Аудитория"]; widths = [18, 20, 20, 45, 55, 25]
    pdf.set_font("Main", "B", 9)
    for w, h in zip(widths, headers): pdf.cell(w, 7, h, border=1, align="C")
    pdf.ln(); pdf.set_font("Main", size=8)
    for r in rows:
        vals = [r.get("day",""), r.get("start_time",""), r.get("end_time",""), r.get("subj",""), r.get("teacher",""), r.get("room","")]
        for w, v in zip(widths, vals):
            v = (str(v)[:22]+"..") if len(str(v))>22 else str(v)
            pdf.cell(w, 7, v, border=1)
        pdf.ln()
    path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF","*.pdf")], initialfilename=f"Расписание_{grp}.pdf")
    if path: 
        pdf.output(path)
        messagebox.showinfo("Готово", f"Сохранено:\n{path}")

# ─── ОСНОВНОЙ РЕДАКТОР ───
# ─── ЗАМЕНИ ВЕСЬ КЛАСС Editor НА ЭТОТ ───
class Editor:
    def __init__(self, root, user):
        self.root = root; self.user = user
        self.cache = {"events": None, "sched": None}
        root.title(f"✎ Editor [v2] | {user['user']}")
        root.update_idletasks()  # Гарантируем отрисовку
        
        # Верхняя панель
        bar = tk.Frame(root, bg=SURFACE, height=30); bar.pack(fill='x')
        tk.Label(bar, text=f"👤 {user['user']} | 🎭 {user['role']}", bg=SURFACE, fg=TXT, font=FONT).pack(side='left', padx=10, pady=3)
        ttk.Button(bar, text="🔑 Пароль", command=lambda: ChangePwdDialog(root)).pack(side='right', padx=5, pady=3)

        self.nb = ttk.Notebook(root); self.nb.pack(expand=True, fill='both', padx=10, pady=5)
        self._build_main(); self._build_sched(); self._build_events()
        
        ttk.Button(root, text="🔄 Обновить", command=self.refresh).pack(fill='x', padx=10, pady=5)
        self.refresh()

    def _build_main(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="🏠 Главная")  # ← ИСПРАВЛЕНО: add() вместо insert(0)
        self.countdown_lbl = tk.Label(tab, text="", bg=BG, fg=ACCENT, font=("Consolas", 18, "bold"), justify="center")
        self.countdown_lbl.pack(pady=40)
        self.invoker_frm = tk.Frame(tab, bg=BG)
        invoker_art = """
              ⚡
             /  \\
            |    |
            | ☾  |
             \\  /
              \\ 
        """
        tk.Label(self.invoker_frm, text=invoker_art, bg=BG, fg=TXT, font=("Consolas", 14), justify="center").pack()
        tk.Label(self.invoker_frm, text="К сожалению, в ближайшее время ивентов не ожидается...", bg=BG, fg=TXT, font=FONT, justify="center").pack(pady=10)
        self.invoker_frm.pack()

    def _make_tree(self, p, cols):
        t = ttk.Treeview(p, columns=cols, show="headings", height=12)
        for c in cols: t.heading(c, text=c); t.column("#0", width=0)
        t.pack(fill='both', expand=True, padx=10, pady=10); return t

    def _build_sched(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="📅 Расписание")
        frm_sel = tk.Frame(tab, bg=BG); frm_sel.pack(fill='x', padx=10, pady=5)
        tk.Label(frm_sel, text="Группа:", bg=BG, fg=TXT).pack(side='left')
        self.grp_cb = AutocompleteCombobox(frm_sel, width=15); self.grp_cb.pack(side='left', padx=5)
        self.grp_cb.bind("<<ComboboxSelected>>", lambda e: self.load_sched())
        ttk.Button(frm_sel, text="📄 PDF", command=self._export).pack(side='right')

        frm_in = tk.Frame(tab, bg=SURFACE); frm_in.pack(fill='x', padx=10, pady=5)
        tk.Label(frm_in, text="День:", bg=SURFACE, fg=TXT).grid(row=0, column=0)
        self.day_cb = ttk.Combobox(frm_in, values=["Пн","Вт","Ср","Чт","Пт","Сб"], width=5); self.day_cb.grid(row=0, column=1, padx=3)
        tk.Label(frm_in, text="С:", bg=SURFACE, fg=TXT).grid(row=0, column=2)
        self.start_cb = AutocompleteCombobox(frm_in, values=["09:00","10:30","10:45","12:15","12:30","14:00","14:15","15:45","16:00","17:30"], width=6); self.start_cb.grid(row=0, column=3, padx=3)
        tk.Label(frm_in, text="По:", bg=SURFACE, fg=TXT).grid(row=0, column=4)
        self.end_cb = AutocompleteCombobox(frm_in, values=["10:15","11:45","12:00","13:30","13:45","15:15","15:30","17:00","17:15","18:45"], width=6); self.end_cb.grid(row=0, column=5, padx=3)
        tk.Label(frm_in, text="Предмет:", bg=SURFACE, fg=TXT).grid(row=1, column=0)
        self.subj_cb = AutocompleteCombobox(frm_in, width=18); self.subj_cb.grid(row=1, column=1, columnspan=2, padx=3)
        tk.Label(frm_in, text="Преподав.:", bg=SURFACE, fg=TXT).grid(row=1, column=3)
        self.teach_cb = AutocompleteCombobox(frm_in, width=18); self.teach_cb.grid(row=1, column=4, columnspan=2, padx=3)
        tk.Label(frm_in, text="Аудитория:", bg=SURFACE, fg=TXT).grid(row=1, column=6)
        self.room_cb = AutocompleteCombobox(frm_in, width=8); self.room_cb.grid(row=1, column=7, padx=3)
        ttk.Button(frm_in, text="➕ Добавить", command=self._add).grid(row=2, column=0, columnspan=8, pady=5, sticky='ew')
        
        self.tree = self._make_tree(tab, ("ID", "День", "С", "По", "Предмет", "Преподаватель", "Аудитория"))
        ttk.Button(tab, text="🗑 Удалить выделенное", command=self._del).pack(anchor='e', padx=10, pady=5)

    def _build_events(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="📢 События")
        frm = tk.Frame(tab, bg=BG); frm.pack(fill='x', padx=10, pady=5)
        tk.Label(frm, text="Дата:", bg=BG, fg=TXT).pack(side='left')
        self.ev_date = tk.Entry(frm, bg=SURFACE, fg=TXT, width=12); self.ev_date.pack(side='left', padx=5)
        tk.Label(frm, text="Название:", bg=BG, fg=TXT).pack(side='left')
        self.ev_name = tk.Entry(frm, bg=SURFACE, fg=TXT, width=20); self.ev_name.pack(side='left', padx=5)
        ttk.Button(frm, text="Добавить", command=self._add_ev).pack(side='left', padx=5)
        self.ev_tree = self._make_tree(tab, ("ID", "Дата", "Название", "Описание"))

    def load_cache(self):
        def _f():
            try:
                d = session.get(f"{API}/autocomplete", headers=token_headers, timeout=5).json()
                self.root.after(0, lambda: [
                    self.teach_cb.set_values(d.get("teachers",[])),
                    self.subj_cb.set_values(d.get("subjects",[])),
                    self.room_cb.set_values(d.get("rooms",[])),
                    self.grp_cb.set_values(d.get("groups",[]))
                ])
            except: pass
        threading.Thread(target=_f, daemon=True).start()

    def refresh(self):
        def _f():
            try:
                grps = session.get(f"{API}/autocomplete", headers=token_headers, timeout=5).json()
                evs = session.get(f"{API}/events", headers=token_headers, timeout=5).json()
                new_hash = hashlib.md5(json.dumps(evs, sort_keys=True).encode()).hexdigest()
                if self.cache["events"] and self.cache["events"] != new_hash:
                    self.root.after(0, lambda: Toast(self.root, "Обновление", "Расписание событий изменено!"))
                self.cache["events"] = new_hash
                self.root.after(0, lambda: [
                    self._fill(self.ev_tree, evs, ["id","date","name","desc"]),
                    self.update_countdown(evs),
                    self.teach_cb.set_values(grps.get("teachers",[])),
                    self.subj_cb.set_values(grps.get("subjects",[])),
                    self.room_cb.set_values(grps.get("rooms",[])),
                    self.grp_cb.set_values(grps.get("groups",[]))
                ])
                if grps.get("groups"): self.grp_cb.current(0)
                self.load_sched()
            except: pass
        threading.Thread(target=_f, daemon=True).start()

    def update_countdown(self, events):
        today = datetime.date.today()
        future = [e for e in events if datetime.date.fromisoformat(e.get("date","")) >= today]
        if not future:
            self.countdown_lbl.pack_forget(); self.invoker_frm.pack(); return
        next_ev = min(future, key=lambda x: x["date"])
        days = (datetime.date.fromisoformat(next_ev["date"]) - today).days
        self.countdown_lbl.config(text=f"⏳ До следующего события:\n{next_ev['name']}\nОсталось дней: {days}")
        self.invoker_frm.pack_forget(); self.countdown_lbl.pack()

    def load_sched(self):
        grp = self.grp_cb.get()
        if not grp: return
        def _f():
            try:
                data = session.get(f"{API}/schedule/group/{grp}", headers=token_headers, timeout=5).json()
                new_h = hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()
                if self.cache["sched"] and self.cache["sched"] != new_h:
                    self.root.after(0, lambda: Toast(self.root, "Расписание", f"Изменения в группе {grp}"))
                self.cache["sched"] = new_h
                self.root.after(0, lambda: self._fill(self.tree, data, ["id","day","start_time","end_time","subj","teacher","room"]))
            except: pass
        threading.Thread(target=_f, daemon=True).start()

    def _fill(self, t, data, keys):
        t.delete(*t.get_children())
        for r in data: t.insert("", "end", values=[r.get(k,"") for k in keys])

    def _add(self):
        grp = self.grp_cb.get()
        if not grp: return messagebox.showwarning("Внимание", "Выберите группу")
        body = {"day": self.day_cb.get(), "start_time": self.start_cb.get(), "end_time": self.end_cb.get(),
                "subj": self.subj_cb.get(), "teacher": self.teach_cb.get(), "room": self.room_cb.get()}
        if not all(body.values()): return messagebox.showwarning("Внимание", "Заполните все поля")
        for i in self.tree.get_children():
            vals = self.tree.item(i)["values"]
            if vals[1]==body["day"] and vals[2]==body["start_time"]:
                if vals[5]==body["teacher"] or vals[6]==body["room"]:
                    return messagebox.showwarning("Конфликт", "Преподаватель или аудитория заняты")
        def _run():
            try:
                r = session.post(f"{API}/schedule/group/{grp}", json=body, headers=token_headers, timeout=5)
                if r.ok: self.root.after(0, lambda: [messagebox.showinfo("Успех","Добавлено"), self.refresh()])
                else: self.root.after(0, lambda: messagebox.showerror("Ошибка", r.json().get("detail")))
            except Exception as e: self.root.after(0, lambda: messagebox.showerror("Сеть", str(e)))
        threading.Thread(target=_run, daemon=True).start()

    def _del(self):
        sel = self.tree.selection()
        if not sel: return
        lid = self.tree.item(sel[0])["values"][0]; grp = self.grp_cb.get()
        def _run():
            try:
                session.delete(f"{API}/schedule/group/{grp}/{lid}", headers=token_headers, timeout=5)
                self.root.after(100, self.refresh)
            except Exception as e: self.root.after(0, lambda: messagebox.showerror("Сеть", str(e)))
        threading.Thread(target=_run, daemon=True).start()

    def _add_ev(self):
        body = {"date": self.ev_date.get(), "name": self.ev_name.get(), "desc": ""}
        if not body["date"] or not body["name"]: return messagebox.showwarning("Внимание", "Заполните дату и название")
        def _run():
            try:
                session.post(f"{API}/events", json=body, headers=token_headers, timeout=5)
                self.root.after(100, self.refresh)
            except Exception as e: self.root.after(0, lambda: messagebox.showerror("Сеть", str(e)))
        threading.Thread(target=_run, daemon=True).start()

    def _export(self):
        grp = self.grp_cb.get()
        if not grp: return messagebox.showwarning("Внимание", "Выберите группу")
        def _run():
            try:
                data = session.get(f"{API}/schedule/group/{grp}", headers=token_headers, timeout=5).json()
                self.root.after(0, lambda: export_pdf(data, grp))
            except Exception as e: self.root.after(0, lambda: messagebox.showerror("Сеть", str(e)))
        threading.Thread(target=_run, daemon=True).start()

# ─── ЗАПУСК (Однооконная архитектура) ───
# ─── ЗАМЕНИ ВСЁ ОТ if __name__ == "__main__": ДО КОНЦА ФАЙЛА ───
if __name__ == "__main__":
    print("🚀 Запуск редактора...")
    try:
        root = tk.Tk()
        root.title("Авторизация")
        root.geometry("340x280")
        root.configure(bg=BG)
        root.resizable(False, False)

        tk.Label(root, text="> SYSTEM ACCESS", bg=BG, fg=ACCENT, font=HDR).pack(pady=10)
        mode_var = tk.StringVar(value="login")
        frm_mode = tk.Frame(root, bg=BG); frm_mode.pack()
        ttk.Radiobutton(frm_mode, text="Вход", variable=mode_var, value="login", command=lambda: _toggle()).pack(side='left', padx=10)
        ttk.Radiobutton(frm_mode, text="Регистрация", variable=mode_var, value="register", command=lambda: _toggle()).pack(side='left', padx=10)

        frm = tk.Frame(root, bg=BG); frm.pack(fill='x', padx=20, pady=10)
        tk.Label(frm, text="Логин:", bg=BG, fg=TXT).grid(row=0, column=0, sticky='w')
        u_entry = tk.Entry(frm, bg=SURFACE, fg=TXT, font=FONT); u_entry.grid(row=0, column=1, padx=5, sticky='ew')
        tk.Label(frm, text="Пароль:", bg=BG, fg=TXT).grid(row=1, column=0, sticky='w')
        p_entry = tk.Entry(frm, bg=SURFACE, fg=TXT, font=FONT, show='*'); p_entry.grid(row=1, column=1, padx=5, sticky='ew')

        role_frm = tk.Frame(root, bg=BG)
        tk.Label(role_frm, text="Роль:", bg=BG, fg=TXT).pack(side='left')
        role_cb = ttk.Combobox(role_frm, values=["student", "teacher", "admin"], state="readonly", width=12)
        role_cb.pack(side='left', padx=5); role_cb.set("student")
        
        btn = ttk.Button(root, text="ВОЙТИ", command=lambda: _submit())
        btn.pack(fill='x', padx=20, pady=10)

        def _toggle():
            if mode_var.get() == "register": role_frm.pack(fill='x', padx=20, pady=5); btn.config(text="ЗАРЕГИСТРИРОВАТЬСЯ")
            else: role_frm.pack_forget(); btn.config(text="ВОЙТИ")

        def _submit():
            u_val = u_entry.get().strip()
            p_val = p_entry.get()
            role_val = role_cb.get()
            if not u_val or not p_val: return messagebox.showwarning("Внимание", "Заполните логин и пароль")
            
            def _net():
                try:
                    if mode_var.get() == "login":
                        r = session.post(f"{API}/login", json={"username": u_val, "password": p_val}, timeout=5)
                        if r.ok: 
                            # 🔑 ПЕРЕДАЁМ u_val в _switch явно
                            root.after(0, lambda: _switch(u_val, r.json()))
                        else: root.after(0, lambda: messagebox.showerror("Ошибка", r.json().get("detail")))
                    else:
                        r = session.post(f"{API}/register", json={"username": u_val, "password": p_val, "role": role_val}, timeout=5)
                        if r.ok: root.after(0, lambda: [messagebox.showinfo("Успех","Аккаунт создан!"), mode_var.set("login"), _toggle(), u_entry.focus_set()])
                        else: root.after(0, lambda: messagebox.showerror("Ошибка", r.json().get("detail")))
                except Exception as e: root.after(0, lambda: messagebox.showerror("Сеть", str(e)))
            threading.Thread(target=_net, daemon=True).start()

        def _switch(username, data):
            print(f"✅ Вход: {data['token'][:20]}...")
            token_headers["Authorization"] = f"Bearer {data['token']}"
            for w in root.winfo_children(): w.destroy()
            root.title(f"✎ Editor [v2] | {username}")
            root.geometry("1980x1080")
            root.resizable(True, True)
            apply_theme(root)
            # 🔑 ИСПОЛЬЗУЕМ ПЕРЕДАННЫЙ username
            Editor(root, {"user": username, "role": data["role"], "token": data["token"]})
            root.update_idletasks()

        print("🔄 mainloop() запущен...")
        root.mainloop()
    except Exception as e:
        print(f"💥 CRITICAL: {e}"); import traceback; traceback.print_exc(); input("Press Enter...")
