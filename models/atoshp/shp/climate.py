import json
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
# 注意：这里路径换成你刚才跑通的那个 climate.shp 的绝对路径
shp_path = r"D:\编程\ICT_Re_predict\China-GeoData-main\atomap\中国气候分区\Chinese_climate.shp"
# 配置文件路径（如果你把脚本放在 test.py 同目录，就是下面这个）
config_path = r"D:\编程\ICT_Re_predict\China-GeoData-main\atomap\中国气候分区\config.json" 

with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)
stations = config['stations']

print("正在读取气候分区数据...")
try:
    climate_gdf = gpd.read_file(shp_path)
except Exception as e:
    climate_gdf = gpd.read_file(shp_path, encoding="gbk")

print("\n--- 站点气候区划查询结果 ---\n")
results = []

for code, info in stations.items():
    site_name = info['site_name']
    lon = info['lon']
    lat = info['lat']
    
    # 创建 WGS84 点并局部投影到气候数据的坐标系
    point_wgs84 = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326")
    point_projected = point_wgs84.to_crs(climate_gdf.crs).iloc[0]
    
    matched = climate_gdf[climate_gdf.geometry.intersects(point_projected)]
    
    if not matched.empty:
        # 直接提取 climate 字段的值
        climate_name = matched.iloc[0]['climate']
    else:
        climate_name = "未匹配到"

    results.append({
        "站点": code,
        "名称": site_name,
        "经纬度": f"{lon}, {lat}",
        "气候区划": climate_name
    })

df_results = pd.DataFrame(results)
print(df_results.to_string(index=False))