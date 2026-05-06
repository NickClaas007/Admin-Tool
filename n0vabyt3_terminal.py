import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import threading
import os
from datetime import datetime

# -------------------------
# Farben & Einstellungen
# -------------------------
BG           = "#0a0a0f"
BG_SECONDARY = "#12121a"
FG           = "#00e5ff"
FG_DIM       = "#4a5568"
ACCENT       = "#00e5ff"
ACCENT_GLOW  = "#00b8d4"
BTN_BG       = "#1a1a2e"
BTN_HOVER    = "#252542"
TEXT_BG      = "#0d0d14"
BORDER       = "#1e1e2e"
SUCCESS      = "#00ff88"
ERROR        = "#ff4757"
WARNING      = "#ffaa00"
HISTORY_COL  = "#a78bfa"
TIMESTAMP_COL= "#2a4a5a"

FONT_SIZE   = 10
MAX_HISTORY = 100

# -------------------------
# PowerShell Commands
# -------------------------
BEFEHL_LOGINS = """Get-EventLog -LogName Security -InstanceId 4624 |
Select-Object TimeGenerated, @{Name="User";Expression={$_.ReplacementStrings[5]}} |
Sort-Object TimeGenerated -Descending"""

BEFEHL_SYSINFO    = "Get-ComputerInfo | Select-Object CsName, OsName, OsVersion, CsProcessors, CsTotalPhysicalMemory"
BEFEHL_PROZESSE   = "Get-Process | Sort-Object CPU -Descending | Select-Object -First 20 Name, CPU, WorkingSet, Id"
BEFEHL_NETZWERK   = "Get-NetIPAddress | Select-Object InterfaceAlias, AddressFamily, IPAddress | Where-Object { $_.IPAddress -ne '127.0.0.1' }"
BEFEHL_DIENSTE    = "Get-Service | Where-Object { $_.Status -eq 'Running' } | Select-Object Name, DisplayName, Status | Sort-Object DisplayName"
BEFEHL_FESTPLATTE = "Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{N='Used(GB)';E={[math]::Round($_.Used/1GB,2)}}, @{N='Free(GB)';E={[math]::Round($_.Free/1GB,2)}}"
BEFEHL_USERS      = "Get-LocalUser | Select-Object Name, Enabled, LastLogon, PasswordLastSet"
BEFEHL_UPDATES    = "Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 15 HotFixID, Description, InstalledOn"
BEFEHL_STARTUP    = "Get-CimInstance Win32_StartupCommand | Select-Object Name, Command, Location, User"
BEFEHL_WIFI       = "netsh wlan show profiles"


# -------------------------
# Tab-Completion Klasse
# -------------------------
class TabCompletion:
    SUGGESTIONS = [
        "Get-Process",
        "Get-Process | Sort-Object CPU -Descending",
        "Get-Service",
        "Get-Service | Where-Object { $_.Status -eq 'Running' }",
        "Get-EventLog -LogName Security",
        "Get-EventLog -LogName Application",
        "Get-EventLog -LogName System",
        "Get-ComputerInfo",
        "Get-NetAdapter",
        "Get-NetIPAddress",
        "Get-NetTCPConnection",
        "Get-Disk",
        "Get-Volume",
        "Get-PSDrive",
        "Get-InstalledModule",
        "Get-LocalUser",
        "Get-LocalGroup",
        "Get-ChildItem",
        "Get-Content",
        "Get-History",
        "Get-HotFix",
        "Get-WmiObject Win32_Battery",
        "Get-WmiObject Win32_BIOS",
        "Get-WmiObject Win32_Processor",
        "Get-CimInstance Win32_StartupCommand",
        "Start-Process",
        "Stop-Process -Name",
        "Restart-Service",
        "Test-NetConnection",
        "Test-Connection -ComputerName",
        "Invoke-Command",
        "netsh wlan show profiles",
        "ipconfig /all",
        "ipconfig /flushdns",
        "sfc /scannow",
        "chkdsk",
        "tasklist",
        "taskkill /F /IM",
        "systeminfo",
        "whoami",
        "net user",
        "net localgroup administrators",
    ]

    def __init__(self, entry_widget, ghost_var):
        self.entry            = entry_widget
        self.ghost_var        = ghost_var
        self.current_suggestion = ""

        self.entry.bind("<KeyRelease>", self._on_key_release)
        self.entry.bind("<Tab>",        self._on_tab)
        self.entry.bind("<Escape>",     self._on_escape)

    def _find_suggestion(self, text):
        if not text.strip():
            return ""
        lower = text.lower()
        for cmd in self.SUGGESTIONS:
            if cmd.lower().startswith(lower) and cmd.lower() != lower:
                return cmd
        return ""

    def _on_key_release(self, event):
        if event.keysym in ("Tab", "Escape", "Return"):
            return
        typed = self.entry.get()
        sug   = self._find_suggestion(typed)
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


# -------------------------
# Command History Klasse
# -------------------------
class CommandHistory:
    def __init__(self, entry_widget, max_entries=MAX_HISTORY):
        self.entry      = entry_widget
        self.history    = []
        self.pos        = -1
        self.max        = max_entries
        self.temp_input = ""

        self.entry.bind("<Up>",   self._go_back)
        self.entry.bind("<Down>", self._go_forward)

    def add(self, cmd):
        cmd = cmd.strip()
        if not cmd:
            return
        # Duplikat direkt hintereinander vermeiden
        if self.history and self.history[-1] == cmd:
            self.pos = -1
            return
        self.history.append(cmd)
        if len(self.history) > self.max:
            self.history.pop(0)
        self.pos = -1

    def _go_back(self, event):
        if not self.history:
            return
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


# -------------------------
# Hilfsfunktionen
# -------------------------
def copy_output():
    content = output_text.get(1.0, tk.END).strip()
    if content:
        root.clipboard_clear()
        root.clipboard_append(content)
        status_label.config(text="● COPIED!", fg=SUCCESS)
        root.after(1500, lambda: status_label.config(text="● READY", fg=SUCCESS))


def run_cmd(cmd):
    threading.Thread(target=execute_cmd, args=(cmd,), daemon=True).start()


def run_custom():
    cmd = entry.get().strip()
    if cmd.startswith("›"):
        cmd = cmd[1:].strip()
    if not cmd:
        messagebox.showwarning("Fehler", "Bitte einen Befehl eingeben!")
        return
    cmd_history.add(cmd)
    run_cmd(cmd)


def execute_cmd(cmd):
    try:
        status_label.config(text="● EXECUTING...", fg=WARNING)

        ts = datetime.now().strftime("%H:%M:%S")

        process = subprocess.Popen(
            ["powershell", "-Command", cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        stdout, stderr = process.communicate(timeout=60)

        output_text.config(state=tk.NORMAL)
        output_text.delete(1.0, tk.END)

        # Timestamp + Command Header
        output_text.insert(tk.END, f"[{ts}] ", "timestamp")
        output_text.insert(tk.END, f"› {cmd}\n", "cmd_echo")
        output_text.insert(tk.END, "─" * 60 + "\n", "separator")

        if stdout:
            _insert_highlighted(stdout)

        if stderr:
            output_text.insert(tk.END, "\n[ERROR]\n", "error_header")
            output_text.insert(tk.END, stderr, "error")
            error_lower = stderr.lower()
            if "registrierungszugriff" in error_lower or "securityexception" in error_lower:
                output_text.insert(
                    tk.END,
                    "\n⚠ Führe das Programm als Administrator aus ⚠\n",
                    "admin_error"
                )

        output_text.config(state=tk.DISABLED)
        status_label.config(text="● READY", fg=SUCCESS)

    except subprocess.TimeoutExpired:
        process.kill()
        status_label.config(text="● TIMEOUT", fg=ERROR)
        output_text.config(state=tk.NORMAL)
        output_text.insert(tk.END, "\n⚠ Timeout: Befehl nach 60s abgebrochen.\n", "admin_error")
        output_text.config(state=tk.DISABLED)
    except Exception as e:
        status_label.config(text="● ERROR", fg=ERROR)
        messagebox.showerror("Fehler", str(e))


def _insert_highlighted(text):
    """Einfaches Syntax-Highlighting für PowerShell-Output."""
    KEYWORDS = {"True", "False", "Running", "Stopped", "Enabled", "Disabled"}
    for line in text.splitlines(keepends=True):
        parts = line.split()
        col_start = 0
        if not parts:
            output_text.insert(tk.END, line)
            continue
        # Ganze Zeile scannen
        remaining = line
        inserted  = 0
        for word in parts:
            idx = remaining.find(word)
            # Text vor dem Wort
            if idx > 0:
                output_text.insert(tk.END, remaining[:idx])
            # Wort mit Tag
            if word in KEYWORDS:
                tag = "kw_true" if word in {"True", "Running", "Enabled"} else "kw_false"
                output_text.insert(tk.END, word, tag)
            elif word.lstrip("-").isdigit() or _is_float(word):
                output_text.insert(tk.END, word, "number")
            elif word.startswith("\\\\") or (":\\" in word) or word.startswith("/"):
                output_text.insert(tk.END, word, "path")
            else:
                output_text.insert(tk.END, word)
            remaining = remaining[idx + len(word):]
        if remaining:
            output_text.insert(tk.END, remaining)


def _is_float(s):
    try:
        float(s.replace(",", "."))
        return True
    except ValueError:
        return False


def battery_report():
    def task():
        try:
            status_label.config(text="● GENERATING REPORT...", fg=WARNING)
            path = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "battery_report.html")
            subprocess.run(f'powercfg /batteryreport /output "{path}"', shell=True)
            os.startfile(path)
            status_label.config(text="● READY", fg=SUCCESS)
        except Exception as e:
            status_label.config(text="● ERROR", fg=ERROR)
            messagebox.showerror("Fehler", str(e))

    threading.Thread(target=task, daemon=True).start()


def clear_output():
    output_text.config(state=tk.NORMAL)
    output_text.delete(1.0, tk.END)
    output_text.config(state=tk.DISABLED)


def increase_font():
    global FONT_SIZE
    FONT_SIZE = min(FONT_SIZE + 1, 20)
    output_text.config(font=("Consolas", FONT_SIZE))


def decrease_font():
    global FONT_SIZE
    FONT_SIZE = max(FONT_SIZE - 1, 8)
    output_text.config(font=("Consolas", FONT_SIZE))


# -------------------------
# BOOT ANIMATION
# -------------------------
def show_boot_animation(root, on_complete):
    boot_frame = tk.Frame(root, bg=BG)
    boot_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

    logo_text = """
    ╔═══════════════════════════════════════════════════╗
    ║                                                   ║
      ███╗   ██╗ ██████╗ ██╗   ██╗ █████╗ ██████╗ ██╗   ██╗████████╗██████╗  
      ████╗  ██║██╔═████╗██║   ██║██╔══██╗██╔══██╗╚██╗ ██╔╝╚══██╔══╝╚════██╗ 
      ██╔██╗ ██║██║██╔██║██║   ██║███████║██████╔╝ ╚████╔╝    ██║    █████╔╝ 
      ██║╚██╗██║████╔╝██║╚██╗ ██╔╝██╔══██║██╔══██╗  ╚██╔╝     ██║    ╚═══██╗ 
      ██║ ╚████║╚██████╔╝ ╚████╔╝ ██║  ██║██████╔╝   ██║      ██║   ██████╔╝ 
      ╚═╝  ╚═══╝ ╚═════╝   ╚═══╝  ╚═╝  ╚═╝╚═════╝    ╚═╝      ╚═╝   ╚═════╝  
    ║                                                   ║
    ║              SYSTEM CONTROL PANEL                 ║
    ╚═══════════════════════════════════════════════════╝
    """

    logo_label = tk.Label(
        boot_frame, text=logo_text,
        bg=BG, fg=ACCENT,
        font=("Consolas", 10, "bold"),
        justify="center"
    )
    logo_label.pack(expand=True)

    progress_frame = tk.Frame(boot_frame, bg=BG)
    progress_frame.pack(pady=20)

    progress_canvas = tk.Canvas(
        progress_frame, width=300, height=6,
        bg=BG_SECONDARY, highlightthickness=0
    )
    progress_canvas.pack()

    loading_label = tk.Label(
        boot_frame,
        text="INITIALIZING SYSTEM...",
        bg=BG, fg=FG_DIM,
        font=("Consolas", 9)
    )
    loading_label.pack(pady=10)

    progress = [0]
    messages = [
        "LOADING CORE MODULES...",
        "CONNECTING TO POWERSHELL...",
        "INITIALIZING INTERFACE...",
        "SYSTEM READY"
    ]

    def animate():
        if progress[0] <= 300:
            progress_canvas.delete("bar")
            progress_canvas.create_rectangle(0, 0, progress[0], 6, fill=ACCENT, outline="", tags="bar")
            msg_index = min(progress[0] // 80, len(messages) - 1)
            loading_label.config(text=messages[msg_index])
            progress[0] += 6
            root.after(30, animate)
        else:
            boot_frame.destroy()
            on_complete()

    root.after(500, animate)


# -------------------------
# MAIN GUI
# -------------------------
def create_main_ui():
    global status_label, entry, output_text, cmd_history

    # ── Header ──────────────────────────────────────────────
    header = tk.Frame(root, bg=BG_SECONDARY, height=50)
    header.pack(fill="x")
    header.pack_propagate(False)

    header_inner = tk.Frame(header, bg=BG_SECONDARY)
    header_inner.pack(fill="both", expand=True, padx=15)

    tk.Label(
        header_inner, text="◈ N0VABYT3 TERMINAL",
        bg=BG_SECONDARY, fg=ACCENT,
        font=("Consolas", 14, "bold")
    ).pack(side="left", pady=12)

    # Font-Size Buttons im Header
    font_frame = tk.Frame(header_inner, bg=BG_SECONDARY)
    font_frame.pack(side="right", pady=8, padx=(0, 15))

    for sym, cmd in [("A+", increase_font), ("A-", decrease_font)]:
        tk.Button(
            font_frame, text=sym, command=cmd,
            bg=BTN_BG, fg=FG_DIM,
            activebackground=BTN_HOVER, activeforeground=FG,
            relief="flat", font=("Consolas", 9), padx=6, pady=2,
            cursor="hand2", borderwidth=0
        ).pack(side="left", padx=2)

    status_label = tk.Label(
        header_inner, text="● READY",
        bg=BG_SECONDARY, fg=SUCCESS,
        font=("Consolas", 10)
    )
    status_label.pack(side="right", pady=12, padx=(0, 10))

    # ── Separator ───────────────────────────────────────────
    sep = tk.Canvas(root, height=2, bg=BG, highlightthickness=0)
    sep.pack(fill="x")
    sep.create_line(0, 1, 2000, 1, fill=ACCENT, width=1)

    # ── Keyboard-Shortcuts Leiste ────────────────────────────
    kb_frame = tk.Frame(root, bg=BG_SECONDARY)
    kb_frame.pack(fill="x")

    shortcuts = [
        ("Tab", "Autocomplete"),
        ("↑↓", "History"),
        ("Ctrl+C", "Copy Output"),
        ("Ctrl++/-", "Font Size"),
        ("Esc", "Clear Suggestion"),
    ]
    for key, desc in shortcuts:
        tk.Label(kb_frame, text=f" {key} ", bg="#1a1a2e", fg=ACCENT,
                 font=("Consolas", 8), padx=4).pack(side="left", padx=(6, 2), pady=4)
        tk.Label(kb_frame, text=desc, bg=BG_SECONDARY, fg=FG_DIM,
                 font=("Consolas", 8)).pack(side="left", padx=(0, 8), pady=4)

    # ── Main Content ─────────────────────────────────────────
    main_frame = tk.Frame(root, bg=BG)
    main_frame.pack(fill="both", expand=True, padx=15, pady=15)

    # ── LEFT: Terminal ───────────────────────────────────────
    left_frame = tk.Frame(main_frame, bg=BG)
    left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

    # Command Input
    input_frame = tk.Frame(left_frame, bg=BORDER, padx=1, pady=1)
    input_frame.pack(fill="x")

    input_inner = tk.Frame(input_frame, bg=TEXT_BG)
    input_inner.pack(fill="x")

    tk.Label(
        input_inner, text="›",
        bg=TEXT_BG, fg=ACCENT,
        font=("Consolas", 14, "bold")
    ).pack(side="left", padx=(10, 0))

    # Container für Entry + Ghost
    input_canvas = tk.Frame(input_inner, bg=TEXT_BG)
    input_canvas.pack(side="left", fill="x", expand=True, pady=10, padx=(0, 10))

    ghost_var = tk.StringVar()

    ghost_label = tk.Label(
        input_canvas,
        textvariable=ghost_var,
        bg=TEXT_BG, fg=FG_DIM,
        font=("Consolas", 12),
        anchor="w"
    )
    ghost_label.place(relx=0, rely=0, relwidth=1, relheight=1)

    entry = tk.Entry(
        input_canvas,
        bg=TEXT_BG, fg=FG,
        insertbackground=ACCENT,
        relief="flat",
        font=("Consolas", 12),
        borderwidth=0
    )
    entry.pack(fill="x", expand=True)
    entry.bind("<Return>", lambda e: run_custom())

    # Ctrl+C → Copy Output (nicht den Entry)
    root.bind("<Control-c>", lambda e: copy_output())
    root.bind("<Control-plus>",  lambda e: increase_font())
    root.bind("<Control-minus>", lambda e: decrease_font())

    ghost_label.lower(entry)

    # Completion + History aktivieren
    TabCompletion(entry, ghost_var)
    cmd_history = CommandHistory(entry)

    # Output Section
    output_frame = tk.Frame(left_frame, bg=BORDER, padx=1, pady=1)
    output_frame.pack(fill="both", expand=True, pady=(15, 0))

    output_header = tk.Frame(output_frame, bg=BG_SECONDARY)
    output_header.pack(fill="x")

    tk.Label(
        output_header, text="OUTPUT",
        bg=BG_SECONDARY, fg=FG_DIM,
        font=("Consolas", 9, "bold")
    ).pack(side="left", padx=10, pady=5)

    # Copy-Button im Output-Header
    tk.Button(
        output_header, text="⎘ COPY",
        command=copy_output,
        bg=BTN_BG, fg=FG_DIM,
        activebackground=BTN_HOVER, activeforeground=FG,
        relief="flat", font=("Consolas", 8),
        padx=8, pady=3, cursor="hand2", borderwidth=0
    ).pack(side="right", padx=8, pady=3)

    output_text = scrolledtext.ScrolledText(
        output_frame,
        wrap=tk.WORD,
        state=tk.DISABLED,
        bg=TEXT_BG, fg=FG,
        insertbackground=ACCENT,
        font=("Consolas", FONT_SIZE),
        relief="flat", borderwidth=0,
        padx=10, pady=10
    )
    output_text.pack(fill="both", expand=True)

    # Tags für Highlighting
    output_text.tag_config("error",       foreground=ERROR)
    output_text.tag_config("error_header",foreground=ERROR,        font=("Consolas", FONT_SIZE, "bold"))
    output_text.tag_config("admin_error", foreground=ERROR,        font=("Consolas", FONT_SIZE, "bold"))
    output_text.tag_config("success",     foreground=SUCCESS)
    output_text.tag_config("timestamp",   foreground=TIMESTAMP_COL,font=("Consolas", FONT_SIZE))
    output_text.tag_config("cmd_echo",    foreground=ACCENT,       font=("Consolas", FONT_SIZE, "bold"))
    output_text.tag_config("separator",   foreground=FG_DIM)
    output_text.tag_config("kw_true",     foreground=SUCCESS)
    output_text.tag_config("kw_false",    foreground=ERROR)
    output_text.tag_config("number",      foreground="#fbbf24")
    output_text.tag_config("path",        foreground=HISTORY_COL)

    # ── RIGHT: Control Panel ─────────────────────────────────
    right_frame = tk.Frame(main_frame, bg=BG_SECONDARY, width=185)
    right_frame.pack(side="right", fill="y")
    right_frame.pack_propagate(False)

    tk.Label(
        right_frame, text="CONTROLS",
        bg=BG_SECONDARY, fg=FG_DIM,
        font=("Consolas", 9, "bold")
    ).pack(pady=(15, 8))

    def make_button(parent, text, cmd, color=ACCENT):
        frm = tk.Frame(parent, bg=color, padx=1, pady=1)
        frm.pack(pady=4, padx=12, fill="x")
        btn = tk.Button(
            frm, text=text, command=cmd,
            bg=BTN_BG, fg=color,
            activebackground=BTN_HOVER, activeforeground=color,
            relief="flat", font=("Consolas", 9, "bold"),
            pady=8, cursor="hand2", borderwidth=0
        )
        btn.pack(fill="x")
        btn.bind("<Enter>", lambda e: btn.config(bg=BTN_HOVER))
        btn.bind("<Leave>", lambda e: btn.config(bg=BTN_BG))
        return btn

    # Separator-Label
    def section_label(txt):
        tk.Label(
            right_frame, text=txt,
            bg=BG_SECONDARY, fg=FG_DIM,
            font=("Consolas", 7)
        ).pack(pady=(8, 0))

    # ── Basis ──
    make_button(right_frame, "▶  RUN",        run_custom,                         ACCENT)
    make_button(right_frame, "⎘  COPY",       copy_output,                        "#38bdf8")
    make_button(right_frame, "✕  CLEAR",      clear_output,                       "#6b7280")

    section_label("── SYSTEM ──────────────")
    make_button(right_frame, "⚙  SYSINFO",    lambda: run_cmd(BEFEHL_SYSINFO),    "#38bdf8")
    make_button(right_frame, "⚡ BATTERY",    battery_report,                     "#fbbf24")
    make_button(right_frame, "💾 DISK",       lambda: run_cmd(BEFEHL_FESTPLATTE), "#fbbf24")
    make_button(right_frame, "▣  STARTUP",    lambda: run_cmd(BEFEHL_STARTUP),    "#f97316")

    section_label("── PROZESSE / DIENSTE ──")
    make_button(right_frame, "◎  PROZESSE",   lambda: run_cmd(BEFEHL_PROZESSE),   "#a78bfa")
    make_button(right_frame, "◈  DIENSTE",    lambda: run_cmd(BEFEHL_DIENSTE),    "#a78bfa")

    section_label("── NETZWERK ────────────")
    make_button(right_frame, "⬡  NETZWERK",   lambda: run_cmd(BEFEHL_NETZWERK),   "#34d399")
    make_button(right_frame, "◌  WIFI",       lambda: run_cmd(BEFEHL_WIFI),       "#34d399")

    section_label("── SECURITY ────────────")
    make_button(right_frame, "◉  LOGINS",     lambda: run_cmd(BEFEHL_LOGINS),     "#f87171")
    make_button(right_frame, "👤 USERS",      lambda: run_cmd(BEFEHL_USERS),      "#f87171")
    make_button(right_frame, "🔧 UPDATES",    lambda: run_cmd(BEFEHL_UPDATES),    "#fb923c")

    # ── Footer ───────────────────────────────────────────────
    footer = tk.Frame(root, bg=BG_SECONDARY, height=30)
    footer.pack(fill="x", side="bottom")
    footer.pack_propagate(False)

    tk.Label(
        footer,
        text="N0VABYT3 TERMINAL v3.0  |  PowerShell Integration",
        bg=BG_SECONDARY, fg=FG_DIM,
        font=("Consolas", 8)
    ).pack(pady=8)


# -------------------------
# Init
# -------------------------
root = tk.Tk()
root.title("N0VABYT3 TERMINAL")
root.geometry("950x600")
root.configure(bg=BG)
root.minsize(850, 520)

show_boot_animation(root, create_main_ui)
root.mainloop()
