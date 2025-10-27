## WKB Raster

Read WKB rasters to Numpy arrays and convert any raster to WKB format.

### Docs

```python
wkb_raster.read_wkb_raster(wkb)
```

**Parameters**

- **wkb** - file-like object. Binary raster in WKB format.

**Returns**

    {
        'version': int,
        'scaleX': float,
        'scaleY': float,
        'ipX': float,
        'ipY': float,
        'skewX': float,
        'skewY': float,
        'srid': int,
        'width': int,
        'height': int,
        'bands': [{
            'nodata': bool|int|float,
            'isOffline': bool,
            'hasNodataValue': bool,
            'isNodataValue': bool,
            'ndarray': numpy.ndarray((width, height), bool|int|float)
        }, ...]
    }

**Usage**

## Reading WKB

With a binary WKB file:

```python
from wkb_raster import read_wkb_raster

with open('img.wkb') as f:
    raster = read_wkb_raster(f)
    raster['bands'][0]
```

With WKB from PostGIS Raster. Use [ST_AsBinary](http://postgis.net/docs/manual-dev/RT_ST_AsBinary.html)
to return the WKB representation of the raster.

```sql
SELECT ST_AsBinary(rast) FROM rasters;
```

Wrap the binary buffer in `cStringIO.StringIO`:

```python
from cStringIO import StringIO
from wkb_raster import read_wkb_raster

raster = read_wkb_raster(StringIO(buf))
raster['bands'][0]
```

## Writing WKB

Write rasterio rasters to binary WKB:

```python
import rasterio
from wkb_raster import write_wkb_raster

with rasterio.open('example.tif') as dataset:
    wkb = write_wkb_raster(dataset)
```

## Writing WKB from Numpy and Affine
Write a Numpy-Array to WKB-Raster
```python
import numpy as np
from affine import Affine
from wkb_raster import numpy_to_wkb

my_rasterdata: np.ndarray = .....

wkb = numpy_to_wkb(my_rasterdata, transform=tr)
```

## Converting wkb to wkb_hex
```python
from wkb_raster import wkb_to_hexstring_raster

wkb_hex = wkb_to_hexstring_raster(wkb)
```

### Links

- [Raster WKB RFC](http://trac.osgeo.org/postgis/browser/trunk/raster/doc/RFC2-WellKnownBinaryFormat)
