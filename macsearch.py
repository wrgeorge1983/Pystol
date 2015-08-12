#! /usr/bin/python
'''
Created on Nov 12, 2014

@author: William.George
'''

# Standard Library Imports
import sys
from optparse import OptionParser


# Imports from other scripts in this project
import networkdevices.networkdevice
from sshexecute import sshrun
import metrics
from sshutil import listify, format_mac_address, get_credentials  # , resolve_mac
import sshutil


def createParser():
    usage = ('macsearch.py -h | (-t <host> | -T <hostfile) (-m MAC | -i IP) '
             '[-u <username>] [-o <optimal>] [-g <default gateway>]')

    description = ('Use mac table and CDP information to identify what port'
                   ' on what switch a device is connected to.')

    epilog = ('    Default behavior is to search the list in order until the '
              'target mac shows up in the mac Address Table.  Then use CDP to '
              'determine next hop switch Search that switch\'s mac Address '
              'Table, lookup next hop  in CDP etc.  Once a MAC Address Table '
              'entry that doesn\'t correspond to another switch is located, '
              'return the switch and port information. Overridden with '
              '"--optimal no".')

    parser = OptionParser(usage=usage, description=description, epilog=epilog)
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
    parser.add_option('-o', '--optimal', help='Set to "no" to force searching'
                      ' every host, omit or any other value for default')
    parser.add_option('-v', '--verbose', action='count', help='Increase output'
                      ' verbosity (e.g., -vv is more than -v) up to 3',
                      default=0)
    parser.add_option('-m', '--mac', help='MAC Address to search for (any '
                      'comonly used format, including "last 4"')
    parser.add_option('-i', '--ip', help='IP Address to search for, will '
                      'resolve to MAC.  Ignored if -m present.')
    parser.add_option('-g', '--defaultgateway', help='Used for ARP resolution '
                      'between IP and MAC.  Only used if -i present.  If not '
                      'specified, will default to first switch in list.')
    return parser


def CollectMACAddressTableEntry(mac, sw, creds):
    cmdShMac = 'show mac address-table | inc {0}'.format(mac)
    # print 'On {0}:'.format(sw)
    result = ''
    try:
        result = sshrun(command=cmdShMac, host=sw, creds=creds)
    except Exception as E:
        print 'Can\'t run commands on this device!'
        print cmdShMac
        # print creds
        print type(E)
        print E
        # continue

    if not (result.strip()):
        print 'Nothing Found'
        # continue
    elif 'invalid' in result.lower():
        metrics.DebugPrint('CollectMACAddressTableEntry Alternate cmd for {0}'
                           ''.format(str(sw)))

        cmdShMac = 'show mac-address-table | inc {0}'.format(mac)
        result = sshrun(command=cmdShMac, host=sw, creds=creds)

    return result


def CollectCDPNeighbors(sw, switchport, creds):
    cmdShCDP = ('Show CDP Neighbor {0} detail | in (IP address|Platform)'
                ''.format(switchport))
    # print 'On {0}:    Running: {1}'.format(sw,cmdShCDP)
    rsltShCDP = sshrun(command=cmdShCDP, host=sw, creds=creds).strip()
    return rsltShCDP


def main(argv):
    """
    Use mac table and CDP information to identify what port on the switch and
         port number a device is connected to

    macsearch.py -m <mac Address> (-t <host> | -T <hostfile>) -o <optimal>
        [-u <username>]

    --mac or -m      -- mac address to search for (any commonly used format,
        including 'last 4').
    --host or -t     -- hostname or IP address of switch *Will prompt if
        neither host nor hostfile are provided.
    --hostfile or -T -- file containing list of switch hostnames or IP
        addresses, one per line.
    --optimal or -o  -- set to 'no' to force script to search all switches.
    --username or -u -- username to use to connect. *Will assume currently
        logged in user if not provided.
    --ip or -i -- IP address to search for, will resolve to MAC.  Ignored if
        MAC present.
    --defaultgateway or -g -- used for ARP resolution between IP and MAC.  Only
        used if -i present.  If not specified, will default to first switch
        in list.
    --help or -h -- print this usage information.

    Default behavior is to search the list in order until the target mac shows
        up in the mac Address Table.  Then use CDP to determine next hop switch
        Search that switch's mac Address Table, lookup next hop  in CDP etc.
        Once a mac Address Table entry that doesn't correspond to another switc
        is located, return the switch and port information. Overridden with
        '--optimal no'.

    """
    hosts = ''
    rslt = ''
    found = False
    abort = False
    sw = None
    switchport = None
    optimal = True
    nextswitch = None
    creds = [None, None]

    parser = createParser()
    (options, args) = parser.parse_args()
    mac = options.mac
    ip = options.ip
    username = options.username
    host = options.host
    hostfile = options.hostfile
    defaultGateway = options.defaultgateway
    if options.optimal == 'no':
        optimal = False
    else:
        optimal = True

    if hostfile:
        if host:
            metrics.DebugPrint('Cannot specify both "host" and "hostfile"!', 3)
            raise Exception('INVALID OPTIONS')
        with open(hostfile, 'r') as fHosts:
            hosts = fHosts.readlines()
    elif host:
        hosts = [host]
    else:
        hosts = raw_input('What host to check?')
    hosts = listify(hosts)

    while creds[1] is None or creds[1] == '':
        creds = get_credentials(username)
        if creds[1] == '' or creds[1] is None:
            print ("blank password isn't what you want!")

    if not mac:
        if ip:
            if not defaultGateway:
                defaultGateway = hosts[0]
            mac = ResolveMAC(ip=ip, device=defaultGateway, creds=creds)
            if 'Not Found' in mac:
                sys.exit('Could not find MAC Address!')
        else:
            mac = raw_input('What MAC Address?')
    mac = format_mac_address(mac)

    i = 0
    while not abort and (not (found and optimal)):

        MACAddressTable = ''
        # nextswitch will be set if we have picked up the mac somewhere and
        # have a specific switch we want to look at next.  Otherwise, (or if
        # 'optimal' is false) just hit the next switch in the list.
        if nextswitch is not None and optimal:
            sw = nextswitch
        else:
            sw = hosts[i].strip()
            # Do the iteration early, so that we don't have to worry about
            # 'continue' statements
            i += 1
            # setting abort to true here means that AFTER this final run, we
            # will stop looping
            if i >= len(hosts):
                abort = True
        # print mac, sw  # creds
        MACAddressTable = CollectMACAddressTableEntry(mac, sw, creds)
        switchport = MACAddressTable.strip(' \r\n\t').split(' ')[-1]
        print 'switchport: ' + switchport
        if switchport:
            CDPNeighbors = CollectCDPNeighbors(sw, switchport, creds)
            # print 'CDPNeighbors: ' + CDPNeighbors
            print "Port: {0}  ---> {1}".format(switchport, CDPNeighbors)
            if 'switch' not in CDPNeighbors.lower():
                print ('{0}\r\nTHIS PORT CONNECTS TO SOMETHING THAT ISN\'T A '
                       'SWITCH!\r\nThis is probably it!\r\n{0}'.format('*'*15))
                rslt = sw
                found = True
            else:
                nextswitch = CDPNeighbors.splitlines()[0].split()[2].strip()
                abort = False
        else:
            nextswitch = None
            # print i, len(hosts)
            if i >= len(hosts):
                abort = True
            print abort

    return found, abort, rslt, switchport


def ResolveMAC(device, ip, creds):
    '''
        Given an IP address and the appropriate subnet default gateway,
        SSH into the default gateway, ping the IP, and use arp table to resolve
        the MAC.
    '''
    # TODO:  We don't check to make sure this device is actually up at all
    lines = []
    command = 'sh arp'
    if not (ip):
        raise Exception('No IP Address specified to resolve!')
    # DebugPrint('resolve_mac.defaultgateway: ' + str(defaultgateway))
    # DebugPrint('resolve_mac.creds[0]: ' + creds[0])

    # ==========================================================================
    # Assume that device is NOT already a CiscoIOS Object.  When that is no
    # longer the case, change the parameters.
    # ==========================================================================

    device = networkdevices.networkdevice.CiscoIOS(ip=device, creds=creds)
    lines = device.execute('ping {0}'.format(ip), timeout=5)
    line = device.execute('sh arp | i {0}'.format(ip))

    if len(line) == 0 or line.split()[3].lower() == 'incomplete':
        return 'Not Found'
    else:
        rslt = line.split()[3]
        return rslt


if __name__ == '__main__':

    found, abort, sw, switchport = main(sys.argv[1:])
    print found, abort, sw, switchport
    print """
To clarify the above possibly confusing output:
We found the device:                               {0}
We made it to the end of the list without finding
the device, deliberately kept looking, or had to
abort for some other reason:                       {1}
We believe the device is attached to switch:       {2}
On port:                                           {3}

We very much assume the device you're looking for is NOT a switch, or at least
doesn't report itself as such in CDP.  Also that any phones don't advertise
'switch' in CDP.
""".format(found, abort, sw, switchport)
