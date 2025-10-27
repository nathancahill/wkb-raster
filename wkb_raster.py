import binascii
from io import BytesIO
from struct import pack, unpack
from sys import byteorder

import numpy as np
from rasterio.transform import Affine

__all__ = [
    'read_wkb_raster',
    'dataset_to_wkb',
    'wkb_to_hexstring_raster',
    'numpy_to_wkb',
    'numpy_to_wkb_hexstring',
    'extract_numpy'
]


def wkb_hexstring_to_wkb(hexstring):
    return bytes.fromhex(hexstring)

def wkb_to_hexstring_raster(wkb: bytes) -> str:
    """Converts a WKB (Well-Known Binary) byte object to a hexadecimal string.

    Args:
        wkb: The WKB byte object to convert.

    Returns:
        A string containing the hexadecimal representation of the WKB.
    """
    hex_bytes = binascii.hexlify(wkb)
    hex_string = hex_bytes.decode("ascii")
    return hex_string


def read_wkb_raster(wkb: BytesIO) -> dict:
    """Read a WKB raster to a Numpy array.

    The WKB must be of Type BytesIO:
    Example:
       with io.BytesIO(wkb) as wkb_bytes_io:
            read_wkb_raster(wkb_bytes_io)


    Based off of the RFC here:
        http://trac.osgeo.org/postgis/browser/trunk/raster/doc/RFC2-WellKnownBinaryFormat


    Object is returned in this format:
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

    :wkb file-like object: Binary raster in WKB format
    :returns: obj
    """
    ret = {}

    # Determine the endiannes of the raster
    #
    # +---------------+-------------+------------------------------+
    # | endiannes     | byte        | 1:ndr/little endian          |
    # |               |             | 0:xdr/big endian             |
    # +---------------+-------------+------------------------------+
    (endian,) = unpack('<b', wkb.read(1))

    if endian == 0:
        endian = '>'
    elif endian == 1:
        endian = '<'

    # Read the raster header data.
    #
    # +---------------+-------------+------------------------------+
    # | version       | uint16      | format version (0 for this   |
    # |               |             | structure)                   |
    # +---------------+-------------+------------------------------+
    # | nBands        | uint16      | Number of bands              |
    # +---------------+-------------+------------------------------+
    # | scaleX        | float64     | pixel width                  |
    # |               |             | in geographical units        |
    # +---------------+-------------+------------------------------+
    # | scaleY        | float64     | pixel height                 |
    # |               |             | in geographical units        |
    # +---------------+-------------+------------------------------+
    # | ipX           | float64     | X ordinate of upper-left     |
    # |               |             | pixel's upper-left corner    |
    # |               |             | in geographical units        |
    # +---------------+-------------+------------------------------+
    # | ipY           | float64     | Y ordinate of upper-left     |
    # |               |             | pixel's upper-left corner    |
    # |               |             | in geographical units        |
    # +---------------+-------------+------------------------------+
    # | skewX         | float64     | rotation about Y-axis        |
    # +---------------+-------------+------------------------------+
    # | skewY         | float64     | rotation about X-axis        |
    # +---------------+-------------+------------------------------+
    # | srid          | int32       | Spatial reference id         |
    # +---------------+-------------+------------------------------+
    # | width         | uint16      | number of pixel columns      |
    # +---------------+-------------+------------------------------+
    # | height        | uint16      | number of pixel rows         |
    # +---------------+-------------+------------------------------+
    (version, bands, scale_x, scale_y, ip_x, ip_y, skew_x, skew_y, srid, width, height) \
        = unpack(endian + 'HHddddddIHH', wkb.read(60))

    ret['version'] = version
    ret['scaleX'] = scale_x
    ret['scaleY'] = scale_y
    ret['ipX'] = ip_x
    ret['ipY'] = ip_y
    ret['skewX'] = skew_x
    ret['skewY'] = skew_y

    ret['transform'] = TransformToolbox.from_transform_parameters(scale_x=scale_x, skew_x=skew_x, east_upperleft=ip_x,
                                                                  skew_y=skew_y, scale_y=scale_y, north_upperleft=ip_y)

    ret['srid'] = srid
    ret['width'] = width
    ret['height'] = height
    ret['bands'] = []

    for _ in range(bands):
        band = {}

        # Read band header data
        #
        # +---------------+--------------+-----------------------------------+
        # | isOffline     | 1bit         | If true, data is to be found      |
        # |               |              | on the filesystem, trought the    |
        # |               |              | path specified in RASTERDATA      |
        # +---------------+--------------+-----------------------------------+
        # | hasNodataValue| 1bit         | If true, stored nodata value is   |
        # |               |              | a true nodata value. Otherwise    |
        # |               |              | the value stored as a nodata      |
        # |               |              | value should be ignored.          |
        # +---------------+--------------+-----------------------------------+
        # | isNodataValue | 1bit         | If true, all the values of the    |
        # |               |              | band are expected to be nodata    |
        # |               |              | values. This is a dirty flag.     |
        # |               |              | To set the flag to its real value |
        # |               |              | the function st_bandisnodata must |
        # |               |              | must be called for the band with  |
        # |               |              | 'TRUE' as last argument.          |
        # +---------------+--------------+-----------------------------------+
        # | reserved      | 1bit         | unused in this version            |
        # +---------------+--------------+-----------------------------------+
        # | pixtype       | 4bits        | 0: 1-bit boolean                  |
        # |               |              | 1: 2-bit unsigned integer         |
        # |               |              | 2: 4-bit unsigned integer         |
        # |               |              | 3: 8-bit signed integer           |
        # |               |              | 4: 8-bit unsigned integer         |
        # |               |              | 5: 16-bit signed integer          |
        # |               |              | 6: 16-bit unsigned signed integer |
        # |               |              | 7: 32-bit signed integer          |
        # |               |              | 8: 32-bit unsigned signed integer |
        # |               |              | 9: 32-bit float                   |
        # |               |              | 10: 64-bit float                  |
        # +---------------+--------------+-----------------------------------+
        #
        # Requires reading a single byte, and splitting the bits into the
        # header attributes
        (bits,) = unpack(endian + 'b', wkb.read(1))

        band['isOffline'] = bool(bits & 128)  # first bit
        band['hasNodataValue'] = bool(bits & 64)  # second bit
        band['isNodataValue'] = bool(bits & 32)  # third bit

        pixtype = bits & 15  # bits 5-8

        # print("pixtype = {0}".format(pixtype))

        # Based on the pixel type, determine the struct format, byte size and
        # numpy dtype
        fmts = ['?', 'B', 'B', 'b', 'B', 'h',
                'H', 'i', 'I', 'f', 'd', 'd']
        dtypes = ['b1', 'u1', 'u1', 'i1', 'u1', 'i2',
                  'u2', 'i4', 'u4', 'f4', 'f8', 'f8']
        sizes = [1, 1, 1, 1, 1, 2, 2, 4, 4, 4, 8, 8]

        dtype = dtypes[pixtype]
        size = sizes[pixtype]
        fmt = fmts[pixtype]

        # Read the nodata value
        (nodata,) = unpack(endian + fmt, wkb.read(size))

        band['nodata'] = nodata

        if band['isOffline']:

            # Read the out-db metadata
            #
            # +-------------+-------------+-----------------------------------+
            # | bandNumber  | uint8       | 0-based band number to use from   |
            # |             |             | the set available in the external |
            # |             |             | file                              |
            # +-------------+-------------+-----------------------------------+
            # | path        | string      | null-terminated path to data file |
            # +-------------+-------------+-----------------------------------+

            # offline bands are 0-based, make 1-based for user consumption
            (band_num,) = unpack(endian + 'B', wkb.read(1))
            band['bandNumber'] = band_num + 1

            data = b''
            while True:
                byte = wkb.read(1)
                if byte == b'\x00':
                    break

                data += byte

            band['path'] = data.decode()

        else:

            # Read the pixel values: width * height * size
            #
            # +------------+--------------+-----------------------------------+
            # | pix[w*h]   | 1 to 8 bytes | Pixels values, row after row,     |
            # |            | depending on | so pix[0] is upper-left, pix[w-1] |
            # |            | pixtype [1]  | is upper-right.                   |
            # |            |              |                                   |
            # |            |              | As for endiannes, it is specified |
            # |            |              | at the start of WKB, and implicit |
            # |            |              | up to 8bits (bit-order is most    |
            # |            |              | significant first)                |
            # |            |              |                                   |
            # +------------+--------------+-----------------------------------+
            band['ndarray'] = np.ndarray(
                shape=(height, width),
                buffer=wkb.read(width * height * size),
                dtype=np.dtype(dtype)
            )

        ret['bands'].append(band)

    return ret

def extract_transform(wkb_raster_dict: dict) -> Affine:
    return wkb_raster_dict["transform"]

def extract_numpy(wkb_raster_dict: dict, channel_at_last_axis: bool = False) -> np.ndarray:
    """
    extrct rasterdaten as Numpy-Array from the result of   read_wkb_raster()

    Parameter:
      channel_at_last_axis:  Default: False ;
                False: (channel, row, col);
                True:  (row, col, channel)
    """
    bands = wkb_raster_dict["bands"]
    num_channels = len(bands)
    band_array = []
    for i in range(num_channels):
        band_array.append(bands[i]['ndarray'])

    if channel_at_last_axis:
        image_np = np.stack(arrays=band_array, axis=2)
    else:
        image_np = np.stack(arrays=band_array)
    return image_np

def dataset_to_wkb(dataset):
    _write_wkb_raster(dataset)

def _write_wkb_raster(dataset):
    """Creates a WKB raster from the given raster file with rasterio.

    :dataset: Rasterio dataset
    :returns: binary: Binary raster in WKB format
    """

    # see also https://docs.python.org/3/library/struct.html
    format_string = "bHHddddddIHH"

    # Determine the endiannes of the machine
    #
    # +---------------+-------------+------------------------------+
    # | endiannes     | byte        | 1:ndr/little endian          |
    # |               |             | 0:xdr/big endian             |
    # +---------------+-------------+------------------------------+
    endian: str = ''
    endian_byte: int = -1

    if byteorder == "big":
        endian = '>'
        endian_byte = 0
    elif byteorder == "little":
        endian = '<'
        endian_byte = 1

    # Write the raster header data.
    #
    # +---------------+-------------+------------------------------+
    # | version       | uint16      | format version (0 for this   |
    # |               |             | structure)                   |
    # +---------------+-------------+------------------------------+
    # | nBands        | uint16      | Number of bands              |
    # +---------------+-------------+------------------------------+
    # | scaleX        | float64     | pixel width                  |
    # |               |             | in geographical units        |
    # +---------------+-------------+------------------------------+
    # | scaleY        | float64     | pixel height                 |
    # |               |             | in geographical units        |
    # +---------------+-------------+------------------------------+
    # | ipX           | float64     | X ordinate of upper-left     |
    # |               |             | pixel's upper-left corner    |
    # |               |             | in geographical units        |
    # +---------------+-------------+------------------------------+
    # | ipY           | float64     | Y ordinate of upper-left     |
    # |               |             | pixel's upper-left corner    |
    # |               |             | in geographical units        |
    # +---------------+-------------+------------------------------+
    # | skewX         | float64     | rotation about Y-axis        |
    # +---------------+-------------+------------------------------+
    # | skewY         | float64     | rotation about X-axis        |
    # +---------------+-------------+------------------------------+
    # | srid          | int32       | Spatial reference id         |
    # +---------------+-------------+------------------------------+
    # | width         | uint16      | number of pixel columns      |
    # +---------------+-------------+------------------------------+
    # | height        | uint16      | number of pixel rows         |
    # +---------------+-------------+------------------------------+

    header = bytes()

    transform = dataset.transform.to_gdal()

    version = 0
    n_bands = int(dataset.count)
    scale_x = transform[1]
    scale_y = transform[5]
    ip_x = transform[0]
    ip_y = transform[3]
    skew_x = 0
    skew_y = 0
    srid = int(dataset.crs.to_string().split("EPSG:")[1])
    width = int(dataset.meta.get("width"))
    height = int(dataset.meta.get("height"))

    fmt = f"{endian}{format_string}"

    header = pack(fmt, endian_byte, version, n_bands, scale_x, scale_y, ip_x, ip_y, skew_x, skew_y, srid, width, height)

    bands = []

    for i in range(1, n_bands + 1):
        band_array = dataset.read(i)

        # Write band header data
        #
        # +---------------+--------------+-----------------------------------+
        # | isOffline     | 1bit         | If true, data is to be found      |
        # |               |              | on the filesystem, trought the    |
        # |               |              | path specified in RASTERDATA      |
        # +---------------+--------------+-----------------------------------+
        # | hasNodataValue| 1bit         | If true, stored nodata value is   |
        # |               |              | a true nodata value. Otherwise    |
        # |               |              | the value stored as a nodata      |
        # |               |              | value should be ignored.          |
        # +---------------+--------------+-----------------------------------+
        # | isNodataValue | 1bit         | If true, all the values of the    |
        # |               |              | band are expected to be nodata    |
        # |               |              | values. This is a dirty flag.     |
        # |               |              | To set the flag to its real value |
        # |               |              | the function st_bandisnodata must |
        # |               |              | must be called for the band with  |
        # |               |              | 'TRUE' as last argument.          |
        # +---------------+--------------+-----------------------------------+
        # | reserved      | 1bit         | unused in this version            |
        # +---------------+--------------+-----------------------------------+
        # | pixtype       | 4bits        | 0: 1-bit boolean                  |
        # |               |              | 1: 2-bit unsigned integer         |
        # |               |              | 2: 4-bit unsigned integer         |
        # |               |              | 3: 8-bit signed integer           |
        # |               |              | 4: 8-bit unsigned integer         |
        # |               |              | 5: 16-bit signed integer          |
        # |               |              | 6: 16-bit unsigned signed integer |
        # |               |              | 7: 32-bit signed integer          |
        # |               |              | 8: 32-bit unsigned signed integer |
        # |               |              | 9: 32-bit float                   |
        # |               |              | 10: 64-bit float                  |
        # +---------------+--------------+-----------------------------------+

        # not used - always False
        is_offline = False
        has_nodata_value = False

        if "nodata" in dataset.meta:
            has_nodata_value = True

        # not used - always False
        is_nodata_value = False

        # unset
        reserved = False

        # # Based on the pixel type, determine the struct format, byte size and
        # # numpy dtype
        fmts = ['?', 'B', 'B', 'b', 'B', 'h',
                'H', 'i', 'I', 'f', 'd']
        dtypes = ['b1', 'u1', 'u1', 'i1', 'u1', 'i2',
                  'u2', 'i4', 'u4', 'f4', 'f8']

        rasterio_dtype = dataset.meta.get("dtype")
        dt_short = np.dtype(rasterio_dtype).descr[0][1][1:]
        pixtype = dtypes.index(dt_short)

        fmt = fmts[pixtype]

        # format binary -> :b
        binary_str = f"{is_offline:b}{has_nodata_value:b}{is_nodata_value:b}{reserved:b}{pixtype:b}"
        # convert to int
        binary_decimal = int(binary_str, 2)

        # pack to 1 byte
        # 4 bits for ifOffline, hasNodataValue, isNodataValue, reserved
        # 4 bit for pixtype
        # -> 8 bit = 1 byte
        band_header = pack("<b", binary_decimal)

        # +---------------+--------------+-----------------------------------+
        # | nodata        | 1 to 8 bytes | Nodata value                      |
        # |               | depending on |                                   |
        # |               | pixtype [1]  |                                   |
        # +---------------+--------------+-----------------------------------+

        # Write the nodata value
        nodata = pack(fmt, int(dataset.meta.get("nodata")))

        # # Write the pixel values: width * height * size
        # #
        # # +------------+--------------+-----------------------------------+
        # # | pix[w*h]   | 1 to 8 bytes | Pixels values, row after row,     |
        # # |            | depending on | so pix[0] is upper-left, pix[w-1] |
        # # |            | pixtype [1]  | is upper-right.                   |
        # # |            |              |                                   |
        # # |            |              | As for endiannes, it is specified |
        # # |            |              | at the start of WKB, and implicit |
        # # |            |              | up to 8bits (bit-order is most    |
        # # |            |              | significant first)                |
        # # |            |              |                                   |
        # # +------------+--------------+-----------------------------------+

        # numpy tobytes() method instead of packing with struct.pack()
        band_binary = band_array.reshape(width * height).tobytes()

        bands.append(band_header + nodata + band_binary)

    # join all bands
    allbands = bytes()
    for b in bands:
        allbands += b

    wkb = header + allbands

    return wkb

def numpy_to_wkb_hexstring(np_rast: np.ndarray, transform: Affine, srid: int = 25832, nodata_val: int = None):
    wkb = numpy_to_wkb(np_rast, transform, srid, nodata_val)
    wkb_hexstring = wkb_to_hexstring_raster(wkb)
    return wkb_hexstring

def numpy_to_wkb(np_rast: np.ndarray, transform: Affine, srid: int = 25832, nodata_val: int = None):
    """
    converts a Numpy-Array in  WKB-Raster .

    Parameter:
      np_rast:  Numpy-Array  (bands, rows, cols)
      transform:  Affine-Object
      srid:   SRID des EPSG-Codes,  z.B. 25832   für "ETRS89 / UTM zone 32N"
      nodata_val:   Wert des NoData-Values soweit vorhanden.


    Erweiterung durch   Manfred Zerndl  ( manfred.zerndl@ldbv.bayern.de )
    Januar 2025

    Based off of the RFC here:

        http://trac.osgeo.org/postgis/browser/trunk/raster/doc/RFC2-WellKnownBinaryFormat

    """
    # see also https://docs.python.org/3/library/struct.html
    format_string = "bHHddddddIHH"

    # Determine the endiannes of the machine
    #
    # +---------------+-------------+------------------------------+
    # | endiannes     | byte        | 1:ndr/little endian          |
    # |               |             | 0:xdr/big endian             |
    # +---------------+-------------+------------------------------+
    endian: str = ''
    endian_byte: int = -1

    if byteorder == "big":
        endian = '>'
        endian_byte = 0
    elif byteorder == "little":
        endian = '<'
        endian_byte = 1

    # Write the raster header data.
    #
    # +---------------+-------------+------------------------------+
    # | version       | uint16      | format version (0 for this   |
    # |               |             | structure)                   |
    # +---------------+-------------+------------------------------+
    # | nBands        | uint16      | Number of bands              |
    # +---------------+-------------+------------------------------+
    # | scaleX        | float64     | pixel width                  |
    # |               |             | in geographical units        |
    # +---------------+-------------+------------------------------+
    # | scaleY        | float64     | pixel height                 |
    # |               |             | in geographical units        |
    # +---------------+-------------+------------------------------+
    # | ipX           | float64     | X ordinate of upper-left     |
    # |               |             | pixel's upper-left corner    |
    # |               |             | in geographical units        |
    # +---------------+-------------+------------------------------+
    # | ipY           | float64     | Y ordinate of upper-left     |
    # |               |             | pixel's upper-left corner    |
    # |               |             | in geographical units        |
    # +---------------+-------------+------------------------------+
    # | skewX         | float64     | rotation about Y-axis        |
    # +---------------+-------------+------------------------------+
    # | skewY         | float64     | rotation about X-axis        |
    # +---------------+-------------+------------------------------+
    # | srid          | int32       | Spatial reference id         |
    # +---------------+-------------+------------------------------+
    # | width         | uint16      | number of pixel columns      |
    # +---------------+-------------+------------------------------+
    # | height        | uint16      | number of pixel rows         |
    # +---------------+-------------+------------------------------+
    if len(np_rast.shape) == 3:
        n_bands, height, width = np_rast.shape
    elif len(np_rast.shape) == 2:
        height, width = np_rast.shape
        n_bands = 1
    else:
        raise Exception(f"Numpy-Array not valid (shape: {np_rast.shape})!")

    trafo_gdal = transform.to_gdal()

    version = 0

    scale_x = trafo_gdal[1]
    scale_y = trafo_gdal[5]
    ip_x = trafo_gdal[0]
    ip_y = trafo_gdal[3]
    skew_x = trafo_gdal[2]
    skew_y = trafo_gdal[4]

    fmt = f"{endian}{format_string}"

    header = pack(fmt, endian_byte, version, n_bands, scale_x, scale_y, ip_x, ip_y, skew_x, skew_y, srid, width, height)

    bands = []

    for i in range(n_bands):
        if n_bands == 1:
            band_array = np_rast[:, :]
        else:
            band_array = np_rast[i, :, :]

        # Write band header data
        #
        # +---------------+--------------+-----------------------------------+
        # | isOffline     | 1bit         | If true, data is to be found      |
        # |               |              | on the filesystem, trought the    |
        # |               |              | path specified in RASTERDATA      |
        # +---------------+--------------+-----------------------------------+
        # | hasNodataValue| 1bit         | If true, stored nodata value is   |
        # |               |              | a true nodata value. Otherwise    |
        # |               |              | the value stored as a nodata      |
        # |               |              | value should be ignored.          |
        # +---------------+--------------+-----------------------------------+
        # | isNodataValue | 1bit         | If true, all the values of the    |
        # |               |              | band are expected to be nodata    |
        # |               |              | values. This is a dirty flag.     |
        # |               |              | To set the flag to its real value |
        # |               |              | the function st_bandisnodata must |
        # |               |              | must be called for the band with  |
        # |               |              | 'TRUE' as last argument.          |
        # +---------------+--------------+-----------------------------------+
        # | reserved      | 1bit         | unused in this version            |
        # +---------------+--------------+-----------------------------------+
        # | pixtype       | 4bits        | 0: 1-bit boolean                  |
        # |               |              | 1: 2-bit unsigned integer         |
        # |               |              | 2: 4-bit unsigned integer         |
        # |               |              | 3: 8-bit signed integer           |
        # |               |              | 4: 8-bit unsigned integer         |
        # |               |              | 5: 16-bit signed integer          |
        # |               |              | 6: 16-bit unsigned signed integer |
        # |               |              | 7: 32-bit signed integer          |
        # |               |              | 8: 32-bit unsigned signed integer |
        # |               |              | 9: 32-bit float                   |
        # |               |              | 10: 64-bit float                  |
        # +---------------+--------------+-----------------------------------+

        # not used - always False
        is_offline = False
        has_nodata_value = False

        if nodata_val is not None:
            has_nodata_value = True

        # not used - always False
        is_nodata_value = False

        # unset
        reserved = False

        # # Based on the pixel type, determine the struct format, byte size and
        # # numpy dtype
        #          0      1     2     3     4     5     6     7     8     9    10
        fmts   = ['?',   'B',  'B',  'b',  'B',  'h',  'H',  'i',  'I',  'f',  'd']
        dtypes = ['b1', 'u1', 'u1', 'i1', 'u1', 'i2', 'u2', 'i4', 'u4', 'f4', 'f8']

        rasterio_dtype = np_rast.dtype
        dt_short = np.dtype(rasterio_dtype).descr[0][1][1:]
        if dt_short == 'u1':
            max_val = np.max(band_array)
            if max_val < 4:
                pixtype = 1   # uint2
            elif max_val < 16:
                pixtype = 2   # uint4
            else:
                pixtype = 4   # uint8
        else:
            pixtype = dtypes.index(dt_short)

        fmt = fmts[pixtype]

        # format binary -> :b
        # binary_str = f"{is_offline:b}{has_nodata_value:b}{is_nodata_value:b}{reserved:b}{pixtype:b}"

        binary_first_4_bits = f"{is_offline:b}{has_nodata_value:b}{is_nodata_value:b}{reserved:b}"

        binary_str = bin(pixtype)[2:]  # Entferne das '0b' am Anfang
        binary_pixval_str = binary_str.zfill(4)  # fülle 4 bits mit führenden 0 auf

        binary_str = binary_first_4_bits + binary_pixval_str

        # convert to int
        binary_decimal = int(binary_str, 2)

        # pack to 1 byte
        # 4 bits for ifOffline, hasNodataValue, isNodataValue, reserved
        # 4 bit for pixtype
        # -> 8 bit = 1 byte
        band_header = pack("<b", binary_decimal)

        # +---------------+--------------+-----------------------------------+
        # | nodata        | 1 to 8 bytes | Nodata value                      |
        # |               | depending on |                                   |
        # |               | pixtype [1]  |                                   |
        # +---------------+--------------+-----------------------------------+

        # Write the nodata value
        # nodata = pack(fmt, int(dataset.meta.get("nodata")))
        nodata = pack(fmt, int(0))
        if nodata_val is not None:
            nodata = pack(fmt, int(nodata_val))

        # # Write the pixel values: width * height * size
        # #
        # # +------------+--------------+-----------------------------------+
        # # | pix[w*h]   | 1 to 8 bytes | Pixels values, row after row,     |
        # # |            | depending on | so pix[0] is upper-left, pix[w-1] |
        # # |            | pixtype [1]  | is upper-right.                   |
        # # |            |              |                                   |
        # # |            |              | As for endiannes, it is specified |
        # # |            |              | at the start of WKB, and implicit |
        # # |            |              | up to 8bits (bit-order is most    |
        # # |            |              | significant first)                |
        # # |            |              |                                   |
        # # +------------+--------------+-----------------------------------+

        # numpy tobytes() method instead of packing with struct.pack()
        band_binary = band_array.reshape(width * height).tobytes()

        bands.append(band_header + nodata + band_binary)

    # join all bands
    allbands = bytes()
    for b in bands:
        allbands += b

    wkb = header + allbands
    return wkb
