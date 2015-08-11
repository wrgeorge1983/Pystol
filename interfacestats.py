#! /usr/bin/python
'''
Created on Dec 3, 2014

@author: William.George
'''

# Standard Library Imports
import sys
import getopt
import csv

# Imports from other scripts in this project
from sshutil import get_credentials
from networkdevices.networkdevice import Switch
from sshutil import deduplicate_list
from metrics import PrintMetrics
from metrics import DebugPrint


def main(argv):
    """
    Collect and output (to screen or file) list of interface statistics for one
        or more switches.

    interfacestats.py -h | ([-t <host>] | -T <hostfile) [-u <username>]
        [-o Output file] [-c CSV Output File] [-d <maximum thread count>])

    --host or -t     -- hostname or IP address of switch *Will prompt if
        neither host nor hostfile are provided.
    --hostfile or -T -- file containing list of switch hostnames or IP
        addresses, one per line.
    --username or -u -- username to use to connect. *Will assume currently
        logged in user if not provided.
    --threads or -d  -- Number of threads to use for DNS resolution (or other
        tasks).
    --outfile or -o  -- primary output to listed file.
    --csv or -c  --primary output to listed CSV file
    --help or -h -- print this usage information.
     """
    global CREDENTIALS
    global CURRENT_SWITCH
    global MAX_THREADS
    global DEFAULT_GATEWAY
    hosts = None
    hostfile = None
    username = None
    outfile = ''
    csvfile = ''
    try:
        opts, _ = getopt.getopt(argv, "ht:T:u:d:o:c:", ["host=",
                                                        "hostfile=",
                                                        "username=",
                                                        "threads=",
                                                        "outfile=",
                                                        "csv=",
                                                        "help"])
    except getopt.GetoptError:
        print('error in processing arguments')
        sys.exit(2)

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            print(main.__doc__)
            sys.exit()
        elif opt in ("-t", "--host"):
            if hostfile is None:
                hosts = [arg]
            else:
                raise Exception('Cannot specify both HOST and HOSTFILE')
        elif opt in ('-T', '--hostfile'):
            if hosts is None:
                hostfile = arg
            else:
                raise Exception('Cannot specify both HOST and HOSTFILE')
        elif opt in ('-u', '--username'):
            username = arg
        elif opt in ('-d', '--threads'):
            MAX_THREADS = int(arg)
        elif opt in ('-o', '--outfile'):
            outfile = arg
        elif opt in ('-c', '--csv'):
            csvfile = arg

    if hostfile is not None:
        with open(hostfile, 'r') as fHosts:
            hosts = fHosts.readlines()
        bHosts = []
        for line in hosts:
            bHosts.append(line.strip())
        hosts = bHosts
    elif hosts is None:                    # Prompt for host if none present
        hosts = raw_input('Enter single hostname or IP address (If you want '
                          'multiple hosts, re-run with -T or --hostfile:\n')

    CREDENTIALS = get_credentials(username)

    oBuffer = ''
    hosts = deduplicate_list(hosts)
    switches = []
    for host in hosts:
        switch = Switch(ip=host, creds=CREDENTIALS)
        switches.append(switch)
        # we're getting ALL interfaces here, as opposed to non-trunks typically
        DebugPrint('Switch._get_interfaces(): {0}'
                   ''.format(str(switch)))
        switch._get_interfaces()
        oBuffer += switch.ip + '\n'
        for interface in sorted(switch.ports):
            oBuffer += ':' + interface.name + '\n'
            for key in sorted(interface.stats):
                oBuffer += '---' + key + ":  " + str(interface.stats[key])\
                    + '\n'
        oBuffer += '\n'

    DebugPrint('interfacestats.switches: {0}'
               ''.format(map(str, switches)))
    if outfile:
        fOut = open(outfile, 'w')
        fOut.write(oBuffer)
        fOut.close()
    else:
        print oBuffer

    print csvfile
    if csvfile:
        stats = ['StatDuration', '5MinInputBPS', '5MinInputPPS',
                 '5MinOutputBPS', '5MinOutputPPS', 'InputPackets',
                 'InputBytes', 'OutputPackets', 'OutputBytes',
                 'InputErrors', 'OutputErrors']

        with open(csvfile, 'w') as fCSV:
            csvWriter = csv.writer(fCSV, delimiter=',', quotechar='|',
                                   quoting=csv.QUOTE_MINIMAL)
            csvWriter.writerow(['Switch', 'Interface'] + stats)
            # print switches
            for switch in switches:
                # print sorted(switch.ports)
                for interface in sorted(switch.ports):
                    values = []
                    for stat in stats:
                        values.append(interface.stats[stat])
                    # print values
                    csvWriter.writerow([switch.ip, interface.name] + values)

    PrintMetrics()


if __name__ == '__main__':
    main(sys.argv[1:])
