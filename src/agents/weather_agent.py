"""
Weather Agent for fetching current weather and 7-day forecast via OpenWeather API.
"""

import asyncio
import httpx
from typing import Optional, List
from datetime import datetime
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel

from models import WeatherModel, WeatherData, AgentResponse
from config import config


class WeatherAgentDeps:
    """Dependencies for Weather Agent."""
    def __init__(self):
        self.api_key = config.OPENWEATHER_API_KEY
        self.timeout = config.REQUEST_TIMEOUT
        self.units = config.WEATHER_UNITS
        self.lang = config.WEATHER_LANG


async def fetch_current_weather(location: str, api_key: str, units: str = "metric") -> dict:
    """Fetch current weather data from OpenWeather API."""
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": location,
        "appid": api_key,
        "units": units
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def fetch_weather_forecast(location: str, api_key: str, units: str = "metric") -> dict:
    """Fetch 7-day weather forecast from OpenWeather API."""
    # First get coordinates from location
    geo_url = "https://api.openweathermap.org/geo/1.0/direct"
    geo_params = {
        "q": location,
        "limit": 1,
        "appid": api_key
    }
    
    async with httpx.AsyncClient() as client:
        geo_response = await client.get(geo_url, params=geo_params)
        geo_response.raise_for_status()
        geo_data = geo_response.json()
        
        if not geo_data:
            raise ValueError(f"Location not found: {location}")
        
        lat, lon = geo_data[0]["lat"], geo_data[0]["lon"]
        
        # Get forecast using coordinates
        forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
        forecast_params = {
            "lat": lat,
            "lon": lon,
            "appid": api_key,
            "units": units
        }
        
        forecast_response = await client.get(forecast_url, params=forecast_params)
        forecast_response.raise_for_status()
        return forecast_response.json()


def parse_weather_data(weather_json: dict) -> WeatherData:
    """Parse OpenWeather API response into WeatherData model."""
    return WeatherData(
        timestamp=datetime.fromtimestamp(weather_json["dt"]).isoformat(),
        temp=weather_json["main"]["temp"],
        description=weather_json["weather"][0]["description"],
        humidity=weather_json["main"].get("humidity"),
        wind_speed=weather_json.get("wind", {}).get("speed")
    )


# Create Weather Agent with instrumentation
weather_agent = Agent(
    model=OpenAIModel(config.WEATHER_MODEL),
    deps_type=WeatherAgentDeps,
    output_type=WeatherModel,
    instrument=True,  # Enable Pydantic AI tracing
    system_prompt="""
    You are a weather information agent. Your job is to:
    1. Fetch current weather conditions for specified locations
    2. Retrieve 7-day weather forecasts
    3. Return structured weather data with current conditions and forecast
    
    Always validate location names and handle API errors gracefully.
    Provide comprehensive weather information in the specified format.
    """,
    retries=config.MAX_RETRIES
)


@weather_agent.tool
async def get_weather_data(ctx: RunContext[WeatherAgentDeps], location: str) -> WeatherModel:
    """Tool to fetch weather data for a location."""
    try:
        if not ctx.deps.api_key:
            # Return minimal WeatherModel with error state
            return WeatherModel(
                location=location,
                current=WeatherData(
                    timestamp=datetime.now().isoformat(),
                    temp=0.0,
                    description="API key not configured",
                    humidity=0,
                    wind_speed=0.0
                ),
                forecast=[],
                units=ctx.deps.units
            )
        
        # Fetch current weather and forecast
        current_data = await fetch_current_weather(
            location, ctx.deps.api_key, ctx.deps.units
        )
        forecast_data = await fetch_weather_forecast(
            location, ctx.deps.api_key, ctx.deps.units
        )
        
        # Parse current weather
        current_weather = parse_weather_data(current_data)
        
        # Parse forecast (take every 8th entry for daily forecast - 3-hour intervals)
        forecast_list = []
        for i in range(0, min(len(forecast_data["list"]), 40), 8):  # 7 days max
            forecast_item = parse_weather_data(forecast_data["list"][i])
            forecast_list.append(forecast_item)
        
        # Return WeatherModel object to match agent output_type
        return WeatherModel(
            location=location,
            current=current_weather,
            forecast=forecast_list,
            units=ctx.deps.units
        )
               
    except Exception as e:
        # Return minimal WeatherModel with error state
        return WeatherModel(
            location=location,
            current=WeatherData(
                timestamp=datetime.now().isoformat(),
                temp=0.0,
                description=f"Error: {str(e)}",
                humidity=0,
                wind_speed=0.0
            ),
            forecast=[],
            units=ctx.deps.units
        )


async def process_weather_request(location: str) -> AgentResponse:
    """Process weather data request."""
    start_time = asyncio.get_event_loop().time()
    
    try:
        deps = WeatherAgentDeps()
        
        if not deps.api_key:
            return AgentResponse(
                agent_name="WeatherAgent",
                success=False,
                error="OpenWeather API key not configured"
            )
        
        # Fetch current weather and forecast
        current_data = await fetch_current_weather(location, deps.api_key, deps.units)
        forecast_data = await fetch_weather_forecast(location, deps.api_key, deps.units)
        
        # Parse current weather
        current_weather = parse_weather_data(current_data)
        
        # Parse forecast (take every 8th entry for daily forecast - 3-hour intervals)
        forecast_list = []
        for i in range(0, min(len(forecast_data["list"]), 40), 8):  # 7 days max
            forecast_item = parse_weather_data(forecast_data["list"][i])
            forecast_list.append(forecast_item)
        
        # Create result model
        result = WeatherModel(
            location=location,
            current=current_weather,
            forecast=forecast_list,
            units=deps.units
        )
        
        processing_time = asyncio.get_event_loop().time() - start_time
        
        return AgentResponse(
            agent_name="WeatherAgent",
            success=True,
            data=result.model_dump(),
            processing_time=processing_time
        )
        
    except Exception as e:
        processing_time = asyncio.get_event_loop().time() - start_time
        return AgentResponse(
            agent_name="WeatherAgent",
            success=False,
            error=str(e),
            processing_time=processing_time
        )
