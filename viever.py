import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests, threading, datetime, os
from fpdf import FPDF

SERVER_IP = "127.0.0.1"
API = f"http://{SERVER_IP}:8000"
session = requests.Session()
token_headers = {}
BG, SURFACE, ACCENT, TXT = "#0d1117", "#161b22", "#58a6ff", "#c9d1d9"
FONT, HDR = ("Consolas", 10), ("Consolas", 11, "bold")

def apply_theme(r):
    r.configure(bg=BG)
    s = ttk.Style(); s.theme_use('clam')
    s.configure('.', background=BG, foreground=TXT, font=FONT)
    s.configure('TNotebook', background=BG)
    s.configure('TNotebook.Tab', background=SURFACE, foreground=TXT, padding=(12,6))
    s.configure('TButton', background='#21262d', foreground=ACCENT, font=FONT)
    s.configure('Treeview', background='#010409', foreground=TXT, fieldbackground='#010409', font=FONT)
    s.configure('Treeview.Heading', background=SURFACE, foreground=ACCENT, font=HDR)
    s.configure('TCombobox', background=SURFACE, foreground=TXT, fieldbackground=SURFACE, font=FONT)

def export_pdf(rows, title, cols, keys):
    if not rows: return messagebox.showwarning("Внимание", "Расписание пусто.")
    def _run():
        try:
            path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF","*.pdf")], initialfilename=f"{title}.pdf")
            if not path: return
            pdf = FPDF(); pdf.set_auto_page_break(auto=True, margin=15); pdf.add_page()
            font = next((p for p in [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\consola.ttf"] if os.path.exists(p)), None)
            if not font: return root.after(0, lambda: messagebox.showerror("Ошибка", "Шрифт Windows не найден."))
            pdf.add_font("Main", "", font, uni=True); pdf.add_font("Main", "B", font, uni=True)
            pdf.set_font("Main", "B", 16); pdf.cell(0, 10, title, align="C"); pdf.ln(10)
            pdf.set_font("Main", size=10); pdf.cell(0, 5, f"Дата: {datetime.datetime.now().strftime('%d.%m.%Y')}", align="C"); pdf.ln(10)
            pdf.set_font("Main", "B", 9)
            for w, c in zip([18,20,20,45,55,25], cols): pdf.cell(w, 7, c, border=1, align="C")
            pdf.ln(); pdf.set_font("Main", size=8)
            for r in rows:
                for w, k in zip([18,20,20,45,55,25], keys):
                    val = str(r.get(k,""))[:22]
                    pdf.cell(w, 7, val, border=1)
                pdf.ln()
            pdf.output(path)
            root.after(0, lambda: messagebox.showinfo("Готово", f"Сохранено:\n{path}"))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Ошибка", str(e)))
    threading.Thread(target=_run, daemon=True).start()

class Viewer:
    def __init__(self, root, user):
        self.root = root; self.user = user
        root.title(f"Viewer | {user['user']}"); root.geometry("950x650"); apply_theme(root)
        bar = tk.Frame(root, bg=SURFACE, height=30); bar.pack(fill='x')
        tk.Label(bar, text=f"👤 {user['user']} | {user['role']}", bg=SURFACE, fg=TXT, font=FONT).pack(side='left', padx=10, pady=3)

        self.nb = ttk.Notebook(root); self.nb.pack(expand=True, fill='both', padx=10, pady=5)
        self._build_home()
        self._build_groups()
        self._build_teachers()
        
        self.refresh()
        self.root.after(30000, self.auto_refresh)

    def _make_tree(self, p, cols):
        t = ttk.Treeview(p, columns=cols, show="headings", height=14)
        for c in cols: t.heading(c, text=c); t.column("#0", width=0)
        t.pack(fill='both', expand=True, padx=10, pady=10); return t

    def _build_home(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="🏠 Главная")
        self.ev_tree = self._make_tree(tab, ("Дата","Название","Описание"))
        self.countdown_lbl = tk.Label(tab, text="", bg=BG, fg=ACCENT, font=("Consolas", 14, "bold"), justify="center")
        self.countdown_lbl.pack(pady=10)
        self.invoker_lbl = tk.Label(tab, text="К сожалению, в ближайшее время ивентов не ожидается.", bg=BG, fg="#555", font=FONT)
        self.invoker_lbl.pack()

    def _build_groups(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="📅 Группы")
        frm = tk.Frame(tab, bg=BG); frm.pack(fill='x', padx=10, pady=5)
        tk.Label(frm, text="Группа:", bg=BG, fg=TXT).pack(side='left')
        # 🔧 Явные значения + явный bind
        self.grp_cb = ttk.Combobox(frm, state="readonly", width=15, values=["Загрузка..."])
        self.grp_cb.pack(side='left', padx=5)
        self.grp_cb.bind("<<ComboboxSelected>>", self._on_grp_select)
        ttk.Button(frm, text="📄 PDF", command=lambda: self._pdf(self.grp_cb.get(), "grp")).pack(side='right')
        self.grp_tree = self._make_tree(tab, ("День","С","По","Предмет","Преподаватель","Аудитория"))

    def _build_teachers(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="👨‍🏫 Преподаватели")
        frm = tk.Frame(tab, bg=BG); frm.pack(fill='x', padx=10, pady=5)
        tk.Label(frm, text="Преподаватель:", bg=BG, fg=TXT).pack(side='left')
        self.teach_cb = ttk.Combobox(frm, state="readonly", width=20, values=["Загрузка..."])
        self.teach_cb.pack(side='left', padx=5)
        self.teach_cb.bind("<<ComboboxSelected>>", self._on_teach_select)
        ttk.Button(frm, text="📄 PDF", command=lambda: self._pdf(self.teach_cb.get(), "teach")).pack(side='right')
        self.teach_tree = self._make_tree(tab, ("День","С","По","Предмет","Группа","Аудитория"))

    def _on_grp_select(self, event=None):
        val = self.grp_cb.get()
        if val and val != "Загрузка...": self._load(val, "grp")

    def _on_teach_select(self, event=None):
        val = self.teach_cb.get()
        if val and val != "Загрузка...": self._load(val, "teach")

    def refresh(self):
        def _f():
            try:
                ac = session.get(f"{API}/autocomplete", headers=token_headers, timeout=5).json()
                evs = session.get(f"{API}/events", headers=token_headers, timeout=5).json()
                self.root.after(0, lambda: self._upd(ac, evs))
            except Exception as e: print(f"[Viewer ERR] {e}")
        threading.Thread(target=_f, daemon=True).start()

    def _upd(self, ac, evs):
        grps = [str(g) for g in ac.get("groups", [])]
        teaches = [str(t) for t in ac.get("teachers", [])]
        
        self.grp_cb.config(values=grps if grps else ["Нет групп"])
        self.teach_cb.config(values=teaches if teaches else ["Нет преподавателей"])
        self.root.update_idletasks()  # 🔧 Принудительная отрисовка значений
        
        if grps: self.grp_cb.current(0); self._on_grp_select()
        if teaches: self.teach_cb.current(0); self._on_teach_select()
            
        self.ev_tree.delete(*self.ev_tree.get_children())
        for r in evs: self.ev_tree.insert("", "end", values=(r.get("date",""), r.get("name",""), r.get("desc","")))
        self._countdown(evs)

    def _load(self, name, kind):
        if not name or name.startswith(("Загрузка", "Нет")): return
        def _f():
            try:
                endpoint = f"/schedule/group/{name}" if kind=="grp" else f"/schedule/teacher/{name}"
                data = session.get(f"{API}{endpoint}", headers=token_headers, timeout=5).json()
                keys = ["day","start_time","end_time","subj","teacher","room"]
                tree = self.grp_tree if kind=="grp" else self.teach_tree
                self.root.after(0, lambda: self._fill(tree, data, keys))
            except: pass
        threading.Thread(target=_f, daemon=True).start()

    def _fill(self, tree, data, keys):
        tree.delete(*tree.get_children())
        for r in data: tree.insert("", "end", values=[str(r.get(k,"")) for k in keys])

    def _pdf(self, name, kind):
        if not name or name.startswith(("Загрузка", "Нет")): 
            return messagebox.showwarning("Внимание", "Выберите элемент")
        cols = ["День","Начало","Конец","Предмет","Преподаватель","Аудитория"] if kind=="grp" else ["День","Начало","Конец","Предмет","Группа","Аудитория"]
        keys = ["day","start_time","end_time","subj","teacher","room"]
        title = f"Расписание группы: {name}" if kind=="grp" else f"Расписание преподавателя: {name}"
        def _run():
            try:
                endpoint = f"/schedule/group/{name}" if kind=="grp" else f"/schedule/teacher/{name}"
                data = session.get(f"{API}{endpoint}", headers=token_headers, timeout=5).json()
                self.root.after(0, lambda: export_pdf(data, title, cols, keys))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Сеть", str(e)))
        threading.Thread(target=_run, daemon=True).start()

    def _countdown(self, events):
        today = datetime.date.today()
        future = [e for e in events if datetime.date.fromisoformat(e.get("date","")) >= today]
        if not future:
            self.countdown_lbl.pack_forget(); self.invoker_lbl.pack(); return
        next_ev = min(future, key=lambda x: x["date"])
        days = (datetime.date.fromisoformat(next_ev["date"]) - today).days
        self.countdown_lbl.config(text=f"⏳ До следующего события: {next_ev['name']}\nОсталось дней: {days}")
        self.invoker_lbl.pack_forget(); self.countdown_lbl.pack()

    def auto_refresh(self):
        self.refresh(); self.root.after(30000, self.auto_refresh)

# ─── ЗАПУСК ───
if __name__ == "__main__":
    try:
        root = tk.Tk()
        root.title("Авторизация"); root.geometry("340x200"); root.configure(bg=BG); root.resizable(False, False)
        tk.Label(root, text="> VIEWER ACCESS", bg=BG, fg=ACCENT, font=HDR).pack(pady=10)
        frm = tk.Frame(root, bg=BG); frm.pack(fill='x', padx=20, pady=5)
        tk.Label(frm, text="Логин:", bg=BG, fg=TXT).grid(row=0, column=0)
        u_entry = tk.Entry(frm, bg=SURFACE, fg=TXT, font=FONT); u_entry.grid(row=0, column=1, padx=5)
        tk.Label(frm, text="Пароль:", bg=BG, fg=TXT).grid(row=1, column=0)
        p_entry = tk.Entry(frm, bg=SURFACE, fg=TXT, font=FONT, show='*'); p_entry.grid(row=1, column=1, padx=5)
        btn = ttk.Button(root, text="ВОЙТИ", command=lambda: _submit())
        btn.pack(fill='x', padx=20, pady=10)

        def _submit():
            u, p = u_entry.get().strip(), p_entry.get()
            if not u or not p: return messagebox.showwarning("Внимание", "Заполните поля")
            def _net():
                try:
                    r = session.post(f"{API}/login", json={"username": u, "password": p}, timeout=5)
                    if r.ok: root.after(0, lambda: _switch(u, r.json()))
                    else: root.after(0, lambda: messagebox.showerror("Ошибка", r.json().get("detail")))
                except Exception as e: root.after(0, lambda: messagebox.showerror("Сеть", str(e)))
            threading.Thread(target=_net, daemon=True).start()

        def _switch(username, data):
            token_headers["Authorization"] = f"Bearer {data['token']}"
            for w in root.winfo_children(): w.destroy()
            root.title(f"Viewer | {username}"); root.geometry("950x650"); root.resizable(True, True)
            apply_theme(root)
            Viewer(root, {"user": username, "role": data["role"]})
            root.update_idletasks()

        root.mainloop()
    except Exception as e:
        try:
            err_root = tk.Tk(); err_root.withdraw()
            messagebox.showerror("Критическая ошибка запуска", f"{e}\n\nСкопируй текст и отправь разработчику.")
            err_root.destroy()
        except: pass
        print(f"[CRIT] {e}"); import traceback; traceback.print_exc()
