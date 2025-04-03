import os
import re
import sqlite3
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder="static")
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", 5000))

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(os.path.join(BASE_DIR, "static"), filename)

@app.route("/index.html")
def index_html():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/consulta", methods=["GET"])
def consulta():
    entrada = request.args.get("processo", "").strip()
    if not entrada:
        return jsonify({"erro": "Número do processo, CPF ou matrícula é obrigatório"}), 400

    entrada = re.sub(r"[^\d]", "", entrada)  # remove caracteres não numéricos

    resultados = buscar_processo_por_entrada(entrada)
    if resultados:
        return jsonify(resultados)
    else:
        return jsonify({"erro": "Nenhum resultado encontrado"}), 404

def buscar_processo_por_entrada(entrada):
    db_processos = os.path.join(BASE_DIR, "processos.db")
    db_calculos = os.path.join(BASE_DIR, "calculos.db")

    conn_proc = sqlite3.connect(db_processos)
    cursor_proc = conn_proc.cursor()

    # Buscar por CPF (normalizado para 11 dígitos)
    cursor_proc.execute("SELECT processo, vara, nome, status, cpf, matriculas FROM processos WHERE cpf = ?", (entrada,))
    result = cursor_proc.fetchone()

    # Se não achar por CPF, busca entre todas as matrículas
    if not result:
        cursor_proc.execute("SELECT processo, vara, nome, status, cpf, matriculas FROM processos")
        for row in cursor_proc.fetchall():
            processo, vara, nome, status, cpf, matriculas = row
            lista_matriculas = [m.strip() for m in re.split(r"[\/,]", matriculas)]
            if entrada in lista_matriculas:
                result = row
                break

    conn_proc.close()

    if not result:
        return []

    processo, vara, nome, status, cpf, matriculas = result
    lista_matriculas = [m.strip() for m in re.split(r"[\/,]", matriculas)]

    # Procurar links relacionados no banco de cálculos
    conn_calc = sqlite3.connect(db_calculos)
    cursor_calc = conn_calc.cursor()

    links = []
    cursor_calc.execute("SELECT nome, matriculas, link FROM calculos")
    for nome_calc, matr_calc, link in cursor_calc.fetchall():
        mats = [m.strip() for m in re.split(r"[\/,]", matr_calc)]
        if any(m in lista_matriculas for m in mats):
            if link not in links:
                links.append(link)

    conn_calc.close()

    return [{
        "processo": processo,
        "vara": vara,
        "nome": nome,
        "status": status,
        "cpf": cpf,
        "matriculas": matriculas,
        "calculos": links
    }]
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
