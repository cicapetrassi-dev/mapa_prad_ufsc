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

# Estilização visual (Fundo verde-sálvia/floresta suave, sem barra superior)
st.markdown(
    """
    <style>
    header[data-testid="stHeader"] {
        visibility: hidden;
        display: none;
    }
    .stApp {
        background-color: #EBF2EB !important;
    }
    [data-testid="stSidebar"] {
        background-color: #DFE8DF !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Título e Subtítulo Maiores com Estilo de Floresta
st.markdown(
    """
    <div style="margin-bottom: 10px;">
        <h1 style="color: #1F361F; font-size: 3.2rem; font-weight: 700; margin-bottom: 5px;">🌿 Mapeamento Geral de Áreas de Plantio (PRAD)</h1>
        <p style="color: #334D33; font-size: 1.4rem; font-weight: 500; margin-top: 0;">Acompanhamento integrado das frentes de plantio nas modalidades Isoladas, Nucleação e Conservação Ambiental.</p>
    </div>
    """,
    unsafe_allow_html=True
)
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
    col4.metric("Base Geográfica", "Campus Florianópolis - Trindade")

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
            m = folium.Map(location=[-27.5985, -48.5185], zoom_start=16, tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community')

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
        <div style="padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 5px solid #27ae60; background-color: #E2EBE2;">
            <b>Áreas de conservação (Verde):</b> Áreas para cercamento e conservação, regeneração natural e proteção.
        </div>
        <div style="padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 5px solid #e67e22; background-color: #E2EBE2;">
            <b>Áreas de plantio isolado (Laranja):</b> Perímetro cercado para o plantio isolado.
        </div>
        <div style="padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 5px solid #f1c40f; background-color: #E2EBE2;">
            <b>Áreas de Nucleação (Amarelo):</b> Aplicação de técnicas de plantio em núcleos para adensamento ecológico.
        </div>
        """, unsafe_allow_html=True)

    # 6. Tabela Detalhada de Atributos
    with st.expander("📋 Ver Tabela Detalhada de Atributos"):
        st.dataframe(df_filtrado, use_container_width=True)

# 7. Galeria de Fotos dos Plantios Vinculada aos Filtros
    st.markdown("---")
    st.markdown("### 📸 Registros Fotográficos dos Plantios Realizados")
    st.markdown(
        "Acompanhamento visual sincronizado com as categorias selecionadas no"
        " mapa."
    )

    # (Opcional) Dicionário para legendas totalmente personalizadas:
    # Digite exatamente o nome do arquivo da foto e a legenda que deseja exibir
    legendas_personalizadas = {
        "isolada_01.jpg": "Plantio Isolado - Setor Norte (Campus Trindade)",
        "conservacao_01.jpg": "Área de Conservação e Regeneração - Bosque",
        "nucleacao_01.jpg": "Implantação de Núcleos de Adensamento Ecológico",
        "con_amiguis_1.png": "Amiga capivara passeando."
        “iso_01.png”: “Plantio isolado – foto 1”
        “iso_02.png”: “Plantio isolado – foto 2”
        “iso_03.png”: “Plantio isolado – foto 3”
        “iso_regenerante_01.png”: “Regenerante em área de plantio isolado – foto 1”
        “iso_regenerante_02.png”: “Regenerante em área de plantio isolado – foto 2”
        “isolada_01.png”: “Plantio isolado – foto 4”
        “isolada_02.png”: “Plantio isolado – foto 5”
        “nuc_01.png”: “Plantio nucleação – foto 1”
        “nuc_02.png”: “Plantio nucleação – foto 2”
        “nuc_03.png”: “Plantio nucleação – foto 3”
        “nuc_04.png”: “Plantio nucleação – foto 4”
        “nuc_05.png”: “Plantio nucleação – foto 5”
        “nuc_remocao_inv_01.png”: “Remoção de invasoras para plantio nucleação – foto 1”
        “nuc_remocao_inv_02.png”: “Remoção de invasoras para plantio nucleação – foto 2”
        “nuc_remocao_inv_03.png”: “Remoção de invasoras para plantio nucleação – foto 3”
        “nuc_remocao_inv_04.png”: “Remoção de invasoras para plantio nucleação – foto 4”
        “nuc_remocao_inv_05.png”: “Remoção de invasoras para plantio nucleação – foto 5”
        “nuc_rev_solo_01.png”: “Revirando solo – plantio nucleação – foto 1”
        “nuc_rev_solo_02.png”: “Revirando solo – plantio nucleação – foto 2”
        "nuc_rev_solo_03.png": "Revirando solo – plantio nucleação – foto 3"
    }

    pasta_fotos = "fotos_prad"
    if os.path.exists(pasta_fotos):
      todas_imagens = sorted([
          f
          for f in os.listdir(pasta_fotos)
          if f.lower().endswith((".png", ".jpg", ".jpeg"))
      ])

      # Filtra dinamicamente com base nas categorias selecionadas na barra lateral
      imagens_filtradas = []
      for img in todas_imagens:
        img_lower = img.lower()
        incluir = False

        if "Área de Conservação" in categorias_selecionadas and any(
            k in img_lower for k in ["con", "conserva"]
        ):
          incluir = True
        if "Áreas Isoladas" in categorias_selecionadas and any(
            k in img_lower for k in ["iso", "isolada"]
        ):
          incluir = True
        if "Áreas de Nucleação" in categorias_selecionadas and any(
            k in img_lower for k in ["nuc", "nuclea"]
        ):
          incluir = True

        if incluir:
          imagens_filtradas.append(img)

      # Se nenhuma imagem tiver filtro específico, exibe todas para não ficar vazio
      if not imagens_filtradas and todas_imagens:
        imagens_filtradas = todas_imagens

      if imagens_filtradas:
        cols = st.columns(min(3, len(imagens_filtradas)))
        for i, img_nome in enumerate(imagens_filtradas):
          caminho_img = os.path.join(pasta_fotos, img_nome)

          # Define a legenda: usa o dicionário se existir, ou limpa o nome do arquivo automaticamente
          if img_nome in legendas_personalizadas:
            legenda_texto = legendas_personalizadas[img_nome]
          else:
            # Transforma "isolada_trindade_01.jpg" em "Isolada Trindade 01"
            legenda_texto = (
                os.path.splitext(img_nome)[0].replace("_", " ").title()
            )

          with cols[i % len(cols)]:
            st.image(
                caminho_img,
                caption=f"📍 {legenda_texto}",
                use_container_width=True,
            )
      else:
        st.info("Nenhuma foto encontrada para as categorias selecionadas.")
    else:
      st.info(
          "💡 **Dica:** Crie uma pasta chamada `fotos_prad` e adicione as"
          " imagens."
      )

else:
  st.error("Não foram encontrados arquivos shapefile válidos na raiz.")
    
# 8. Rodapé Institucional
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: #4A634A; font-size: 0.9rem;'>"
    "<b>Departamento de Gestão Ambiental</b> • Compromisso com a Sustentabilidade."
    "</p>",
    unsafe_allow_html=True
)
