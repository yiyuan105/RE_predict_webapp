import geopandas as gpd
import os

# 把这里换成你刚下载的气候 SHP 文件的绝对路径
shp_path = r"D:\编程\ICT_Re_predict\China-GeoData-main\atomap\中国气候分区\Chinese_climate.shp" 

print(f"正在读取: {shp_path}")
try:
    gdf = gpd.read_file(shp_path)
except Exception as e:
    gdf = gpd.read_file(shp_path, encoding="gbk")

print("=== 属性表字段 ===")
print(gdf.columns.tolist())

print("\n=== 前 5 行的数据长什么样 ===")
# 只打印非几何字段
print(gdf.drop(columns='geometry').head())

print("\n=== 坐标系信息 ===")
print(gdf.crs)