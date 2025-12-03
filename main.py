import ttkbootstrap as tb
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import os
import json
import sqlite3
import pandas as pd

"""
Multi-column Data Loader and Comparator
Layout: 4 side-by-side panels (SQLite, CSV, JSON, TOON)
Each panel: Select file, Load, Search, Log, Table view
Bottom: Comparison summary (format | file | time(s) | rows)

Requirements:
    pip install ttkbootstrap pandas
    optional: pip install toon_format (for TOON support)

Run:
    python multi_format_comparator.py
"""


class FormatPanel(ttk.LabelFrame):
    def __init__(self, master, title, fmt_key, comparator, *args, **kwargs):
        super().__init__(master, text=title, padding=8, *args, **kwargs)
        self.fmt_key = fmt_key
        self.comparator = comparator
        self.selected_file = None
        self.df = None
        self._build_ui()

    def _build_ui(self):

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=X, pady=(0,6))

        ttk.Button(btn_frame, text="Selecionar", command=self.select_file, bootstyle=PRIMARY).pack(side=LEFT)
        ttk.Button(btn_frame, text="Carregar", command=self.load_file, bootstyle=SUCCESS).pack(side=LEFT, padx=6)

        self.info_var = tk.StringVar(value='Nenhum arquivo')
        ttk.Label(self, textvariable=self.info_var).pack(anchor=W)

        # Log area
        self.log = tk.Text(self, height=6, bg="#101010", fg="#a8ffb0", wrap='word')
        self.log.pack(fill=X, pady=6)
        # Loading spinner (fica oculto até carregar)
        self.spinner = ttk.Progressbar(self, mode="indeterminate", bootstyle=INFO)
        self.spinner.pack(fill=X, pady=4)
        self.spinner.stop()
        self.spinner.place_forget()


        # Search
        search_frame = ttk.Frame(self)
        search_frame.pack(fill=X, pady=(0,6))
        self.search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.search_var).pack(side=LEFT, fill=X, expand=True)
        ttk.Button(search_frame, text='Buscar', command=self.search, bootstyle=INFO).pack(side=LEFT, padx=6)

        # Table
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=BOTH, expand=True)
        self.table = ttk.Treeview(table_frame, show='headings')
        self.table.pack(fill=BOTH, expand=True, side=LEFT)
        vsb = ttk.Scrollbar(table_frame, orient='vertical', command=self.table.yview)
        hsb = ttk.Scrollbar(table_frame, orient='horizontal', command=self.table.xview)
        self.table.configure(yscroll=vsb.set, xscroll=hsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        hsb.pack(side=BOTTOM, fill=X)

        # tag style for highlights
        self.table.tag_configure('found', background='#fff3a3')

    def _append_log(self, txt):
        now = time.strftime('%H:%M:%S')
        self.log.insert(END, f'[{now}] {txt}\n')
        self.log.see(END)

    def select_file(self):
        ft = []
        if self.fmt_key == 'sqlite':
            ft = [('SQLite', '*.db *.sqlite *.sqlite3'), ('All','*.*')]
        elif self.fmt_key == 'csv':
            ft = [('CSV','*.csv'), ('All','*.*')]
        elif self.fmt_key == 'json':
            ft = [('JSON','*.json'), ('All','*.*')]
        elif self.fmt_key == 'toon':
            ft = [('TOON','*.toon'), ('All','*.*')]
        path = filedialog.askopenfilename(filetypes=ft)
        if path:
            self.selected_file = path
            self.info_var.set(f'Selecionado: {os.path.basename(path)}')
            self._append_log(f'Arquivo selecionado: {path}')

    def load_file(self):
        if not self.selected_file:
            messagebox.showwarning('Aviso', 'Selecione um arquivo antes de carregar.')
            return

        # Mostrar spinner
        self.spinner.place(relx=0.02, rely=0.42, relwidth=0.96)
        self.spinner.start(10)

        threading.Thread(target=self._load_worker, daemon=True).start()


    def _load_worker(self):
        path = self.selected_file
        self._append_log(f'Iniciando carregamento ({self.fmt_key})')
        t0 = time.perf_counter()
        try:
            if self.fmt_key == 'sqlite':
                df = self._load_sqlite(path)
            elif self.fmt_key == 'csv':
                df = pd.read_csv(path)
            elif self.fmt_key == 'json':
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    df = pd.DataFrame(data)
                else:
                    df = pd.json_normalize(data)
            elif self.fmt_key == 'toon':
                with open(path, 'r', encoding='utf-8') as f:
                    linhas = f.readlines()

                # Determina número de colunas pela primeira linha
                colunas = ['col_' + str(i+1) for i in range(len(linhas[0].split('|')))]

                parsed = []
                for linha in linhas:
                    partes = linha.strip().split('|')
                    parsed.append(partes)

                df = pd.DataFrame(parsed, columns=colunas)

            else:
                raise RuntimeError('Formato não suportado')

        except Exception as e:
            self._append_log(f'ERRO ao carregar: {e}')
            self.df = None
            self.comparator.record(self.fmt_key, path, None, None)
            self.spinner.stop()
            self.spinner.place_forget()

            return

        t1 = time.perf_counter()
        elapsed = round(t1 - t0, 4)
        rows = len(df)
        self.df = df
        self._append_log(f'Concluído em {elapsed}s — {rows} linhas')
        self.info_var.set(f'Arquivo: {os.path.basename(path)} | {rows} linhas')
        self._fill_table()
        self.comparator.record(self.fmt_key, path, elapsed, rows)
        # parar spinner quando terminar
        self.spinner.stop()
        self.spinner.place_forget()

    def _load_sqlite(self, path):
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        if not tables:
            conn.close()
            raise RuntimeError('BD SQLite sem tabelas')
        table = tables[0]
        if len(tables) > 1:
            # ask user for table
            table = self._ask_table_choice(tables)
        df = pd.read_sql_query(f'SELECT * FROM "{table}"', conn)
        conn.close()
        return df

    def _ask_table_choice(self, tables):
        win = tk.Toplevel(self)
        win.title('Escolha a tabela')
        win.geometry('300x120')
        ttk.Label(win, text='Selecione a tabela:').pack(pady=6)
        cmb = ttk.Combobox(win, values=tables, state='readonly')
        cmb.pack(pady=6)
        cmb.current(0)
        chosen = tk.StringVar()

        def confirm():
            chosen.set(cmb.get())
            win.destroy()

        ttk.Button(win, text='OK', command=confirm).pack(pady=6)
        win.wait_window()
        return chosen.get()

    def _fill_table(self):
        # limpar colunas e linhas atuais
        for c in self.table['columns']:
            self.table.heading(c, text='')
        self.table.delete(*self.table.get_children())

        cols = list(map(str, self.df.columns))
        self.table['columns'] = cols

        # configurar colunas centralizadas
        for c in cols:
            self.table.heading(c, text=c, anchor=CENTER)
            self.table.column(c, width=140, anchor=CENTER)

        # Inserir linhas (limitado para não travar a UI)
        maxrows = min(len(self.df), 1000)
        for idx in range(maxrows):
            vals = [self._shortify(v) for v in self.df.iloc[idx].tolist()]
            self.table.insert('', 'end', values=vals)


    def _shortify(self, v):
        s = '' if pd.isna(v) else str(v)
        return s if len(s) <= 200 else s[:197] + '...'

    def search(self):
        if self.df is None:
            self._append_log('ERRO: nenhum dado carregado')
            return
        term = self.search_var.get().strip()
        if not term:
            self._append_log('Aviso: termo de busca vazio')
            return
        t0 = time.perf_counter()
        try:
            mask = self.df.apply(lambda col: col.astype(str).str.contains(term, case=False, na=False))
            found = self.df[mask.any(axis=1)]
        except Exception as e:
            self._append_log(f'ERRO na busca: {e}')
            return
        t1 = time.perf_counter()
        elapsed = round(t1 - t0, 4)
        count = len(found)
        self._append_log(f"Busca '{term}' → {count} resultados ({elapsed}s)")
        self._highlight_found(found)

    def _highlight_found(self, found_df):
        # clear tags
        for item in self.table.get_children():
            self.table.item(item, tags='')
        found_set = {tuple(self._shortify(v) for v in row) for row in found_df.values}
        for item in self.table.get_children():
            vals = tuple(self.table.item(item)['values'])
            if vals in found_set:
                self.table.item(item, tags=('found',))


class ComparatorPanel(ttk.LabelFrame):
    def __init__(self, master, *args, **kwargs):
        super().__init__(master, text='Comparação', padding=8, *args, **kwargs)
        self.records = {}  # fmt -> (file, time, rows)
        self._build_ui()

    def _build_ui(self):
        cols = ('format', 'file', 'time_s', 'rows', 'size', 'speed', 'rank')
        self.table = ttk.Treeview(self, columns=cols, show='headings', height=6)

        headers = {
            'format': 'Formato',
            'file': 'Arquivo',
            'time_s': 'Tempo (s)',
            'rows': 'Linhas',
            'size': 'Tamanho',
            'speed': 'Linhas/s',
            'rank': 'Ranking'
        }

        for c in cols:
            self.table.heading(c, text=headers[c], anchor=CENTER)
            self.table.column(c, width=140, anchor=CENTER)

        # cores suaves para destaque
        self.table.tag_configure("fastest", background="#d4fcd4")   # verde pastel
        self.table.tag_configure("slowest", background="#fcd4d4")   # vermelho suave

        self.table.pack(fill=BOTH, expand=True)

    def record(self, fmt_key, file, time_s, rows):
        self.records[fmt_key] = (file, time_s, rows)
        self._refresh()

    def _refresh(self):
        self.table.delete(*self.table.get_children())

        valid_times = [(fmt, rec[0], rec[1], rec[2]) 
                       for fmt, rec in self.records.items() if rec[1] is not None]

        if not valid_times:
            return

        fastest = min(valid_times, key=lambda x: x[2])
        slowest = max(valid_times, key=lambda x: x[2])
        ordered = sorted(valid_times, key=lambda x: x[2])
        ranking = {fmt: i + 1 for i, (fmt, *_rest) in enumerate(ordered)}

        for fmt in ('sqlite', 'csv', 'json', 'toon'):
            rec = self.records.get(fmt)
            if not rec:
                self.table.insert('', 'end', values=(fmt, '', '', '', '', '', ''))
                continue

            file, t, rows = rec
            filename = os.path.basename(file) if file else ''

            # tamanho do arquivo
            if file:
                size_bytes = os.path.getsize(file)
                size_str = (
                    f"{size_bytes/1024:.1f} KB"
                    if size_bytes < 1_000_000 else
                    f"{size_bytes/1024/1024:.2f} MB"
                )
            else:
                size_str = ''

            # velocidade (linhas/seg)
            speed = ''
            if t and rows:
                speed = f"{int(rows / t):,}".replace(",", ".")

            # ranking
            rnk = ranking.get(fmt, '')

            row = (fmt, filename, t, rows, size_str, speed, rnk)

            # destaque suave
            tag = ''
            if fmt == fastest[0]:
                tag = 'fastest'
            elif fmt == slowest[0]:
                tag = 'slowest'

            self.table.insert('', 'end', values=row, tags=(tag,))


class App(tb.Window):
    def __init__(self):
        super().__init__(themename='solar')
        self.title('Comparator — SQLite | CSV | JSON | TOON')
        self.geometry('1400x800')
        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self, padding=10)
        main.pack(fill=BOTH, expand=True)

        # four columns in a paned window
        paned = ttk.PanedWindow(main, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=True)

        self.comparator = ComparatorPanel(self)

        self.panels = {}
        for title, key in (('SQLite', 'sqlite'), ('CSV', 'csv'), ('JSON', 'json'), ('TOON', 'toon')):
            frame = ttk.Frame(paned)
            panel = FormatPanel(frame, title, key, self.comparator)
            panel.pack(fill=BOTH, expand=True)
            paned.add(frame, weight=1)
            self.panels[key] = panel

        # bottom comparison
        self.comparator.pack(fill=X, pady=8)
        ttk.Button(main, text="Limpar Tudo", bootstyle=DANGER, command=self.limpar_tudo)\
            .pack(fill=X, pady=(10,5))

    def run(self):
        self.mainloop()
    def limpar_tudo(self):
        # limpar comparador
        self.comparator.records = {}
        self.comparator._refresh()

        # limpar cada painel
        for panel in self.panels.values():
            panel.selected_file = None
            panel.df = None

            # limpar info
            panel.info_var.set("Nenhum arquivo")

            # limpar log
            panel.log.delete("1.0", "end")

            # limpar tabela
            panel.table.delete(*panel.table.get_children())
            panel.table['columns'] = []

            # parar spinner se estiver ativo
            try:
                panel.spinner.stop()
                panel.spinner.place_forget()
            except:
                pass

        messagebox.showinfo("Limpo", "Todos os dados foram apagados.")


if __name__ == '__main__':
    app = App()
    app.run()
