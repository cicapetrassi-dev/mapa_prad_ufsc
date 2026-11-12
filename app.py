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

# Título Nativo Bem Destacado
st.title("🌿 Mapeamento Geral de Áreas de Plantio (PRAD)")
st.markdown("Acompanhamento integrado das frentes de Isoladas, Nucleação e Conservação Ambiental.")
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
    
    # Tenta carregar das pastas estruturadas
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
                    
    # Fallback inteligente: se não achou nas pastas, busca diretamente na raiz (.) do repositório
    if not gdfs:
        arquivos_raiz = [f for f in os.listdir(".") if f.lower().endswith(".shp")]
        for arq in arquivos_raiz:
            try:
                temp_gdf = gpd.read_file(arq)
                temp_gdf.set_crs("EPSG:31982", allow_override=True, inplace=True)
                temp_gdf = temp_gdf.to_crs(epsg=4326)
                temp_gdf["Categoria"] = "Áreas de Plantio"
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
    # 3. Painel de Métricas de Impacto (KPIs)
    st.markdown("### 📊 Indicadores Globais do Programa")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Área Total Mapeada", f"{df_prad['Área (ha)'].sum():.2f} hectares")
    col2.metric("Total de Áreas", f"{len(df_prad)} áreas")
    col3.metric("Frentes de Atuação", f"{df_prad['Categoria'].nunique()} categorias")
    col4.metric("Base Geográfica", "Florianópolis / SC")

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
                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                attr='Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
            )

            def estilo_feature(feature):
                cat = feature['properties'].get('Categoria', '')
                if cat == "Área de Conservação":
                    cor_preenchimento = "#27ae60"  # Verde
                elif cat == "Áreas Isoladas":
                    cor_preenchimento = "#e67e22"  # Laranja
                elif cat == "Áreas de Nucleação":
                    cor_preenchimento = "#f1c40f"  # Amarelo
                else:
                    cor_preenchimento = "#3498db"  # Azul padrão
                    
                return {
                    'fillColor': cor_preenchimento,
                    'color': '#ffffff',
                    'weight': 2,
                    'fillOpacity': 0.75
                }

            ids_filtrados = set(df_filtrado["Identificação"])
            features_filtradas = [
                f for f in geojson_data["features"]
                if f["properties"].get("Identificação") in ids_filtrados
            ]
            
            geojson_filtrado = {
                "type": "FeatureCollection",
                "features": features_filtradas if features_filtradas else geojson_data["features"]
            }

            folium.GeoJson(
                geojson_filtrado,
                style_function=estilo_feature,
                tooltip=folium.GeoJsonTooltip(
                    fields=['Identificação', 'Categoria', 'Área (ha)'],
                    aliases=['Identificação:', 'Categoria:', 'Área (ha):'],
                    localize=True
                )
            ).add_to(m)

            st_folium(m, width=None, height=480)
        else:
            st.warning("Nenhuma área selecionada para exibição no mapa.")

    with col_info:
        st.subheader("Legenda de Intervenções")
        st.markdown("""
        <div style="padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 5px solid #27ae60; background-color: #f9f9f9;">
            <b>Áreas de conservação (Verde):</b> Áreas para cercamento e conservação, regeneração natural e proteção.
        </div>
        <div style="padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 5px solid #e67e22; background-color: #f9f9f9;">
            <b>Áreas de plantio isolado (Laranja):</b> Perímetro cercado para o plantio isolado.
        </div>
        <div style="padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 5px solid #f1c40f; background-color: #f9f9f9;">
            <b>Áreas de Nucleação (Amarelo):</b> Aplicação de técnicas de plantio em núcleos para adensamento ecológico.
        </div>
        """, unsafe_allow_html=True)

    # 6. Tabela Detalhada de Atributos
    with st.expander("📋 Ver Tabela Detalhada de Atributos"):
        st.dataframe(df_filtrado, use_container_width=True)

    # 7. Galeria de Fotos dos Plantios Realizados
    st.markdown("---")
    st.markdown("### 📸 Registros Fotográficos dos Plantios Realizados")
    st.markdown("Acompanhamento visual do desenvolvimento e execução das frentes de restauração ecológica.")

    pasta_fotos = "fotos_prad"
    if os.path.exists(pasta_fotos):
        imagens_disponiveis = [f for f in os.listdir(pasta_fotos) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        
        if imagens_disponiveis:
            cols = st.columns(min(3, len(imagens_disponiveis)))
            for i, img_nome in enumerate(imagens_disponiveis):
                caminho_img = os.path.join(pasta_fotos, img_nome)
                with cols[i % len(cols)]:
                    st.image(caminho_img, caption=f"Registro: {os.path.splitext(img_nome)[0]}", use_container_width=True)
        else:
            st.info(f"A pasta '{pasta_fotos}' existe, mas não contém imagens suportadas (.jpg, .png).")
    else:
        st.info("💡 **Dica:** Crie uma pasta chamada `fotos_prad` no diretório do seu projeto e adicione imagens dos plantios para exibi-las automaticamente aqui.")

else:
    st.error("Não foram encontrados arquivos shapefile válidos na raiz ou nas pastas de plantio.")

# 8. Rodapé Institucional
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: #666; font-size: 0.9rem;'>"
    "<b>Coordenação de Gestão Ambiental</b> • Compromisso com a Sustentabilidade."
    "</p>",
    unsafe_allow_html=True
)
