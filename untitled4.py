import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pyspark.sql import SparkSession
from pyspark.sql.functions import explode, col

API_KEY = "abaa4d0c32318cdd32cea687247af76d"

cities = {
    "Mumbai": "1275339",
    "Delhi": "1273294",
    "Bengaluru": "1277333",
    "Hyderabad": "1269843",
    "Ahmedabad": "1279233",
    "Chennai": "1264527",
    "Kolkata": "1275004",
    "Pune": "1259229",
    "Jaipur": "1269515",
    "Lucknow": "1264731",
    "Kanpur": "1259279",
    "Nagpur": "1268086",
    "Indore": "1273293",
    "Thane": "1275334",
    "Bhopal": "1275002"
}

st.title("🌤️ Real-time Weather Data Analytics - Indian Cities")

city_name = st.selectbox("Select a city", list(cities.keys()))

metrics = st.multiselect(
    "Select metrics to analyze & visualize",
    ['Temperature', 'Humidity', 'Wind Speed', 'Precipitation'],
    default=['Temperature', 'Humidity']
)

date_filter = st.checkbox("Filter by date range")

# Date filter inputs
start_date = None
end_date = None
if date_filter:
    start_date = st.date_input("Start date")
    end_date = st.date_input("End date")
    if start_date > end_date:
        st.error("Start date must be before end date.")

if st.button("Fetch and Analyze Weather Data"):
    with st.spinner('Fetching data...'):
        FORECAST_URL = f"http://api.openweathermap.org/data/2.5/forecast?id={cities[city_name]}&appid={API_KEY}&units=metric"
        response = requests.get(FORECAST_URL)

        if response.status_code != 200:
            st.error("Failed to fetch weather data.")
        else:
            weather_json = response.json()
            forecasts = weather_json['list']

            spark = SparkSession.builder.appName("WeatherApp").getOrCreate()

            rdd = spark.sparkContext.parallelize(forecasts)
            df = spark.read.json(rdd)

            weather_df = df.select(
                col("dt_txt"),
                col("main.temp").alias("temperature"),
                col("main.humidity").alias("humidity"),
                col("wind.speed").alias("wind_speed"),
                explode("weather").alias("weather_desc")
            ).select(
                "dt_txt", "temperature", "humidity", "wind_speed", col("weather_desc.description").alias("description")
            )

            # Convert to Pandas
            weather_pd = weather_df.toPandas()
            weather_pd['dt_txt'] = pd.to_datetime(weather_pd['dt_txt'])

            # Precipitation
            precipitation = [f.get('rain', {}).get('3h', 0) for f in forecasts]
            weather_pd['precipitation'] = precipitation

            # Date range filter
            if date_filter and start_date and end_date:
                weather_pd = weather_pd[(weather_pd['dt_txt'].dt.date >= start_date) & (weather_pd['dt_txt'].dt.date <= end_date)]
                if weather_pd.empty:
                    st.warning("No data available in this date range.")

            # Show summary stats
            st.subheader(f"Summary Statistics for {city_name}")
            for metric in metrics:
                col_name = metric.lower().replace(" ", "_")
                avg_val = weather_pd[col_name].mean()
                st.write(f"**Average {metric}:** {avg_val:.2f}")

            # Plotting
            st.subheader("Visualizations")

            # Time series line plots for selected metrics
            plt.figure(figsize=(12, 6))
            for metric in metrics:
                col_name = metric.lower().replace(" ", "_")
                sns.lineplot(data=weather_pd, x='dt_txt', y=col_name, label=metric, marker='o')
            plt.xlabel('Date Time')
            plt.ylabel('Value')
            plt.title(f"{', '.join(metrics)} Trends over Time")
            plt.xticks(rotation=45)
            plt.legend()
            st.pyplot(plt.gcf())
            plt.clf()

            # Additional plots
            # Histogram of temperature
            if 'Temperature' in metrics:
                st.subheader("Temperature Distribution")
                plt.figure(figsize=(8, 4))
                sns.histplot(weather_pd['temperature'], bins=15, kde=True, color='orange')
                plt.xlabel('Temperature (°C)')
                st.pyplot(plt.gcf())
                plt.clf()

            # Wind speed scatter with precipitation size
            if 'Wind Speed' in metrics and 'Precipitation' in metrics:
                st.subheader("Wind Speed vs Precipitation")
                plt.figure(figsize=(8, 5))
                sizes = weather_pd['precipitation'] * 100  # scale for size
                plt.scatter(weather_pd['wind_speed'], weather_pd['precipitation'], s=sizes + 10, alpha=0.6, c=weather_pd['temperature'], cmap='coolwarm')
                plt.colorbar(label='Temperature (°C)')
                plt.xlabel('Wind Speed (m/s)')
                plt.ylabel('Precipitation (mm)')
                plt.title('Wind Speed vs Precipitation (Bubble size scaled to precipitation)')
                st.pyplot(plt.gcf())
                plt.clf()

spark.stop()
