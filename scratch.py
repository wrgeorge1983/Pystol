import sshutil

import time
from pprint import pprint

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
    suffix_list = {0: '', 1: 'K', 2: 'M', 3: 'G', 4:'T'}
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


def format_byte_interpretation(bytes_in, unit=''):
    rslts = interpret_bytes(bytes_in, unit)
    interpretation = \
    '{bytes:n}{B_unit} == {bits:n}{b_unit}\n' \
    '  {bytes_hr_decimal}{B_unit} == {bytes_hr_bin}{B_unit}\n' \
    '  {bits_hr_decimal}{b_unit} == {bits_hr_bin}{b_unit}\n'.format(**rslts)

    return interpretation


def report_status_from_sum_of_bps(sum_in, sum_out, seconds=3600):
    '''Interpret data from SMC returned in 'sum of bps'.
    Does NOT swap in/out
    '''
    rx_bytes = sum_in*60./8.
    tx_bytes = sum_out*60./8.
    report_status_from_bytes(rx_bytes, tx_bytes, seconds)


def report_status_from_bytes(rx_bytes, tx_bytes, seconds=3600.):
    print 'DeltaRX:\n{0}'.format(format_byte_interpretation(rx_bytes))
    print 'DeltaTX:\n{0}'.format(format_byte_interpretation(tx_bytes))
    print 'RXps:\n{0}'.format(format_byte_interpretation(rx_bytes/seconds))
    print 'TXps:\n{0}'.format(format_byte_interpretation(tx_bytes/seconds))


def get_riverbed_interfaces(rb):
    rslt = rb.Execute('show interface', timeout=1)
    while rslt.find('>') < 0:
        time.sleep(.5)
        rslt += rb.bufferflush()
    rslt = rslt[:rslt.rfind('\r\n')]
    entries = rslt.split('\r\nInterface')[1:]
    ifaces = dict()
    for entry in entries:
        entry_dict = dict()
        entry = filter(bool, entry.splitlines())
        entry_dict['Name'] = entry.pop(0).split()[0]
        for line in entry:
            line = line.split(':', 1)
            try:
                k, v = map(str.strip, line)
                entry_dict[k] = v
            except:
                print entry_dict['Name']
                pprint(entry)
                pprint(line)
                pprint((k, v))
                raise

        ifaces[entry_dict['Name']] = entry_dict
    return ifaces


def get_riverbed_traffic_stats(rb, interface):
    ifaces = get_riverbed_interfaces(rb)
    return [x for x in ifaces[interface].items() if x[0][1] == 'X']


def poll_riverbed_stats(rb, interface, run_time):
    start_time = time.time()
    start_time_s = time.asctime(time.localtime(start_time))
    print(start_time_s)
    interval = run_time / 10
    interval = max(interval, 15)
    interval = min(interval, 60*5)
    interval = int(interval)
    run_time += 9  # approx time it takes to poll once
    first_run = None
    stats = [None, 0]
    while time.time() <= start_time + run_time:
        stats = get_riverbed_traffic_stats(rb, interface)
        if first_run is None:
            first_run = stats
        print 'Stats after {0} seconds'.format(time.time() - start_time)
        pprint(stats)
        time.sleep(interval)
    end_time = time.time() - interval
    run_time = end_time - start_time
    delta_stats = []
    for first, last in zip(first_run, stats):
        delta = first[0], int(last[1]) - int(first[1])
        delta_stats.append(delta)

    rate_stats = []
    for stat in delta_stats:
        rate = stat[0], stat[1] / run_time
        rate_stats.append(rate)

    end_time_s = time.asctime(time.localtime(end_time))
    print('Ran from {0} to {1}'.format(start_time_s, end_time_s))
    print('Final Stats after {0} seconds:'.format(run_time))
    pprint(stats)
    print('Delta')
    pprint(delta_stats)
    print('Rates')
    pprint(rate_stats)

    return stats, delta_stats, rate_stats

'''
from pysnmp.entity.rfc3413.oneliner import cmdgen

cmdGen = cmdgen.CommandGenerator()

community = 'A2!!vA1bEEc'
host = '192.168.2.82'
oids = ['1.3.6.1.2.1.1.1.0', '1.3.6.1.2.1.1.6.0']

*errorData, varBindTable = cmdGen.nextCmd(
    cmdgen.CommunityData(community),
    cmdgen.UdpTransportTarget((host, 161)),
    cmdgen.MibVariable('IF-MIB', 'ifDescr'),
    cmdgen.MibVariable('IF-MIB', 'ifType'),
    cmdgen.MibVariable('IF-MIB', 'ifMtu'),
    cmdgen.MibVariable('IF-MIB', 'ifSpeed'),
    cmdgen.MibVariable('IF-MIB', 'ifPhysAddress'),
    lookupValues=True
)

*errorData, varBinds = cmdGen.getCmd(
    cmdgen.CommunityData(community),
    cmdgen.UdpTransportTarget((host, 161)),
    *oids
)


def
# Check for errors and print out results
if errorIndication:
    print(errorIndication)
else:
    if errorStatus:
        print('%s at %s' % (
            errorStatus.prettyPrint(),
            errorIndex and varBinds[int(errorIndex)-1] or '?'
            )
        )
    else:
        for name, val in varBinds:
            print('%s = %s' % (name.prettyPrint(), val.prettyPrint()))

'''

from collections import namedtuple
PingResult = namedtuple('PingResult', 'target, sent, received, dropped')


class ExtendedPingResult(PingResult):
    def __add__(self, other):
        assert type(self) == type(other), (
            "Can only add other instances of {0}, not {1}"
            "".format(type(self), type(other))
        )
        assert self.target == other.target, (
            "Cannot add results for different targets! "
            "What would that even mean!?")
        return self.__class__(self.target, *map(sum, zip(self[1:], other[1:])))

    @property
    def percent_dropped(self):
        return self.dropped / self.sent

    @property
    def percent_received(self):
        return self.received / self.sent

    def __str__(self):
        rep = self.__repr__()
        return rep[:-1] + ", percent_dropped={0:.2%})".format(self.percent_dropped)
