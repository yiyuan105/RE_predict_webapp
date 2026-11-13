import pandas as pd
import openmeteo_requests

def get_weather_data(lat, lon):
    openmeteo = openmeteo_requests.Client()
    url = "https://ensemble-api.open-meteo.com/v1/ensemble"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": [
            "temperature_2m",
            "relative_humidity_2m",
            "surface_pressure",
            "soil_moisture_0_to_7cm",
            "soil_moisture_7_to_28cm",
            "shortwave_radiation",
        ],
        "models": "gfs_seamless",
        "forecast_days": 1,
        "timezone": "Asia/Shanghai",
    }

    response = openmeteo.weather_api(url, params=params)[0]
    hourly = response.Hourly()

    df = pd.DataFrame({
        "time": pd.date_range(
            start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
            end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left",
        ).tz_convert("Asia/Shanghai")
    })

    for i, variable in enumerate(params["hourly"]):
        df[variable] = hourly.Variables(i).ValuesAsNumpy()

    df_daily = df.resample("1D", on="time").mean(numeric_only=True).reset_index()
    means_value = df_daily.head(3).mean(numeric_only=True)

    mean_rn = means_value["shortwave_radiation"] * 0.6

    features = [
        mean_rn,
        means_value["temperature_2m"],
        means_value["relative_humidity_2m"],
        means_value["surface_pressure"],
        means_value["soil_moisture_0_to_7cm"],
        means_value["soil_moisture_7_to_28cm"],
    ]

    return features