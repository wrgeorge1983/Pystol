__author__ = 'William.George'
__version__ = '0.05'

# Standard Library
import time
from collections import namedtuple
from itertools import starmap, repeat

# Third Party
from pysnmp.entity.rfc3413.oneliner import cmdgen
import prettytable

# Local
from . import trafficstats

cmdGen = cmdgen.CommandGenerator()
InterfaceStat = trafficstats.InterfaceStat


def tuplify(obj):
    if type(obj) is tuple:
        return obj
    elif obj is None:
        return tuple()
    elif type(obj) is list:
        return tuple(obj)
    else:
        return (obj, )


class SNMPInterfaceStats(object):
    """
    Wraps SNMP interface statistic results from pysnmp
    """
    def __init__(self, host, community, mibs=None, port=161, minimum_age=10,
                 maximum_age=300):
        """
        :param host: IP Address/hostname
        :param community: SNMPv2 community string
        :param mibs: list of additional MIBs to pull, if any.
        :param port: UDP port
        :param minimum_age: in seconds, will always give cached values if results are not
            at least this old.
        :param maximum_age: ||UNUSED||in seconds, will always update if results are older
            than this.||UNUSED||
        """
        default_mibs = 'ifDescr', 'ifHCInOctets', 'ifHCOutOctets'

        self.time = 0.0
        self.minimum_age = minimum_age

        self.host = None
        self.host_string = host.lower()
        self.udp_port = port

        self.community = None
        self.community_string = community

        self.mibs = []
        mibs = tuplify(mibs)

        mibs = (mibs, ) if type(mibs) is str else tuple(mibs)
        self.mib_names = default_mibs + mibs
        self.pysnmp_init()

        self.errorData = (0, 0, 0)
        self._raw_snmp_result = None
        self._interface_stats = dict()
        self._interpreted_results = []
        self._result_dict = {}

    def pysnmp_init(self):
        self.host = cmdgen.UdpTransportTarget((self.host_string, self.udp_port))
        self.community = cmdgen.CommunityData(self.community_string)
        for mib_name in self.mib_names:
            self.mibs.append(cmdgen.MibVariable('IF-MIB', mib_name))

    @property
    def update_permitted(self):
        """
        Validates age of current results to prevent flooding SNMP traffic.
        This should be evaluated at the beginning of any method that sends
        a request
        :return: True if self.minimum_age seconds have passed, else False
        """
        if time.time() < self.time + self.minimum_age:
            return False
        else:
            return True

    @property
    def raw_snmp_results(self):
        """
        WILL trigger an update if self.minimum_age has passed.
        Use self._raw_snmp_result if that's not desirable.
        :return:
        """
        if self.update_permitted:
            *self.errorData, self._raw_snmp_result = cmdGen.bulkCmd(
                self.community,
                self.host,
                0,
                100,
                *self.mibs,
                lookupValues=True
            )
            self.time = time.time()

        return self._raw_snmp_result

    @property
    def interpreted_snmp_results(self):
        """
        provides list of lists [['interface name', bytes_in, bytes_out]]
        WILL trigger an update if self.minimum_age has passed.
        Use self._interpreted_results if that's not desirable.
        :return: [['interface name', bytes_in, bytes_out]]
        """
        if self.update_permitted:
            interfaces = []
            for raw_interface in self.raw_snmp_results:
                interface = [extract_snmp_value(x[1]) for x in raw_interface]
                interfaces.append(interface)
            self._interpreted_results = interfaces

        return self._interpreted_results

    @property
    def result_dict(self):
        """
        WILL trigger an update if self.minimum_age has passed.
        Use self._result_dict if that's not desirable.
        :return:
        """
        self._result_dict = \
            dict(((x[0], tuple(x[1:])) for x in self.interpreted_snmp_results))
        # Because this is large for a Generator Expression:
        #    runs through list of lists given by interpreted_snmp_results
        #    for each: name, (bytes_in, bytes_out)
        #    Gives an iterator like [ (name, (bytes_in, bytes_out)), (name... ]
        #    which is what dict() expects.
        return self._result_dict

    @property
    def interface_stats(self):
        """
        Will only trigger an update on first use, otherwise will use existing
        data to populate dict.
        """
        if not self._interface_stats:
            self.update_stats()

        return self._interface_stats

    def update_stats(self):
        """
        update _interface_stats dict with InterfaceStat objects
            (still obeying age rules, inherited from other methods)
        """
        for interface in self.interpreted_snmp_results:
            self._interface_stats[interface[0]] = InterfaceStat.from_stats(
                name=interface[0],
                in_out_tuple=(interface[1], interface[2]),
                unit='B', start_time=time.time()
            )

    def __getitem__(self, item):
        """ Pass index operations through to result_dict"""
        return self.result_dict[item]


def extract_snmp_value(var):
    def test_type(type_string, new_type, var):
        f = lambda x: x.find(type_string) >= 0

        m = map(str,var.__class__.mro()) # to str
        m = map(str.lower, m)  # .lower()
        m = map(f, m)  # contains 'type_string'?
        if any(m):
            return new_type(var)
        else:
            return False

    def test_types(converter_list, var):
        args = (x + (var, ) for x in converter_list)
        m = starmap(test_type, args)
        return m

    def extract_value(var):
        converter_list = (
            ('integer', int),
            ('float', float)
            )
        m = test_types(converter_list, var)
        l = list(filter(None, m))
        return l[0] if l else str(var)

    return extract_value(var)

def poll_and_compare(A, B, duration=30):
    """
    given a pair of (dict,key) tuples, compare their values over time.
    :param A: (SNMPInterfaceStats(), 'interface_name')
    :param B: (SNMPInterfaceStats(), 'interface_name')
    :param duration:  Time to run comparison in seconds
    :return:
    """
    host_a, interface_a = A
    host_b, interface_b = B

    increment = 10
    # If we're out of time by less than a second, it's probably because the timers
    # are precise, and overhead inside this function has a non-zero cost, so add
    # in some slack.
    result_table = prettytable.PrettyTable( ['Set', 'Time',
                                             'Bits In', 'Bits Out',
                                             'Change In', 'Change Out',
                                             'Total Change In', 'Total Change Out',
                                             'Total bps in', 'Total bps out'])
    rows = []
    first_stats_a = None  # sentinel for detecting first pass

    # Moved test to the bottom so we don't wast time sleeping if
    # we're just going to return
    while True:
        current_time = time.time()
        current_stats_a = InterfaceStat.from_stats(interface_a, host_a[interface_a],
                                                      unit='B', start_time=current_time)
        current_stats_b = InterfaceStat.from_stats(interface_b, host_b[interface_b],
                                                      unit='B', start_time=current_time)


        if first_stats_a is None:
            start_time = current_time
            last_stats_a, first_stats_a = (current_stats_a, ) * 2
            last_stats_b, first_stats_b = (current_stats_b, ) * 2
            rows.append(create_row('A initial:', current_stats_a))
            rows.append(create_row('B initial:', current_stats_b))

            [result_table.add_row(x) for x in rows[-2:]]
            print(result_table)
            duration += .3
            time.sleep(increment)
            continue

        runtime = current_time - start_time
        rows.append(create_row('A :', current_stats_a,
                               last_stats_a, first_stats_a))
        rows.append(create_row('B :', current_stats_b,
                               last_stats_b, first_stats_b))
        last_stats_a, last_stats_b = current_stats_a, current_stats_b

        [result_table.add_row(x) for x in rows[-2:]]
        print(result_table)

        duration += .3
        if time.time() + increment > start_time + duration:
            break
        time.sleep(increment)
    return rows


def create_row(label, current_stats, last_stats=None, first_stats=None):

    cs, ls, fs = current_stats, last_stats, first_stats
    cs.to_bits()
    current_time = cs.start_time
    row = [label, current_time]
    row.extend((cs.site_in.hr, cs.site_out.hr))
    if ls is not None:
        ls.to_bits(), fs.to_bits()
        dls = cs - ls  # delta last_stats to current_stats
        dfs = cs - fs  # delta first_stats to current_stats

        row[1] = dfs.input.duration  # TODO: This is silly

        row.extend((dls.hri, dls.hro,
                    dfs.hri, dfs.hro,
                    dfs.hri_vot, dfs.hro_vot))
    else:
        row.extend(repeat(None, 6))

    return row



def quick_compare(A, B, duration=10):
    host_a, key_a = A
    host_b, key_b = B
    ex = lambda x,y: int(x[1][y])
    first_a, first_b = ex(A.raw_snmp_results[key_a], 1), ex(B.raw_snmp_results[key_b], 2)
    time.sleep(duration)
    last_a, last_b = ex(A.raw_snmp_results[key_a], 1), ex(B.raw_snmp_results[key_b], 2)
    return last_a - first_a, last_b - first_a


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