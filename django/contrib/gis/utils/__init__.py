"""
 This module contains useful utilities for GeoDjango.
"""
# Importing the utilities that depend on GDAL, if available.
from django.contrib.gis.gdal import HAS_GDAL
if HAS_GDAL:
    from django.contrib.gis.utils.ogrinfo import ogrinfo, sample
    from django.contrib.gis.utils.ogrinspect import mapping, ogrinspect
    try:
        # LayerMapping requires DJANGO_SETTINGS_MODULE to be set, 
        # so this needs to be in try/except.
        from django.contrib.gis.utils.layermapping import LayerMapping
    except:
        pass
    
# Attempting to import the GeoIP class.
try:
    from django.contrib.gis.utils.geoip import GeoIP, GeoIPException
    HAS_GEOIP = True
except:
    HAS_GEOIP = False
