import os
import logging
import oracledb
import psycopg2
from psycopg2 import extras
from datetime import datetime, timedelta
import streamlit as st 

# ============================================================================
# CONFIGURAÇÃO DE LOGGING
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(metadata)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.LoggerAdapter(logging.getLogger(__name__), {"metadata": "ETL-TENA"})

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

# ============================================================================
# CONEXÕES DE BANCO DE DADOS (LENDO DO SECRETS.TOML)
# ============================================================================
def get_oracle_connection():
    
    return oracledb.connect(
        user=st.secrets["ORACLE_USER"],
        password=st.secrets["ORACLE_PASSWORD"],
        dsn=st.secrets["ORACLE_DSN"] 
    )

def get_supabase_connection():
    return psycopg2.connect(
        host=st.secrets["SUPABASE_DB_HOST"],
        database=st.secrets["SUPABASE_DB_NAME"],
        user=st.secrets["SUPABASE_DB_USER"],
        password=st.secrets["SUPABASE_DB_PASSWORD"],
        port=st.secrets["SUPABASE_DB_PORT"]
    )

def read_sql_file(filename: str) -> str:
    path = os.path.join('sql', filename)
    with open(path, 'r', encoding='utf-8') as file:
        return file.read()

# ============================================================================
# ESTRATÉGIA 1: UPSERT PARA DIMENSÕES (INSERT ON CONFLICT DO UPDATE)
# ============================================================================
def load_dimension(oracle_conn, supabase_conn, sql_filename: str, target_table: str, pkey: str):
    """
    Executa a carga de tabelas dimensionais aplicando UPSERT dinâmico com base na PKEY.
    Mantém a integridade referencial evitando falhas de Foreign Key (FK).
    """
    query_oracle = read_sql_file(sql_filename)
    
    with oracle_conn.cursor() as ora_cursor, supabase_conn.cursor() as supa_cursor:
        logger.info(f"Extraindo dimensão de origem: {sql_filename}")
        ora_cursor.execute(query_oracle)
        
        columns = [col[0].lower() for col in ora_cursor.description]
        records = ora_cursor.fetchall()
        
        if not records:
            logger.warning(f"Nenhum registro retornado para a dimensão: {target_table}")
            return

        # Constrói as cláusulas do UPSERT do PostgreSQL
        col_names = ', '.join(columns)
        update_clause = ', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col != pkey])
        
        upsert_query = f"""
            INSERT INTO {target_table} ({col_names}) 
            VALUES %s 
            ON CONFLICT ({pkey}) 
            DO UPDATE SET {update_clause};
        """
        
        extras.execute_values(supa_cursor, upsert_query, records, page_size=2000)
        supabase_conn.commit()
        logger.info(f"Dimensão {target_table} atualizada com sucesso. Registros: {len(records)}")

# ============================================================================
# ESTRATÉGIA 2 & 3: OVERWRITE WINDOW / SNAPSHOT PARA TABELAS FATO
# ============================================================================
def load_fact_incremental(oracle_conn, supabase_conn, sql_filename: str, target_table: str, delete_query: str, chunk_size: int = 20000):
    """
    Executa a carga idempotente de tabelas fato.
    Aplica um DELETE prévio na janela de dados correspondente e realiza Bulk Insert por Chunks.
    """
    query_oracle = read_sql_file(sql_filename)
    
    with oracle_conn.cursor() as ora_cursor, supabase_conn.cursor() as supa_cursor:
        # Executa a limpeza da janela/snapshot no Supabase antes da inserção
        logger.info(f"Garantindo idempotência: Executando limpeza prévia em {target_table}")
        supa_cursor.execute(delete_query)
        
        logger.info(f"Iniciando extração da Fato: {target_table}")
        ora_cursor.execute(query_oracle)
        
        columns = [col[0].lower() for col in ora_cursor.description]
        col_names = ', '.join(columns)
        insert_query = f"INSERT INTO {target_table} ({col_names}) VALUES %s"
        
        total_rows = 0
        while True:
            chunks = ora_cursor.fetchmany(chunk_size)
            if not chunks:
                break
                
            extras.execute_values(supa_cursor, insert_query, chunks, page_size=chunk_size)
            supabase_conn.commit()
            
            total_rows += len(chunks)
            logger.info(f"Fato {target_table}: {total_rows} registros inseridos no cluster destino...")
            
        logger.info(f"Carga da Fato {target_table} concluída com sucesso. Total: {total_rows} registros.")

# ============================================================================
# ORQUESTRADOR PRINCIPAL (MAIN PIPELINE)
# ============================================================================
def main():
    logger.info("Iniciando execução do Pipeline Batch Diário.")
    
    try:
        oracle_conn = get_oracle_connection()
        supabase_conn = get_supabase_connection()
        
        # --------------------------------------------------------------------
        # FASE 1: EXECUÇÃO DAS DIMENSÕES (ESTRATEGIA: UPSERT PKEY)
        # --------------------------------------------------------------------
        logger.info("--- INICIANDO FASE DE DIMENSÕES ---")
        load_dimension(oracle_conn, supabase_conn, 'extract_dim_filial.sql', 'dim_filial', 'cod_filial')
        load_dimension(oracle_conn, supabase_conn, 'extract_dim_fornecedor.sql', 'dim_fornecedor', 'cod_fornecedor')
        load_dimension(oracle_conn, supabase_conn, 'extract_dim_cliente.sql', 'dim_cliente', 'cod_cliente')
        load_dimension(oracle_conn, supabase_conn, 'extract_dim_produto.sql', 'dim_produto', 'cod_produto')
        
        # --------------------------------------------------------------------
        # FASE 2: EXECUÇÃO DAS FATOS (ESTRATEGIA: DELETE & BULK INSERT)
        # --------------------------------------------------------------------
        logger.info("--- INICIANDO FASE DE TABELAS FATO ---")
        
        # Fato Estoque: Estratégia de Snapshot Diário (Apaga o D-1 e reinsere)
        delete_estoque_d1 = "DELETE FROM fato_estoque_diario WHERE dt_estoque = CURRENT_DATE - INTERVAL '1 day';"
        load_fact_incremental(
            oracle_conn, supabase_conn, 
            sql_filename='extract_estoque_diario.sql', 
            target_table='fato_estoque_diario', 
            delete_query=delete_estoque_d1
        )
        
        # Fato Vendas (Sell Out): Estratégia de Lookback Window (Histórico completo de 2026)
        # Como sua query extrai de forma estática a partir de 01/01/2026, limpamos o período completo para evitar duplicidade.
        delete_vendas_2026 = "DELETE FROM fato_sell_out WHERE dt_venda >= '2026-01-01';"
        load_fact_incremental(
            oracle_conn, supabase_conn, 
            sql_filename='extract_sell_out.sql', 
            target_table='fato_sell_out', 
            delete_query=delete_vendas_2026,
            chunk_size=30000  # Tamanho de lote maior para otimizar o tráfego da pcmov
        )
        
        # Fato Pedidos de Compra (Sell In): Janela completa de 2026
        delete_sell_in_2026 = "DELETE FROM fato_sell_in WHERE dt_emissao >= '2026-01-01';"
        load_fact_incremental(
            oracle_conn, supabase_conn, 
            sql_filename='extract_sell_in.sql', 
            target_table='fato_sell_in', 
            delete_query=delete_sell_in_2026
        )
        
        logger.info("Pipeline executado com sucesso absoluto em todas as fases.")
        
    except Exception as e:
        logger.critical(f"Falha catastrófica na execução do pipeline: {e}", exc_info=True)
        # Espaço ideal para acionamento de Webhooks de alertas (Ex: Slack, Teams, PagerDuty)
        raise
    finally:
        if 'oracle_conn' in locals() and oracle_conn: 
            oracle_conn.close()
            logger.info("Conexão com banco Oracle encerrada.")
        if 'supabase_conn' in locals() and supabase_conn: 
            supabase_conn.close()
            logger.info("Conexão com banco Supabase encerrada.")

if __name__ == "__main__":
    main()