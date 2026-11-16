import os
import glob
import streamlit as st
import pandas as pd
import geopandas as gpd
import json
import folium
from streamlit_folium import st_folium

# 1. Configuração da Página e Layout
st.set_page_config(
    page_title="Monitoramento PRAD - Áreas de Plantio",
    page_icon="🌿",
    layout="wide"
)

# Estilização visual (Fundo bege, sem barra superior)
st.markdown(
    """
    <style>
    header[data-testid="stHeader"] {
        visibility: hidden;
        display: none;
    }
    .stApp {
        background-color: #FDF5E6 !important;
    }
    [data-testid="stSidebar"] {
        background-color: #F7EEDD !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Título Nativo Bem Destacado
st.title("🌿 Mapeamento Geral de Áreas de Plantio (PRAD)")
st.markdown("Acompanhamento integrado das frentes de plantio nas modalidades Isoladas, Nucleação e Conservação Ambiental.")
st.markdown("---")

# 2. Carregamento de Dados Geográficos (Com suporte a pastas ou raiz)
@st.cache_data
def carregar_dados_prad():
    pastas_alvo = {
        "plantio/Isoladas": "Áreas Isoladas",
        "plantio/nucleacao": "Áreas de Nucleação",
        "plantio/Áreas de Conservação Ambiental": "Área de Conservação"
    }
    
    gdfs = []
    
    # Tenta carregar das pastas estruturadas (caso existam)
    for pasta, categoria in pastas_alvo.items():
        if os.path.exists(pasta):
            arquivos_shp = [os.path.join(pasta, f) for f in os.listdir(pasta) if f.lower().endswith(".shp")]
            for arq in arquivos_shp:
                try:
                    temp_gdf = gpd.read_file(arq)
                    temp_gdf.set_crs("EPSG:31982", allow_override=True, inplace=True)
                    temp_gdf = temp_gdf.to_crs(epsg=4326)
                    temp_gdf["Categoria"] = categoria
                    nome_base = os.path.splitext(os.path.basename(arq))[0]
                    temp_gdf["Nome_Arquivo"] = nome_base
                    gdfs.append(temp_gdf)
                except Exception:
                    continue
                    
    # Fallback inteligente na raiz: classifica automaticamente pelo nome do arquivo
    if not gdfs:
        arquivos_raiz = [f for f in os.listdir(".") if f.lower().endswith(".shp")]
        for arq in arquivos_raiz:
            try:
                temp_gdf = gpd.read_file(arq)
                temp_gdf.set_crs("EPSG:31982", allow_override=True, inplace=True)
                temp_gdf = temp_gdf.to_crs(epsg=4326)
                
                arq_lower = arq.lower()
                if "iso" in arq_lower:
                    categoria = "Áreas Isoladas"
                elif "nuc" in arq_lower:
                    categoria = "Áreas de Nucleação"
                elif "con" in arq_lower:
                    categoria = "Área de Conservação"
                else:
                    categoria = "Áreas de Plantio"
                    
                temp_gdf["Categoria"] = categoria
                nome_base = os.path.splitext(os.path.basename(arq))[0]
                temp_gdf["Nome_Arquivo"] = nome_base
                gdfs.append(temp_gdf)
            except Exception:
                continue
                
    if not gdfs:
        return pd.DataFrame(), {}
        
    gdf = pd.concat(gdfs, ignore_index=True)
    
    if "Nome" in gdf.columns:
        base_names = gdf["Nome"].fillna(gdf["Nome_Arquivo"])
    elif "nome" in gdf.columns:
        base_names = gdf["nome"].fillna(gdf["Nome_Arquivo"])
    elif "ID" in gdf.columns:
        base_names = gdf["ID"].fillna(gdf["Nome_Arquivo"])
    else:
        base_names = gdf["Nome_Arquivo"]
        
    contador = {}
    identificacoes_finais = []
    for nome in base_names:
        contador[nome] = contador.get(nome, 0) + 1
        if contador[nome] > 1:
            identificacoes_finais.append(f"{nome} (Parte {contador[nome]})")
        else:
            identificacoes_finais.append(str(nome))
            
    gdf["Identificação"] = identificacoes_finais
        
    if "Área_comp" in gdf.columns:
        gdf["Área (ha)"] = pd.to_numeric(gdf["Área_comp"], errors='coerce')
    elif "Area_ha" in gdf.columns:
        gdf["Área (ha)"] = pd.to_numeric(gdf["Area_ha"], errors='coerce')
    elif "Área_1" in gdf.columns:
        valores_area = pd.to_numeric(gdf["Área_1"], errors='coerce')
        gdf["Área (ha)"] = valores_area.apply(lambda x: x / 10000.0 if x > 10 else x)
    else:
        gdf["Área (ha)"] = None

    mask_nulo = gdf["Área (ha)"].isna()
    if mask_nulo.any():
        calc_ha = gdf[mask_nulo].to_crs(epsg=31982).area / 10000.0
        gdf.loc[mask_nulo, "Área (ha)"] = calc_ha

    gdf["Área (ha)"] = gdf["Área (ha)"].fillna(1.0).round(2)
        
    geojson_data = json.loads(gdf.to_json())
    df = pd.DataFrame(gdf.drop(columns="geometry"))
    
    return df, geojson_data

df_prad, geojson_data = carregar_dados_prad()

if not df_prad.empty:
    # 3. Painel de Métricas de Impacto (KPIs) com largura ajustada para a última coluna
    st.markdown("### 📊 Indicadores Globais do Programa")
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1.4])
    
    col1.metric("Área Total Mapeada", f"{df_prad['Área (ha)'].sum():.2f} hectares")
    col2.metric("Total de Áreas", f"{len(df_prad)} áreas")
    col3.metric("Frentes de Atuação", f"{df_prad['Categoria'].nunique()} categorias")
    col4.metric("Base Geográfica", "Campus Florianópolis - UFSC")

    st.markdown("---")

    # 4. Filtros na Barra Lateral
    st.sidebar.header("🔍 Filtros do Mapa")
    categorias_disponiveis = sorted(df_prad["Categoria"].unique())
    categorias_selecionadas = st.sidebar.multiselect(
        "Filtrar por Categoria de Plantio:",
        options=categorias_disponiveis,
        default=categorias_disponiveis
    )

    df_filtrado = df_prad[df_prad["Categoria"].isin(categorias_selecionadas)]

    # 5. Layout Principal: Mapa com Satélite de Alta Resolução (Esri)
    col_mapa, col_info = st.columns([2, 1])

    with col_mapa:
        st.subheader("🗺️ Mapeamento Espacial Integrado")
        if not df_filtrado.empty and geojson_data:
            m = folium.Map(
                location=[-27.5985, -48.5185], 
                zoom_start=16, 
                tiles='
