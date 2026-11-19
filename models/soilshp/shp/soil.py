import json
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(current_dir, 'config.json')
shp_path = os.path.join(current_dir, 'Soil.shp')

with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)
stations = config['stations']

print("正在读取原始土壤数据...")
try:
    soil_gdf = gpd.read_file(shp_path)
except Exception as e:
    soil_gdf = gpd.read_file(shp_path, encoding="gbk")

# 【最终修复】使用真正的三位数编码字段
code_field = 'SOIL_ID' 

# 完整的中国土壤土类字典（基于你的文档）
soil_dict = {
    "01": "南方水稻土", "02": "鲜血水稻土", "03": "北方水稻土",
    "04": "黄刚土", "05": "黄堰土", "06": "黄垆土", "07": "娄土", "08": "黑垆土", "09": "绵土",
    "10": "熟黑土", "11": "潮土", "12": "灌淤土", "13": "绿洲土", 
    "14": "砖红壤", "15": "赤红壤", "16": "红壤", "17": "燥红土", "18": "黄壤", 
    "19": "黄棕壤", "20": "棕壤", "21": "褐土", "22": "灰褐土", "23": "暗棕壤",
    "24": "漂灰土", "25": "灰色森林土", "26": "黑土", "27": "白浆土", "28": "黑钙土",
    "29": "栗钙土", "30": "棕钙土", "31": "灰钙土", "32": "灰漠土", "33": "灰棕漠土",
    "34": "棕漠土", "35": "暗色草甸土", "36": "灰色草甸土", "37": "沼泽土", "38": "滨海盐土",
    "39": "盐土", "40": "内陆盐土", "41": "碱土", "42": "磷质石灰土", "43": "石灰(岩)土",
    "44": "紫色土", "45": "龟裂土", "46": "风沙土", "47": "山地草甸土", "48": "山地灌丛草原土",
    "49": "黑毡土(亚高山草甸土)", "50": "巴嘎土(亚高山草原土)", "51": "草毡土(高山草甸土)",
    "52": "莎嘎土(高山草原土)", "53": "高山漠土", "54": "寒漠土",
    "71": "冰川和雪被", "72": "盐壳", "90": "湖泊"
}

print("\n--- 站点土壤区划查询结果 ---\n")
results = []

for code, info in stations.items():
    site_name = info['site_name']
    lon = info['lon']
    lat = info['lat']
    
    # 局部投影
    point_wgs84 = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326")
    point_projected = point_wgs84.to_crs(soil_gdf.crs).iloc[0]
    
    matched = soil_gdf[soil_gdf.geometry.intersects(point_projected)]
    
    if not matched.empty:
        raw_code_val = matched.iloc[0][code_field]
        
        if pd.isna(raw_code_val):
            soil_name = "无数据"
        else:
            # 确保编码是三位字符串
            raw_code = str(int(raw_code_val)).zfill(3)
            main_class_code = raw_code[:2]
            soil_name = soil_dict.get(main_class_code, f"未知土类 (编码:{raw_code})")
    else:
        soil_name = "未匹配到 (落在多边形外)"

    results.append({
        "站点": code,
        "名称": site_name,
        "经纬度": f"{lon}, {lat}",
        "土壤类型": soil_name
    })

df_results = pd.DataFrame(results)
print(df_results.to_string(index=False))

out_csv = os.path.join(current_dir, "station_soil_results.csv")
df_results.to_csv(out_csv, index=False, encoding='utf-8-sig')