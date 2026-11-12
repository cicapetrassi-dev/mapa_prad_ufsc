import os
import glob
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium

# Configuração da página
st.set_page_config(
    page_title="Mapeamento Geral de Áreas de Plantio (PRAD)",
    page_icon="🌿",
    layout="wide"
)

# Cabeçalho do Aplicativo
st.markdown("🌿 **Mapeamento Geral de Áreas de Plantio (PRAD)**")
st.markdown("Acompanhamento integrado das frentes de Isoladas, Nucleação e Conservação Ambiental.")
st.markdown("---")

# Procurar arquivos .shp diretamente na raiz do repositório (.)
shape_files = glob.glob("*.shp")

if not shape_files:
    st.warning("Não foram encontrados arquivos shapefile válidos na raiz do repositório.")
    st.info("Certifique-se de que os arquivos (.shp, .shx, .dbf, .prj) foram enviados corretamente para a página principal do GitHub.")
else:
    # Sidebar com opções de visualização
    st.sidebar.header("⚙️ Configurações do Mapa")
    selected_file = st.sidebar.selectbox("Selecione o shapefile:", shape_files)
    
    if selected_file:
        try:
            # Ler o shapefile com geopandas
            gdf = gpd.read_file(selected_file)
            
            # Reposicionar para o sistema de coordenadas padrão de mapas web (WGS84 / EPSG:4326)
            if gdf.crs and gdf.crs != "EPSG:4326":
                gdf = gdf.to_crs(epsg=4326)
            
            # Métricas rápidas no topo
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total de Feições / Áreas", len(gdf))
            with col2:
                if 'geometry' in gdf:
                    # Cálculo aproximado de área se estiver em coordenadas projetadas ou métricas
                    st.metric("Sistema de Coordenadas", str(gdf.crs).split('/')[-1])
            with col3:
                st.metric("Atributos Disponíveis", len(gdf.columns) - 1)
            
            st.markdown("---")

            # Obter o centroide médio para centralizar o mapa
            if not gdf.empty:
                bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
                center_lat = (bounds[1] + bounds[3]) / 2
                center_lon = (bounds[0] + bounds[2]) / 2
            else:
                center_lat, center_lon = -27.601, -48.518  # UFSC Florianópolis padrão
                
            # Criar o mapa com Folium
            m = folium.Map(location=[center_lat, center_lon], zoom_start=15, control_scale=True)
            
            # Adicionar camada geojson ao mapa com tooltip interativo
            # Identifica colunas úteis para exibição no mapa
            tooltip_cols = [col for col in gdf.columns if col != 'geometry'][:3]
            
            folium.GeoJson(
                gdf,
                name="Área PRAD",
                style_function=lambda x: {
                    'fillColor': '#2E7D32', 
                    'color': '#1B5E20', 
                    'weight': 2, 
                    'fillOpacity': 0.6
                },
                tooltip=folium.GeoJsonTooltip(fields=tooltip_cols, aliases=[f"{c}:" for c in tooltip_cols])
            ).add_to(m)
            
            folium.LayerControl().add_to(m)
            
            # Exibir o mapa no Streamlit
            st.subheader(f"Visualização do Mapa: {selected_file}")
            st_folium(m, width=1100, height=550)
            
            # Exibir tabela de dados correspondente
            st.markdown("### 📋 Tabela de Atributos")
            with st.expander("Expandir para ver todos os dados da tabela", expanded=True):
                st.dataframe(gdf.drop(columns="geometry", errors="ignore"), use_container_width=True)
                
        except Exception as e:
            st.error(f"Erro ao processar o arquivo {selected_file}: {e}")

# Rodapé institucional
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: gray;'>Coordenação de Gestão Ambiental • Compromisso com a Sustentabilidade.</p>", 
    unsafe_allow_html=True
)
