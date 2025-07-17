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

    conn_proc = sqlite3.connect(db_processos)
    cursor_proc = conn_proc.cursor()

    # Buscar por CPF
    cursor_proc.execute("SELECT processo, tipo, vara, nome, status, cpf, matriculas FROM processos WHERE cpf = ?", (entrada,))
    resultados = cursor_proc.fetchall()

    # Se não encontrou por CPF, tenta por matrícula
    if not resultados:
        cursor_proc.execute("SELECT processo, tipo, vara, nome, status, cpf, matriculas FROM processos")
        for row in cursor_proc.fetchall():
            processo, tipo, vara, nome, status, cpf, matriculas = row
            lista_matriculas = [m.strip() for m in re.split(r"[\/,]", matriculas)]
            if entrada in lista_matriculas:
                resultados.append(row)

    conn_proc.close()

    if not resultados:
        return []

    saida = []

    for processo, tipo, vara, nome, status, cpf, matriculas in resultados:
        # Escolher banco de dados de cálculos com base no tipo
        if tipo == "0003570-25.1999.8.19.0066":
            db_calculos = os.path.join(BASE_DIR, "calculosasvre1999.db")
        elif tipo == "0011127-19.2006.8.19.0066":
            db_calculos = os.path.join(BASE_DIR, "calculosasvre2006.db")
        else:
            db_calculos = os.path.join(BASE_DIR, "calculos.db")

        conn_calc = sqlite3.connect(db_calculos)
        cursor_calc = conn_calc.cursor()
        cursor_calc.execute("SELECT nome, matriculas, link FROM calculos")
        calculos = cursor_calc.fetchall()
        cursor_calc.execute("SELECT nome, link FROM calculos")
        calculos_por_nome = cursor_calc.fetchall()
        conn_calc.close()

        todas_matriculas = list(set([m.strip() for m in re.split(r"[\/,]", matriculas) if m]))

        links = []
        for nome_calc, mats_calc, link in calculos:
            mats = [m.strip() for m in re.split(r"[\/,]", mats_calc)] if mats_calc else []
            if any(m in todas_matriculas for m in mats):
                if link not in links:
                    links.append(link)

        if not links:
            nome_normalizado = re.sub(r"\s+", "", nome).lower()
            for nome_calc, link in calculos_por_nome:
                nome_calc_normalizado = re.sub(r"\s+", "", nome_calc).lower()
                if nome_normalizado in nome_calc_normalizado or nome_calc_normalizado in nome_normalizado:
                    if link not in links:
                        links.append(link)

        saida.append({
            "tipo": tipo,
            "processo": processo,
            "vara": vara,
            "nome": nome,
            "status": status,
            "cpf": cpf,
            "matriculas": " / ".join(todas_matriculas),
            "calculos": links
        })

    return saida

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
