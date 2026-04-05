import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sys
import os
from pathlib import Path

VISUALIZER_SCRIPT = Path("lumina_visualizer.py")
bot_process = None
viz_process = None

def get_available_bots():
    bots = []
    for file in Path(".").glob("*.py"):
        name = file.name.lower()
        if "lumina" in name and "visualizer" not in name and "launcher" not in name:
            bots.append(file.name)
    bots.sort(reverse=True)
    return bots if bots else ["Geen bot gevonden"]

def start_bot():
    global bot_process
    selected_bot = combo_bot.get()
    risk_profile = combo_risk.get()

    if selected_bot == "Geen bot gevonden":
        messagebox.showerror("Fout", "Geen bot gevonden!")
        return

    # Oude bot afsluiten
    if bot_process and bot_process.poll() is None:
        bot_process.terminate()
        bot_process.wait(timeout=3)

    try:
        # Gebruikt de Python die de launcher zelf draait (sys.executable)
        cmd = [sys.executable, selected_bot]

        env = os.environ.copy()
        env["LUMINA_RISK_PROFILE"] = risk_profile

        bot_process = subprocess.Popen(
            cmd,
            cwd=os.getcwd(),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            env=env
        )
        lbl_bot.config(text=f"✅ {selected_bot} ({risk_profile}) gestart", foreground="#00FF88")
    except Exception as e:
        messagebox.showerror("Fout", f"Bot starten mislukt:\n{e}")

def start_visualizer():
    global viz_process
    if viz_process and viz_process.poll() is None:
        messagebox.showinfo("Info", "Visualizer draait al!")
        return
    try:
        cmd = [sys.executable, str(VISUALIZER_SCRIPT)]
        viz_process = subprocess.Popen(
            cmd,
            cwd=os.getcwd(),
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        lbl_viz.config(text="✅ VISUALIZER ACTIEF", foreground="#00FF88")
    except Exception as e:
        messagebox.showerror("Fout", f"Visualizer starten mislukt:\n{e}")

def stop_all():
    global bot_process, viz_process
    if bot_process:
        bot_process.terminate()
        lbl_bot.config(text="❌ Bot gestopt", foreground="#FF5555")
        bot_process = None
    if viz_process:
        viz_process.terminate()
        lbl_viz.config(text="❌ Visualizer gestopt", foreground="#FF5555")
        viz_process = None
    messagebox.showinfo("Gestopt", "Alle processen gestopt.")

def refresh_bot_list():
    new_bots = get_available_bots()
    combo_bot['values'] = new_bots
    if new_bots and new_bots[0] != "Geen bot gevonden":
        combo_bot.set(new_bots[0])

# ==================== GUI ====================
root = tk.Tk()
root.title("LUMINA PRO LAUNCHER v2.7 – Eenvoudig & VPS-ready")
root.geometry("580x500")
root.configure(bg="#0f0f0f")
root.resizable(False, False)

style = ttk.Style()
style.theme_use("clam")

tk.Label(root, text="LUMINA PRO LAUNCHER", font=("Arial", 24, "bold"), bg="#0f0f0f", fg="#00FF88").pack(pady=20)

tk.Label(root, text="Kies bot versie:", bg="#0f0f0f", fg="#AAAAAA", font=("Arial", 11)).pack(anchor="w", padx=40)
combo_bot = ttk.Combobox(root, width=48, state="readonly", font=("Arial", 10))
combo_bot.pack(pady=8, padx=40)

available_bots = get_available_bots()
combo_bot['values'] = available_bots
if available_bots and available_bots[0] != "Geen bot gevonden":
    combo_bot.set(available_bots[0])

tk.Label(root, text="Risk Profile:", bg="#0f0f0f", fg="#AAAAAA", font=("Arial", 11)).pack(anchor="w", padx=40, pady=(15,5))
combo_risk = ttk.Combobox(root, width=48, state="readonly", font=("Arial", 10), values=["Conservative", "Balanced", "Aggressive"])
combo_risk.set("Balanced")
combo_risk.pack(pady=8, padx=40)

ttk.Button(root, text="▶️ START GEKOZEN BOT", style="Accent.TButton", command=start_bot).pack(pady=20, ipadx=40, ipady=12)

lbl_bot = tk.Label(root, text="Bot: Niet gestart", bg="#0f0f0f", fg="#888888", font=("Arial", 10))
lbl_bot.pack(pady=6)

ttk.Button(root, text="▶️ START VISUALIZER", style="Accent.TButton", command=start_visualizer).pack(pady=12, ipadx=40, ipady=12)

lbl_viz = tk.Label(root, text="Visualizer: Niet gestart", bg="#0f0f0f", fg="#888888", font=("Arial", 10))
lbl_viz.pack(pady=6)

ttk.Button(root, text="⏹️ STOP ALLES", command=stop_all).pack(pady=25, ipadx=50, ipady=10)

tk.Label(root, text="Tip: Start deze launcher vanuit je geactiveerde conda omgeving\n(conda activate NinjaTraderBot)", 
         bg="#0f0f0f", fg="#666666", justify="center").pack(pady=10)

root.mainloop()