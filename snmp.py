import collections

__author__ = 'William George'
__version__ = '0.05'

# Standard Library
import time
import collections.abc
import decimal
from itertools import starmap, repeat

# Third Party
from pysnmp.entity.rfc3413.oneliner import cmdgen
import prettytable

# Local
from . import trafficstats

D = decimal.Decimal
decimal.getcontext().prec = 6
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
    Wraps SNMP interface statistic results from pysnmp and controlls their polling
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

        self.collection_time = 0.0
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
        self.vc = ValueConverter(lambda: ValueConverter.default_converter)

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
        if time.time() < self.collection_time + self.minimum_age:
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
            self.collection_time = time.time()

        return self._raw_snmp_result

    @property
    def interpreted_snmp_results(self):
        """
        provides list of lists [['interface name', bytes_in, bytes_out]]
        WILL trigger an update if self.minimum_age has passed.
        Use self._interpreted_results if that's not desirable.
        :return: [['interface name', bytes_in, bytes_out]]
        """
        vc = self.vc
        if self.update_permitted:
            interfaces = []
            for raw_interface in self.raw_snmp_results:
                interface = [vc.convert(x[1]) for x in raw_interface]
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
                interface_name=interface[0],
                snmp_is=(interface[1], interface[2]),
                unit='B', start_time=time.time()
            )

    def __getitem__(self, item):
        """ Pass index operations through to result_dict"""
        return self.result_dict[item]

class ValueConverter(collections.defaultdict):
    """
    Class to convert/reduce variety of specialized pysnmp types into basic
        python types.

    Implemented as a defaultdict with added methods:

    register(): preferred interface for adding types
    convert(): preferred interface for conversion

    """

    def convert(self, o):
        func = self[type(o)]
        return func(o)

    def register(self, o_type, func):
        try:
            if not issubclass(o_type, (type, object)):
                raise TypeError
        except TypeError:
            raise TypeError('Can only register types and classes')

        self[o_type] = func

    @staticmethod
    def default_converter(o):
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

        return extract_value(o)

        pass


    @property
    def _args(self):
        """
        :return: dict of parameters needed to recreate this object
        """
        _dict = dict(default_factory=self.default_factory)
        _dict.update(self)
        return _dict

    def __repr__(self):
        args = ('{0}={1}'.format(k, v) for k, v in self._args.items())
        key = lambda k: int('default_factory' in k) * -1
        args = sorted(sorted(args), key=key)  # always list default_factory first
        args = ', '.join(args)

        rslt = '{0}({1})'.format(self.__class__.__name__, args)
        return rslt


def extract_snmp_value(var):
    """
    Convert/reduce variety of specialized pysnmp types into basic
        python types.
    :param var: SNMP Object to extract
    :return: converted object
    """

    pass

def poll_and_compare(*targets, duration=30, swap_wan_lan=True, minute_sync=True):
    """
    given a pair of (SNMPInterfaceStat, 'interface_name') tuples,
        compare their values over time.
    :param targets: ((SNMPInterfaceStats(), 'interface_name'), ...)
        count should == 2
    :param duration:  Time to run comparison in seconds
    :param swap_wan_lan:    Swap the in/out direction of every other target
    :param minute_sync:     Don't begin polling until we're near to the start of
                                a new minute
    :return:
    """
    increment = 10
    if (duration / increment) < 3:
        increment = duration / 3  # at least 3 intervals

    stats_dict = {}  # dict of stats
    runs = stats_dict['runs'] = []  # list of runs
    first_run = True

    while True:
        if int(time.time()) % 60:
            time.sleep(0.5)
            continue
        print('begin polling')
        break

    while True:
        run_start_time = time.time()
        swap = swap_wan_lan
        # collect stats for run

        run = []  # list of hosts
        runs.append(run)
        for interface_stats, interface_name in targets:
            swap = not swap
            label = interface_stats.host_string
            cs = InterfaceStat.from_stats(interface_name, interface_stats,
                                          invert_wan_lan=swap, unit='B')
            # cs = current_stats
            cs.to_bits()


            if first_run:
                ls, fs = (cs, ) * 2
                poll_start_time = cs.start_time
            else:
                last_run = runs[-2][len(run)]
                # runs already has our (empty) run appended, so "last" run
                #   is "two back".
                # hosts are appended to 'run', and the host we're on hasn't
                #   been appended yet, so len(run) is the index of the
                #   current host.

                ls, fs = [last_run[x] for x in ('ls', 'fs')]

                # last_stats, first_stats

            d_ls, d_fs = cs - ls, cs - fs
            # delta_from_last_stats, delta_from_first_stats

            host = dict(cs=cs, ls=ls, fs=fs, d_ls=d_ls, d_fs=d_fs,
                        label=label)
            run.append(host)

        first_run = False
        # send stats to update_stats_table
        update_stats_table(stats_dict)
        # display table
        print(stats_dict['table'])
        # set up for next iteration
        run_run_time = time.time() - run_start_time
        duration += (1.1 * run_run_time)  # build in slack so we don't miss a run.
        if (time.time() + increment) > (poll_start_time + duration):
            break
        time.sleep(increment)
    return stats_dict


def update_stats_table(stats_dict):
    """
    Given stats in stats_dict, will create or update table with new rows.
    Will not perform any reordering of stats (in <-> out, etc)

    :param stats_dict: dict containing referenced objects.
    :return: stat_dict updated with {'table': PrettyTable}
    """
    # columns doesn't include first column, specified later
    columns = [
        # (label, key, attribute of value or None for repr(value))
        ("Time", "d_fs", "duration"),
        # TODO: replace 'bits in' with something that gives right amount of significant digits
        ("I. Delta In", "d_ls", "hri"),
        ("I. Delta Out", "d_ls", "hro"),
        ("I. bps In", "d_ls", "hri_vot"),
        ("I. bps Out", "d_ls", "hro_vot"),
        # ("I. Throughput", )
        ("T. Delta In", "d_fs", "hri"),
        ("T. Delta Out", "d_fs", "hro"),
        ("T. bps In", "d_fs", "hri_vot"),
        ("T. bps Out", "d_fs", "hro_vot"),
        # ("T. Throughput", )
    ]
    try:
        table = stats_dict['table']
    except KeyError:
        table = stats_dict['table'] = prettytable.PrettyTable(
            ['label'] + [label for label, *_ in columns]
        )
        first_run = True
    else:
        first_run = False

    this_run = stats_dict['runs'][-1]  # assume last run == most recent == relevant
    try:

        for host_stats in this_run:
            label = '{0} initial:' if first_run else '{0} :'

            label = label.format(host_stats['label'])

            row = create_row(label, columns, host_stats)
            table.add_row(row)
    except Exception as e:
        import pprint
        pprint.pprint(stats_dict)
        raise e

    stats_dict['table'] = table  # only strictly necessary on first run, but don't care.


def create_row(row_label, columns, host_stats):
    """
    Create rows for a table IAW the spec in columns
    (format defined in snmp.update_stats_table())

    :param columns: column spec
    :param stats_run:   dict() of objects referenced in column spec
    :return:  List of strings for table output.
    """
    row = [row_label, ]

    for _, key, attr in columns:
        o = host_stats[key]
        value = getattr(o, attr, None)
        row.append(value)

    return row


def safe_decimal(o):
    try:
        return D(o) * 1  # force precision
    except (TypeError, decimal.InvalidOperation):
        return o


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