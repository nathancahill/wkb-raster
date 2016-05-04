"""
WKB-Raster
----------

Read WKB rasters to Numpy arrays.

Links
`````

* `Docs <https://github.com/nathancahill/wkb-raster>`_
* `Raster WKB RFC
  <http://trac.osgeo.org/postgis/browser/trunk/raster/doc/RFC2-WellKnownBinaryFormat>`_
* `GitHub <https://github.com/nathancahill/wkb-raster>`_

"""
from setuptools import setup

setup(
    name='WKB-Raster',
    version='0.6',
    url='https://github.com/nathancahill/wkb-raster',
    license='MIT',
    author='Nathan Cahill',
    author_email='nathan@nathancahill.com',
    description='Read WKB rasters to Numpy arrays.',
    long_description=__doc__,
    py_modules=['wkb_raster'],
    install_requires=['numpy']
)
