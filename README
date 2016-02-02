## WKB Raster

Read WKB rasters to Numpy arrays.

```python
from wkb_raster import read_wkb_raster

raster = read_wkb_raster(buf)
raster['bands'][0]
```

Usage with PostGIS Rasters. Use [ST_AsBinary](http://postgis.net/docs/manual-dev/RT_ST_AsBinary.html)
to return the WKB representation of the raster.

```sql
SELECT ST_AsBinary(rast) FROM rasters;
```

The binary buffer can be passed directly to read_wkb_raster.
