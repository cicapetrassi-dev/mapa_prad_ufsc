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
    # Seletor para escolher qual shapefile visualizar
    selected_file = st.selectbox("Selecione a área de plantio / shapefile:", shape_files)
    
    if selected_file:
        try:
            # Ler o shapefile com geopandas
            gdf = gpd.read_file(selected_file)
            
            # Reposicionar para o sistema de coordenadas padrão de mapas web (WGS84 / EPSG:4326)
            if gdf.crs and gdf.crs != "EPSG:4326":
                gdf = gdf.to_crs(epsg=4326)
            
            # Obter o centroide médio para centralizar o mapa
            if not gdf.empty:
                bounds = gdf.total_bounds # [minx, miny, maxx, maxy]
                center_lat = (bounds[1] + bounds[3]) / 2
                center_lon = (bounds[0] + bounds[2]) / 2
            else:
                center_lat, center_lon = -27.601, -48.518 # UFSC Florianópolis padrão
                
            # Criar o mapa com Folium
            m = folium.Map(location=[center_lat, center_lon], zoom_start=15)
            
            # Adicionar camada geojson ao mapa
            folium.GeoJson(
                gdf,
                name="Área PRAD",
                style_function=lambda x: {'fillColor': '#2E7D32', 'color': '#1B5E20', 'weight': 2, 'fillOpacity': 0.5}
            ).add_to(m)
            
            folium.LayerControl().add_to(m)
            
            # Exibir o mapa no Streamlit
            st.subheader(f"Visualização: {selected_file}")
            st_folium(m, width=1100, height=550)
            
            # Exibir tabela de dados correspondente
            with st.expander("📋 Ver dados e atributos da tabela"):
                st.dataframe(gdf.drop(columns="geometry", errors="ignore"))
                
        except Exception as e:
            st.error(f"Erro ao processar o arquivo {selected_file}: {e}")

# Rodapé institucional
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: gray;'>Coordenação de Gestão Ambiental • Compromisso com a Sustentabilidade.</p>", 
    unsafe_allow_html=True
)
