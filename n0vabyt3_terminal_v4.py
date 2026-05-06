import tkinter as tk
from tkinter import scrolledtext, messagebox
import subprocess
import threading
import os
import math
import random
import time
from datetime import datetime

# ─────────────────────────────────────────
#  FARBEN  (eDEX monochrom grün/cyan)
# ─────────────────────────────────────────
BG         = "#000000"
BG2        = "#050a05"
BG3        = "#0a0f0a"
FG         = "#00ff41"       # Matrix-Grün
FG_DIM     = "#004d14"
FG_MID     = "#00aa2c"
ACCENT     = "#00ff41"
ACCENT2    = "#00cc33"
TEXT_BG    = "#010801"
BORDER     = "#00ff41"
BORDER_DIM = "#003010"
SUCCESS    = "#00ff41"
ERROR      = "#ff0000"
WARNING    = "#ffff00"
INACTIVE   = "#1a1a1a"
KEY_NORMAL = "#0a1a0a"
KEY_BORDER = "#00ff41"
KEY_ACTIVE = "#00ff41"
KEY_TEXT   = "#00ff41"

FONT        = "Consolas"
FONT_SIZE   = 10
MAX_HISTORY = 100

# ─────────────────────────────────────────
#  POWERSHELL BEFEHLE
# ─────────────────────────────────────────
BEFEHL_LOGINS     = 'Get-EventLog -LogName Security -InstanceId 4624 | Select-Object TimeGenerated, @{Name="User";Expression={$_.ReplacementStrings[5]}} | Sort-Object TimeGenerated -Descending | Select-Object -First 20'
BEFEHL_SYSINFO    = "Get-ComputerInfo | Select-Object CsName, OsName, OsVersion, CsProcessors, CsTotalPhysicalMemory"
BEFEHL_PROZESSE   = "Get-Process | Sort-Object CPU -Descending | Select-Object -First 20 Name, CPU, WorkingSet, Id"
BEFEHL_NETZWERK   = "Get-NetIPAddress | Select-Object InterfaceAlias, AddressFamily, IPAddress | Where-Object { $_.IPAddress -ne '127.0.0.1' }"
BEFEHL_DIENSTE    = "Get-Service | Where-Object { $_.Status -eq 'Running' } | Select-Object Name, DisplayName | Sort-Object DisplayName | Select-Object -First 30"
BEFEHL_FESTPLATTE = "Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{N='Used(GB)';E={[math]::Round($_.Used/1GB,2)}}, @{N='Free(GB)';E={[math]::Round($_.Free/1GB,2)}}"
BEFEHL_USERS      = "Get-LocalUser | Select-Object Name, Enabled, LastLogon, PasswordLastSet"
BEFEHL_UPDATES    = "Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 15 HotFixID, Description, InstalledOn"
BEFEHL_STARTUP    = "Get-CimInstance Win32_StartupCommand | Select-Object Name, Command, Location, User"
BEFEHL_WIFI       = "netsh wlan show profiles"
BEFEHL_CPU        = "Get-WmiObject Win32_Processor | Select-Object Name, LoadPercentage, NumberOfCores, MaxClockSpeed"
BEFEHL_NET_STAT   = "Get-NetTCPConnection | Where-Object {$_.State -eq 'Established'} | Select-Object -First 15 LocalAddress, LocalPort, RemoteAddress, RemotePort, State"

# ─────────────────────────────────────────
#  TAB-COMPLETION
# ─────────────────────────────────────────
class TabCompletion:
    SUGGESTIONS = [
        "Get-Process","Get-Process | Sort-Object CPU -Descending",
        "Get-Service","Get-Service | Where-Object { $_.Status -eq 'Running' }",
        "Get-EventLog -LogName Security","Get-EventLog -LogName Application",
        "Get-EventLog -LogName System","Get-ComputerInfo","Get-NetAdapter",
        "Get-NetIPAddress","Get-NetTCPConnection","Get-Disk","Get-Volume",
        "Get-PSDrive","Get-InstalledModule","Get-LocalUser","Get-LocalGroup",
        "Get-ChildItem","Get-Content","Get-History","Get-HotFix",
        "Get-WmiObject Win32_Battery","Get-WmiObject Win32_BIOS",
        "Get-WmiObject Win32_Processor","Get-CimInstance Win32_StartupCommand",
        "Start-Process","Stop-Process -Name","Restart-Service",
        "Test-NetConnection","Test-Connection -ComputerName","Invoke-Command",
        "netsh wlan show profiles","ipconfig /all","ipconfig /flushdns",
        "sfc /scannow","chkdsk","tasklist","taskkill /F /IM",
        "systeminfo","whoami","net user","net localgroup administrators",
    ]
    def __init__(self, entry_widget, ghost_var):
        self.entry = entry_widget
        self.ghost_var = ghost_var
        self.current_suggestion = ""
        self.entry.bind("<KeyRelease>", self._on_key_release)
        self.entry.bind("<Tab>",        self._on_tab)
        self.entry.bind("<Escape>",     self._on_escape)

    def _find_suggestion(self, text):
        if not text.strip(): return ""
        lower = text.lower()
        for cmd in self.SUGGESTIONS:
            if cmd.lower().startswith(lower) and cmd.lower() != lower:
                return cmd
        return ""

    def _on_key_release(self, event):
        if event.keysym in ("Tab","Escape","Return"): return
        typed = self.entry.get()
        sug = self._find_suggestion(typed)
        self.current_suggestion = sug
        self.ghost_var.set(sug[len(typed):] if sug else "")

    def _on_tab(self, event):
        if self.current_suggestion:
            self.entry.delete(0, tk.END)
            self.entry.insert(0, self.current_suggestion)
            self.ghost_var.set("")
            self.current_suggestion = ""
        return "break"

    def _on_escape(self, _event):
        self.ghost_var.set("")
        self.current_suggestion = ""


# ─────────────────────────────────────────
#  COMMAND HISTORY
# ─────────────────────────────────────────
class CommandHistory:
    def __init__(self, entry_widget, max_entries=MAX_HISTORY):
        self.entry = entry_widget
        self.history = []
        self.pos = -1
        self.max = max_entries
        self.temp_input = ""
        self.entry.bind("<Up>",   self._go_back)
        self.entry.bind("<Down>", self._go_forward)

    def add(self, cmd):
        cmd = cmd.strip()
        if not cmd: return
        if self.history and self.history[-1] == cmd:
            self.pos = -1
            return
        self.history.append(cmd)
        if len(self.history) > self.max:
            self.history.pop(0)
        self.pos = -1

    def _go_back(self, event):
        if not self.history: return
        if self.pos == -1:
            self.temp_input = self.entry.get()
        self.pos = min(self.pos + 1, len(self.history) - 1)
        self._set(self.history[-(self.pos + 1)])
        return "break"

    def _go_forward(self, event):
        if self.pos <= 0:
            self.pos = -1
            self._set(self.temp_input)
            return "break"
        self.pos -= 1
        self._set(self.history[-(self.pos + 1)])
        return "break"

    def _set(self, text):
        self.entry.delete(0, tk.END)
        self.entry.insert(0, text)


# ─────────────────────────────────────────
#  GLOBALE REFS
# ─────────────────────────────────────────
root         = None
output_text  = None
status_label = None
entry        = None
cmd_history  = None

cpu_history    = [0] * 40
mem_history    = [0] * 40
net_up_history = [0] * 40
net_dn_history = [0] * 40

left_panel   = None
right_panel  = None
cpu_canvas   = None
mem_canvas   = None
net_canvas   = None
proc_text    = None
net_stat_lbl = None
clock_label  = None
date_label   = None
uptime_start = time.time()


# ─────────────────────────────────────────
#  HILFSFUNKTIONEN
# ─────────────────────────────────────────
def copy_output():
    content = output_text.get(1.0, tk.END).strip()
    if content:
        root.clipboard_clear()
        root.clipboard_append(content)
        flash_status("● COPIED!", SUCCESS)

def flash_status(msg, color):
    status_label.config(text=msg, fg=color)
    root.after(1800, lambda: status_label.config(text="● READY", fg=SUCCESS))

def run_cmd(cmd):
    threading.Thread(target=execute_cmd, args=(cmd,), daemon=True).start()

def run_custom():
    cmd = entry.get().strip()
    if not cmd:
        return
    cmd_history.add(cmd)
    run_cmd(cmd)

def clear_output():
    output_text.config(state=tk.NORMAL)
    output_text.delete(1.0, tk.END)
    output_text.config(state=tk.DISABLED)

def execute_cmd(cmd):
    try:
        status_label.config(text="● EXECUTING...", fg=WARNING)
        ts = datetime.now().strftime("%H:%M:%S")
        process = subprocess.Popen(
            ["powershell", "-Command", cmd],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace"
        )
        stdout, stderr = process.communicate(timeout=60)

        output_text.config(state=tk.NORMAL)
        output_text.delete(1.0, tk.END)
        output_text.insert(tk.END, f"[{ts}] ", "timestamp")
        output_text.insert(tk.END, f"› {cmd}\n", "cmd_echo")
        output_text.insert(tk.END, "─" * 50 + "\n", "separator")

        if stdout:
            _insert_highlighted(stdout)
        if stderr:
            output_text.insert(tk.END, "\n[ERROR]\n", "error_header")
            output_text.insert(tk.END, stderr, "error")
            if "registrierungszugriff" in stderr.lower() or "securityexception" in stderr.lower():
                output_text.insert(tk.END, "\n⚠ Als Administrator ausführen!\n", "admin_error")

        output_text.config(state=tk.DISABLED)
        status_label.config(text="● READY", fg=SUCCESS)

    except subprocess.TimeoutExpired:
        process.kill()
        status_label.config(text="● TIMEOUT", fg=ERROR)
        output_text.config(state=tk.NORMAL)
        output_text.insert(tk.END, "\n⚠ Timeout nach 60s\n", "admin_error")
        output_text.config(state=tk.DISABLED)
    except Exception as e:
        status_label.config(text="● ERROR", fg=ERROR)
        messagebox.showerror("Fehler", str(e))

def _insert_highlighted(text):
    KEYWORDS_OK  = {"True","Running","Enabled","Online","Connected","Up"}
    KEYWORDS_BAD = {"False","Stopped","Disabled","Offline","Disconnected","Down","Error"}
    for line in text.splitlines(keepends=True):
        words = line.split()
        if not words:
            output_text.insert(tk.END, line)
            continue
        remaining = line
        for word in words:
            idx = remaining.find(word)
            if idx > 0:
                output_text.insert(tk.END, remaining[:idx])
            if word in KEYWORDS_OK:
                output_text.insert(tk.END, word, "kw_true")
            elif word in KEYWORDS_BAD:
                output_text.insert(tk.END, word, "kw_false")
            elif word.lstrip("-").isdigit() or _is_float(word):
                output_text.insert(tk.END, word, "number")
            elif (":\\" in word) or word.startswith("\\\\") or word.startswith("/"):
                output_text.insert(tk.END, word, "path")
            else:
                output_text.insert(tk.END, word)
            remaining = remaining[idx + len(word):]
        if remaining:
            output_text.insert(tk.END, remaining)

def _is_float(s):
    try: float(s.replace(",",".")); return True
    except: return False

def battery_report():
    def task():
        try:
            status_label.config(text="● GENERATING...", fg=WARNING)
            path = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "battery_report.html")
            subprocess.run(f'powercfg /batteryreport /output "{path}"', shell=True)
            os.startfile(path)
            status_label.config(text="● READY", fg=SUCCESS)
        except Exception as e:
            status_label.config(text="● ERROR", fg=ERROR)
            messagebox.showerror("Fehler", str(e))
    threading.Thread(target=task, daemon=True).start()


# ─────────────────────────────────────────
#  LIVE STATS (Thread)
# ─────────────────────────────────────────
def fetch_live_stats():
    """Holt CPU/RAM/Prozesse alle 3 Sekunden via PowerShell."""
    while True:
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "$cpu=(Get-WmiObject Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average;"
                 "$os=Get-WmiObject Win32_OperatingSystem;"
                 "$mem=[math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/$os.TotalVisibleMemorySize*100,1);"
                 "$memUsed=[math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/1MB,2);"
                 "$memTotal=[math]::Round($os.TotalVisibleMemorySize/1MB,2);"
                 "Write-Output \"$cpu|$mem|$memUsed|$memTotal\""],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=8
            )
            line = result.stdout.strip()
            if "|" in line:
                parts = line.split("|")
                if len(parts) >= 4:
                    cpu_val  = float(parts[0]) if parts[0] else 0
                    mem_pct  = float(parts[1]) if parts[1] else 0
                    mem_used = float(parts[2]) if parts[2] else 0
                    mem_tot  = float(parts[3]) if parts[3] else 0
                    cpu_history.append(cpu_val)
                    cpu_history.pop(0)
                    mem_history.append(mem_pct)
                    mem_history.pop(0)
                    root.after(0, lambda c=cpu_val, m=mem_pct, mu=mem_used, mt=mem_tot:
                               update_stats_ui(c, m, mu, mt))
        except Exception:
            pass

        # Prozesse holen
        try:
            result2 = subprocess.run(
                ["powershell", "-Command",
                 "Get-Process | Sort-Object CPU -Descending | Select-Object -First 8 Name,Id,"
                 "@{N='CPU';E={[math]::Round($_.CPU,1)}},@{N='MEM';E={[math]::Round($_.WorkingSet/1MB,1)}} |"
                 "ForEach-Object { \"$($_.Name)|$($_.Id)|$($_.CPU)|$($_.MEM)\" }"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=8
            )
            lines = result2.stdout.strip().splitlines()
            root.after(0, lambda l=lines: update_proc_ui(l))
        except Exception:
            pass

        time.sleep(3)


def update_stats_ui(cpu, mem_pct, mem_used, mem_tot):
    if cpu_canvas:
        draw_graph(cpu_canvas, cpu_history, cpu, "CPU", f"{cpu:.0f}%")
    if mem_canvas:
        draw_graph(mem_canvas, mem_history, mem_pct, "MEM",
                   f"{mem_used:.1f}/{mem_tot:.1f} GB")

def update_proc_ui(lines):
    if not proc_text: return
    proc_text.config(state=tk.NORMAL)
    proc_text.delete(1.0, tk.END)
    proc_text.insert(tk.END, f"{'NAME':<18} {'PID':>5} {'CPU':>6} {'MEM':>7}\n", "proc_header")
    proc_text.insert(tk.END, "─" * 40 + "\n", "proc_sep")
    for line in lines:
        parts = line.split("|")
        if len(parts) == 4:
            name, pid, cpu, mem = parts
            name = name[:17]
            proc_text.insert(tk.END,
                f"{name:<18} {pid:>5} {cpu:>5}s {mem:>6}M\n", "proc_row")
    proc_text.config(state=tk.DISABLED)

def draw_graph(canvas, history, current_val, label, value_str):
    canvas.delete("all")
    w = canvas.winfo_width()
    h = canvas.winfo_height()
    if w < 10 or h < 10: return

    # Border
    canvas.create_rectangle(0, 0, w-1, h-1, outline=BORDER_DIM, fill=BG)

    # Label oben links
    canvas.create_text(4, 4, text=label, fill=FG_MID, font=(FONT, 7), anchor="nw")
    canvas.create_text(w-4, 4, text=value_str, fill=ACCENT, font=(FONT, 7, "bold"), anchor="ne")

    # Graph
    max_val = 100
    pad_x, pad_y = 4, 16
    gw = w - pad_x * 2
    gh = h - pad_y - 4
    step = gw / max(len(history) - 1, 1)

    points = []
    for i, v in enumerate(history):
        x = pad_x + i * step
        y = pad_y + gh - (v / max_val) * gh
        points.extend([x, y])

    if len(points) >= 4:
        # Füllung
        fill_pts = [pad_x, pad_y + gh] + points + [pad_x + gw, pad_y + gh]
        canvas.create_polygon(fill_pts, fill=FG_DIM, outline="")
        # Linie
        canvas.create_line(points, fill=ACCENT, width=1, smooth=True)

    # Aktueller Wert als Balken unten
    bar_w = int((current_val / 100) * (w - 2))
    canvas.create_rectangle(1, h-3, bar_w, h-1, fill=ACCENT, outline="")


def update_clock():
    now = datetime.now()
    if clock_label:
        clock_label.config(text=now.strftime("%H:%M:%S"))
    if date_label:
        elapsed = int(time.time() - uptime_start)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        date_label.config(text=f"{now.strftime('%Y-%m-%d')}   UP {h:02d}:{m:02d}:{s:02d}")
    root.after(1000, update_clock)


# ─────────────────────────────────────────
#  TASTATUR
# ─────────────────────────────────────────
KEYBOARD_ROWS = [
    ["ESC","F1","F2","F3","F4","F5","F6","F7","F8","F9","F10","F11","F12","DEL"],
    ["`","1","2","3","4","5","6","7","8","9","0","-","=","BACK"],
    ["TAB","q","w","e","r","t","y","u","i","o","p","[","]","\\"],
    ["CAPS","a","s","d","f","g","h","j","k","l",";","'","ENTER"],
    ["SHIFT","z","x","c","v","b","n","m",",",".","/","SHIFT↑"],
    ["CTRL","FN","ALT","SPACE","ALT","CTRL"],
]

KEY_WIDTHS = {
    "ESC": 1.5, "BACK": 2.0, "TAB": 1.8, "CAPS": 2.0,
    "ENTER": 2.2, "SHIFT": 2.5, "SHIFT↑": 2.5,
    "CTRL": 1.6, "FN": 1.2, "ALT": 1.4, "SPACE": 6.0,
    "DEL": 1.5, "\\": 1.5,
    "F1":1.2,"F2":1.2,"F3":1.2,"F4":1.2,
    "F5":1.2,"F6":1.2,"F7":1.2,"F8":1.2,
    "F9":1.2,"F10":1.2,"F11":1.2,"F12":1.2,
}

# Mapping tkinter keysym → key label
KEYSYM_MAP = {
    "Escape":"ESC","BackSpace":"BACK","Tab":"TAB","Caps_Lock":"CAPS",
    "Return":"ENTER","Delete":"DEL","space":"SPACE",
    "shift_l":"SHIFT","shift_r":"SHIFT↑",
    "control_l":"CTRL","control_r":"CTRL",
    "alt_l":"ALT","alt_r":"ALT",
    "F1":"F1","F2":"F2","F3":"F3","F4":"F4","F5":"F5","F6":"F6",
    "F7":"F7","F8":"F8","F9":"F9","F10":"F10","F11":"F11","F12":"F12",
}

key_buttons = {}   # label → canvas item ids


def build_keyboard(parent):
    global key_buttons
    kb_canvas = tk.Canvas(parent, bg=BG, highlightthickness=0, height=170)
    kb_canvas.pack(fill="x", padx=0, pady=0)

    KEY_H   = 28
    KEY_W   = 36
    GAP     = 3
    PAD_X   = 8
    PAD_Y   = 6

    key_items = {}   # label → (rect_id, text_id)

    def draw_key(row_idx, col_x, label, width_units):
        w = int(KEY_W * width_units + GAP * (width_units - 1))
        x1 = PAD_X + col_x
        y1 = PAD_Y + row_idx * (KEY_H + GAP)
        x2 = x1 + w
        y2 = y1 + KEY_H

        rect = kb_canvas.create_rectangle(
            x1, y1, x2, y2,
            fill=KEY_NORMAL, outline=KEY_BORDER, width=1
        )
        disp = label if len(label) <= 5 else label[:4]
        txt = kb_canvas.create_text(
            (x1+x2)//2, (y1+y2)//2,
            text=disp, fill=KEY_TEXT,
            font=(FONT, 7, "bold")
        )
        key_items[label] = (rect, txt)
        return x2 + GAP

    for row_idx, row in enumerate(KEYBOARD_ROWS):
        col_x = 0
        for label in row:
            w = KEY_WIDTHS.get(label, 1.0)
            col_x = draw_key(row_idx, col_x, label, w)

    key_buttons.update(key_items)

    def on_key_press(event):
        sym = event.keysym.lower()
        mapped = KEYSYM_MAP.get(sym, None)
        char = event.char.lower() if event.char else None

        targets = set()
        if mapped: targets.add(mapped)
        if char and char.strip(): targets.add(char)
        # Zahl / Sonderzeichen direkt
        if event.keysym in [str(i) for i in range(10)]:
            targets.add(event.keysym)

        for lbl in targets:
            if lbl in key_buttons:
                rect, txt = key_buttons[lbl]
                kb_canvas.itemconfig(rect, fill=KEY_ACTIVE, outline=KEY_ACTIVE)
                kb_canvas.itemconfig(txt, fill=BG)
                root.after(180, lambda r=rect, t=txt: (
                    kb_canvas.itemconfig(r, fill=KEY_NORMAL, outline=KEY_BORDER),
                    kb_canvas.itemconfig(t, fill=KEY_TEXT)
                ))

    root.bind("<KeyPress>", on_key_press)
    return kb_canvas


# ─────────────────────────────────────────
#  BOOT ANIMATION
# ─────────────────────────────────────────
def show_boot_animation(on_complete):
    boot = tk.Frame(root, bg=BG)
    boot.place(relx=0, rely=0, relwidth=1, relheight=1)

    logo = """
  ███╗   ██╗ ██████╗ ██╗   ██╗ █████╗ ██████╗ ██╗   ██╗████████╗██████╗
  ████╗  ██║██╔═████╗██║   ██║██╔══██╗██╔══██╗╚██╗ ██╔╝╚══██╔══╝╚════██╗
  ██╔██╗ ██║██║██╔██║██║   ██║███████║██████╔╝ ╚████╔╝    ██║    █████╔╝
  ██║╚██╗██║████╔╝██║╚██╗ ██╔╝██╔══██║██╔══██╗  ╚██╔╝     ██║    ╚═══██╗
  ██║ ╚████║╚██████╔╝ ╚████╔╝ ██║  ██║██████╔╝   ██║      ██║   ██████╔╝
  ╚═╝  ╚═══╝ ╚═════╝   ╚═══╝  ╚═╝  ╚═╝╚═════╝    ╚═╝      ╚═╝   ╚═════╝
                         SYSTEM CONTROL PANEL  v4.0"""

    tk.Label(boot, text=logo, bg=BG, fg=ACCENT,
             font=(FONT, 10, "bold"), justify="center").pack(expand=True)

    pf = tk.Frame(boot, bg=BG)
    pf.pack(pady=10)
    pc = tk.Canvas(pf, width=500, height=6, bg=BG3, highlightthickness=0)
    pc.pack()
    ll = tk.Label(boot, text="INITIALIZING...", bg=BG, fg=FG_MID, font=(FONT, 9))
    ll.pack(pady=8)

    msgs = ["LOADING CORE MODULES...","CONNECTING TO POWERSHELL...",
            "INITIALIZING INTERFACE...","MAPPING KEYBOARD...","SYSTEM READY"]
    prog = [0]

    def animate():
        if prog[0] <= 500:
            pc.delete("bar")
            pc.create_rectangle(0, 0, prog[0], 6, fill=ACCENT, outline="", tags="bar")
            ll.config(text=msgs[min(prog[0]//110, len(msgs)-1)])
            prog[0] += 8
            root.after(20, animate)
        else:
            boot.destroy()
            on_complete()

    root.after(400, animate)


# ─────────────────────────────────────────
#  PANEL-HELPER
# ─────────────────────────────────────────
def panel_label(parent, text):
    tk.Label(parent, text=text, bg=BG, fg=FG_MID,
             font=(FONT, 7, "bold")).pack(fill="x", padx=4, pady=(6,1))
    tk.Canvas(parent, height=1, bg=BORDER_DIM, highlightthickness=0).pack(fill="x", padx=4)

def make_cmd_btn(parent, text, cmd, color=FG_MID):
    frm = tk.Frame(parent, bg=color, padx=1, pady=1)
    frm.pack(fill="x", padx=4, pady=2)
    btn = tk.Button(frm, text=text, command=cmd,
                    bg=BG3, fg=color,
                    activebackground=BG2, activeforeground=ACCENT,
                    relief="flat", font=(FONT, 8, "bold"),
                    pady=4, cursor="hand2", borderwidth=0)
    btn.pack(fill="x")
    btn.bind("<Enter>", lambda e: btn.config(bg=BG2, fg=ACCENT))
    btn.bind("<Leave>", lambda e: btn.config(bg=BG3, fg=color))
    return btn


# ─────────────────────────────────────────
#  HAUPT-UI
# ─────────────────────────────────────────
def create_main_ui():
    global output_text, status_label, entry, cmd_history
    global left_panel, right_panel, cpu_canvas, mem_canvas
    global net_canvas, proc_text, net_stat_lbl, clock_label, date_label

    root.configure(bg=BG)

    # ══════════════════════════════════════
    #  TOP BAR
    # ══════════════════════════════════════
    top = tk.Frame(root, bg=BG2, height=28)
    top.pack(fill="x", side="top")
    top.pack_propagate(False)

    # Tabs
    tabs = [("PANEL","left"), ("SYSTEM","left"), ("TERMINAL","left"),
            ("MAIN SHELL","right"), ("PANEL","right"), ("NETWORK","right")]
    for label, side in tabs:
        tk.Label(top, text=f"  {label}  ", bg=BG2, fg=FG_MID,
                 font=(FONT, 8), relief="flat",
                 borderwidth=0).pack(side=side, padx=2, pady=4)

    tk.Canvas(top, width=1, bg=BORDER_DIM, highlightthickness=0).pack(side="left", fill="y")

    # ══════════════════════════════════════
    #  BODY (LEFT | CENTER | RIGHT)
    # ══════════════════════════════════════
    body = tk.Frame(root, bg=BG)
    body.pack(fill="both", expand=True)

    # ── LEFT PANEL ──────────────────────
    left_panel = tk.Frame(body, bg=BG, width=220)
    left_panel.pack(side="left", fill="y")
    left_panel.pack_propagate(False)

    # Uhr
    clock_frame = tk.Frame(left_panel, bg=BG2)
    clock_frame.pack(fill="x", padx=0, pady=0)
    clock_label = tk.Label(clock_frame, text="00:00:00", bg=BG2, fg=ACCENT,
                           font=(FONT, 28, "bold"))
    clock_label.pack(pady=(8,0))
    date_label = tk.Label(clock_frame, text="", bg=BG2, fg=FG_MID,
                          font=(FONT, 8))
    date_label.pack(pady=(0,6))

    tk.Canvas(left_panel, height=1, bg=BORDER_DIM, highlightthickness=0).pack(fill="x")

    # CPU Graph
    panel_label(left_panel, "CPU USAGE")
    cpu_canvas = tk.Canvas(left_panel, bg=BG, height=60, highlightthickness=0)
    cpu_canvas.pack(fill="x", padx=4, pady=2)

    # MEM Graph
    panel_label(left_panel, "MEMORY")
    mem_canvas = tk.Canvas(left_panel, bg=BG, height=60, highlightthickness=0)
    mem_canvas.pack(fill="x", padx=4, pady=2)

    # Prozesse
    panel_label(left_panel, "TOP PROCESSES  PID  CPU    MEM")
    proc_text = tk.Text(left_panel, bg=BG, fg=FG_MID,
                        font=(FONT, 7), relief="flat",
                        borderwidth=0, state=tk.DISABLED, height=10)
    proc_text.pack(fill="x", padx=4, pady=2)
    proc_text.tag_config("proc_header", foreground=FG_MID, font=(FONT, 7, "bold"))
    proc_text.tag_config("proc_sep",    foreground=BORDER_DIM)
    proc_text.tag_config("proc_row",    foreground=ACCENT2)

    tk.Canvas(left_panel, height=1, bg=BORDER_DIM, highlightthickness=0).pack(fill="x")

    # Clipboard Buttons
    panel_label(left_panel, "CLIPBOARD")
    cb_frame = tk.Frame(left_panel, bg=BG)
    cb_frame.pack(fill="x", padx=4, pady=4)
    make_cmd_btn(cb_frame, "COPY OUTPUT", copy_output, FG_MID)
    make_cmd_btn(cb_frame, "CLEAR",       clear_output, FG_DIM)

    # ── VERTICAL SEPARATOR ──────────────
    tk.Canvas(body, width=1, bg=BORDER_DIM, highlightthickness=0).pack(side="left", fill="y")

    # ── CENTER: TERMINAL ─────────────────
    center = tk.Frame(body, bg=BG)
    center.pack(side="left", fill="both", expand=True)

    # Terminal Header
    term_header = tk.Frame(center, bg=BG2, height=22)
    term_header.pack(fill="x")
    term_header.pack_propagate(False)
    tk.Label(term_header, text="  ~/n0vabyt3", bg=BG2, fg=FG_MID,
             font=(FONT, 8)).pack(side="left", pady=3)
    status_label = tk.Label(term_header, text="● READY", bg=BG2, fg=SUCCESS,
                            font=(FONT, 8))
    status_label.pack(side="right", padx=10, pady=3)

    # Output
    output_text = tk.Text(
        center, bg=TEXT_BG, fg=ACCENT,
        insertbackground=ACCENT,
        font=(FONT, FONT_SIZE),
        relief="flat", borderwidth=0,
        padx=10, pady=8, state=tk.DISABLED,
        wrap=tk.WORD
    )
    output_text.pack(fill="both", expand=True)

    # Scrollbar
    sb = tk.Scrollbar(output_text, command=output_text.yview, bg=BG2,
                      troughcolor=BG, activebackground=FG_MID)
    output_text.configure(yscrollcommand=sb.set)

    # Tags
    output_text.tag_config("timestamp",   foreground="#003a1a", font=(FONT, FONT_SIZE))
    output_text.tag_config("cmd_echo",    foreground=ACCENT,    font=(FONT, FONT_SIZE, "bold"))
    output_text.tag_config("separator",   foreground=BORDER_DIM)
    output_text.tag_config("error",       foreground=ERROR)
    output_text.tag_config("error_header",foreground=ERROR,     font=(FONT, FONT_SIZE, "bold"))
    output_text.tag_config("admin_error", foreground=WARNING,   font=(FONT, FONT_SIZE, "bold"))
    output_text.tag_config("success",     foreground=SUCCESS)
    output_text.tag_config("kw_true",     foreground=SUCCESS)
    output_text.tag_config("kw_false",    foreground=ERROR)
    output_text.tag_config("number",      foreground="#88ff88")
    output_text.tag_config("path",        foreground="#44aa44")

    # Input Bar
    input_bar = tk.Frame(center, bg=BG2, height=36)
    input_bar.pack(fill="x", side="bottom")
    input_bar.pack_propagate(False)

    tk.Label(input_bar, text=" ~/n0vabyt3 › ", bg=BG2, fg=ACCENT,
             font=(FONT, 11, "bold")).pack(side="left")

    input_sub = tk.Frame(input_bar, bg=BG2)
    input_sub.pack(side="left", fill="x", expand=True)

    ghost_var = tk.StringVar()
    ghost_lbl = tk.Label(input_sub, textvariable=ghost_var,
                         bg=BG2, fg=FG_DIM, font=(FONT, 11), anchor="w")
    ghost_lbl.place(relx=0, rely=0, relwidth=1, relheight=1)

    entry = tk.Entry(input_sub, bg=BG2, fg=ACCENT,
                     insertbackground=ACCENT,
                     relief="flat", font=(FONT, 11),
                     borderwidth=0)
    entry.pack(fill="x", expand=True, pady=6)
    entry.bind("<Return>", lambda e: run_custom())
    ghost_lbl.lower(entry)

    tk.Button(input_bar, text="RUN", command=run_custom,
              bg=BG3, fg=ACCENT,
              activebackground=BG2, activeforeground=SUCCESS,
              relief="flat", font=(FONT, 8, "bold"),
              padx=10, pady=6, cursor="hand2", borderwidth=0
              ).pack(side="right", padx=6, pady=4)

    root.bind("<Control-c>",     lambda e: copy_output())
    root.bind("<Control-plus>",  lambda e: increase_font())
    root.bind("<Control-minus>", lambda e: decrease_font())

    TabCompletion(entry, ghost_var)
    cmd_history = CommandHistory(entry)

    # ── VERTICAL SEPARATOR ──────────────
    tk.Canvas(body, width=1, bg=BORDER_DIM, highlightthickness=0).pack(side="left", fill="y")

    # ── RIGHT PANEL ──────────────────────
    right_panel = tk.Frame(body, bg=BG, width=220)
    right_panel.pack(side="right", fill="y")
    right_panel.pack_propagate(False)

    # Network Status Block
    net_top = tk.Frame(right_panel, bg=BG2)
    net_top.pack(fill="x")
    tk.Label(net_top, text="NETWORK STATUS", bg=BG2, fg=FG_MID,
             font=(FONT, 8, "bold")).pack(anchor="w", padx=6, pady=(6,2))

    net_info = tk.Frame(net_top, bg=BG2)
    net_info.pack(fill="x", padx=6, pady=(0,6))

    net_stat_lbl = tk.Label(net_info, text="STATE    IPv4\nONLINE   –\nPING     –",
                            bg=BG2, fg=ACCENT, font=(FONT, 8), justify="left")
    net_stat_lbl.pack(anchor="w")

    tk.Canvas(right_panel, height=1, bg=BORDER_DIM, highlightthickness=0).pack(fill="x")

    # Network Traffic Graph
    panel_label(right_panel, "NETWORK TRAFFIC")
    net_canvas = tk.Canvas(right_panel, bg=BG, height=80, highlightthickness=0)
    net_canvas.pack(fill="x", padx=4, pady=2)

    tk.Canvas(right_panel, height=1, bg=BORDER_DIM, highlightthickness=0).pack(fill="x")

    # Quick Commands
    panel_label(right_panel, "── SYSTEM ──")
    make_cmd_btn(right_panel, "SYSINFO",   lambda: run_cmd(BEFEHL_SYSINFO),    FG_MID)
    make_cmd_btn(right_panel, "BATTERY",   battery_report,                     FG_MID)
    make_cmd_btn(right_panel, "DISK",      lambda: run_cmd(BEFEHL_FESTPLATTE), FG_MID)
    make_cmd_btn(right_panel, "STARTUP",   lambda: run_cmd(BEFEHL_STARTUP),    FG_MID)

    panel_label(right_panel, "── PROZESSE ──")
    make_cmd_btn(right_panel, "PROZESSE",  lambda: run_cmd(BEFEHL_PROZESSE),   FG_MID)
    make_cmd_btn(right_panel, "DIENSTE",   lambda: run_cmd(BEFEHL_DIENSTE),    FG_MID)

    panel_label(right_panel, "── NETZWERK ──")
    make_cmd_btn(right_panel, "NETZWERK",  lambda: run_cmd(BEFEHL_NETZWERK),   FG_MID)
    make_cmd_btn(right_panel, "WIFI",      lambda: run_cmd(BEFEHL_WIFI),       FG_MID)
    make_cmd_btn(right_panel, "NET CONN",  lambda: run_cmd(BEFEHL_NET_STAT),   FG_MID)

    panel_label(right_panel, "── SECURITY ──")
    make_cmd_btn(right_panel, "LOGINS",    lambda: run_cmd(BEFEHL_LOGINS),     FG_MID)
    make_cmd_btn(right_panel, "USERS",     lambda: run_cmd(BEFEHL_USERS),      FG_MID)
    make_cmd_btn(right_panel, "UPDATES",   lambda: run_cmd(BEFEHL_UPDATES),    FG_MID)

    # ══════════════════════════════════════
    #  KEYBOARD (ganz unten)
    # ══════════════════════════════════════
    tk.Canvas(root, height=1, bg=BORDER_DIM, highlightthickness=0).pack(fill="x", side="bottom")
    kb_frame = tk.Frame(root, bg=BG)
    kb_frame.pack(fill="x", side="bottom")
    build_keyboard(kb_frame)

    # Ping & Netzwerk live
    threading.Thread(target=fetch_network_status, daemon=True).start()

    # Uhr starten
    update_clock()

    # Live Stats
    threading.Thread(target=fetch_live_stats, daemon=True).start()

    # Willkommensnachricht
    output_text.config(state=tk.NORMAL)
    output_text.insert(tk.END, "N0VABYT3 TERMINAL v4.0\n", "cmd_echo")
    output_text.insert(tk.END, "PowerShell Integration  |  Tab-Completion  |  Live Stats\n", "separator")
    output_text.insert(tk.END, "─" * 50 + "\n", "separator")
    output_text.insert(tk.END, "Befehl eingeben oder Button klicken.\n", "number")
    output_text.config(state=tk.DISABLED)

    entry.focus_set()


def fetch_network_status():
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "$ip=(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -ne '127.0.0.1'} | Select-Object -First 1).IPAddress;"
             "$ping=(Test-Connection 8.8.8.8 -Count 1 -ErrorAction SilentlyContinue).ResponseTime;"
             "Write-Output \"$ip|$ping\""],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
        line = result.stdout.strip()
        if "|" in line:
            ip, ping = line.split("|", 1)
            state = "ONLINE" if ping.strip() else "OFFLINE"
            ping_str = f"{ping.strip()}ms" if ping.strip() else "–"
            txt = f"STATE    IPv4\n{state:<8} {ip.strip()}\nPING     {ping_str}"
            root.after(0, lambda: net_stat_lbl.config(text=txt,
                fg=SUCCESS if state == "ONLINE" else ERROR))
    except Exception:
        pass


def increase_font():
    global FONT_SIZE
    FONT_SIZE = min(FONT_SIZE + 1, 20)
    output_text.config(font=(FONT, FONT_SIZE))

def decrease_font():
    global FONT_SIZE
    FONT_SIZE = max(FONT_SIZE - 1, 7)
    output_text.config(font=(FONT, FONT_SIZE))


# ─────────────────────────────────────────
#  INIT
# ─────────────────────────────────────────
root = tk.Tk()
root.title("N0VABYT3 TERMINAL v4.0")
root.geometry("1280x800")
root.configure(bg=BG)
root.minsize(1100, 700)

show_boot_animation(create_main_ui)
root.mainloop()
