import pandas as pd
import sqlite3
import re
import os

# Caminhos atualizados
base_path = r"C:\Users\PedroDiaz\Desktop\Render Atualizado"
excel_path = os.path.join(base_path, "links_calculos.xlsx")
db_path = os.path.join(base_path, "calculos.db")

# 📥 Ler a planilha
df = pd.read_excel(excel_path, dtype=str)
df = df[["Nome", "Link"]].dropna()

# 🧠 Função para extrair nome e matrículas, tratando "e", "/", "-", vírgulas ou espaços
def extrair_nome_e_matriculas(valor):
    valor = valor.replace("CÁLCULOS -", "").replace(".pdf", "").strip()

    # Separar o nome das matrículas
    partes = re.split(r'\s*-\s*', valor, maxsplit=1)
    if len(partes) < 2:
        return valor.strip(), ""

    nome = partes[0].strip()
    matriculas_raw = partes[1]

    # Dividir por múltiplos separadores
    matriculas = re.split(r'\s*(?:e|/|,|-|\s)\s*', matriculas_raw)
    matriculas = [m for m in matriculas if m.isdigit()]

    return nome, " / ".join(matriculas)

# ⚙️ Aplicar extração
df[["nome", "matriculas"]] = df["Nome"].apply(lambda x: pd.Series(extrair_nome_e_matriculas(x)))

# 💾 Criar banco de dados SQLite
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS calculos")

cursor.execute('''
    CREATE TABLE calculos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        matriculas TEXT NOT NULL,
        link TEXT NOT NULL
    )
''')

# Inserir dados no banco
for _, row in df.iterrows():
    cursor.execute("""
        INSERT INTO calculos (nome, matriculas, link)
        VALUES (?, ?, ?)
    """, (row["nome"], row["matriculas"], row["Link"]))

conn.commit()
conn.close()

print(f"✅ Banco de dados 'calculos.db' criado com sucesso em: {db_path}")
print(f"🔗 Total de arquivos processados: {len(df)}")
