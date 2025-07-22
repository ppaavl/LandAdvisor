import os
import requests
from fastapi import FastAPI, HTTPException, Query
from dotenv import load_dotenv
import json
import googlemaps # Biblioteca pentru Google Maps

# --- Configurare ---
load_dotenv()
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

app = FastAPI(
    title="LandAdvisor API",
    description="An API to obtain consolidated environmental data for a given location."
)

# --- Inițializarea clienților API ---
if not GOOGLE_MAPS_API_KEY:
    raise RuntimeError("Cheia GOOGLE_MAPS_API_KEY nu a fost găsită în fișierul .env")
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# Lista reședințelor de județ din România pentru calculul distanței
JUDET_CAPITALS = [
    "Alba Iulia", "Arad", "Pitești", "Bacău", "Oradea", "Bistrița", "Botoșani", "Brașov",
    "Brăila", "București", "Buzău", "Reșița", "Călărași", "Cluj-Napoca", "Constanța",
    "Sfântu Gheorghe", "Târgoviște", "Craiova", "Galați", "Giurgiu", "Târgu Jiu",
    "Miercurea Ciuc", "Deva", "Slobozia", "Iași", "Baia Mare", "Drobeta-Turnu Severin",
    "Piatra Neamț", "Slatina", "Ploiești", "Satu Mare", "Zalău", "Sibiu", "Suceava",
    "Alexandria", "Timișoara", "Tulcea", "Vaslui", "Râmnicu Vâlcea", "Focșani"
]

# --- Servicii API Reale ---

def get_coordinates_from_address(address: str):
    """Folosește Google Geocoding API pentru precizie maximă."""
    try:
        print(f"[API Real] Se caută coordonatele pentru: {address} folosind Google Maps...")
        geocode_result = gmaps.geocode(address, components={"country": "RO"})
        if not geocode_result: return None
        location = geocode_result[0]['geometry']['location']
        return {"lat": location['lat'], "lon": location['lng']}
    except Exception as e:
        print(f"Eroare la geocodificare Google Maps: {e}")
        return None

def get_elevation_data(lat: float, lon: float):
    """Obține datele de elevație (altitudine) de la Google Maps Elevation API."""
    try:
        print(f"[API Real] Se obține elevația de la Google Maps...")
        elevation_result = gmaps.elevation((lat, lon))
        if not elevation_result: return None
        elevation = elevation_result[0]['elevation']
        return {"elevation_m": round(elevation, 2), "source": "Google Maps Elevation API"}
    except Exception as e:
        print(f"[AVERTISMENT] Eroare la Google Elevation API: {e}")
        return None

def get_fallback_weather_data(lat: float, lon: float):
    """Sursă de rezervă: Obține datele curente de la OpenWeatherMap."""
    if not WEATHER_API_KEY: return None
    api_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric&lang=ro"
    try:
        print("[Fallback API] Calling OpenWeatherMap...")
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return {
            "current_temp_c": data.get("main", {}).get("temp"),
            "current_feels_like_temp_c": data.get("main", {}).get("feels_like"),
            "current_temp_min_c": data.get("main", {}).get("temp_min"),
            "current_temp_max_c": data.get("main", {}).get("temp_max"),
            "current_pressure_hPa": data.get("main", {}).get("pressure"),
            "current_humidity_percent": data.get("main", {}).get("humidity"),
            "current_wind_speed_ms": data.get("wind", {}).get("speed"),
            "current_wind_direction_deg": data.get("wind", {}).get("deg"),
            "current_wind_gust_ms": data.get("wind", {}).get("gust"),
            "current_visibility_m": data.get("visibility"),
            "current_cloudiness_percent": data.get("clouds", {}).get("all"),
            "source": "OpenWeatherMap API"
        }
    except Exception as e:
        print(f"[WARNING] Fallback call to OpenWeatherMap failed: {e}")
        return None

def get_air_quality_data(lat: float, lon: float):
    """Obține date despre calitatea aerului de la OpenWeatherMap."""
    if not WEATHER_API_KEY: return None
    api_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}"
    try:
        print("[API Real] Se apelează OpenWeatherMap Air Pollution...")
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        aqi_map = {1: "Bună", 2: "Acceptabilă", 3: "Moderată", 4: "Rea", 5: "Foarte Rea"}
        aqi_index = data.get("list", [{}])[0].get("main", {}).get("aqi")
        
        return {
            "aqi_index": aqi_index,
            "aqi_description": aqi_map.get(aqi_index, "Necunoscut"),
            "pollutants_ug_m3": data.get("list", [{}])[0].get("components", {}),
            "source": "OpenWeatherMap Air Pollution API"
        }
    except Exception as e:
        print(f"[AVERTISMENT] Eroare la apelul OpenWeatherMap Air Pollution: {e}")
        return None

def get_advanced_soil_data(lat: float, lon: float):
    """Obține atât tipul, cât și proprietățile detaliate ale solului de la OpenEPI."""
    soil_info = {}
    
    # Apel pentru Tipul de Sol
    type_url = f"https://api.openepi.io/soil/type?lat={lat}&lon={lon}&top_k=3"
    try:
        print(f"[Real API] Calling OpenEPI Soil Type...")
        response = requests.get(type_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        soil_info["top_3_types_wrb"] = data.get("properties", {}).get("probabilities", [])
    except Exception as e:
        print(f"[WARNING] Could not obtain general soil type from OpenEPI: {e}")
        soil_info["top_3_types_wrb"] = []

    # Apel pentru Proprietățile Solului
    property_url = "https://api.openepi.io/soil/property"
    params = [
        ('lat', lat), ('lon', lon),
        ('depths', '0-5cm'), ('depths', '5-15cm'),
        ('properties', 'phh2o'), ('properties', 'soc'), ('properties', 'clay'),
        ('properties', 'bdod'), ('properties', 'cec'), ('properties', 'nitrogen'),
        ('properties', 'sand'), ('properties', 'silt'),
        ('values', 'mean')
    ]
    try:
        print(f"[Real API] Calling OpenEPI Soil Property for detailed data...")
        response = requests.get(property_url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        soil_properties_by_depth = {"0-5cm_depth": {}, "5-15cm_depth": {}}
        has_detailed_data = False
        if "properties" in data and "layers" in data["properties"]:
            for layer in data["properties"]["layers"]:
                prop_code = layer.get("name")
                for depth_entry in layer.get("depths", []):
                    depth_label = depth_entry.get("label")
                    mean_value = depth_entry.get("values", {}).get("mean")
                    if mean_value is not None:
                        has_detailed_data = True
                        target_depth_key = f"{depth_label}_depth"
                        if target_depth_key in soil_properties_by_depth:
                            prop_name = f"{prop_code}_value"
                            soil_properties_by_depth[target_depth_key][prop_name] = round(mean_value, 2)
        soil_info["detailed_properties_by_depth"] = soil_properties_by_depth
        soil_info["source"] = "OpenEPI Soil API (EUSO)" if has_detailed_data else "OpenEPI Soil API (Tip General) / Proprietăți Indisponibile"
        
    except Exception as e:
        print(f"[WARNING] Could not obtain detailed soil properties from OpenEPI: {e}")
        soil_info["detailed_properties_by_depth"] = {"source": "Error during OpenEPI Properties call"}
        if "source" not in soil_info: soil_info["source"] = "OpenEPI Indisponibil"

    return soil_info

def get_climate_data_nasa_power(lat: float, lon: float):
    """Obține date climatice medii anuale (precipitații, solar) de la NASA POWER."""
    base_url = "https://power.larc.nasa.gov/api/temporal/climatology/point"
    parameters_str = "PRECTOTCORR,ALLSKY_SFC_SW_DWN"
    params = {
        "parameters": parameters_str, "community": "RE", "longitude": lon,
        "latitude": lat, "format": "JSON"
    }
    try:
        print(f"[Real API] Calling NASA POWER for climatology data...")
        response = requests.get(base_url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        
        properties = data.get("properties", {}).get("parameter", {})
        if not properties:
            return None

        precip_val = properties.get("PRECTOTCORR", {}).get("ANN")
        solar_val = properties.get("ALLSKY_SFC_SW_DWN", {}).get("ANN")

        return {
            "annual_avg_precipitation_mm_day": round(precip_val, 2) if precip_val is not None and precip_val > -900 else "N/A",
            "annual_avg_ghi_kwh_m2_day": round(solar_val, 2) if solar_val is not None and solar_val > -900 else "N/A",
            "source": "NASA POWER (Climatology)"
        }
    except Exception as e:
        print(f"[WARNING] Call to NASA POWER API failed: {e}.")
        return None

def get_infrastructure_data(lat: float, lon: float):
    """Obține date extinse despre infrastructură folosind Google Maps API."""
    origin = (lat, lon)
    infra_data = {}
    
    try:
        print("[API Real] Se calculează distanța până la orașe folosind Google Distance Matrix...")
        matrix = gmaps.distance_matrix(origins=[origin], destinations=JUDET_CAPITALS, mode="driving")
        closest_city = None
        min_distance = float('inf')
        if matrix['rows'][0]['elements']:
            for i, element in enumerate(matrix['rows'][0]['elements']):
                if element['status'] == 'OK' and element['distance']['value'] < min_distance:
                    min_distance = element['distance']['value']
                    closest_city = {
                        "name": matrix['destination_addresses'][i],
                        "distance_km": round(element['distance']['value'] / 1000, 2),
                        "duration_text": element['duration']['text']
                    }
        infra_data["closest_major_city"] = closest_city
    except Exception as e:
        print(f"[AVERTISMENT] Eroare la Google Distance Matrix API: {e}")

    try:
        print("[API Real] Se caută infrastructura energetică (stații electrice, conducte de gaze)...")
        places_electric = gmaps.places_nearby(location=origin, radius=5000, keyword="substație electrică", language="ro")
        substations = [{"name": place.get('name')} for place in places_electric.get('results', [])]
        infra_data["nearby_substations_5km"] = substations
        infra_data["grid_connectivity_proxy"] = "Probabil ridicată" if len(substations) > 0 else "Necesită investigații"
        
        places_gas = gmaps.places_nearby(location=origin, radius=5000, keyword="conductă de gaze naturale", language="ro")
        gas_pipelines = [{"name": place.get('name')} for place in places_gas.get('results', [])]
        infra_data["nearby_gas_pipelines_5km"] = gas_pipelines
        infra_data["gas_utility_proxy"] = "Acces posibil" if len(gas_pipelines) > 0 else "Acces improbabil"
    except Exception as e:
        print(f"[AVERTISMENT] Eroare la Google Places API (Energie): {e}")

    try:
        print("[API Real] Se caută zone protejate în apropiere...")
        keywords_protected = "parc național OR rezervație naturală OR sit natura 2000"
        places_protected = gmaps.places_nearby(location=origin, radius=10000, keyword=keywords_protected, language="ro")
        protected_areas = [{"name": place.get('name')} for place in places_protected.get('results', [])]
        infra_data["nearby_protected_areas_10km"] = protected_areas
        infra_data["environmental_restrictions_proxy"] = "Risc ridicat de restricții" if len(protected_areas) > 0 else "Risc scăzut de restricții"
    except Exception as e:
        print(f"[AVERTISMENT] Eroare la Google Places API (Zone Protejate): {e}")

    infra_data["source"] = "Google Maps Platform APIs"
    return infra_data

# --- Funcția Principală de Preluare a Datelor ---
def get_environmental_data(lat: float, lon: float):
    """Orchestrează toate apelurile API și structurează răspunsul final."""
    elevation_data = get_elevation_data(lat, lon)
    soil_data = get_advanced_soil_data(lat, lon)
    current_weather_data = get_fallback_weather_data(lat, lon)
    air_quality_data = get_air_quality_data(lat, lon)
    infrastructure_data = get_infrastructure_data(lat, lon)
    nasa_climate_data = get_climate_data_nasa_power(lat, lon)

    final_data = {
        "location_details": {
            "provided_lat": lat, "provided_lon": lon,
            "elevation_m": elevation_data.get("elevation_m", "N/A") if elevation_data else "N/A",
            "source_elevation": elevation_data.get("source", "N/A") if elevation_data else "N/A",
            "country": "Romania"
        },
        "current_conditions": current_weather_data if current_weather_data else {"source": "Data Indisponibilă"},
        "air_quality": air_quality_data if air_quality_data else {"source": "Date indisponibile"},
        "historical_climatology": nasa_climate_data if nasa_climate_data else {"source": "Data Indisponibilă"},
        "soil_properties": soil_data if soil_data else {"source": "OpenEPI indisponibil"},
        "infrastructure": infrastructure_data
    }
    return final_data

# --- Endpoint-ul API ---
@app.get("/api/get-land-data")
async def get_land_data(
    lat: float = Query(..., description="Latitudinea locației."),
    lon: float = Query(..., description="Longitudinea locației.")
):
    """
    Preia date de mediu consolidate pentru o anumită latitudine și longitudine.
    """
    environmental_data = get_environmental_data(lat, lon)
    if not environmental_data:
        raise HTTPException(status_code=500, detail="Eroare la preluarea datelor de mediu.")
    return environmental_data

if __name__ == "__main__":
    import uvicorn
    print("Pentru a porni serverul, rulați în terminal comanda:")
    print("uvicorn main:app --reload")
