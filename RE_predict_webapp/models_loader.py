import os
import json
import joblib
from django.conf import settings


config_path = os.path.join(settings.BASE_DIR, 'RE_predict_webapp', 'config.json')


with open(config_path, 'r', encoding='utf-8') as f:
    config_data = json.load(f)


stations = config_data["stations"]

_models_cache = {}

def load_models():
    global _models_cache
    if _models_cache:
        return _models_cache
    
    print("========== 开始加载 12 个站点的模型... ==========")
    

    for station in stations.keys():

        model_path = os.path.join(settings.BASE_DIR, f'models/rf_models/{station}_rf.joblib')
        
        if os.path.exists(model_path):
            try:
                _models_cache[station] = joblib.load(model_path)
                print(f"[成功] {station} 模型已装载进内存。")
            except Exception as e:
                print(f"[失败] {station} 模型文件损坏或读取出错: {e}")
        else:
            print(f"[警告] 找不到 {station} 的模型文件，路径: {model_path}")
            
    print(f"========== 模型加载完毕！共成功加载 {len(_models_cache)} 个。 ==========")
    return _models_cache

def get_model(station_name):
    return _models_cache.get(station_name)