import math
from django.http import HttpResponse
from .models_loader import get_model, stations  
from .openmeteo import get_weather_data
import numpy as np

def calculate_distance(lat1, lon1, lat2, lon2):
    return math.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)

def home(request):
    lat_str = request.GET.get('lat')
    lon_str = request.GET.get('lon')

    if not lat_str or not lon_str:
        return HttpResponse("请在网址带上经纬度，比如 ?lat=39.9&lon=116.4")

    try:
        user_lat = float(lat_str)
        user_lon = float(lon_str)
    except ValueError:
        return HttpResponse("经纬度必须是数字格式！")

    nearest_station_code = None
    min_distance = float('inf') 

    for code, info in stations.items():
        dist = calculate_distance(user_lat, user_lon, info["lat"], info["lon"])
        if dist < min_distance:
            min_distance = dist
            nearest_station_code = code

    model = get_model(nearest_station_code)
    if model is None:
        return HttpResponse("模型加载失败，请检查终端。")

    use_data = get_weather_data(user_lat, user_lon)
    
    try:
        prediction = model.predict(np.array(use_data).reshape(1, -1))
        result_value = prediction[0]
        
        return HttpResponse(
            f"您的位置:({user_lat}, {user_lon})。\n"
            f"匹配到最近的站点: {nearest_station_code} ({stations[nearest_station_code]['site_name']})\n"
            f"距离: {min_distance:.2f} 度\n"
            f"预测值: {result_value:.2f}"
        )
    except Exception as e:
        return HttpResponse(f"模型预测报错: {e}")