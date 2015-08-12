#! /usr/bin/python
"""
Created on Dec 1, 2014

@author: William.George
"""

# Standard Library Imports
import sys
from optparse import OptionParser
import multiprocessing.pool

# Imports from other scripts in this project
from sshutil import get_credentials
from networkdevices.networkdevice import CiscoIOS
from sshutil import deduplicate_list
import metrics


def createParser():
    """
    Create a parser object for optparse package to collect command line
    arguments
    """

    usage = ('cdpmap.py -h | ([-t <host>] | -T <hostfile) '
             '[-u <username>] [-o Output file] [-d <maximum thread count>])')

    description = ('Given switch or list of switches, list CDP Neighbors.')

    parser = OptionParser(usage=usage, description=description)
    parser.add_option('-t', '--host', help='Hostname or IP address of switch '
                      '*Will prompt if neither host nor hostfile are provided.'
                      )
    parser.add_option('-T', '--hostfile', help='File containing list of switch'
                      ' hostnames or IP addresses, one per line.')
    parser.add_option('-u', '--username', help='Username to use to connect.'
                      ' *Will assume currently logged in user if not provided.'
                      )
    parser.add_option('-d', '--threads', type='int', help='Number of threads '
                      'to use for DNS resolution (or other tasks).', default=1)
    parser.add_option('-o', '--outfile', help='Primary output to listed file.')
    parser.add_option('-v', '--verbose', action='count', help='Increase output'
                      ' verbosity (e.g., -vv is more than -v) up to 3',
                      default=0)
    return parser


def main(argv):
    """
    Given switch or list of switches, list CDP neighbors, and a few other stats
     """
    global CREDENTIALS
    global CURRENT_SWITCH
    global MAX_THREADS
    hosts = None
    hostfile = None
    username = None
    outfile = ''

    # using optparse module to collect commandline arguments
    parser = createParser()
    (options, args) = parser.parse_args()
    hostfile = options.hostfile
    host = options.host
    username = options.username
    MAX_THREADS = options.threads
    metrics.VERBOSITY = options.verbose
    outfile = options.outfile

    if hostfile:  # make sense of host/hostfile options
        if host:
            metrics.DebugPrint('Cannot specify both "host" and "hostfile"!', 3)
            raise Exception('INVALID OPTIONS')
        with open(hostfile, 'r') as fHosts:
            hosts = fHosts.readlines()
        bHosts = []
        for line in hosts:
            bHosts.append(line.strip())
        hosts = bHosts
    elif host:  # even if it's a single entry, it should be a 'list'
        hosts = [host]
    else:                   # Prompt for host if none present
        hosts = [raw_input('Enter single hostname or IP address (If you want '
                           'multiple hosts, re-run with -T or --hostfile:\n')]

    # Collect UN/PW for connecting to devices.
    CREDENTIALS = get_credentials(username)

    # Start clock to report how long the actual processing takes
    metrics.Clock(True)

    oBuffer = ''
    switches = []
    hosts = deduplicate_list(hosts)
    for host in hosts:
        switch = CiscoIOS(ip=host, creds=CREDENTIALS)
        switches.append(switch)

    if MAX_THREADS > 1:  # Single or MultiThreaded...
        switches = PopulateSwitchesMT(switches)
    else:
        switches = PopulateSwitchesST(switches)

    ScrubbedSwitches = []
    for switch in switches:
        if switch.state in switch.goodstates:  # ignore 'DOWN' switches
            ScrubbedSwitches.append(switch)
        else:
            continue

    for switch in ScrubbedSwitches:  # prepair output
        oBuffer += ('{0}:  {1}, {2} ports\n'
                    ''.format(switch.ip, switch.model, len(switch.ports)))
        for interface in switch.ports:
            for entry in interface.CDPneigh:
                if 'CiscoIOS' in entry[2] or 'Router' in entry[2]:
                    oBuffer += '--{0}\n'.format(interface.name)
                    oBuffer += '----{0}\n'.format(interface.CDPneigh)
        oBuffer += '\n\n'
    oBuffer += 'Given Hosts:\n\t' + '\n\t'.join(sorted(hosts)) + '\n\n'
    finalhosts = sorted([x.ip for x in switches if x.state in x.goodstates])
    oBuffer += 'Discovered Switches:\n\t' + '\n\t'.join(finalhosts)
    oBuffer += '\n\n'
    diffhosts = set(finalhosts).difference(set(hosts))
    oBuffer += 'Difference:\n  Added:\n\t' + '\n\t'.join(diffhosts)
    oBuffer += '\n'
    diffhosts = set(hosts).difference(set(finalhosts))
    oBuffer += '  Removed:\n\t' + '\n\t'.join(diffhosts)
    oBuffer += '\n'
    cdphosts = [x[1] for x in ListCDPEndpoints(switches)]
    diffcdphosts = set(cdphosts).difference(set(finalhosts))
    oBuffer += '  Unaccounted for, but in CDP:\n\t' + '\n\t'.join(diffcdphosts)
    oBuffer += '\n\n'

    if outfile:  # Send output to file or screen
        fOut = open(outfile, 'w')
        fOut.write(oBuffer)
        fOut.close()
    else:
        print oBuffer

    print 'Completed in {0} seconds.'.format(metrics.Clock())
    metrics.PrintMetrics()


def ListCDPEndpoints(switches):
    s = set()
    for switch in switches:
        for port in switch.ports:
            for entry in port.CDPneigh:
                s.add((entry[0], entry[1]))
    return s


def PopulateSwitch(switch):
    """
    Wrapper to support multiprocessing.pool.map() syntax
    """
    switch.populate()
    return switch


def PopulateSwitchesMT(switches):
    metrics.DebugPrint('interfacedescription.py:PopulateSwitchesMT.Threads: '
                       '{0}'.format(MAX_THREADS), 2)
    metrics.DebugPrint('interfacedescription.py:PopulateSwitchesMT.Switches: '
                       '{0}'.format(', '.join(map(str, switches))), 1)

    pool = multiprocessing.pool.ThreadPool(processes=MAX_THREADS)
    mtRslts = pool.map(PopulateSwitch, switches)
    pool.close()
    pool.join()
    return mtRslts


def PopulateSwitchesST(switches):
    metrics.DebugPrint('interfacedescription.py:PopulateSwitchesST()', 2)
    metrics.DebugPrint('interfacedescription.py:PopulateSwitchesST.Switches: '
                       '{0}'.format(', '.join(map(str, switches))), 1)

    for sw in switches:
        # use this instead of sw.populate() for consistency... doesn't
        # really matter.
        PopulateSwitch(sw)
    return switches


def Exit():
    """
    Used for quick/dirty troubleshooting/performance measurements
    """
    print 'completed in {0} seconds.'. format(metrics.Clock())
    sys.exit()


if __name__ == '__main__':
    main(sys.argv[1:])
