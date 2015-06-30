__author__ = 'william.george'
__version__ = '0.01'

# Standard Library
import time
from functools import partial

# Third Party
import prettytable

def mirror(x,y):
    return (x,y), (y,x)

BITS, BYTES = ('b', 1), ('B', 8)
units = dict(mirror(*BITS) + mirror(*BYTES))

DECIMAL, BINARY = ('dec', 10), ('bin', 2)
units.update(mirror(*DECIMAL) + mirror(*BINARY))


def human_readable(number, base, magnitude=99):
    """
    :param number: number to be formatted
    :param base: 2 for binary (k = 1024, etc), 10 for decimal (k = 1000, etc)
    :param magnitude: If specified, maximum magnitude of units to use
    :return: string expressing number in the given format, rounded to 2 decimal places.
    Formats number from raw value to human readable form using either decimal or binary units.
    Example:
        human_readable(1024, 2)
        '1K'
        human_readable(1024**2, 2)
        '1M'
        human_readable(1024**2, 2, 1)
        '1024K'
        human_readable(1024**2, 10, 1)
        '1048.58k'
    """
    assert magnitude >= 1, 'A magnitude less than one is meaningless.'
    kilo = {10: 1000., 2: 1024.}[base]
    suffix_list = {0: '', 1: 'K', 2: 'M', 3: 'G', 4:'T', 5:'P', 6:'E'}
    n = 0
    while (number > 1000) and (n < magnitude):
        number /= kilo
        n += 1

    suffix = suffix_list.get(n, '?')
    if base == 10:
        suffix = suffix.lower()

    rslt = '{0:.2f}{1}'.format(number, suffix)
    return rslt


def interpret_bytes(bytes_in, unit=''):
    bits_in = bytes_in * 8
    rslts = dict()
    rslts['b_unit'] = 'b' + unit
    rslts['B_unit'] = 'B' + unit
    rslts['bytes'] = bytes_in
    rslts['bits'] = bits_in
    rslts['bytes_hr_decimal'] = human_readable(bytes_in, 10)
    rslts['bytes_hr_bin'] = human_readable(bytes_in, 2)
    rslts['bits_hr_decimal'] = human_readable(bits_in, 10)
    rslts['bits_hr_bin'] = human_readable(bits_in, 2)

    return rslts


class TrafficStat(object):
    """
    Store and represent unidirectional traffic statistic in a number of useful ways.
    """
    def __init__(self, val, unit='b', base='bin', magnitude=10,
                 start_time=0, duration=0, end_time=0):
        """
        :param val: Raw value in 'units'
        :param unit: ('b' | 'B') for bits or bytes.
        :param base: ('bin' | 'dec') for binary or decimal
        :param magnitude: Maximum magnitude of units in human_readable format.
            e.x.: 1 will always express numbers in kilo-units, 2 always gives mega-units
        :param start_time: Instant of measurement for instantaneous measurements, start
            of period for measurements over time.
        :param duration: Duration of measurement over time.
        :param end_time: End of period of measurement over time, overrides duration.
        :return:
        """
        self.val = val
        self.unit = unit
        self.base = base
        self.magnitude = magnitude

        self.start_time = start_time

        if end_time > 0:
            duration = end_time - start_time

        self.duration = duration

    def to_bytes(self):
        """
        Convert object to bytes in place
        :return: None
        """
        if self.unit in BITS:
            self.val /= 8
            self.unit = 'B'

    def to_bits(self):
        """
        Convert object to bits in place
        :return: None
        """
        if self.unit in BYTES:
            self.val *= 8
            self.unit = 'b'

    @property
    def in_bits(self):
        """
        :return:  Returns object in bits.
        """
        if self.unit in BYTES:
            rslt = self.__class__(**self.__dict__)
            rslt.to_bits()
        else:
            rslt = self
        return rslt

    @property
    def in_bytes(self):
        """
        :return:  Returns object in bytes.
        """
        if self.unit in BITS:
            rslt = self.__class__(**self.__dict__)
            rslt.to_bytes()
        else:
            rslt = self
        return rslt

    @property
    def as_swapped(self):
        if self.unit in BITS:
            return self.in_bytes
        else:
            return self.in_bits

    @property
    def value_over_time(self):
        """
        Returns rate over time.
        :return: Rate in (bits | bytes) per second.
        """
        return self.val / self.duration

    @property
    def value_over_time_s(self):
        """
        Returns value_over_time as a string concatenated with ('bps' | 'Bps')
        """
        return ''.join((str(self.value_over_time), self.rate_ps))

    @property
    def hr_vot(self):  # HumanReadable_ValueOverTime
        ot = human_readable(self.value_over_time, units[self.base], self.magnitude)

        return ''.join((ot, self.rate_ps))

    @property
    def rate_ps(self):
        return ''.join((self.unit, 'ps'))

    @property
    def human_readable(self):
        return human_readable(self.val, units[self.base], self.magnitude)

    @property
    def hr(self):  # HumanReadable
        return self.human_readable

    def __add__(self, other):
        if self.unit != other.unit:
            other = other.as_swapped
        _dict = self.__dict__.copy()
        _dict.update({'val': self.val + other.val,
                      'duration': self.duration + other.duration})
        return self.__class__(**_dict)

    def __sub__(self, other):
        if self.unit != other.unit:
            other = other.as_swapped
        _dict = self.__dict__.copy()
        _dict.update({'val': self.val - other.val,
                      'duration': 0,
                      'start_time': other.start_time,
                      'end_time': self.start_time + self.duration})
        return self.__class__(**_dict)


class InterfaceStat(object):
    """
    Inbound and Outbound traffic stats for an interface.
    """
    def __init__(self, name, inbound, outbound, invert_wan_lan=False):
        """
        :param name: Interface name.
        :param inbound: TrafficStat object for traffic into interface.  Aliased to
            'site_in' by default.
        :param outbound: TrafficStat object for traffic from interface. Aliased to
            'site_out' by default.
        :param invert_wan_lan: Swap site_in/site_out aliases.  Use for Service Provider
            interfaces, etc.
        :return:
        """

        self.name = name
        self.inbound = inbound
        self.outbound = outbound
        self.invert_wan_lan = invert_wan_lan

    @classmethod
    def from_stats(cls, name, in_out_tuple, unit='b', invert_wan_lan=False,
                   start_time=0, duration=0):
        """
        Alternate constructor for InterfaceStat objects.
        :param name: Interface name
        :param in_out_tuple: tuple of form (input units, output units)
        :param unit: ('b' | 'B')
        :param invert_wan_lan: Swap site_in/site_out aliases.
        :param start_time: start_time to pass to TrafficStat objects
        :param duration: duration to pass to TrafficStat objects
        :return:
        """
        constructor = partial(TrafficStat,unit=unit, start_time=start_time, duration=duration)
        inbound, outbound = tuple(map(constructor, in_out_tuple))
        return cls(name=name, inbound=inbound, outbound=outbound,
                   invert_wan_lan=invert_wan_lan)


    @property
    def site_in(self):
        return self.outbound if self.invert_wan_lan else self.inbound

    @property
    def site_out(self):
        return self.inbound if self.invert_wan_lan else self.outbound

    @property
    def hri(self):  # HumanReadableInput
        """
        shortcut to self.***site_in***.human_readable
        :return: String:
        """
        return self.site_in.human_readable

    @property
    def hro(self):  # HumanReadableOutput
        """
        shortcut to self.***site_out***.human_readable
        :return: String:
        """
        return self.site_out.human_readable

    @property
    def hri_vot(self):  # HumanReadableInput_ValueOverTime
        """
        shortcut to self.***site_in***.hr_vot (HumanReadable_ValueOverTime)
        :return:
        """
        return self.site_in.hr_vot

    @property
    def hro_vot(self):  # HumanReadableOutput_ValueOverTime
        """
        shortcut to self.***site_out***.hr_vot (HumanReadable_ValueOverTime)
        :return:
        """
        return self.site_out.hr_vot

    def to_bits(self):
        self.inbound.to_bits()
        self.outbound.to_bits()

    def to_bytes(self):
        self.inbound.to_bytes()
        self.outbound.to_bytes()

    def match_other(self, other):
        match = all((self.name == other.name,
                     self.invert_wan_lan == other.invert_wan_lan))
        assert match, 'Names and invert settings must match to compare stats!'

    def __add__(self, other):
        self.match_other(other)
        inbound, outbound = self.inbound + other.inbound, self.outbound + other.outbound
        _dict = self.__dict__.copy()
        _dict.update({'inbound': inbound, 'outbound': outbound})
        # This could be better done with ChainMap I think.
        return self.__class__(**_dict)

    def __sub__(self, other):
        self.match_other(other)
        inbound, outbound = self.inbound - other.inbound, self.outbound - other.outbound
        _dict = self.__dict__.copy()
        _dict.update({'inbound': inbound, 'outbound': outbound})
        # This could be better done with ChainMap I think.
        return self.__class__(**_dict)