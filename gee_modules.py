"""
gee_modules.py
Modul Pemrosesan Spasial Google Earth Engine untuk LontaraGeo
Berisi fungsi prapemrosesan, indeks spektral, analisis medan (terrain), dan machine learning.
"""

import ee

# ==========================================
# 1. KONFIGURASI BAND & PALET WARNA
# ==========================================
SATELLITE_BANDS = {
    'COPERNICUS/S2_SR_HARMONIZED': {'BLUE': 'B2', 'GREEN': 'B3', 'RED': 'B4', 'NIR': 'B8', 'SWIR1': 'B11', 'SWIR2': 'B12'},
    'LANDSAT/LC08/C02/T1_L2': {'BLUE': 'SR_B2', 'GREEN': 'SR_B3', 'RED': 'SR_B4', 'NIR': 'SR_B5', 'SWIR1': 'SR_B6', 'SWIR2': 'SR_B7'},
    'LANDSAT/LC09/C02/T1_L2': {'BLUE': 'SR_B2', 'GREEN': 'SR_B3', 'RED': 'SR_B4', 'NIR': 'SR_B5', 'SWIR1': 'SR_B6', 'SWIR2': 'SR_B7'}
}

PALETTES = {
    'NDVI': ['#d7191c', '#fdae61', '#ffffbf', '#a6d96a', '#1a9641'],
    'SAVI': ['#8c510a', '#d8b365', '#f6e8c3', '#c7eae5', '#5ab4ac', '#01665e'], # Coklat ke Hijau
    'NDWI': ['#d73027', '#f46d43', '#fdae61', '#fee090', '#e0f3f8', '#abd9e9', '#74add1', '#4575b4'],
    'NDBI': ['#2c7bb6', '#abd9e9', '#ffffbf', '#fdae61', '#d7191c'],
    'ELEVATION': ['#006600', '#002200', '#fff700', '#ab7634', '#c4d0ff', '#ffffff'],
    'SLOPE': ['#2b83ba', '#abdda4', '#ffffbf', '#fdae61', '#d7191c']
}

# ==========================================
# 2. PRAPEMROSESAN (PRE-PROCESSING)
# ==========================================

def apply_scale_factors(image, satellite_id):
    """
    Menerapkan faktor skala (scaling factor) optik agar nilai pantulan (reflectance) 
    berada pada rentang 0 - 1. Sangat penting untuk akurasi Landsat Collection 2.
    """
    if 'LANDSAT' in satellite_id:
        optical_bands = image.select('SR_B.').multiply(0.0000275).add(-0.2)
        thermal_bands = image.select('ST_B.*').multiply(0.00341802).add(149.0)
        return image.addBands(optical_bands, None, True).addBands(thermal_bands, None, True)
    elif 'S2' in satellite_id:
        # Sentinel-2 Harmonized (membagi nilai dengan 10000)
        optical = image.select('B.*').divide(10000)
        return image.addBands(optical, None, True)
    return image

def mask_clouds(image, satellite_id):
    """
    Melakukan masking awan dan bayangan awan berdasarkan band QA.
    """
    if 'S2' in satellite_id:
        qa = image.select('QA60')
        cloudBitMask = 1 << 10
        cirrusBitMask = 1 << 11
        mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(qa.bitwiseAnd(cirrusBitMask).eq(0))
        return image.updateMask(mask)
    else:
        qa = image.select('QA_PIXEL')
        cloudShadowBitMask = 1 << 4
        cloudsBitMask = 1 << 3
        mask = qa.bitwiseAnd(cloudShadowBitMask).eq(0).And(qa.bitwiseAnd(cloudsBitMask).eq(0))
        return image.updateMask(mask)

def mask_water(image, satellite_id):
    """
    Melakukan masking pada area perairan menggunakan NDWI.
    Berguna jika analisis hanya difokuskan pada daratan/tanah.
    """
    bands = SATELLITE_BANDS[satellite_id]
    ndwi = image.normalizedDifference([bands['GREEN'], bands['NIR']])
    water_mask = ndwi.lt(0.1) # Asumsi nilai < 0.1 bukan air
    return image.updateMask(water_mask)

# ==========================================
# 3. INDEKS SPEKTRAL & KEBUMIAN
# ==========================================

def calculate_indices(image, index_type, satellite_id):
    """
    Menghitung berbagai indeks spektral berdasarkan satelit yang dipilih.
    """
    bands = SATELLITE_BANDS.get(satellite_id)
    if not bands:
        raise ValueError("Satelit tidak didukung untuk kalkulasi indeks.")

    # 1. NDVI (Kerapatan Vegetasi)
    if index_type == 'NDVI':
        return image.normalizedDifference([bands['NIR'], bands['RED']]).rename('NDVI')
    
    # 2. NDWI (Indeks Kelembapan Air)
    elif index_type == 'NDWI':
        return image.normalizedDifference([bands['GREEN'], bands['NIR']]).rename('NDWI')
    
    # 3. NDBI (Kawasan Bangun / Lahan Terbuka)
    elif index_type == 'NDBI':
        return image.normalizedDifference([bands['SWIR1'], bands['NIR']]).rename('NDBI')
    
    # 4. EVI (Enhanced Vegetation Index)
    elif index_type == 'EVI':
        evi = image.expression(
            '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
                'NIR': image.select(bands['NIR']),
                'RED': image.select(bands['RED']),
                'BLUE': image.select(bands['BLUE'])
            }
        ).rename('EVI')
        return evi

    # 5. SAVI (Soil Adjusted Vegetation Index)
    elif index_type == 'SAVI':
        savi = image.expression(
            '((NIR - RED) / (NIR + RED + L)) * (1 + L)', {
                'NIR': image.select(bands['NIR']),
                'RED': image.select(bands['RED']),
                'L': 0.5 
            }
        ).rename('SAVI')
        return savi

    return image # Fallback

# ==========================================
# 4. ANALISIS TOPOGRAFI & HIDROLOGI
# ==========================================

def get_terrain_data(aoi, terrain_type='ELEVATION'):
    """
    Mengambil data Digital Elevation Model (DEM) dari NASADEM.
    """
    dataset = ee.Image('NASA/NASADEM_HGT/001').select('elevation').clip(aoi)
    
    if terrain_type == 'ELEVATION':
        return dataset.rename('Elevation')
    elif terrain_type == 'SLOPE':
        slope = ee.Terrain.slope(dataset)
        return slope.rename('Slope')
    elif terrain_type == 'HILLSHADE':
        hillshade = ee.Terrain.hillshade(dataset)
        return hillshade.rename('Hillshade')
        
    return dataset

# ==========================================
# 5. KLASIFIKASI MACHINE LEARNING (LULC)
# ==========================================

def classify_land_use(image, training_data, class_property='landcover'):
    """
    Menerapkan model Random Forest untuk klasifikasi tutupan lahan.
    """
    bands = image.bandNames()
    
    training = image.select(bands).sampleRegions(
        collection=training_data,
        properties=[class_property],
        scale=30 
    )
    
    classifier = ee.Classifier.smileRandomForest(50).train(
        features=training,
        classProperty=class_property,
        inputProperties=bands
    )
    
    classified_image = image.classify(classifier)
    return classified_image

# ==========================================
# 6. FUNGSI UTAMA (MAIN GENERATOR)
# ==========================================

def process_satellite_data(params):
    """
    Fungsi orkestrasi yang dipanggil oleh app.py untuk menghasilkan URL Map ID.
    """
    try:
        # 0. Ambil Parameter dari Frontend
        aoi_coords = params.get('aoi')
        if not aoi_coords:
            raise ValueError("Koordinat Area of Interest (AOI) tidak ditemukan.")
            
        aoi = ee.Geometry.Polygon(aoi_coords)
        satellite_id = params.get('satellite', 'COPERNICUS/S2_SR_HARMONIZED')
        start_date = params.get('startDate', '2023-01-01')
        end_date = params.get('endDate', '2023-12-31')
        cloud_cover = int(params.get('cloudCover', 15))
        index_type = params.get('indexType', 'NDVI')
        apply_cloud = params.get('cloudMask', True)
        apply_water_mask = params.get('waterMask', False)

        # 1. Filter Koleksi
        cloud_prop = 'CLOUDY_PIXEL_PERCENTAGE' if 'S2' in satellite_id else 'CLOUD_COVER'
        collection = ee.ImageCollection(satellite_id) \
            .filterBounds(aoi) \
            .filterDate(start_date, end_date) \
            .filter(ee.Filter.lt(cloud_prop, cloud_cover))
            
        # Peringatan: getInfo() bisa memperlambat proses, tapi aman untuk aplikasi skala kecil
        if collection.size().getInfo() == 0:
            raise ValueError("Tidak ada citra satelit yang memenuhi kriteria (coba perlebar tanggal atau batas awan).")

        # 2. Prapemrosesan & Komposit
        if apply_cloud:
            collection = collection.map(lambda img: mask_clouds(img, satellite_id))
            
        collection = collection.map(lambda img: apply_scale_factors(img, satellite_id))
        composite = collection.median().clip(aoi)

        # 3. Masking Air (Opsional)
        if apply_water_mask:
            composite = mask_water(composite, satellite_id)

        # 4. Kalkulasi Indeks
        if index_type == 'TRUE_COLOR':
            bands = SATELLITE_BANDS[satellite_id]
            vis_params = {'bands': [bands['RED'], bands['GREEN'], bands['BLUE']], 'min': 0.0, 'max': 0.3}
            final_image = composite
        else:
            final_image = calculate_indices(composite, index_type, satellite_id)
            vis_params = {
                'min': -1.0 if index_type not in ['EVI', 'SAVI'] else -0.5,
                'max': 1.0,
                'palette': PALETTES.get(index_type, PALETTES['NDVI'])
            }

        # 5. Dapatkan Map ID & URL untuk Leaflet
        map_id = final_image.getMapId(vis_params)
        
        return {
            "status": "success",
            "tile_url": map_id['tile_fetcher'].url_format
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }