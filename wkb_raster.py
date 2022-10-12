from struct import unpack, pack
import numpy as np
import rasterio as rio
from sys import byteorder

__all__ = [
    'read_wkb_raster',
    'write_wkb_raster'
]

def read_wkb_raster(wkb):
    """Read a WKB raster to a Numpy array.

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
    (version, bands, scaleX, scaleY, ipX, ipY, skewX, skewY,
     srid, width, height) = unpack(endian + 'HHddddddIHH', wkb.read(60))

    ret['version'] = version
    ret['scaleX'] = scaleX
    ret['scaleY'] = scaleY
    ret['ipX'] = ipX
    ret['ipY'] = ipY
    ret['skewX'] = skewX
    ret['skewY'] = skewY
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

        # Based on the pixel type, determine the struct format, byte size and
        # numpy dtype
        fmts = ['?', 'B', 'B', 'b', 'B', 'h',
                'H', 'i', 'I', 'f', 'd']
        dtypes = ['b1', 'u1', 'u1', 'i1', 'u1', 'i2',
                  'u2', 'i4', 'u4', 'f4', 'f8']
        sizes = [1, 1, 1, 1, 1, 2, 2, 4, 4, 4, 8]

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
                (height, width),
                buffer=wkb.read(width * height * size),
                dtype=np.dtype(dtype)
            )

        ret['bands'].append(band)

    return ret


def write_wkb_raster(raster_file_path):
    """Creates a WKB raster from the given raster file with rasterio.

    :raster_file_path: String
    :returns: wkb: Binary raster in WKB format
    """

    # see also https://docs.python.org/3/library/struct.html
    format_string = "bHHddddddIHH"

    # Determine the endiannes of the machine
    #
    # +---------------+-------------+------------------------------+
    # | endiannes     | byte        | 1:ndr/little endian          |
    # |               |             | 0:xdr/big endian             |
    # +---------------+-------------+------------------------------+

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

    with rio.open(raster_file_path) as src:

        transform = src.transform.to_gdal()

        version = 0
        nBands = int(src.count)
        scaleX = transform[1]
        scaleY = transform[5]
        ipX = transform[0]
        ipY = transform[3]
        skewX = 0
        skewY = 0
        srid = int(src.crs.to_string().split("EPSG:")[1])
        width = int(src.meta.get("width"))
        height = int(src.meta.get("height"))

        fmt = f"{endian}{format_string}"

        header = pack(fmt, endian_byte, version, nBands, scaleX, scaleY, ipX, ipY, skewX, skewY, srid, width, height)

        bands = []

        for i in range(1, nBands + 1):
            band_array = src.read(i)

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
            isOffline = False
            hasNodataValue = False

            if "nodata" in src.meta:
                hasNodataValue = True

            # not used - always False
            isNodataValue = False

            # unset
            reserved = False

            # band['isOffline'] = bool(bits & 128)  # first bit
            # band['hasNodataValue'] = bool(bits & 64)  # second bit
            # band['isNodataValue'] = bool(bits & 32)  # third bit

            # pixtype = bits & 15  # bits 5-8

            # # Based on the pixel type, determine the struct format, byte size and
            # # numpy dtype
            fmts = ['?', 'B', 'B', 'b', 'B', 'h',
                    'H', 'i', 'I', 'f', 'd']
            dtypes = ['b1', 'u1', 'u1', 'i1', 'u1', 'i2',
                      'u2', 'i4', 'u4', 'f4', 'f8']

            rasterio_dtype = src.meta.get("dtype")
            dt_short = np.dtype(rasterio_dtype).descr[0][1][1:]
            pixtype = dtypes.index(dt_short)

            fmt = fmts[pixtype]

            # format binary -> :b
            binary_str = f"{ifOffline:b}{hasNodataValue:b}{isNodataValue:b}{reserved:b}{pixtype:b}"
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
            nodata = pack(fmt, int(src.meta.get("nodata")))

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
