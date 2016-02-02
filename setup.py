"""
WKB-Raster

Read WKB rasters to Numpy arrays.

.. code:: python

    from wkb_raster import read_wkb_raster

    raster = read_wkb_raster(binary)
    raster['bands'][0]

Usage with PostGIS Rasters. Use `ST_AsBinary
<http://postgis.net/docs/manual-dev/RT_ST_AsBinary.html>`_
to return the WKB representation of the raster.

.. code:: sql
    SELECT ST_AsBinary(rast) FROM rasters;

Wrap the returned buffer in `cStringIO.StringIO` to
pass it to `read_wkb_raster`.

Links
`````

* `Raster WKB RFC
  <http://trac.osgeo.org/postgis/browser/trunk/raster/doc/RFC2-WellKnownBinaryFormat>`_
* `GitHub <https://github.com/nathancahill/wkb-raster>`_

"""
from setuptools import setup

setup(
    name='WKB-Raster',
    version='0.2',
    url='https://github.com/nathancahill/wkb-raster',
    license='MIT',
    author='Nathan Cahill',
    author_email='nathan@nathancahill.com',
    description='Read WKB rasters to Numpy arrays.',
    long_description=__doc__,
    py_modules=['wkb_raster'],
    install_requires=['numpy']
)
