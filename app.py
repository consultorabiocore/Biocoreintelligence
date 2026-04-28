import ee
import gspread
from google.oauth2.service_account import Credentials
import datetime

# 1. Conexión con Google Earth Engine
ee.Authenticate()
ee.Initialize()

# 2. Conexión con tu Excel (Usa las mismas credenciales de la App)
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file('tu_archivo_credenciales.json', scopes=scope)
client = gspread.authorize(creds)
sheet = client.open_by_key('TU_ID_DE_EXCEL_LARGO').worksheet('Hoja 1')

# 3. Definir el área (Usa las coordenadas de Pascua Lama que registramos)
area_estudio = ee.Geometry.Polygon([[-70.01, -29.31], [-70.02, -29.31], [-70.02, -29.32], [-70.01, -29.32]])

# 4. Función para calcular NDSI y otros índices
def obtener_indices_satelitales():
    # Buscamos la imagen más reciente de Sentinel-2
    imagen = ee.ImageCollection("COPERNICUS/S2_SR") \
        .filterBounds(area_estudio) \
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
        .sort('system:time_start', False) \
        .first()
    
    fecha = imagen.date().format('dd/MM/yyyy').getInfo()
    
    # Cálculo de NDSI (Nieve)
    ndsi = imagen.normalizedDifference(['B3', 'B11']).reduceRegion(ee.Reducer.mean(), area_estudio).get('nd').getInfo()
    
    # Cálculo de SAVI (Suelo/Veg)
    savi = imagen.expression('((NIR - RED) / (NIR + RED + 0.5)) * (1.5)', {
        'NIR': imagen.select('B8'),
        'RED': imagen.select('B4')
    }).reduceRegion(ee.Reducer.mean(), area_estudio).get('constant').getInfo()

    # (Puedes agregar MNDWI, SWIR, etc., de la misma forma)
    
    return [fecha, round(savi, 4), 0, round(ndsi, 4), 0, 0] # El orden de tu Excel

# 5. ¡DISPARAR EL LLENADO!
datos_nuevos = obtener_indices_satelitales()
sheet.append_row(datos_nuevos)

print(f"✅ Satélite procesado. Datos de la fecha {datos_nuevos[0]} enviados a Biocore Intelligence.")
