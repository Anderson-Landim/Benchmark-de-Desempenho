
# Gerador e Comparador de Dados (SQLite, CSV, JSON e TOON)

Este projeto é composto por  **dois programas complementares** :

1. **Gerador de Dados Fake (`bd.py`)**
   Gera grandes volumes de dados fictícios e exporta automaticamente para diferentes formatos.
2. **Comparador de Formatos (`main.py`)**
   Carrega arquivos gerados, mede desempenho, uso de memória, tamanho e permite buscas nos dados.

O objetivo é **comparar formatos de armazenamento** em termos de:

* Tempo de carregamento
* Uso de memória RAM
* Tamanho em disco
* Facilidade de leitura e busca

---

## 📦 Formatos Suportados

* **SQLite** (.sqlite / .db)
* **CSV** (.csv)
* **JSON** (.json)
* **TOON** (formato texto customizado separado por `|`)

---

## 🧩 Estrutura do Projeto

```
📁 projeto/
 ├── bd.py        # Gerador de dados fake e exportação
 ├── main.py      # Interface de comparação e análise
 └── README.md    # Documentação
```

---

## ⚙️ Requisitos

Python 3.9+

Bibliotecas necessárias:

```bash
pip install faker ttkbootstrap pandas psutil
```

(As demais bibliotecas usadas fazem parte da biblioteca padrão do Python.)

---

## 🚀 Como Usar

### 1️⃣ Gerar os dados (`bd.py`)

Execute:

```bash
python bd.py
```

Funcionalidades:

* Escolha a **quantidade de registros**
* Selecione a **pasta de saída**
* Geração automática dos arquivos:
  * `dados.sqlite`
  * `dados.csv`
  * `dados.json`
  * `dados.toon`
* Barra de progresso
* Exibição do tamanho final de cada arquivo

---

### 2️⃣ Comparar os formatos (`main.py`)

Execute:

```bash
python main.py
```

Funcionalidades:

* Interface gráfica com painéis separados por formato
* Carregamento de arquivos individuais
* Medição automática de:
  * Tempo de leitura
  * Quantidade de linhas
  * Uso de RAM
  * Tamanho do arquivo
  * Velocidade (linhas/segundo)
* Ranking automático de desempenho
* Busca textual nos dados
* Destaque visual para resultados encontrados

---

## 📊 Comparação Automática

Após carregar os arquivos:

* O painel **Comparação** mostra:
  * Formato mais rápido
  * Formato mais lento
  * Ranking geral
* Destaque em cores:
  * 🟢 Mais rápido
  * 🔴 Mais lento

---

## 🔍 Busca nos Dados

* A busca funciona em **todas as colunas**
* Não diferencia maiúsculas/minúsculas
* Resultados são destacados na tabela

---

## 🧪 Caso de Uso Sugerido

1. Gere 10k, 100k ou 1M de registros no `bd.py`
2. Abra os arquivos no `main.py`
3. Compare:
   * Qual formato carrega mais rápido?
   * Qual consome menos memória?
   * Qual ocupa menos espaço?

Ideal para estudos de:

* Estruturas de dados
* Bancos de dados
* Sistemas de arquivos
* Performance em Python

---

## 📝 Observações

* A tabela de visualização limita a exibição a **1000 linhas** para evitar travamentos
* O formato **TOON** é apenas experimental e não possui compressão
* SQLite utiliza apenas a primeira tabela encontrada no banco

---

## 📄 Licença

Projeto livre para uso educacional e experimental.
