import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine

# ============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ============================================================================
st.set_page_config(
    page_title="B.I. Fornecedor | Sell In, Sell Out & Positivação",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# 1.1 INJEÇÃO DE ESTILOS CSS (UI/UX POLISH)
# ============================================================================
st.markdown("""
    <style>
    /* Oculta a barra superior padrão do Streamlit (menu sanduíche e botão deploy) */
    header {visibility: hidden;}
    
    /* Ajuste de padding: espaço para o título respirar e expansão de largura */
    .block-container { 
        padding-top: 2rem; 
        padding-bottom: 1rem; 
        max-width: 95%; 
    }
    
    /* Estilização Avançada dos Cartões de KPI (Theme Agnostic) */
    [data-testid="stMetricValue"] { 
        font-size: 28px !important; 
        font-weight: bold; 
    }
    
    [data-testid="stMetric"] { 
        background-color: var(--secondary-background-color); 
        padding: 15px; 
        border-radius: 8px; 
        border: 1px solid rgba(128, 128, 128, 0.2); 
        box-shadow: 2px 2px 10px rgba(0,0,0,0.1); 
        min-height: 145px !important; /* Fix: Garante altura simétrica com ou sem delta */
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    
    /* Assegura o alinhamento vertical flexível dos elementos internos do cartão */
    [data-testid="stMetric"] > div {
        margin-top: auto;
        margin-bottom: auto;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# 2. FUNÇÕES UTILITÁRIAS (FORMATAÇÃO DE DATA VIZ)
# ============================================================================
def formatar_moeda(valor, simbolo_moeda="R$"):
    """Formata valores numéricos para o padrão monetário PT-BR."""
    if pd.isna(valor):
        return ""
    try:
        return f"{simbolo_moeda} {float(valor):,.2f}".replace(",", "x").replace(".", ",").replace("x", ".")
    except (TypeError, ValueError):
        return "Valor inválido"

def formatar_inteiro(valor):
    """
    Formata volumetria física e contagens (unidades, caixas, clientes)
    Removendo casas decimais e aplicando separador de milhar PT-BR.
    """
    if pd.isna(valor):
        return ""
    try:
        return f"{int(float(valor)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "Valor inválido"

def formatar_decimal(valor, casas=1):
    """
    Formata grandezas contínuas (como DOH ou Taxas) com controle de 
    casas decimais e padrão PT-BR.
    """
    if pd.isna(valor):
        return ""
    try:
        format_str = f"{{:,.{casas}f}}"
        return format_str.format(float(valor)).replace(",", "x").replace(".", ",").replace("x", ".")
    except (TypeError, ValueError):
        return "Valor inválido"

# ============================================================================
# 3. GESTÃO DE CONEXÃO E CACHE DE DADOS
# ============================================================================
@st.cache_resource
def init_connection():
    db_user = st.secrets["SUPABASE_DB_USER"]
    db_pass = st.secrets["SUPABASE_DB_PASSWORD"]
    db_host = st.secrets["SUPABASE_DB_HOST"]
    db_port = st.secrets["SUPABASE_DB_PORT"]
    db_name = st.secrets["SUPABASE_DB_NAME"]
    
    conn_str = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    return create_engine(conn_str)

@st.cache_data(ttl=3600)
def load_data(query: str):
    engine = init_connection()
    with engine.connect() as conn:
        return pd.read_sql_query(query, conn)

# ============================================================================
# 4. MÓDULOS DE ANÁLISE (FUNÇÕES POR ABA)
# ============================================================================

# --- ABA 1: SELL IN E ESTOQUE ---
def render_tab_sell_in():
    st.header("📦 Acompanhamento de Sell In e Estoque")
    
    col_visao, col_vazia = st.columns([1, 2])
    with col_visao:
        tipo_visao = st.radio(
            "Métrica de Análise:",
            options=["Valor (R$)", "Quantidade (Unidades)"],
            horizontal=True,
            key="radio_visao_sell_in"
        )
    is_valor = tipo_visao == "Valor (R$)"
    
    st.markdown("---")

    query_estoque_doh = """
        WITH cte_media_sell_out_30d AS (
            SELECT 
                cod_produto,
                COALESCE(SUM(qtd_vendida - qtd_devolvida), 0) / 30.0 AS media_diaria_30d
            FROM fato_sell_out
            WHERE dt_venda >= (SELECT MAX(dt_estoque) FROM fato_estoque_diario) - INTERVAL '30 days'
            GROUP BY cod_produto
        )
        SELECT 
            p.cod_produto, p.desc_produto, p.categoria, p.marca,
            e.qtd_estoque, ROUND(e.qtd_estoque * e.valor_ultima_entrada, 2) AS vl_total_estoque,
            e.valor_ultima_entrada AS custo_unitario, e.dias_zerados_90d,
            COALESCE(aso.media_diaria_30d, 0) AS venda_media_diaria
        FROM fato_estoque_diario e
        JOIN dim_produto p ON e.cod_produto = p.cod_produto
        LEFT JOIN cte_media_sell_out_30d aso ON e.cod_produto = aso.cod_produto
        WHERE e.dt_estoque = (SELECT MAX(dt_estoque) FROM fato_estoque_diario);
    """
    
    query_evolucao_sell_in = """
        SELECT 
            TO_CHAR(dt_emissao, 'YYYY-MM') AS mes_ano,
            SUM(qt_pedida) AS qtd_pedida, SUM(qt_entregue) AS qtd_entregue,
            ROUND(SUM(qt_pedida * preco_compra), 2) AS vl_total_pedido,
            ROUND(SUM(qt_entregue * preco_compra), 2) AS vl_total_entregue
        FROM fato_sell_in
        GROUP BY TO_CHAR(dt_emissao, 'YYYY-MM')
        ORDER BY mes_ano;
    """
    
    df_estoque = load_data(query_estoque_doh)
    df_sell_in = load_data(query_evolucao_sell_in)

    total_estoque_qtd = df_estoque['qtd_estoque'].sum()
    total_estoque_valor = df_estoque['vl_total_estoque'].sum()
    
    venda_diaria_total_qtd = df_estoque['venda_media_diaria'].sum()
    venda_diaria_total_valor = (df_estoque['venda_media_diaria'] * df_estoque['custo_unitario']).sum()
    
    if is_valor:
        doh_total = total_estoque_valor / venda_diaria_total_valor if venda_diaria_total_valor > 0 else 0
        df_estoque['DOH'] = df_estoque.apply(lambda r: round(r['vl_total_estoque'] / (r['venda_media_diaria'] * r['custo_unitario']), 1) if r['venda_media_diaria'] > 0 else 999, axis=1)
    else:
        doh_total = total_estoque_qtd / venda_diaria_total_qtd if venda_diaria_total_qtd > 0 else 0
        df_estoque['DOH'] = df_estoque.apply(lambda r: round(r['qtd_estoque'] / r['venda_media_diaria'], 1) if r['venda_media_diaria'] > 0 else 999, axis=1)

    kpi1, kpi2, kpi3 = st.columns(3)
    with kpi1:
        if is_valor:
            st.metric("Estoque Total Disponível", formatar_moeda(total_estoque_valor))
        else:
            st.metric("Estoque Total Disponível", f"{total_estoque_qtd:,.0f} Unid.".replace(",", "."))
            
    with kpi2:
        st.metric("Cobertura Total da Operação (DOH)", f"{doh_total:.1f} Dias".replace(".", ","))
        
    with kpi3:
        rupturas = df_estoque[df_estoque['qtd_estoque'] <= 0].shape[0]
        st.metric("Produtos em Ruptura Crítica", f"{rupturas} SKU(s)", delta=f"{df_estoque[df_estoque['dias_zerados_90d'] > 0].shape[0]} sofreram oscilação (90d)", delta_color="off")

    st.markdown("---")

    graf1, graf2 = st.columns(2)
    with graf1:
        st.subheader("📈 Evolução Mensal de Abastecimento (Sell In)")
        if is_valor:
            fig_si = px.bar(
                df_sell_in, x='mes_ano', y=['vl_total_pedido', 'vl_total_entregue'],
                barmode='group', labels={'value': 'Montante (R$)', 'mes_ano': 'Período'},
                title="Financeiro: Compras Pedidas vs. Entregues",
                color_discrete_sequence=['#1f77b4', '#aec7e8']
            )
            # CORREÇÃO: separators=",." (decimal=vírgula, milhares=ponto)
            fig_si.update_layout(separators=",.", yaxis_tickformat=",.2f")
            fig_si.update_traces(hovertemplate="<b>%{data.name}</b><br>Período: %{x}<br>Montante: R$ %{y:,.2f}<extra></extra>")
        else:
            fig_si = px.bar(
                df_sell_in, x='mes_ano', y=['qtd_pedida', 'qtd_entregue'],
                barmode='group', labels={'value': 'Volume (Unidades)', 'mes_ano': 'Período'},
                title="Volumetria: Peças Pedidas vs. Entregues",
                color_discrete_sequence=['#2ca02c', '#98df8a']
            )
            # CORREÇÃO: separators=",."
            fig_si.update_layout(separators=",.", yaxis_tickformat=",.0f")
            fig_si.update_traces(hovertemplate="<b>%{data.name}</b><br>Período: %{x}<br>Volume: %{y:,.0f} Unid.<extra></extra>")
        st.plotly_chart(fig_si, use_container_width=True)

    with graf2:
        st.subheader("📊 Concentração de Estoque por Categoria")
        metric_col = 'vl_total_estoque' if is_valor else 'qtd_estoque'
        df_cat = df_estoque.groupby('categoria', as_index=False)[metric_col].sum().sort_values(metric_col, ascending=False)
        fig_cat = px.bar(
            df_cat, x=metric_col, y='categoria', orientation='h',
            labels={metric_col: 'Total em Estoque', 'categoria': 'Categoria'},
            title="Distribuição do Inventário Atual",
            color=metric_col, color_continuous_scale='Blues'
        )
        # CORREÇÃO: separators=",."
        fig_cat.update_layout(separators=",.", xaxis_tickformat=",.2f" if is_valor else ",.0f")
        if is_valor:
            fig_cat.update_traces(hovertemplate="<b>%{y}</b><br>Total em Estoque: R$ %{x:,.2f}<extra></extra>")
        else:
            fig_cat.update_traces(hovertemplate="<b>%{y}</b><br>Total em Estoque: %{x:,.0f} Unid.<extra></extra>")
        st.plotly_chart(fig_cat, use_container_width=True)

    st.markdown("---")

    st.subheader("📋 Painel Gerencial de Estoque e Cobertura por Produto")
    df_view = df_estoque.copy()
    df_view = df_view.rename(columns={
        'cod_produto': 'Cód. SKU',
        'desc_produto': 'Descrição do Produto',
        'categoria': 'Categoria',
        'marca': 'Marca',
        'qtd_estoque': 'Qtd. Estoque',
        'vl_total_estoque': 'Valor Estoque (R$)',
        'custo_unitario': 'Custo Última Entrada (R$)',
        'dias_zerados_90d': 'Dias Zerados (90d)',
        'DOH': 'DOH (Dias)'
    })
    
    cols_to_show = ['Cód. SKU', 'Descrição do Produto', 'Categoria', 'Marca', 'Qtd. Estoque', 'Valor Estoque (R$)', 'Custo Última Entrada (R$)', 'DOH (Dias)', 'Dias Zerados (90d)']
    
    st.dataframe(
        df_view[cols_to_show].style.format({
            'Valor Estoque (R$)': formatar_moeda,
            'Custo Última Entrada (R$)': formatar_moeda,
            'Qtd. Estoque': formatar_inteiro,
            'DOH (Dias)': lambda x: formatar_decimal(x, 1)
        }),
        use_container_width=True,
        hide_index=True
    )


# --- ABA 2: SELL OUT ---
def render_tab_sell_out():
    st.header("🛍️ Acompanhamento de Sell Out (Escoamento)")

    ctrl_col1, ctrl_col2, _ = st.columns([1, 1, 2])
    with ctrl_col1:
        tipo_visao = st.radio(
            "Métrica de Análise (Sell Out):",
            options=["Valor Líquido (R$)", "Quantidade Líquida (Unid.)"],
            horizontal=True,
            key="radio_visao_sell_out"
        )
    with ctrl_col2:
        top_n = st.selectbox("Profundidade dos Rankings (Top N):", [5, 10, 20, 50], index=1)
        
    is_valor = tipo_visao == "Valor Líquido (R$)"
    metric_target = 'vl_liquido' if is_valor else 'qtd_liquida'
    metric_label = 'Montante Líquido (R$)' if is_valor else 'Volume Líquido (Unid.)'

    st.markdown("---")

    query_sell_out = """
        SELECT 
            TO_CHAR(so.dt_venda, 'YYYY-MM') AS mes_ano,
            c.nm_cliente, c.nm_cliente_fantasia, c.uf,
            p.desc_produto, p.categoria, p.marca,
            so.origem_pedido,
            SUM(so.qtd_vendida - so.qtd_devolvida) AS qtd_liquida,
            SUM(so.vl_total_vendido - so.vl_total_devolvido) AS vl_liquido,
            SUM(so.vl_total_vendido) AS vl_bruto,
            SUM(so.vl_total_devolvido) AS vl_devolvido
        FROM fato_sell_out so
        JOIN dim_produto p ON so.cod_produto = p.cod_produto
        JOIN dim_cliente c ON so.cod_cliente = c.cod_cliente
        GROUP BY 
            TO_CHAR(so.dt_venda, 'YYYY-MM'), c.nm_cliente, c.nm_cliente_fantasia, 
            c.uf, p.desc_produto, p.categoria, p.marca, so.origem_pedido;
    """
    df_so = load_data(query_sell_out)

    if df_so.empty:
        st.warning("Nenhum dado de Sell Out encontrado no período selecionado.")
        return

    total_bruto = df_so['vl_bruto'].sum()
    total_devolvido = df_so['vl_devolvido'].sum()
    total_liquido = total_bruto - total_devolvido
    
    ol_mask = df_so['origem_pedido'] == 'OPERADOR LOGÍSTICO'
    total_ol_valor = df_so[ol_mask]['vl_liquido'].sum()
    pct_participacao_ol = (total_ol_valor / total_liquido * 100) if total_liquido > 0 else 0

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("Sell Out Bruto", formatar_moeda(total_bruto))
    with kpi2:
        st.metric("Total Devoluções", formatar_moeda(total_devolvido), delta=f"{(total_devolvido/total_bruto*100):.1f}% do Bruto" if total_bruto > 0 else "0%", delta_color="inverse")
    with kpi3:
        st.metric("Sell Out Líquido", formatar_moeda(total_liquido))
    with kpi4:
        st.metric("Participação OL (Valor)", f"{pct_participacao_ol:.1f}%".replace(".", ","), delta="Ref. ao Faturamento Líquido", delta_color="off")

    st.markdown("---")

    g1, g2 = st.columns([2, 1])
    with g1:
        st.subheader("📅 Evolução de Vendas Líquidas Mês a Mês")
        df_evolucao = df_so.groupby('mes_ano', as_index=False)[metric_target].sum()
        fig_ev = px.line(
            df_evolucao, x='mes_ano', y=metric_target,
            labels={'mes_ano': 'Mês de Competência', metric_target: metric_label},
            markers=True, title="Curva de Escoamento Temporal"
        )
        # CORREÇÃO: separators=",."
        fig_ev.update_layout(separators=",.", yaxis_tickformat=",.2f" if is_valor else ",.0f")
        fig_ev.update_traces(hovertemplate="<b>%{x}</b><br>Montante: R$ %{y:,.2f}<extra></extra>" if is_valor else "<b>%{x}</b><br>Volume: %{y:,.0f} Unid.<extra></extra>")
        st.plotly_chart(fig_ev, use_container_width=True)
        
    with g2:
        st.subheader("🍕 Participação por Origem (Share OL)")
        df_origem = df_so.groupby('origem_pedido', as_index=False)[metric_target].sum()
        fig_share = px.pie(
            df_origem, values=metric_target, names='origem_pedido',
            hole=0.4, title="Mix de Canais de Distribuição",
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        # CORREÇÃO: separators=",."
        fig_share.update_layout(separators=",.")
        fig_share.update_traces(
            hovertemplate="<b>%{label}</b><br>Montante: R$ %{value:,.2f}<extra></extra>" if is_valor else "<b>%{label}</b><br>Volume: %{value:,.0f} Unid.<extra></extra>"
        )
        st.plotly_chart(fig_share, use_container_width=True)

    st.markdown("---")

    r1, r2 = st.columns(2)
    with r1:
        st.subheader(f"🏆 Top {top_n} Clientes por Faturamento/Volume")
        df_rank_cli = df_so.groupby('nm_cliente', as_index=False)[metric_target].sum()
        df_rank_cli = df_rank_cli.sort_values(metric_target, ascending=False).head(top_n)
        fig_cli = px.bar(
            df_rank_cli, x=metric_target, y='nm_cliente', orientation='h',
            labels={metric_target: metric_label, 'nm_cliente': 'Cliente'},
            color=metric_target, color_continuous_scale='GnBu'
        )
        # CORREÇÃO: separators=",."
        fig_cli.update_layout(
            separators=",.", 
            xaxis_tickformat=",.2f" if is_valor else ",.0f",
            yaxis={'categoryorder':'total ascending'}
        )
        fig_cli.update_traces(hovertemplate="<b>%{y}</b><br>Montante: R$ %{x:,.2f}<extra></extra>" if is_valor else "<b>%{y}</b><br>Volume: %{x:,.0f} Unid.<extra></extra>")
        st.plotly_chart(fig_cli, use_container_width=True)
        
    with r2:
        st.subheader(f"📦 Top {top_n} Produtos mais Vendidos")
        df_rank_prod = df_so.groupby('desc_produto', as_index=False)[metric_target].sum()
        df_rank_prod = df_rank_prod.sort_values(metric_target, ascending=False).head(top_n)
        fig_prod = px.bar(
            df_rank_prod, x=metric_target, y='desc_produto', orientation='h',
            labels={metric_target: metric_label, 'desc_produto': 'Produto'},
            color=metric_target, color_continuous_scale='Oranges'
        )
        # CORREÇÃO: separators=",."
        fig_prod.update_layout(
            separators=",.", 
            xaxis_tickformat=",.2f" if is_valor else ",.0f",
            yaxis={'categoryorder':'total ascending'}
        )
        fig_prod.update_traces(hovertemplate="<b>%{y}</b><br>Montante: R$ %{x:,.2f}<extra></extra>" if is_valor else "<b>%{y}</b><br>Volume: %{x:,.0f} Unid.<extra></extra>")
        st.plotly_chart(fig_prod, use_container_width=True)

    st.markdown("---")

    st.subheader("🔄 Matriz de Evolução de Vendas por Cliente Mês a Mês")
    df_pivot = df_so.pivot_table(
        index=['nm_cliente', 'uf'],
        columns='mes_ano',
        values=metric_target,
        aggfunc='sum',
        fill_value=0
    ).reset_index()
    
    df_pivot['Total Consolidado'] = df_pivot.drop(columns=['nm_cliente', 'uf']).sum(axis=1)
    df_pivot = df_pivot.sort_values('Total Consolidado', ascending=False)

    cols_to_format = [col for col in df_pivot.columns if col not in ['nm_cliente', 'uf']]
    if is_valor:
        format_dict = {col: formatar_moeda for col in cols_to_format}
    else:
        format_dict = {col: formatar_inteiro for col in cols_to_format}
        
    st.dataframe(df_pivot.style.format(format_dict), use_container_width=True, hide_index=True)


# --- ABA 3: POSITIVAÇÃO ---
def render_tab_positivacao():
    st.header("🎯 Positivação e Capilaridade de Mercado")
    st.markdown("---")

    query_positivacao = """
        SELECT 
            TO_CHAR(so.dt_venda, 'YYYY-MM') AS mes_ano,
            p.desc_produto, p.categoria, p.marca,
            COUNT(DISTINCT so.cod_cliente) AS qtd_clientes_positivados,
            SUM(so.vl_total_vendido - so.vl_total_devolvido) AS vl_liquido
        FROM fato_sell_out so
        JOIN dim_produto p ON so.cod_produto = p.cod_produto
        WHERE so.qtd_vendida > so.qtd_devolvida
        GROUP BY TO_CHAR(so.dt_venda, 'YYYY-MM'), p.desc_produto, p.categoria, p.marca;
    """
    
    query_total_clientes = "SELECT COUNT(*) as total FROM dim_cliente;"
    
    df_pos = load_data(query_positivacao)
    df_total_cli = load_data(query_total_clientes)
    
    base_total_clientes = df_total_cli['total'].iloc[0] if not df_total_cli.empty else 1

    if df_pos.empty:
        st.warning("Nenhum registro de positivação encontrado para este fornecedor.")
        return

    df_mensal_consolidado = load_data("""
        SELECT 
            TO_CHAR(dt_venda, 'YYYY-MM') AS mes_ano,
            COUNT(DISTINCT cod_cliente) AS total_unicos
        FROM fato_sell_out
        WHERE qtd_vendida > qtd_devolvida
        GROUP BY TO_CHAR(dt_venda, 'YYYY-MM')
        ORDER BY mes_ano DESC;
    """)
    
    clientes_positivados_atual = df_mensal_consolidado['total_unicos'].iloc[0] if not df_mensal_consolidado.empty else 0
    taxa_penetracao_atual = (clientes_positivados_atual / base_total_clientes) * 100

    kpi1, kpi2, kpi3 = st.columns(3)
    with kpi1:
        st.metric("Base Total de Clientes Cadastrados", formatar_inteiro(base_total_clientes))
    with kpi2:
        st.metric("Clientes Positivados (Mês Atual)", formatar_inteiro(clientes_positivados_atual))
    with kpi3:
        st.metric("Taxa de Penetração de Mercado", f"{taxa_penetracao_atual:.1f}%".replace(".", ","), delta="Share de Clientes Ativos")

    st.markdown("---")

    g1, g2 = st.columns(2)
    with g1:
        st.subheader("📈 Evolução da Positivação Mensal da Carteira")
        df_ev_pos = df_mensal_consolidado.sort_values('mes_ano')
        fig_line = px.line(
            df_ev_pos, x='mes_ano', y='total_unicos',
            labels={'mes_ano': 'Mês/Ano', 'total_unicos': 'Clientes Únicos Atendidos'},
            markers=True, title="Evolução da Ativação de Contas Comerciais"
        )
        # CORREÇÃO: separators=",."
        fig_line.update_layout(separators=",.", yaxis_tickformat=",.0f")
        fig_line.update_traces(hovertemplate="<b>%{x}</b><br>Clientes Únicos: %{y:,.0f}<extra></extra>")
        st.plotly_chart(fig_line, use_container_width=True)

    with g2:
        st.subheader("🛡️ Clientes Positivados por Categoria de Produto")
        mes_atual_str = df_mensal_consolidado['mes_ano'].iloc[0] if not df_mensal_consolidado.empty else ''
        df_cat_pos = df_pos[df_pos['mes_ano'] == mes_atual_str].groupby('categoria', as_index=False)['qtd_clientes_positivados'].sum()
        df_cat_pos = df_cat_pos.sort_values('qtd_clientes_positivados', ascending=False)
        fig_cat = px.bar(
            df_cat_pos, x='qtd_clientes_positivados', y='categoria', orientation='h',
            labels={'qtd_clientes_positivados': 'Clientes Positivados', 'categoria': 'Categoria'},
            title=f"Capilaridade por Categoria em {mes_atual_str}",
            color='qtd_clientes_positivados', color_continuous_scale='Purples'
        )
        # CORREÇÃO: separators=",."
        fig_cat.update_layout(separators=",.", xaxis_tickformat=",.0f")
        fig_cat.update_traces(hovertemplate="<b>%{y}</b><br>Clientes Positivados: %{x:,.0f}<extra></extra>")
        st.plotly_chart(fig_cat, use_container_width=True)

    st.markdown("---")

    st.subheader("📋 Cobertura de SKUs e Penetração por Produto")
    df_prod_atual = df_pos[df_pos['mes_ano'] == mes_atual_str].copy()
    df_prod_atual['Taxa de Cobertura (%)'] = (df_prod_atual['qtd_clientes_positivados'] / base_total_clientes) * 100
    df_prod_atual = df_prod_atual.sort_values('qtd_clientes_positivados', ascending=False)
    
    df_prod_view = df_prod_atual.rename(columns={
        'desc_produto': 'Descrição do Produto',
        'categoria': 'Categoria',
        'marca': 'Marca',
        'qtd_clientes_positivados': 'Clientes Positivados (Nº)',
        'vl_liquido': 'Faturamento Líquido (R$)'
    })

    st.dataframe(
        df_prod_view[['Descrição do Produto', 'Categoria', 'Marca', 'Clientes Positivados (Nº)', 'Taxa de Cobertura (%)', 'Faturamento Líquido (R$)']].style.format({
            'Faturamento Líquido (R$)': formatar_moeda,
            'Taxa de Cobertura (%)': lambda x: f"{x:.2f}%".replace(".", ","),
            'Clientes Positivados (Nº)': formatar_inteiro
        }),
        use_container_width=True,
        hide_index=True
    )

# ============================================================================
# 5. ORQUESTRAÇÃO DA INTERFACE PRINCIPAL
# ============================================================================
def main():
    with st.sidebar:
        st.title("⚙️ B.I. Fornecedor")
        st.markdown("---")
        ano_selecionado = st.selectbox("Ano de Referência", ["2026"])
        st.markdown("---")
        st.caption("Atualizado via Pipeline Batch diário.")

    tab1, tab2, tab3 = st.tabs([
        "📦 1. SELL IN (Estoque e Compras)", 
        "🛍️ 2. SELL OUT (Vendas)", 
        "🎯 3. POSITIVAÇÃO"
    ])
    
    with tab1: render_tab_sell_in()
    with tab2: render_tab_sell_out()
    with tab3: render_tab_positivacao()

if __name__ == "__main__":
    main()