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

    # normaliza: mantém só dígitos para buscar por CPF/matrícula
    entrada = re.sub(r"[^\d]", "", entrada)

    resultados = buscar_processo_por_entrada(entrada)
    if resultados:
        return jsonify(resultados)
    else:
        return jsonify({"erro": "Nenhum resultado encontrado"}), 404

def escolher_db_calculos(tipo: str) -> str:
    """
    Decide qual banco de cálculos usar com base no 'tipo' do processo.
    """
    tipo = (tipo or "").strip()
    if tipo == "0003570-25.1999.8.19.0066":
        return os.path.join(BASE_DIR, "calculosasvre1999.db")
    elif tipo == "0011127-19.2006.8.19.0066":
        return os.path.join(BASE_DIR, "calculosasvre2006.db")
    elif tipo == "0006175-79.2015.8.19.0066":
        # NOVO mapeamento solicitado
        return os.path.join(BASE_DIR, "calculosSEPE2.db")
    else:
        return os.path.join(BASE_DIR, "calculos.db")

def status_e_protocolado(status: str) -> bool:
    return (status or "").strip().lower() == "protocolado"

def buscar_processo_por_entrada(entrada):
    db_processos = os.path.join(BASE_DIR, "processos.db")

    conn_proc = sqlite3.connect(db_processos)
    cursor_proc = conn_proc.cursor()

    # Buscar por CPF
    cursor_proc.execute("""
        SELECT processo, tipo, vara, nome, status, cpf, matriculas
        FROM processos
        WHERE cpf = ?
    """, (entrada,))
    resultados = cursor_proc.fetchall()

    # Se não encontrou por CPF, tenta por matrícula (matrículas podem vir separadas por "/" ou ",")
    if not resultados:
        cursor_proc.execute("SELECT processo, tipo, vara, nome, status, cpf, matriculas FROM processos")
        for row in cursor_proc.fetchall():
            processo, tipo, vara, nome, status, cpf, matriculas = row
            lista_matriculas = [m.strip() for m in re.split(r"[\/,]", matriculas or "") if m.strip()]
            if entrada in lista_matriculas:
                resultados.append(row)

    conn_proc.close()

    if not resultados:
        return []

    processos_dict = {}

    for processo, tipo, vara, nome, status, cpf, matriculas in resultados:
        # Decide o banco de cálculos conforme o tipo
        db_calculos = escolher_db_calculos(tipo)

        # Por padrão, nenhum link se o status NÃO for "Protocolado"
        links = []
        if status_e_protocolado(status) and os.path.exists(db_calculos):
            try:
                conn_calc = sqlite3.connect(db_calculos)
                cursor_calc = conn_calc.cursor()

                # Tabela esperada: calculos(nome, matriculas, link)
                cursor_calc.execute("SELECT nome, matriculas, link FROM calculos")
                calculos = cursor_calc.fetchall()

                # Também deixo um índice por nome para fallback
                cursor_calc.execute("SELECT nome, link FROM calculos")
                calculos_por_nome = cursor_calc.fetchall()
                conn_calc.close()

                # Normaliza matrículas do processo
                todas_matriculas = list(set([m.strip() for m in re.split(r"[\/,]", matriculas or "") if m.strip()]))

                # 1) Match por matrícula
                for nome_calc, mats_calc, link in calculos:
                    mats = [m.strip() for m in re.split(r"[\/,]", mats_calc or "") if m.strip()]
                    if any(m in todas_matriculas for m in mats):
                        if link and link not in links:
                            links.append(link)

                # 2) Fallback por nome (normalizado) se ainda não achou
                if not links and nome:
                    nome_normalizado = re.sub(r"\s+", "", nome).lower()
                    for nome_calc, link in calculos_por_nome:
                        nome_calc_normalizado = re.sub(r"\s+", "", (nome_calc or "")).lower()
                        if nome_calc_normalizado and (nome_normalizado in nome_calc_normalizado or nome_calc_normalizado in nome_normalizado):
                            if link and link not in links:
                                links.append(link)

            except Exception as e:
                print(f"Erro ao acessar {db_calculos}: {e}")
        else:
            # Se não for protocolado, apenas loga (sem links)
            if not status_e_protocolado(status):
                print(f"Status não é 'Protocolado' para {processo}. Links suprimidos.")
            elif not os.path.exists(db_calculos):
                print(f"Banco de dados não encontrado (ainda): {db_calculos}")

        # Agrupar por número de processo (unifica múltiplas linhas do mesmo processo)
        if processo in processos_dict:
            # Mantém o status mais “forte” se algum for Protocolado
            if status_e_protocolado(status):
                processos_dict[processo]["status"] = status
                # só adiciona links quando protocolado
                processos_dict[processo]["calculos"].extend([l for l in links if l not in processos_dict[processo]["calculos"]])
        else:
            processos_dict[processo] = {
                "tipo": tipo or "",
                "processo": processo,
                "vara": vara or "",
                "nome": nome or "",
                "status": status or "",
                "cpf": cpf or "",
                "matriculas": " / ".join([m.strip() for m in re.split(r"[\/,]", matriculas or "") if m.strip()]),
                # Se não for Protocolado, fica lista vazia (sem botão de download no front)
                "calculos": links if status_e_protocolado(status) else []
            }

    # Retorna lista de processos agregados
    return list(processos_dict.values())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)


