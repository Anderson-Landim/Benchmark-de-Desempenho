import csv
import json
import sqlite3
import threading
import os
from faker import Faker
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

fake = Faker()


# -------------------------------------------------------
# Gera N registros fake
# -------------------------------------------------------
def gerar_dados(qtd, callback=None):
    dados = []
    for i in range(qtd):
        dados.append({
            "id": i + 1,
            "nome": fake.name(),
            "email": fake.email(),
            "idade": fake.random_int(18, 70),
            "cidade": fake.city()
        })
        # Atualiza progresso
        if callback:
            callback(i + 1, qtd)
    return dados


# -------------------------------------------------------
# Exportação em todos os formatos (com progresso)
# -------------------------------------------------------
def exportar_todos(dados, pasta_saida, callback):
    tamanhos = {}

    etapas = 4  # SQLite, CSV, JSON, TOON
    etapa_atual = 0

    # --- SQLite ---
    etapa_atual += 1
    callback(etapa_atual, etapas)

    sqlite_path = os.path.join(pasta_saida, "dados.sqlite")
    conn = sqlite3.connect(sqlite_path)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS pessoas (
                    id INTEGER PRIMARY KEY,
                    nome TEXT,
                    email TEXT,
                    idade INTEGER,
                    cidade TEXT
                )""")
    cur.executemany(
        "INSERT INTO pessoas (id, nome, email, idade, cidade) VALUES (:id, :nome, :email, :idade, :cidade)",
        dados
    )
    conn.commit()
    conn.close()
    tamanhos["SQLite"] = os.path.getsize(sqlite_path)

    # --- CSV ---
    etapa_atual += 1
    callback(etapa_atual, etapas)

    csv_path = os.path.join(pasta_saida, "dados.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=dados[0].keys())
        writer.writeheader()
        writer.writerows(dados)
    tamanhos["CSV"] = os.path.getsize(csv_path)

    # --- JSON ---
    etapa_atual += 1
    callback(etapa_atual, etapas)

    json_path = os.path.join(pasta_saida, "dados.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, separators=(",", ":"))
    tamanhos["JSON"] = os.path.getsize(json_path)

    # --- TOON ---
    etapa_atual += 1
    callback(etapa_atual, etapas)

    toon_path = os.path.join(pasta_saida, "dados.toon")

    with open(toon_path, "w", encoding="utf-8") as f:
        f.write("|".join(dados[0].keys()) + "\n")
        for linha in dados:
            f.write("|".join([str(v) for v in linha.values()]) + "\n")
    tamanhos["TOON"] = os.path.getsize(toon_path)

    return tamanhos


# -------------------------------------------------------
# Interface
# -------------------------------------------------------
class App(tb.Window):
    def __init__(self):
        super().__init__(title="Gerador de Dados Fake", themename="cyborg")
        self.geometry("550x400")

        self.qtd_var = tk.IntVar(value=1000)
        self.pasta_var = tk.StringVar()

        self._build_ui()

    def _build_ui(self):
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill="both", expand=True)

        # Quantidade
        ttk.Label(frame, text="Quantidade de registros (linhas):").pack(anchor="w")
        ttk.Entry(frame, textvariable=self.qtd_var, width=15).pack(anchor="w", pady=5)

        # Pasta de saída
        ttk.Label(frame, text="Pasta de saída:").pack(anchor="w")
        f = ttk.Frame(frame)
        f.pack(fill="x")
        ttk.Entry(f, textvariable=self.pasta_var).pack(side="left", fill="x", expand=True)
        ttk.Button(f, text="Selecionar", command=self.selecionar_pasta).pack(side="right")

        # Botão gerar
        ttk.Button(
            frame, text="Gerar Todos os Formatos", bootstyle=SUCCESS, command=self.iniciar_thread
        ).pack(pady=20, fill="x")

        # Progressbar
        self.progresso = ttk.Progressbar(frame, mode="determinate")
        self.progresso.pack(fill="x", pady=5)

        # Status
        self.status = ttk.Label(frame, text="", bootstyle=INFO)
        self.status.pack(fill="x")

    def selecionar_pasta(self):
        pasta = filedialog.askdirectory()
        if pasta:
            self.pasta_var.set(pasta)

    # ---------------- THREAD -------------------

    def iniciar_thread(self):
        self.progresso["value"] = 0
        thread = threading.Thread(target=self.gerar, daemon=True)
        thread.start()

    # -------- callback do progresso ----------
    def atualizar_barra(self, etapa, total):
        pct = (etapa / total) * 100
        self.progresso["value"] = pct
        self.status.config(text=f"Progresso: {pct:.1f}%")
        self.update_idletasks()

    def gerar(self):
        try:
            qtd = self.qtd_var.get()
            if qtd <= 0:
                messagebox.showerror("Erro", "A quantidade deve ser maior que zero.")
                return

            pasta = self.pasta_var.get()
            if not pasta:
                messagebox.showerror("Erro", "Selecione a pasta de saída.")
                return

            self.status.config(text="Gerando dados...")
            self.update_idletasks()

            # Progresso da geração de dados
            dados = gerar_dados(qtd, callback=self.atualizar_barra)

            # Progresso da exportação
            def callback_export(etapa, total):
                self.atualizar_barra(etapa + qtd, total + qtd)

            tamanhos = exportar_todos(dados, pasta, callback_export)

            # Montar mensagem de tamanho
            texto = "Tamanhos gerados:\n"
            for nome, bytes_ in tamanhos.items():
                mb = bytes_ / (1024 * 1024)
                texto += f"{nome}: {mb:.2f} MB  "

            self.status.config(text=texto)

            self.progresso["value"] = 100

            messagebox.showinfo("OK", "Arquivos gerados com sucesso!")

        except Exception as e:
            messagebox.showerror("Erro", str(e))


if __name__ == "__main__":
    App().mainloop()
