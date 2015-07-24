#! /usr/bin/python
'''
Created on Nov 18, 2014

@author: William.George
Create interface descriptions to be applied to switch interfaces, listed as the
    appropriate commands
-accept individual host or list of hosts
-assuming switches, not routers
-will present existing descriptions (if any) alongside (after) new description
    so that if commands are ran in bulk, existing will override new
-if multiple devices off

'''

CREDENTIALS = None
CURRENT_SWITCH = None
MAX_THREADS = None
DEFAULT_GATEWAY = None
MULTITHREADING = False

# Standard Library Imports
import sys
from optparse import OptionParser
import multiprocessing.pool

# Imports from other scripts in this project
import sshutil
from sshutil import get_credentials, Switch  # EndDevice, SwitchPort
from sshutil import Date, DateTime  # DeduplicateList
import metrics


def createParser():
    usage = ('interfacedescription.py -h | ([-t <host>] | -T <hostfile) '
             '[-u <username>] [-o Output file] [-d <maximum thread count>] '
             '[-g <default-gateway>])')

    description = ('Generate interface descriptions to be applied to switch '
                   'interfaces, listed as the appropriate commands.  Print to '
                   'screen or output to file.')

    parser = OptionParser(usage=usage, description=description)
    parser.add_option('-t', '--host', help='Hostname or IP address of switch '
                      '*Will prompt if neither host nor hostfile are provided.'
                      )
    parser.add_option('-T', '--hostfile', help='File containing list of switch'
                      ' hostnames or IP addresses, one per line.')
    parser.add_option('-u', '--username', help='Username to use to connect.'
                      ' *Will assume currently logged in user if not provided.'
                      )
    parser.add_option('-g', '--gateway', help='Switch or router to use for '
                      'MAC -> IP resolution (via ARP table lookup).')
    parser.add_option('-d', '--threads', type='int', help='Number of threads '
                      'to use for DNS resolution (or other tasks).',
                      default=1)
    parser.add_option('-o', '--outfile', help='Primary output to listed file.')
    parser.add_option('-v', '--verbose', action='count', help='Increase output'
                      ' verbosity (e.g., -vv is more than -v) up to 3',
                      default=0)
    parser.add_option('-e', '--edge', help='Include Edge Devices',
                      action='store_true')
    return parser


def main(argv):
    """
    Generate interface descriptions to be applied to switch interfaces,
        listed as the appropriate commands.  Print to screen or output to file.

    interfacedescription.py -h | ([-t <host>] | -T <hostfile) [-u <username>]
        [-o Output file] [-d <maximum thread count>] [-g <default-gateway>])

    --host or -t     -- hostname or IP address of switch *Will prompt if
        neither host nor hostfile are provided.
    --hostfile or -T -- file containing list of switch hostnames or IP
        addresses, one per line.
    --username or -u -- username to use to connect. *Will assume currently
        logged in user if not provided.
    --threads or -d  -- Number of  threads to use for DNS resolution (or other
        tasks).
    --outfile or -o  -- primary output to listed file.
    --gateway or -g  -- switch or router to use for MAC -> IP resolution (via
        ARP table lookup).
    --help or -h -- print this usage information.
     """
    global CREDENTIALS
    global CURRENT_SWITCH
    global MAX_THREADS
    global DEFAULT_GATEWAY
    global MULTITHREADING
    hosts = None

    parser = createParser()
    (options, args) = parser.parse_args()

    hostfile = options.hostfile
    host = options.host
    username = options.username
    defaultGateway = options.gateway
    outfile = options.outfile
    metrics.VERBOSITY = options.verbose
    MAX_THREADS = options.threads
    edge = options.edge

    if MAX_THREADS > 1:
        MULTITHREADING = True

    if hostfile:
        if host:
            raise Exception('Cannot specify both HOST and HOSTFILE')
        with open(hostfile, 'r') as fHosts:
            hosts = fHosts.readlines()
        bHosts = []
        for line in hosts:
            bHosts.append(line.strip())
        hosts = bHosts
    else:
        hosts = [host]
    if None in hosts:                    # Prompt for host if none present
        hosts = raw_input('Enter single hostname or IP address (If you want '
                          'multiple hosts, re-run with -T or --hostfile:\n')

    metrics.DebugPrint("Options: {0}".format(options), 2)

    if not defaultGateway:
        defaultGateway = None  # '10.10.104.1'
    DEFAULT_GATEWAY = defaultGateway
    CREDENTIALS = get_credentials(username)

    metrics.Clock(True)
    switches = PrepairSwitches(hosts, CREDENTIALS, DEFAULT_GATEWAY)

    oBuffer = ''
    for switch in switches:
        if switch.state not in switch.goodstates:
            oBuffer += switch.ip + '\nCould Not Connect!\n'
            continue
        # metrics.DebugPrint('[{0}].CollectInterfaceDescription()'
        #                    ''.format(switch.ip), 2)
        # switch._collect_interface_descriptions()
        # metrics.DebugPrint('[{0}]._collect_cdp_information()'
        #                    ''.format(switch.ip), 2)
        # switch._collect_cdp_information()

        tmp = prepCommands(switch, edge)
        oBuffer += switch.ip + '\n'
        oBuffer += '\n'.join(tmp)
        oBuffer += '\n'

    if outfile:
        fOut = open(outfile, 'w')
        fOut.write(oBuffer)
        fOut.close()
    else:
        print oBuffer

    print 'Completed at {0} after {1} seconds.'.format(DateTime(),
                                                       metrics.Clock())
    goodswitches = [x for x in switches if (x.state in x.goodstates)]
    metrics.DebugPrint('Total Switches: {0}'
                       ''.format(len(goodswitches)), 2)
    lenPorts = 0
    lenActivePorts = 0
    for sw in goodswitches:
        lenPorts += len(sw.ports)
        lenActivePorts += len([x for x in
                               sw.ports if x.status.lower() == 'up'])
    metrics.DebugPrint('Total Interfaces: {0}'.format(lenPorts), 2)
    metrics.DebugPrint('Active Interfaces: {0}'.format(lenActivePorts), 2)
    metrics.PrintMetrics()


def prepCommands(switch, edge):
    '''
        Given Switch, iterate through SwitchPort objects
        prepare commands to apply descriptions
        only to ports that have no CDP switch neighbor and no manually applied
        description
    '''
    commands = []
    commands.append('conf t')

    for switchport in switch.ports:
        # print switchport.name
        # print switchport.description
        test = (switchport.description == ''
                or switchport.description[0] == '%')
        # print switchport.description
        # print test
        if test:
            commands.append('interface {0}'.format(switchport.name))
            if not edge and switchport.edge:
                commands.append('no description')
            else:
                commands.append('description {0}'
                                ''.format(PrepairDescripiton(switchport)))
        else:
            commands.append('!interface {0}'.format(switchport.name))
            commands.append('!description {0}'.format(switchport.description))
            metrics.UpdateMetric("existing description")
            # print switchport.description
    return commands


def PrepairDescripiton(switchport):
    '''
        Given a SwitchPort object, output an appropriate
        interface description
    '''

    metrics.DebugPrint('interfacedescription.py.prepairdescription: {0}'
                       ''.format(switchport), 1)
    metrics.DebugPrint('CDP Neighbors: {0}'.format(switchport.CDPneigh), 0)
    metrics.DebugPrint('End Devices: {0}'.format(switchport.devices), 0)

    count = 0
    netdevice = False

    for entry in switchport.CDPneigh:
        caps = [x.lower() for x in entry[2]]
        if ('switch' in caps) or ('router' in caps):
            netdevice = switchport.CDPneigh.index(entry)

    # print str(netdevice), str(bool(netdevice))
    if netdevice is not False:  # if this connects to a switch or router,
                                # go with that
        entry = switchport.CDPneigh[netdevice]
        description = '%{0} ({1})'.format(entry[0],
                                          sshutil.format_interface_name(entry[3],
                                                                      True))
        description += (' Date: {0}'.format(Date())).replace('/', '-')
        metrics.DebugPrint('--Description: {0}'.format(description), 0)
        return description

    # otherwise:
    if switchport.name[0].lower() == 'v':
        return ''

    description = '%End Device:'
    for device in switchport.devices:
        count += 1
        if count > 2:
            description += (' {0} ADDITIONAL '
                            'DEVICES;'.format(len(switchport.devices)))
            break
        description += ' mac:{0}'.format(device.mac)
        if device.dns == '':
            description += ' host:{0};'.format(device.ip)
        else:
            description += ' host:{0};'.format(device.dns.split('.')[0])
    if count == 0:
        description += ' NONE;'
    description += (' Date: {0}'.format(Date())).replace('/', '-')
    metrics.DebugPrint('--Description: {0}'.format(description), 0)
    return description


def PrepairSwitches(hosts, creds, defaultgateway):
    '''
        Given host,creds,defaultgateway, call switchuserinfo.process_end_devices
        use 'switch' strings in each EndDevice to populate list of switches,
        properly link Switch and EndDevice ojbects
        create device.switchport.  device.switchport property handles linking
        return list of switches
    '''
    metrics.DebugPrint('interfacedescription.py:PrepairSwitches()', 2)
    switches = []

    for host in hosts:
        sw = Switch(ip=host, creds=creds)
        switches.append(sw)

    if MULTITHREADING:
        switches = PopulateSwitchesMT(switches)
    else:
        switches = PopulateSwitchesST(switches)

    metrics.DebugPrint('interfacedescription.py:PrepairSwitches.len(switches):'
                       ' {0}'.format(len(switches)), 2)
    ScrubbedSwitches = []
    for sw in switches:
        if sw.state in sw.goodstates:
            ScrubbedSwitches.append(sw)

    metrics.DebugPrint('interfacedescription.py:PrepairSwitches.'
                       'len(ScrubbedSwitches): '
                       '{0}'.format(len(ScrubbedSwitches)), 2)

    endDevices = sshutil.process_end_devices(switches=ScrubbedSwitches,
                                           creds=creds,
                                           defaultgateway=defaultgateway,
                                           maxThreads=MAX_THREADS)
    metrics.DebugPrint('Total End Devices:\n{0}'.format(len(endDevices)), 2)

    return switches


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
        PopulateSwitch(sw)
    return switches


def PopulateSwitch(switch):
    metrics.DebugPrint('Populating Switch: {0}'.format(switch.ip), 2)
    switch.populate()
    return switch


def Exit():
    print 'completed in {0} seconds.'. format(metrics.Clock())
    sys.exit()

if __name__ == '__main__':
    main(sys.argv[1:])
