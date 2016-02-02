"""
WKB-Raster

Read WKB rasters to Numpy arrays.

.. code:: python

    from wkb_raster import read_wkb_raster

    raster = read_wkb_raster(buf)
    raster['bands'][0]

Links
`````

* `raster wkb rfc
  <http://trac.osgeo.org/postgis/browser/trunk/raster/doc/RFC2-WellKnownBinaryFormat>`_
* `github <https://github.com/nathancahill/wkb-raster>`_

"""
from setuptools import setup

setup(
    name='WKB-Raster',
    version='0.1',
    url='https://github.com/nathancahill/wkb-raster',
    license='MIT',
    author='Nathan Cahill',
    author_email='nathan@nathancahill.com',
    description='Read WKB rasters to Numpy arrays.',
    long_description=__doc__,
    py_modules=['wkb_raster'],
    install_requires=['numpy']
)
