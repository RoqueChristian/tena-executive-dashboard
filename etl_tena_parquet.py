import os
import logging
import oracledb
import pandas as pd
from datetime import datetime
import streamlit as st 

# ============================================================================
# CONFIGURAÇÃO DE LOGGING
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(metadata)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.LoggerAdapter(logging.getLogger(__name__), {"metadata": "ETL-TENA-DATALAKE"})

# ============================================================================
# DRIVER ORACLE - MODO THICK
# ============================================================================
CLIENT_DIR = r"C:\instantclient_21"
try:
    oracledb.init_oracle_client(lib_dir=CLIENT_DIR)
    logger.info("Oracle Instant Client inicializado com sucesso.")
except Exception as e:
    logger.error(f"Falha ao inicializar Oracle Client: {e}")
    raise

def get_oracle_connection():
    return oracledb.connect(
        user=st.secrets["ORACLE_USER"],
        password=st.secrets["ORACLE_PASSWORD"],
        dsn=st.secrets["ORACLE_DSN"] 
    )

def read_sql_file(filename: str) -> str:
    path = os.path.join('sql', filename)
    with open(path, 'r', encoding='utf-8') as file:
        return file.read()

# ============================================================================
# EXTRAÇÃO PARA CAMADA BRONZE (PARQUET)
# ============================================================================
def extract_to_parquet(oracle_conn, sql_filename: str, target_name: str):
    """
    Executa a query na origem e materializa os resultados em formato colunar Parquet.
    Implementa versionamento de arquivos via timestamp para evitar sobrescrita (imutabilidade).
    """
    query = read_sql_file(sql_filename)
    output_dir = os.path.join(os.getcwd(), 'data')
    
    # Garante a existência do diretório 'data' evidenciado na estrutura do projeto
    os.makedirs(output_dir, exist_ok=True)
    
    # Timestamp para versionamento do arquivo (Padrão Data Lake)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(output_dir, f"{target_name}_{timestamp}.parquet")
    
    with oracle_conn.cursor() as cursor:
        logger.info(f"Iniciando extração de {target_name}...")
        cursor.execute(query)
        
        columns = [col[0].lower() for col in cursor.description]
        records = cursor.fetchall()
        
        if not records:
            logger.warning(f"Nenhum registro retornado para {target_name}. Processamento ignorado.")
            return
            
        # Conversão em memória para DataFrame
        df = pd.DataFrame(records, columns=columns)
        
        # Escrita otimizada utilizando PyArrow e compressão Snappy
        df.to_parquet(file_path, engine='pyarrow', compression='snappy', index=False)
        logger.info(f"Arquivo gerado com sucesso: {file_path} (Total: {len(df)} linhas).")

# ============================================================================
# ORQUESTRADOR PRINCIPAL
# ============================================================================
def main():
    logger.info("Iniciando execução do Pipeline de Extração para Parquet.")
    
    try:
        oracle_conn = get_oracle_connection()
        
        # Dimensões
        logger.info("--- INICIANDO EXTRAÇÃO DE DIMENSÕES ---")
        extract_to_parquet(oracle_conn, 'extract_dim_filial.sql', 'dim_filial')
        extract_to_parquet(oracle_conn, 'extract_dim_fornecedor.sql', 'dim_fornecedor')
        extract_to_parquet(oracle_conn, 'extract_dim_cliente.sql', 'dim_cliente')
        extract_to_parquet(oracle_conn, 'extract_dim_produto.sql', 'dim_produto')
        
        # Fatos
        logger.info("--- INICIANDO EXTRAÇÃO DE TABELAS FATO ---")
        extract_to_parquet(oracle_conn, 'extract_estoque_diario.sql', 'fato_estoque_diario')
        extract_to_parquet(oracle_conn, 'extract_sell_out.sql', 'fato_sell_out')
        extract_to_parquet(oracle_conn, 'extract_sell_in.sql', 'fato_sell_in')
        extract_to_parquet(oracle_conn, 'extract_recebimento.sql', 'fato_recebimento')
        
        logger.info("Pipeline Parquet concluído com sucesso.")
        
    except Exception as e:
        logger.critical(f"Falha na execução da extração: {e}", exc_info=True)
        raise
    finally:
        if 'oracle_conn' in locals() and oracle_conn: 
            oracle_conn.close()
            logger.info("Conexão com banco Oracle encerrada.")

if __name__ == "__main__":
    main()