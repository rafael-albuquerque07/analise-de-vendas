import streamlit as st
import pandas as pd
import sqlite3
import requests
import plotly.express as px
import io 

# --- Configuração da Página ---
st.set_page_config(layout="wide")
st.title("Análise de Vendas - Desafio Prático SQL 📈")

# --- ETAPA 1: DOWNLOAD DO SCRIPT SQL (Como corrigido pelo professor) ---
# Separamos o download dos dados em sua própria função com cache de dados (ttl=300s)

@st.cache_data(ttl=300)
def carregar_dados_sql():
    """Carrega SQL bruto do GitHub (raw)"""
    
    url = "https://raw.githubusercontent.com/rafael-albuquerque07/analise-de-vendas/refs/heads/main/scripts_atividade.sql"
    
    try:
        response = requests.get(url)
        response.raise_for_status() 
        st.success("✅ Script SQL baixado com sucesso!")
        return response.text
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao baixar o script SQL: {e}")
        st.error(f"URL utilizada: {url}")
        return None

# --- ETAPA 1 (Continuação): CRIAÇÃO DO BANCO ---
# Esta função pega o script baixado e cria o banco em memória.
# A conexão é um "recurso" e não deve ser serializada, por isso @st.cache_resource.

@st.cache_resource
def criar_conexao_e_popular(_sql_script):
    """Cria o banco em memória e popula os dados."""
    if _sql_script is None:
        return None
        
    try:
        conn = sqlite3.connect(":memory:") 
        cursor = conn.cursor()
        cursor.executescript(_sql_script)
        conn.commit()
        return conn
    except sqlite3.Error as e:
        st.error(f"Erro ao executar o script SQL no banco: {e}")
        st.error(f"DEBUG: O script baixado começou com: {_sql_script[:100]}...")
        st.warning("Se o erro for 'near \"<\": syntax error', o download falhou e recebemos um HTML.")
        return None

# --- ETAPA 2: DEFINIÇÃO DA QUERY PRINCIPAL ---

# Definimos a query principal com o JOIN e a coluna calculada
query_join = """
SELECT
    v.id_venda,
    v.data_venda,
    p.nome_produto,
    p.categoria,
    v.quantidade,
    p.preco_unitario,
    v.desconto,
    
    -- Coluna calculada 'valor_total'
    (v.quantidade * (p.preco_unitario * (1 - IFNULL(v.desconto, 0)))) AS valor_total

FROM vendas v
LEFT JOIN produtos p ON v.id_produto = p.id_produto;
"""
    
# --- ETAPA 3: IMPORTAÇÃO NO PYTHON (PANDAS) ---

@st.cache_data
def carregar_dados_no_pandas(_conn, query):
    """
    Executa a query SQL e carrega o resultado em um DataFrame Pandas.
    """
    try:
        df = pd.read_sql_query(query, _conn)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados no Pandas: {e}")
        return pd.DataFrame()

# --- ETAPA 4: TRATAMENTO DE DADOS ---

def tratar_dados(df):
    """
    Analisa e limpa o DataFrame, tratando valores nulos 
    (conforme solicitado na Etapa 4).
    """
    df_limpo = df.copy()
    
    # 1. Tratar NaNs na coluna 'desconto' (assumindo que NaN = 0% de desconto)
    df_limpo['desconto'] = df_limpo['desconto'].fillna(0.0)
    
    # 2. Tratar NaNs na coluna 'preco_unitario' (assumindo que NaN = R$ 0.00)
    df_limpo['preco_unitario'] = df_limpo['preco_unitario'].fillna(0.0)
    
    # 3. Tratar NaNs na coluna 'categoria' (identificado no script SQL)
    df_limpo['categoria'] = df_limpo['categoria'].fillna('Outros')

    # 4. Tratar NaNs na coluna 'nome_produto' (venda de produto não cadastrado)
    df_limpo['nome_produto'] = df_limpo['nome_produto'].fillna('Produto Desconhecido')
    
    # 5. Recalcular 'valor_total' com TODOS os NaNs tratados
    df_limpo['valor_total'] = df_limpo['quantidade'] * (df_limpo['preco_unitario'] - df_limpo['desconto'])

    
    # 6. Converter 'data_venda' para o formato datetime
    df_limpo['data_venda'] = pd.to_datetime(df_limpo['data_venda'])
    
    return df_limpo

# --- ETAPA 5: ANÁLISES E INDICADORES ---

def calcular_metricas(df):
    """
    Calcula os principais indicadores de negócio.
    """
    total_faturamento = df['valor_total'].sum()
    total_produtos_vendidos = df['quantidade'].sum()
    
    faturamento_por_categoria = df.groupby('categoria')['valor_total'].sum().reset_index()
    faturamento_por_categoria = faturamento_por_categoria.sort_values(by='valor_total', ascending=False)
    
    produtos_mais_vendidos = df.groupby('nome_produto')['quantidade'].sum().sort_values(ascending=False).reset_index().head(5)
    
    faturamento_por_dia = df.groupby(df['data_venda'].dt.date)['valor_total'].sum().reset_index()
    faturamento_por_dia = faturamento_por_dia.sort_values(by='data_venda')
    
    dias_maior_venda = faturamento_por_dia.sort_values(by='valor_total', ascending=False).head(5)
    
    return {
        "total_faturamento": total_faturamento,
        "total_produtos_vendidos": total_produtos_vendidos,
        "faturamento_por_categoria": faturamento_por_categoria,
        "produtos_mais_vendidos": produtos_mais_vendidos,
        "dias_maior_venda": dias_maior_venda,
        "faturamento_por_dia": faturamento_por_dia
    }

# --- Execução Principal do App ---

sql_script = carregar_dados_sql()
conn = criar_conexao_e_popular(sql_script)

if conn:
    # Exibe o script SQL baixado
    with st.expander("Ver Script SQL Baixado (Etapa 1)"):
        st.code(sql_script, language='sql')
    
    # Etapa 3: Carregar dados
    df_bruto = carregar_dados_no_pandas(conn, query_join)
    
    st.subheader("Etapa 3 e 4: Exploração e Tratamento de Dados")
    col1_bruto, col2_tratado = st.columns(2)
    
    with col1_bruto:
        st.write("Dados Brutos (Antes do Tratamento)")
        st.dataframe(df_bruto)
        st.write("Valores Nulos (NaN) Identificados no DataFrame:")
        st.code(df_bruto.isnull().sum())

    # Etapa 4: Limpar dados
    df_limpo = tratar_dados(df_bruto)
    
    with col2_tratado:
        st.write("Dados Limpos (Após Tratamento)")
        st.dataframe(df_limpo)
        st.write("Valores Nulos (NaN) Após Limpeza:")
        st.code(df_limpo.isnull().sum())

    st.divider()

    # --- ETAPA 5: MÉTRICAS (COM CORREÇÃO DE SINTAXE) ---
    st.subheader("Etapa 5: Indicadores de Negócio")
    
    metricas = calcular_metricas(df_limpo)
    
    col_met1, col_met2 = st.columns(2)
    col_met1.metric(
        "Faturamento Total", 
        f"R$ {metricas['total_faturamento']:,.2f}"  # <-- Correção de sintaxe
    )
    col_met2.metric(
        "Total de Produtos Vendidos", 
        f"{metricas['total_produtos_vendidos']}"  # <-- Correção de sintaxe
    )
    
    col_tbl1, col_tbl2 = st.columns(2)
    with col_tbl1:
        st.write("**Produtos Mais Vendidos (Top 5)**")
        st.dataframe(metricas['produtos_mais_vendidos'], use_container_width=True)
    
    with col_tbl2:
        st.write("**Dias de Maior Faturamento (Top 5)**")
        st.dataframe(metricas['dias_maior_venda'], use_container_width=True)
    
    st.divider()
    
    # --- ETAPA 6: VISUALIZAÇÕES ---
    st.subheader("Etapa 6: Visualizações Gráficas")
    
    col_viz1, col_viz2 = st.columns(2)
    
    with col_viz1:
        fig_bar_categoria = px.bar(
            metricas['faturamento_por_categoria'], 
            x='categoria', 
            y='valor_total',
            title='Faturamento por Categoria',
            labels={'categoria': 'Categoria', 'valor_total': 'Faturamento (R$)'},
            color='categoria'
        )
        st.plotly_chart(fig_bar_categoria, use_container_width=True)
        
    with col_viz2:
        fig_line_data = px.line(
            metricas['faturamento_por_dia'], 
            x='data_venda', 
            y='valor_total',
            title='Evolução do Faturamento por Data',
            labels={'data_venda': 'Data', 'valor_total': 'Faturamento (R$)'},
            markers=True
        )
        st.plotly_chart(fig_line_data, use_container_width=True)
        
    st.divider()
    
    # --- ETAPA 7: CONCLUSÕES ---
    st.subheader("Etapa 7: Conclusões da Análise")
    
    st.markdown("""
    Após a análise dos dados de vendas do último mês, observamos o seguinte:
    
    1.  **Tratamento de Dados foi Crucial:** O conjunto de dados original continha valores nulos (`NaN`) em `preco_unitario`, `desconto` e `categoria`. Se não fossem tratados, esses dados corromperiam a análise de faturamento. Ao preencher os preços nulos com R$ 0,00, descontos nulos com 0% e categorias nulas com "Outros", garantimos que todas as vendas fossem contabilizadas corretamente.
    
    2.  **Performance de Categorias:** O gráfico de barras mostra claramente que **"Informática"** é a categoria que mais gera faturamento, sendo responsável pela maior parte da receita. "Acessórios" e "Telefonia" vêm em seguida com resultados robustos.
    
    3.  **Impacto do Desconto:** O `valor_total` foi calculado aplicando o desconto corretamente. Vemos que, apesar de alguns descontos altos (como R$ 200,00 no Smartphone), a receita geral permanece forte. A política de descontos parece estar focada em produtos de alto valor.
    
    4.  **Padrão de Vendas (Temporal):** O gráfico de linha mostra uma volatilidade diária significativa. Existem picos claros de faturamento (ex: 2025-10-07) e vales (ex: 2025-10-02 e 2025-10-06). Isso sugere que o faturamento é concentrado em dias específicos, que podem coincidir com promoções, lançamentos ou fatores externos.
    
    **Em resumo:** A empresa depende fortemente da categoria "Informática". Existe uma oportunidade de investigar o desempenho das categorias com menor faturamento e entender os motivos dos picos e vales diários para otimizar o estoque e as promoções.
    """)

    # Fechar a conexão ao final
    conn.close()
    st.success("Análise concluída com sucesso!")