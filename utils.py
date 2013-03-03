"""
Some utilities that might come in handy when working with user-supplied
data and filesizes. Converts human readable <-> num_bytes.
"""

from math import log

def readable_to_bytes(readable):
    """ Convert from space-separated human-readable form to number of bytes.

    This function is binary unit aware, 2 kB != 2 KiB.

    >>>readable_to_bytes("14 GB")
    14000000000
    >>>readable_to_bytes("3 KiB")
    3072
    """

    val, unit = readable.split()
    multipliers = {
                   'kB': 10**3,
                   'MB': 10**6,
                   'GB': 10**9,
                   'TB': 10**12,
                   'KiB': 2**10,
                   'MiB': 2**20,
                   'GiB': 2**30,
                   'TiB': 2**40,
                   }
    multiplier = multipliers.get(unit, 1)
    return int(val)*multiplier

def bytes_to_readable(num_bytes, binary=True):
    """ Format a number of bytes to human readable form.

    The optional boolean argument binary select wheter to use binary form
    or not, that is binary=True gives 1 KiB, instead of 1 kB. Default is True.
    """
    base = 1024 if binary else 1000
    if binary:
        unit_list = zip(['bytes', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB'], [0, 0, 1, 2, 2, 2])
    else:
        unit_list = zip(['bytes', 'kB', 'MB', 'GB', 'TB', 'PB'], [0, 0, 1, 2, 2, 2])
    if num_bytes >= 1:
        exponent = min(int(log(num_bytes, base)), len(unit_list) - 1)
        quotient = float(num_bytes) / base**exponent
        unit, num_decimals = unit_list[exponent]
        format_string = '{:.%sf} {}' % (num_decimals)
        return format_string.format(quotient, unit)
    elif num_bytes == 0:
        return '0 bytes'
    else:
        return "-" + bytes_to_readable(-num_bytes)