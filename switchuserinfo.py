#! /usr/bin/python
'''
Created on Nov 14, 2014

@author: William.George

intent: given one or more switch IP addresses identify the end devices by mac
address, and present a list of IP addresses
pseudocode:

main(hosts):
    macIPpairs=[]
    for host in hosts:
        endDevices += GetEndDevices(host)

    for endDevice in endDevices:
        IP = resolveMAC(endDevice)
        macIPpairs.append (mac,IP)


'''

# Standard Library Imports
import sys
from optparse import OptionParser

# Imports from other scripts in this project
from sshutil import get_credentials
from sshutil import clSwitch
import sshutil
import metrics

DEFAULT_GATEWAY = None
CREDENTIALS = None  # SET THESE IN MAIN()!
CURRENT_SWITCH = None
DEBUG = False


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
                      'to use for DNS resolution (or other tasks).')
    parser.add_option('-S', '--single', action='store_False',
                      dest='multithreading',
                      help='Force single threaded operation.  You MUST use '
                      'this if you expect to make sense of the debug output.',
                      default='True')
    parser.add_option('-o', '--outfile', help='Primary output to listed file.')
    parser.add_option('-g', '--defaultgateway', help='Switch or router to use '
                      'for MAC-> IP resolution (via ARP table lookup).')
    parser.add_option('-v', '--verbose', action='count', help='Increase output'
                      ' verbosity (e.g., -vv is more than -v) up to 3.',
                      default=0)
    return parser


def main(argv):
    """
    Identify end devices of switch by MAC and IP Address

    switchuserinfo.py -h | ([-t <host>] | -T <hostfile) [-u <username>]
        [-d <maximum thread count>] [-g <default-gateway>] [-o <output file>])

    --host or -t     -- hostname or IP address of switch *Will prompt if
        neither host nor hostfile are provided.
    --hostfile or -T -- file containing list of switch hostnames or IP
        addresses, one per line.
    --username or -u -- username to use to connect. *Will assume currently
        logged in user if not provided.
    --threads or -d  -- Number of threads to use for DNS resolution (or other
        tasks).  Defaults to 4 (seems optimal)
    --single or -S   -- Force single threaded operation.  You MUST use this if
        you expect to make sense of the debug output.
    --gateway or -g  -- switch or router to use for MAC -> IP resolution (via
        ARP table lookup).
    --outfile or -o  -- primary output to listed file.
    --help or -h -- print this usage information.

     """
    global CREDENTIALS
    global CURRENT_SWITCH
    global DEFAULT_GATEWAY

    parser = createParser()
    (options, args) = parser.parse_args()
    host = options.host
    hostfile = options.hostfile
    username = options.username
    maxThreads = int(options.threads)
    MultiThreading = options.multithreading
    defaultGateway = options.defaultgateway
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
    elif host:                    # Prompt for host if none present
        hosts = [host]
    else:
        hosts = [raw_input('Enter single hostname or IP address (If you want '
                           'multiple hosts, re-run with -T or --hostfile:\n')]

    if not defaultGateway:
        defaultGateway = '10.217.104.1'
    DEFAULT_GATEWAY = defaultGateway

    CREDENTIALS = get_credentials(username)

    metrics.Clock(True)
    metrics.DebugPrint('hosts:' + str(hosts), 1)
    switches = []
    for host in hosts:
        switches.append(clSwitch(ip=host, creds=CREDENTIALS))

    endDevices = sshutil.ProcessEndDevices(hosts=switches, creds=CREDENTIALS,
                                           maxThreads=maxThreads,
                                           MultiThreading=MultiThreading,
                                           defaultgateway=defaultGateway)

    oBuffer = ''
    for endDevice in endDevices:
        oBuffer += repr(endDevice) + '\n'

    footer = '*' * 15 + '\n'
    footer += '{0} end devices.\n'.format(len(endDevices))
    footer += 'Threads: {0}\n'.format(maxThreads)
    footer += 'Duration: {0} seconds.\n'.format(metrics.Clock())
    oBuffer += footer

    if outfile:
        fOut = open(outfile, 'w')
        fOut.write(oBuffer)
        fOut.close()
        print footer
    else:
        print oBuffer
    if MultiThreading:
        print ('Not printing metrics because they are mangled due to '
               'multi-threading and will be wildly inaccurate.')
    else:
        metrics.PrintMetrics()


if __name__ == '__main__':
    main(sys.argv[1:])
