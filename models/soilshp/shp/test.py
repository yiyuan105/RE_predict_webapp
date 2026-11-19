import geopandas as gpd
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
shp_path = os.path.join(current_dir, 'Soil.shp')

soil_gdf = gpd.read_file(shp_path, encoding="gbk")

# 打印前 10 行，看看这四个字段里到底装了啥
print(soil_gdf[['SOIL_', 'SOIL_ID', 'DL']].head(10))