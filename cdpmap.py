#! /usr/bin/python
'''
Created on Dec 1, 2014

@author: William.George
'''
import sys
from sshutil import GetCredentials
from sshutil import clSwitch
from sshutil import DedupilicateList
import metrics
from optparse import OptionParser
import multiprocessing


def createParser():
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
    Given switch or list of switches, list CDP neighbors

    cdpmap.py -h | ([-t <host>] | -T <hostfile) [-u <username>]
        [-o Output file] [-d <maximum thread count>]

    --host or -t     -- hostname or IP address of switch *Will prompt if
        neither host nor hostfile are provided.
    --hostfile or -T -- file containing list of switch hostnames or IP
        addresses, one per line.
    --username or -u -- username to use to connect. *Will assume currently
        logged in user if not provided.
    --threads or -d  -- Number of threads to use for DNS resolution (or other
        tasks).
    --outfile or -o  -- primary output to listed file.
    --help or -h -- print this usage information.
     """
    global CREDENTIALS
    global CURRENT_SWITCH
    global MAX_THREADS
    hosts = None
    hostfile = None
    username = None
    outfile = ''

    parser = createParser()
    (options, args) = parser.parse_args()
    hostfile = options.hostfile
    host = options.host
    username = options.username
    MAX_THREADS = options.threads
    metrics.VERBOSITY = options.verbose
    outfile = options.outfile

    if hostfile:
        if host:
            metrics.DebugPrint('Cannot specify both "host" and "hostfile"!', 3)
            raise Exception('INVALID OPTIONS')
        with open(hostfile, 'r') as fHosts:
            hosts = fHosts.readlines()
        bHosts = []
        for line in hosts:
            bHosts.append(line.strip())
        hosts = bHosts
    elif host:
        hosts = [host]
    else:                   # Prompt for host if none present
        hosts = [raw_input('Enter single hostname or IP address (If you want '
                           'multiple hosts, re-run with -T or --hostfile:\n')]

    CREDENTIALS = GetCredentials(username)

    metrics.Clock(True)

    oBuffer = ''
    switches = []
    hosts = DedupilicateList(hosts)
    for host in hosts:
        switch = clSwitch(ip=host, creds=CREDENTIALS)
        switches.append(switch)

    if MAX_THREADS > 1:
        switches = PopulateSwitchesMT(switches)
    else:
        switches = PopulateSwitchesST(switches)

    ScrubbedSwitches = []
    for switch in switches:
        if switch.state in switch.goodstates:
            ScrubbedSwitches.append(switch)
        else:
            continue

    for switch in ScrubbedSwitches:
        oBuffer += switch.ip + '\n'
        for interface in switch.ports:
            for entry in interface.CDPneigh:
                if 'Switch' in entry[2] or 'Router' in entry[2]:
                    oBuffer += '--{0}\n'.format(interface.name)
                    oBuffer += '----{0}\n'.format(interface.CDPneigh)
        oBuffer += '\n\n'
    oBuffer += 'Given Hosts:\n\t' + '\n\t'.join(sorted(hosts)) + '\n\n'
    finalhosts = sorted([x.ip for x in switches if x.state in x.goodstates])
    oBuffer += 'Discovered Switches:\n\t' + '\n\t'.join(finalhosts)
    oBuffer += '\n\n'
    diffhosts = set(finalhosts).difference(set(hosts))
    oBuffer += 'Difference:\n  Added:\n\t' + '\n\t'.join(diffhosts)
    diffhosts = set(hosts).difference(set(finalhosts))
    oBuffer += '\n'
    oBuffer += '  Removed:\n\t' + '\n\t'.join(diffhosts)
    oBuffer += '\n\n'

    if outfile:
        fOut = open(outfile, 'w')
        fOut.write(oBuffer)
        fOut.close()
    else:
        print oBuffer

    print 'Completed in {0} seconds.'.format(metrics.Clock())
    metrics.PrintMetrics()


def ListCDPEndpoints(switches):
    CDPNeighbors = [x.CDPneigh for x in switches]
    


def PopulateSwitchesMT(switches):
    metrics.DebugPrint('interfacedescription.py:PopulateSwitchesMT.Threads: '
                       '{0}'.format(MAX_THREADS), 2)
    metrics.DebugPrint('interfacedescription.py:PopulateSwitchesMT.Switches: '
                       '{0}'.format(', '.join(map(str, switches))), 1)

    pool = multiprocessing.Pool(processes=MAX_THREADS)
    mtRslts = pool.map(PopulateSwitch, switches)
    pool.close()
    pool.join()
    return mtRslts


def PopulateSwitchesST(switches):
    metrics.DebugPrint('interfacedescription.py:PopulateSwitchesST()', 2)
    metrics.DebugPrint('interfacedescription.py:PopulateSwitchesST.Switches: '
                       '{0}'.format(', '.join(map(str, switches))), 1)

    for sw in switches:
        PopulateSwitch(sw)
    return switches


def PopulateSwitch(switch):
    switch.Populate()
    return switch


def Exit():
    print 'completed in {0} seconds.'. format(metrics.Clock())
    sys.exit()


if __name__ == '__main__':
    main(sys.argv[1:])
