import subprocess
import shutil
import os
import time
import socket
import getpass
from datetime import datetime

# Importa a sua nova conexão local
from CONN_LOCAL import get_conexao_forced_tcp

# --- DIRETÓRIOS ---
BASE_DEV = r"C:\Users\CarlosBranches\OneDrive - MARK UP\Área de Trabalho\Ambiente DEV"
BASE_STORAGE = r"\\10.11.142.100\crm\CRM\Business_Inteligence\Ambiente_Producao\Projetos"

def get_git_last_commit_date(filepath):
    try:
        file_dir = os.path.dirname(filepath)
        file_name = os.path.basename(filepath)
        cmd = f'git -C "{file_dir}" log -1 --format=%ct "{file_name}"'
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode().strip()
        return int(result) if result else 0
    except:
        return 0

def registrar_log_sql(cursor, arquivo, caminho, dt_commit):
    query = """
        INSERT INTO DB_MARKUP.mkp.TB_LOG_DEPLOY_GIT 
        (NOME_ARQUIVO, CAMINHO_RELATIVO, DATA_COMMIT, MAQUINA_ORIGEM, USUARIO_ORIGEM, STATUS_SINC)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    dt_commit_formated = datetime.fromtimestamp(dt_commit)
    cursor.execute(query, (arquivo, caminho, dt_commit_formated, socket.gethostname(), getpass.getuser(), 'ATUALIZADO'))

def sync_git_to_storage():
    print(f"Iniciando varredura em: {BASE_DEV}")
    count_updates = 0
    conn = None
    
    try:
        print("Conectando ao banco via TCP (VPN Mode)...")
        conn = get_conexao_forced_tcp()
        cursor = conn.cursor()
        print("✅ Conexão OK!")
    except Exception as e:
        print(f"⚠️ Erro de conexão: {e}")
        print("A sincronização continuará sem gerar logs no SQL.")

    for root, dirs, files in os.walk(BASE_DEV):
        if ".git" in root: continue
            
        for file in files:
            if file.endswith(('.pyc', '.tmp', '.log', '.user', '.ispac', '.dtproj')): continue
                
            local_full_path = os.path.join(root, file)
            relative_path = os.path.relpath(local_full_path, BASE_DEV)
            storage_full_path = os.path.join(BASE_STORAGE, relative_path)
            
            commit_time = get_git_last_commit_date(local_full_path)
            if commit_time == 0: continue
            
            storage_mtime = os.path.getmtime(storage_full_path) if os.path.exists(storage_full_path) else 0
            
            if commit_time > (storage_mtime + 1):
                try:
                    os.makedirs(os.path.dirname(storage_full_path), exist_ok=True)
                    shutil.copy2(local_full_path, storage_full_path)
                    os.utime(storage_full_path, (commit_time, commit_time))
                    
                    print(f"✅ ATUALIZADO: {relative_path}")
                    count_updates += 1

                    if conn:
                        registrar_log_sql(cursor, file, relative_path, commit_time)
                        conn.commit()
                except Exception as err:
                    print(f"❌ Erro no arquivo {file}: {err}")

    if conn:
        cursor.close()
        conn.close()
    
    print(f"\nProcesso finalizado. {count_updates} arquivos sincronizados.")

if __name__ == "__main__":
    sync_git_to_storage()