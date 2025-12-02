"""
GUI Data Loader + RAM Monitor
- Uses tkinter + ttkbootstrap for GUI
- Monitors RAM usage (psutil) while loading data
- Supports SQLite3, CSV, JSON and TOON (if `toon_format` / `python-toon` installed)
- Shows a live memory plot (matplotlib) and a table preview (pandas -> ttk Treeview)

Requirements (pip):
    pip install ttkbootstrap psutil matplotlib pandas numpy
    # TOON support (optional):
    pip install toon_format   # or: pip install python-toon

Run:
    python ttkbootstrap_ram_monitor_app.py

"""

import threading
import time
import os
import sqlite3
import csv
import json
import sys
from collections import deque

import tkinter as tk
from tkinter import filedialog, messagebox

import ttkbootstrap as tb
from ttkbootstrap.constants import *

# plotting
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# data helpers
import pandas as pd
import numpy as np

# memory
try:
    import psutil
except Exception as e:
    psutil = None

# Try to import TOON parser from known package names
TOON_AVAILABLE = False
TOON_DECODER = None
for modname in ('toon_format', 'toon', 'python_toon', 'toon_format_python', 'toon_python'):
    try:
        TOON_DECODER = __import__(modname)
        TOON_AVAILABLE = True
        print(f"TOON parser found: {modname}")
        break
    except Exception:
        pass


class DataLoaderApp(tb.Window):
    def __init__(self):
        super().__init__(themename="solar")
        self.title("Data Loader + RAM Monitor")
        self.geometry('1100x700')

        # state
        self.mem_history = deque(maxlen=300)
        self.time_history = deque(maxlen=300)
        self.loading = False
        self.stop_event = threading.Event()

        self._build_ui()
        self._start_monitor_loop()

    def _build_ui(self):
        frm = tb.Frame(self, padding=10)
        frm.pack(fill=BOTH, expand=YES)

        left = tb.Frame(frm)
        right = tb.Frame(frm)
        left.pack(side=LEFT, fill=BOTH, expand=NO)
        right.pack(side=RIGHT, fill=BOTH, expand=YES)

        # Left controls
        tb.Label(left, text="Fonte de dados", font=(None, 12, 'bold')).pack(pady=(0,6))
        self.source_var = tk.StringVar(value='file')
        tb.Radiobutton(left, text='Arquivo', variable=self.source_var, value='file').pack(anchor=W)
        tb.Radiobutton(left, text='SQLite (arquivo)', variable=self.source_var, value='sqlite').pack(anchor=W)

        tb.Separator(left, orient='horizontal').pack(fill=X, pady=8)

        tb.Button(left, text='Escolher arquivo...', width=18, command=self.choose_file).pack(pady=6)
        tb.Button(left, text='Carregar', bootstyle=SUCCESS, width=18, command=self.start_load).pack(pady=6)
        tb.Button(left, text='Parar', bootstyle=DANGER, width=18, command=self.stop_load).pack(pady=6)

        tb.Separator(left, orient='horizontal').pack(fill=X, pady=8)
        tb.Label(left, text='Informações', font=(None, 11, 'bold')).pack(pady=(6,4))
        self.info_box = tk.Text(left, height=12, width=40, wrap='word')
        self.info_box.pack()
        self.info_box.insert('end', 'Instruções:\n- Se quiser TOON: instale `pip install toon_format`\n')
        self.info_box.config(state='disabled')

        # Right: plot + preview
        top_right = tb.Frame(right)
        top_right.pack(fill=BOTH, expand=YES)
        bot_right = tb.Frame(right)
        bot_right.pack(fill=BOTH, expand=YES)

        # Memory plot
        self.fig = Figure(figsize=(6,2.5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_ylabel('RAM (GB)')
        self.ax.set_ylim(0, max(4, self._get_total_memory_gb()))
        self.line, = self.ax.plot([], [])
        self.canvas = FigureCanvasTkAgg(self.fig, master=top_right)
        self.canvas.get_tk_widget().pack(fill=BOTH, expand=YES)

        # preview table
        tb.Label(bot_right, text='Preview dos dados', font=(None, 11, 'bold')).pack(anchor=W, padx=6)
        self.table_frame = tb.Frame(bot_right)
        self.table_frame.pack(fill=BOTH, expand=YES)
        self.tree = None

        # status
        self.status_var = tk.StringVar(value='Idle')
        tb.Label(self, textvariable=self.status_var, anchor=W).pack(fill=X, side=BOTTOM)

    def choose_file(self):
        if self.source_var.get() == 'sqlite':
            path = filedialog.askopenfilename(title='Escolha o arquivo SQLite', filetypes=[('SQLite files', '*.sqlite *.db'), ('All files','*.*')])
            if path:
                self.db_path = path
                self._set_status(f"SQLite selecionado: {path}")
        else:
            path = filedialog.askopenfilename(title='Escolha o arquivo', filetypes=[('All supported', '*.csv *.json *.toon *.sqlite *.db'), ('CSV','*.csv'), ('JSON','*.json'), ('TOON','*.toon'), ('All files','*.*')])
            if path:
                self.file_path = path
                self._set_status(f"Arquivo selecionado: {path}")

    def start_load(self):
        if self.loading:
            messagebox.showinfo('Já carregando', 'Um processo de carregamento já está em execução.')
            return
        self.stop_event.clear()
        t = threading.Thread(target=self._load_worker, daemon=True)
        t.start()

    def stop_load(self):
        self.stop_event.set()
        self._set_status('Parando...')

    def _load_worker(self):
        self.loading = True
        start_time = time.time()
        try:
            source = getattr(self, 'file_path', None) if self.source_var.get() != 'sqlite' else getattr(self, 'db_path', None)
            if not source:
                messagebox.showwarning('Nenhum arquivo', 'Escolha um arquivo antes de carregar.')
                self.loading = False
                return

            ext = os.path.splitext(source)[1].lower()
            self._set_status(f'Carregando {source} ...')

            # streaming-load style behavior for large files: simulate chunked loading and monitor memory
            df = None

            if self.source_var.get() == 'sqlite' or ext in ('.db', '.sqlite'):
                # open sqlite and load table names
                conn = sqlite3.connect(source)
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [r[0] for r in cur.fetchall()]
                if not tables:
                    self._set_status('BD SQLite sem tabelas')
                    conn.close()
                    self.loading = False
                    return
                # for demo, pick first table
                table = tables[0]
                self._set_status(f'Carregando tabela `{table}` do SQLite...')
                # load in chunks
                chunks = []
                for chunk in pd.read_sql_query(f"SELECT * FROM {table}", conn, chunksize=1000):
                    chunks.append(chunk)
                    # simulate time and check stop
                    if self.stop_event.is_set():
                        self._set_status('Carregamento interrompido pelo usuário')
                        conn.close()
                        self.loading = False
                        return
                    time.sleep(0.01)
                if chunks:
                    df = pd.concat(chunks, ignore_index=True)
                conn.close()

            elif ext == '.csv':
                # stream with pandas iterator
                it = pd.read_csv(source, chunksize=10000, iterator=True, encoding='utf-8', low_memory=True)
                parts = []
                for chunk in it:
                    parts.append(chunk)
                    if self.stop_event.is_set():
                        self._set_status('Carregamento interrompido pelo usuário')
                        self.loading = False
                        return
                    time.sleep(0.01)
                if parts:
                    df = pd.concat(parts, ignore_index=True)

            elif ext == '.json':
                # for large json, readlines or load
                try:
                    # try to read as JSON lines
                    with open(source, 'r', encoding='utf-8') as f:
                        first = f.read(2)
                        f.seek(0)
                        if first.strip().startswith('['):
                            df = pd.read_json(source, lines=False)
                        else:
                            # try lines
                            df = pd.read_json(source, lines=True)
                except Exception:
                    # fallback to normal load
                    with open(source, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        df = pd.json_normalize(data)

            elif ext == '.toon' or ext == '.toon.txt' or ext == '.toonformat':
                if not TOON_AVAILABLE:
                    self._set_status('TOON não disponível (instale `pip install toon_format`)')
                    messagebox.showwarning('TOON não disponível', 'Para suporte TOON instale: pip install toon_format (ou python-toon)')
                    self.loading = False
                    return
                # use the imported module - try common decode function names
                s = open(source, 'r', encoding='utf-8').read()
                if hasattr(TOON_DECODER, 'decode'):
                    parsed = TOON_DECODER.decode(s)
                elif hasattr(TOON_DECODER, 'loads'):
                    parsed = TOON_DECODER.loads(s)
                else:
                    # try top-level functions
                    parsed = TOON_DECODER.to_python(s) if hasattr(TOON_DECODER, 'to_python') else None
                if parsed is None:
                    raise RuntimeError('Falha ao decodificar TOON')
                df = pd.json_normalize(parsed)

            else:
                # fallback: try pandas autodetect
                df = pd.read_csv(source)

            # show preview
            if isinstance(df, pd.DataFrame):
                self._show_preview(df)
            else:
                # try to convert
                try:
                    df = pd.DataFrame(df)
                    self._show_preview(df)
                except Exception:
                    self._set_status('Tipo de dado carregado não suportado para preview')

            elapsed = time.time() - start_time
            self._set_status(f'Concluído em {elapsed:.2f}s — linhas: {len(df) if isinstance(df, pd.DataFrame) else "?"}')

        except Exception as e:
            self._set_status(f'Erro: {e}')
            messagebox.showerror('Erro ao carregar', str(e))
        finally:
            self.loading = False

    def _show_preview(self, df: pd.DataFrame):
        # clear tree
        for child in self.table_frame.winfo_children():
            child.destroy()
        self.tree = tb.Treeview(self.table_frame, columns=list(df.columns), show='headings', height=12)
        vsb = tb.Scrollbar(self.table_frame, orient='vertical', command=self.tree.yview)
        hsb = tb.Scrollbar(self.table_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=YES)
        vsb.pack(side=RIGHT, fill=Y)
        hsb.pack(side=BOTTOM, fill=X)

        for c in df.columns:
            self.tree.heading(c, text=str(c))
            self.tree.column(c, width=100, anchor=W)

        # insert first 200 rows
        for idx, row in df.head(200).iterrows():
            vals = [self._shortify(v) for v in row.tolist()]
            try:
                self.tree.insert('', 'end', values=vals)
            except Exception:
                pass

    def _shortify(self, v):
        s = str(v)
        if len(s) > 120:
            return s[:117] + '...'
        return s

    def _get_total_memory_gb(self):
        if psutil:
            return round(psutil.virtual_memory().total / (1024**3), 1)
        return 4

    def _start_monitor_loop(self):
        # start a thread to sample memory even when not loading
        def monitor():
            while True:
                if psutil:
                    mem = psutil.virtual_memory().used / (1024**3)
                else:
                    mem = 0.0
                self.mem_history.append(mem)
                self.time_history.append(time.time())
                # update plot in main thread
                try:
                    self.after(1000, self._update_plot)
                except Exception:
                    pass
                time.sleep(1)
        t = threading.Thread(target=monitor, daemon=True)
        t.start()

    def _update_plot(self):
        if not self.time_history:
            return
        times = np.array(self.time_history)
        # normalize time to seconds from end
        t_rel = (times - times[-1])
        mem = np.array(self.mem_history)
        self.line.set_data(t_rel, mem)
        self.ax.relim()
        self.ax.autoscale_view()
        # keep y limit at least total memory
        self.ax.set_ylim(0, max(self._get_total_memory_gb(), mem.max()*1.1))
        self.ax.set_xlim(t_rel.min(), 0)
        self.canvas.draw_idle()

    def _set_status(self, txt):
        self.status_var.set(txt)
        print(txt)


if __name__ == '__main__':
    if psutil is None:
        print('Aviso: psutil não está instalado — instale com `pip install psutil` para monitorar memória corretamente.')
    app = DataLoaderApp()
    app.mainloop()
