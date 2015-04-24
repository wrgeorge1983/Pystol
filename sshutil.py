'''
Created on Nov 13, 2014

Library of functions and classes to use in other scripts.

@author: William.George
'''
# Standard Library Imports
import getpass
import time
import multiprocessing
import socket
import re

# Imports from other scripts in this project
from metrics import UpdateMetric
from sshexecute import sshrunP
import sshexecute
from metrics import DebugPrint
import metrics


# TODO:  FIX THIS MESS
DEBUG = True
ARP_TABLE = []
DEFAULT_GATEWAY = None
CREDENTIALS = None  # SET THESE IN MAIN()!
CURRENT_SWITCH = None


def DedupilicateList(oList, tag=None):
    '''
        Given oList, search for duplicates.  If found, print
        information to screen to assist in troubleshooting

        TODO: this can easily be restructured using sets that I didn't know
        about when I first wrote it.
    '''
    nList = []
    for item in oList:
        if item in nList:
            index = nList.index(item)
            if DEBUG:
                print ('******\n{2}\nDuplicate Entry!!\nOld:{0}\nNew:{1}\n'
                       '******'.format(repr(nList[index]), repr(item), tag))
            nList[index] = item
        else:
            nList.append(item)
    return nList


def Listify(obj):
    """Return obj if it's already a list, package it in a list and return it if
    it's not.
    """
    if type(obj) == list:
        rslt = obj
    else:
        rslt = [obj]
    return rslt


def FormatMACAddress(oMac):
    """
        Ensure a MAC address (or fragment) is formatted consistent with the
        Cisco show commands.  If it's 4 characters, return it unmodified.
        If it's 12 or more characters, remove any '.' or '-', and format it
        'the Cisco Way'; return.
    """
    if oMac is None:
        return None
    elif len(oMac) == 4:
        rslt = oMac
    elif len(oMac) >= 12:
        wMac = oMac.replace('-', '')
        wMac = wMac.replace('.', '')
        rslt = '.'.join([wMac[:4], wMac[4:8], wMac[8:]])
    else:
        raise Exception('I don\'t know how to process this MAC Address!')
    return rslt.lower()


def FormatInterfaceName(oInterface, short=False):
    '''
       Ensure consistent formatting of interface names.
       long form unless short == True

       TODO: The whole way this works is dumb, and will match any string
       that starts with the letter 'e'.
    '''

    Formats = {
        'gi': ['Gi', 'GigabitEthernet'],
        'fa': ['Fa', 'FastEthernet'],
        'e':  ['E', 'Ethernet'],
        'vl': ['Vl', 'Vlan'],
        'se': ['Se', 'Serial'],
        'te': ['Te', 'TenGigabitEthernet'],
        'po': ['Po', 'Port-Channel'],
        'tu': ['Tu', 'Tunnel']
        }
    if oInterface in ['', None]:
        return oInterface

    iInterface = oInterface.lower()
    prefix = iInterface[:2]
    if prefix in Formats:
        lName = Formats[prefix][1]
        sName = Formats[prefix][0]
    elif prefix[0] in Formats:
        prefix = prefix[0]
        lName = Formats[prefix][1]
        sName = Formats[prefix][0]
    else:
        raise Exception(ValueError)

    buff = iInterface.strip(lName.lower())
    if short:
        nName = sName
    else:
        nName = lName
    nInterface = nName + buff

    return nInterface


def GetCredentials(user=None):
    '''
       Prompt user for password.  Use username if provided,
       otherwise, assume current logged in user.
    '''
    password = None
    if user is None or user == '':
        user = getpass.getuser()
    while password is None or password == '':
        password = getpass.getpass('Password:')
    return (user, password)


def DateTime():
    '''Return current time as dd/mm/yyyy - hh:mm:ss'''
    DTFormat = "%d/%m/%Y - %H:%M:%S"
    rslt = time.strftime(DTFormat)
    return rslt


def Date():
    '''Return current Date as dd/mm/yyyy'''
    DTFormat = "%d/%m/%Y"
    rslt = time.strftime(DTFormat)
    return rslt


class clEndDevice(object):
    """Represent an end device"""
    def __init__(self, mac=None, ip=None, switchport=None, switch=None,
                 dns=None):
        self.mac = mac
        self.ip = ip
        self._switch = switch
        self._switchport = switchport
        self.dns = dns

    def get_mac(self):
        return self._mac

    def set_mac(self, value):
        self._mac = FormatMACAddress(value)

    mac = property(get_mac, set_mac)

    def get_switchport(self):
        return self._switchport

    def set_switchport(self, port):  # could be clSwitchPort or str
        if not isinstance(self.switch, clSwitch):
            self._switchport = FormatInterfaceName(str(port))
            # if switch is str, this must also be str
            return
            # raise Exception('can\'t set \'clEndDevice({0}).switchport({1})\'
            # before .switch has a real object '.format(self,port))
        if type(port) == str:
            port = FormatInterfaceName(port)
            # if it's a string, make sure it's formatted properly
        # even if it's a string, we don't create an object yet, because it
        # could already be created and in place
        if port not in self.switch.ports:
            if type(port) == str:
                self.switch.ports += [clSwitchPort(name=port)]
            else:
                self.switch.ports += port
        index = self.switch.ports.index(port)
        devices = self.switch.ports[index].devices

        if self not in devices:
            devices += [self]
        self._switchport = self.switch.ports[index]
    switchport = property(get_switchport, set_switchport)

    def get_switch(self):
        return self._switch

    def set_switch(self, switch):
        # needs to be an actual clSwitch or None or String
        if type(switch) == str:
            self._switch = switch
            return
            # raise Exception('Need to pass an actual switch object to
            # clEndDevice.switch')
        self._switch = switch
        if self._switch is None:
            return
        devices = self.switch.devices
        if self not in devices:
            self.switch.devices += [self]
        else:
            self.switch.devices[self.switch.devices.index(self)] = self

    switch = property(get_switch, set_switch)

    def __repr__(self):
        return ('EndDevice(mac={0}, ip={1}, dns={2}, switch={3}, '
                'switchport={4})'.format(self.mac, self.ip, self.dns,
                                         self.switch, self.switchport))

    def __str__(self):
        return self.mac

    def __eq__(self, other):
        return (self.mac == str(other)) or (self.ip == str(other))

    def __ne__(self, other):
        return not (self == other)

    def __lt__(self, other):
        return NotImplemented

    def __le__(self, other):
        return NotImplemented

    def __ge__(self, other):
        return NotImplemented

    def __gt__(self, other):
        return NotImplemented


class clSwitch(object):
    '''
        represent a switch, contains clSwitchPorts and references
        to their clEndDevices
    '''
    def __init__(self, ip='None', creds=None):  # str ip
        self._ip = 'None'
        self.ip = ip
        self.ports = []
        self.devices = []
        self.CDPinformation = {}
        if not creds:
            raise SyntaxError('No Credentials Specified')
        self.credentials = creds
        self.goodstates = ['UNK', 'UP']
        self.state = 'UNK'  # valid states: ['UNK', 'UP', 'DOWN']
        self.model = 'UNK'
        self._MACAddressTable = ''
        self.connection = None

    def get_ports(self):
        return self._ports

    def set_ports(self, arg):
        if type(arg) == list:
            self._ports = arg
            i = 0
            while i < len(arg):
                if type(arg[i]) == str:
                    self.ports[i] = clSwitchPort(name=self.ports[i],
                                                 switch=self)
                elif (self.ports[i].switch != self):
                    self.ports[i].switch = self
                i += 1
        else:
            raise Exception('can\'t set \'clSwitch({0}).ports\''
                            'with {1}'.format(self, type(arg)))
    ports = property(get_ports, set_ports)

    def get_devices(self):
        return self._devices

    def set_devices(self, arg):
        if type(arg) == list:
            self._devices = arg
        else:
            raise Exception('can\'t set \'clSwitch({0}).devices\' with {1}'
                            ''.format(self, type(arg)))
    devices = property(get_devices, set_devices)

    def get_ip(self):
        return self._ip

    def set_ip(self, arg):
        if type(arg) == str:
            self._ip = arg
        else:
            raise Exception('can\'t set \'clSwitch({0}).ip\' to {1}'
                            ''.format(self, type(arg)))
    ip = property(get_ip, set_ip)

    def _Connect(self):
        if self.connection is None:
            self.connection = sshexecute.clSSHConnection(self.ip,
                                                         self.credentials,
                                                         True)

    def Execute(self, command, trim=True, timeout=1.5):
        """
        Connect to switch and execute 'command'
        """
        self._Connect()
        UpdateMetric('Switch.Execute')
        lines = self.connection.run(command=command,
                                    trim=trim,
                                    timeout=timeout)
        # ======================================================================
        # lines = sshrunP(command=command, host=self.ip,
        #                 creds=self.credentials, timeout=timeout)
        # ======================================================================
        return lines

    def Populate(self):
        """
        Run all of this switches 'collect' methods.  Typically faster
        than running them one by one at different times because you never
        have to rebuild the connection, etc...
        """
        metrics.DebugPrint('[{0}].Populate()'.format(self.ip))

        # need an IP and creds to start.
        if self.ip == 'None' or not self.credentials:
            metrics.DebugPrint('Attempt to populate switch data missing IP'
                               'and/or creds', 3)
            raise Exception('missing IP or creds')

        metrics.DebugPrint('[{0}]..GetInterfaces()'.format(self.ip))
        self.GetInterfaces()
        if self.state not in self.goodstates:
            metrics.DebugPrint('[{0}].Populate failed!  State: {1}'
                               ''.format(self.ip, self.state))
            return self.state

        metrics.DebugPrint('[{0}]..ClassifyPorts()'.format(self.ip))
        self.ClassifyPorts()

        metrics.DebugPrint('[{0}]..CollectCDPInformation()'.format(self.ip))
        self.CollectCDPInformation()

        metrics.DebugPrint('[{0}]..CollectMACAddressTable()'.format(self.ip))
        self.CollectMACAddressTable()

        metrics.DebugPrint('[{0}]..CollectInterfaceDescriptions()'
                           ''.format(self.ip))
        self.CollectInterfaceDescriptions()
        self.CollectVersion()

        return self.state

    def CollectMACAddressTable(self):
        """
        Connect to switch and pull MAC Address table
        """
        command = 'sh mac address-table'
        UpdateMetric('Switch.CollectMACAddressTable')
        lines = self.Execute(command)
        self._MACAddressTable = '\n'.join(
            [x for x in lines.splitlines() if 'dynamic' in x.lower()])

    def get_MACAddressTable(self):
        if not self._MACAddressTable:
            self.CollectMACAddressTable()
        table = self._MACAddressTable
        return table
    MACAddressTable = property(get_MACAddressTable)

    def GetInterfaces(self, data=False):
        '''
        Return all interfaces on a switch, including stats
        '''
        command = 'show interface'
        UpdateMetric('clSwitch.GetInterfaces')
        if not data:
            try:
                lines = self.Execute(command).splitlines()
            except:
                self.state = 'DOWN'
                return []
        else:
            lines = data.splitlines()
        self.state = 'UP'
        detail = []
        first = True
        for line in lines:
            try:
                FormatInterfaceName(line.split()[0], True)
            except Exception:
                pass
            else:
                if (not first and 'line protocol' in line):
                    port = clSwitchPort(detail=('\n'.join(detail)),
                                        switch=self)
                    self.ports.append(port)
                    detail = []
                else:
                    first = False
            detail.append(line)
        # Don't forget the last one...
        port = clSwitchPort(detail=('\n'.join(detail)), switch=self)
        self.ports.append(port)

    def CollectCDPInformation(self, data=False):
        '''
           Apply CDP neighbor information to self.ports[]
           ex. switch.ports[1].CDPneigh[0] == (
               NeighborID,
               NeighborIP,
               NeighborCapabilities,
               NieghborPort)
        '''
        command = 'sh cdp ne det'
        UpdateMetric('clSwitch.CollectCDPInformation')
        try:
            rBuffer = self.Execute(command)
        except:
            raise

        spLines = rBuffer.splitlines()
        CDPEntries = {}
        for line in spLines:
            # print line
            if line.split() == []:
                continue
            cat = line.split()[0].lower()
            if 'device' in cat:
                cdpid = ''.join(line.split()[2:])
            elif 'ip' == cat:
                ip = line.split()[2]
            elif 'platform' in cat:
                i = 0
                while i < len(line.split()):
                    word = line.split()[i]
                    if 'capabilit' in word.lower():
                        capindex = i + 1
                    i += 1
                caps = line.split()[capindex:]
            elif 'interface' in cat:
                interface = line.split()[1].strip(':,')
                neighborinterface = line.split()[-1]
                CDPEntries[interface.lower()] = (cdpid, ip, caps,
                                                 neighborinterface)

        for switchport in self.ports:
            if switchport.name.lower() in CDPEntries:
                switchport.CDPneigh.append(CDPEntries[switchport.name.lower()])
        self.CDPinformation = CDPEntries

    def CollectVersion(self, data=False):
        '''
           Pull Version info
        '''
        command = 'sh ver'
        UpdateMetric('clSwitch.CollectVersion')
        try:
            rBuffer = self.Execute(command)
        except:
            raise

        spLines = rBuffer.splitlines()
        lines = [line for line in spLines if 'WS' in line]
        if len(lines) < 1:
            self.model = 'UNK'
        else:
            line = lines[0]
            for word in line.split():
                if 'WS' in word:
                    self.model = word
                    break

    def ClassifyPorts(self, data=False):
        '''
            Classify ports by switchport mode.
            ('access', 'trunk')
        '''
        name = ''
        switchport = ''
        mode = ''
        command = 'sh int switchport'
        UpdateMetric('clSwitch.ClassifyPorts')
        if data:
            rBuffer = data.strip()
        else:
            if self.state not in self.goodstates:
                return
            try:
                rBuffer = self.Execute(command)
            except:
                raise

        spLines = rBuffer.splitlines()
        DebugPrint('clSwitch.ports: {0}'.format(self.ports))
        for line in spLines:
            if 'Name:' in line:
                name = FormatInterfaceName(line.split()[-1])
                switchport = ''
                mode = ''
            elif 'Switchport:' in line:
                switchport = line.split()[-1]
            elif 'Operational Mode:' in line:
                mode = line.split()[-1]
#                if switchport == 'Enabled' and mode == 'access':
                DebugPrint('Classifying {0}'.format(name))
                try:
                    i = self.ports.index(name)
                except:
                    DebugPrint('TRYING TO CLASSIFY PORT {0} THAT DOESN\'T'
                               ' EXIST ON {1}'.format(name, self.ip), 3)
                    continue
                port = self.ports[i]
                port.switchportMode = mode
                port.switchport = switchport

    def CollectInterfaceDescriptions(self, data=False):
        '''
            Apply existing interface descriptions to
            switch.ports[] ex. switch.ports[1].description = 'Trunk to
            ABQCore1'
        '''
        command = 'sh int description'
        UpdateMetric('CollectInterfaceDescriptions')
        if not (self.state in self.goodstates):
            return

        try:
            rBuffer = self.Execute(command)
        except:
            raise
        spLines = rBuffer.splitlines()[1:]
        for switchport in self.ports:
            name = FormatInterfaceName(str(switchport), short=True)
            try:
                line = next(x for x in spLines if name in x)
            except StopIteration:
                print 'Unexpected StopIteration!'
                print 'switch =', self.ip
                print 'Port = ', name
                print 'Data:'
                print spLines
                raise Exception('It Broke')

            spLine = re.split('\s\s+', line)
            if len(spLine) >= 4:
                description = '  '.join(spLine[3:]).strip()
            else:
                description = ''
            switchport.description = description

    def GetEndDevices(self):
        rslt = []
        scrubbedInterfaceList = []
        scrubbedMACAddressTable = []

        for port in self.ports:
            metrics.DebugPrint('[{0}].[{1}].edge:  {2}'.format(self.ip,
                                                               port.name,
                                                               port.edge))
            if port.edge:
                scrubbedInterfaceList.append(port)
        DebugPrint('[{0}].GetEndDevices.len(scrubbedInterfaceList): {1}'
                   ''.format(self.ip, len(scrubbedInterfaceList)), 1)
        DebugPrint('[{0}].GetEndDevices.scrubbedInterfaceList: {1}'
                   ''.format(self.ip, scrubbedInterfaceList), 0)

        macAddressTable = self.MACAddressTable
        DebugPrint('[{0}].GetEndDevices.len(macAddressTable): {1}'
                   ''.format(self.ip, len(macAddressTable.splitlines())), 1)
        DebugPrint('[{0}].GetEndDevices.macAddressTable: {1}'
                   ''.format(self.ip, macAddressTable), 0)

        for interface in scrubbedInterfaceList:
            for line in macAddressTable.splitlines():
                if line.strip().endswith(FormatInterfaceName(str(interface),
                                                             short=True)):
                    scrubbedMACAddressTable.append(line.strip())

        for line in scrubbedMACAddressTable:
            mac = FormatMACAddress(line.split()[1])
            port = line.split()[-1]
            ed = clEndDevice()
            ed.mac = mac
            ed.switch = self
            ed.switchport = port
            rslt.append(ed)
        rslt = DedupilicateList(rslt, 'returning from GetEndDevices')
        return rslt

    def __repr__(self):
        return ('Switch(ip={0}, Ports={1}, Devices={2})'
                ''.format(self.ip, len(self.ports), len(self.devices)))

    def __str__(self):
        return self.ip

    def __eq__(self, other):
        return (self.ip == str(other))

    def __ne__(self, other):
        return not (self == other)


class clSwitchPort(object):
    '''
        Represent ports attached to a clSwitch.  Contains
        clEndDevice objects and reference to its parent
        clSwitch.
    '''

    def __init__(self, name=None, switch=None, switchportMode=None,
                 detail=None):
        # str ip, clSwitch switch
        self.stats = {}
        self.switchportMode = switchportMode
        self.CDPneigh = []
        self.devices = []
        self.switch = switch
        self.switchport = ''
        self._detail = ''
        self.status = ''
        self.description = ''
        self._name = None
        if detail:
            self.detail = detail
        else:
            self.name = name
        self._edge = True

    def get_CDPneigh(self):
        return self._CDPneigh

    def set_CDPneigh(self, arg):
        if type(arg) == list or arg is None:
            self._CDPneigh = arg
        else:
            raise Exception('can\'t set \'clSwitchPort({0}).CDPneigh\' with '
                            '{1}'.format(self, type(arg)))
    CDPneigh = property(get_CDPneigh, set_CDPneigh)

    def get_devices(self):
        return self._devices

    def set_devices(self, arg):
        if type(arg) == list:
            self._devices = arg
            i = 0
            while i < len(arg):
                if type(self.devices[i]) == str:
                    self.devices[i] = clEndDevice(mac=self.devices[i],
                                                  switch=self)
                elif (self.devices[i].swtich != self):
                    self.devices[i].switch = self
                i += 1
        else:
            raise Exception('can\'t set \'clSwitchPort({0}).devices\' with '
                            '{1}'.format(self, type(arg)))
    devices = property(get_devices, set_devices)

    def get_name(self):
        return self._name

    def set_name(self, value):
        if value is None:
            self._name = value
        else:
            self._name = FormatInterfaceName(value)
    name = property(get_name, set_name)

    def get_switchportMode(self):
        if self._switchportMode:
            return self._switchportMode
        else:
            return 'access'

    def set_switchportMode(self, value):
        if type(value) == str:
            value = value.lower()

        if value in ('access', 'trunk', None):
            self._switchportMode = value
        else:
            self._switchportMode = 'unknown'
    switchportMode = property(get_switchportMode, set_switchportMode)

    def get_detail(self):
        return self._detail

    def set_detail(self, value):
        UpdateMetric('SwitchportSetDetail')
        if type(value) is not str and not (len(value) > 0):
            raise Exception('can\'t set \'clSwitchPort({0}).detail with '
                            '{1}'.format(self, type(value)))

        self._detail = value
        lines = value.strip().splitlines()
        try:
            for line in lines:
                lsplit = line.split()
                if 'line protocol' in line:
                    self.name = line.split()[0]
                    status = [x.lower() for x in line.split()
                              if x.lower() in ['up', 'down']][-1]
                    self.status = status
                elif 'Last clearing of' in line:
                    self.stats['StatDuration'] = lsplit[-1]
                elif '5 minute input' in line:
                    self.stats['5MinInputBPS'] = int(lsplit[4])
                    self.stats['5MinInputPPS'] = int(lsplit[-2])
                elif '5 minute output' in line:
                    self.stats['5MinOutputBPS'] = int(lsplit[4])
                    self.stats['5MinOutputPPS'] = int(lsplit[-2])
                elif 'packets input' in line:
                    self.stats['InputPackets'] = int(lsplit[0])
                    self.stats['InputBytes'] = int(lsplit[3])
                elif 'packets output' in line:
                    self.stats['OutputPackets'] = int(lsplit[0])
                    self.stats['OutputBytes'] = int(lsplit[3])
                elif 'input errors' in line:
                    self.stats['InputErrors'] = int(lsplit[0])
                elif 'output errors' in line:
                    self.stats['OutputErrors'] = int(lsplit[0])
                elif 'Description:' in line:
                    self.description = ' '.join(lsplit[1:])
        except Exception as e:
            print self._detail
            raise e
    detail = property(get_detail, set_detail)

    def _get_edge(self, CDPneigh=[], switchportMode='access'):
        '''
            'edge' in this context means
            'not connected to a switch or router, determined via CDP'
            AND
            'switchport mode == access'
        '''
        for neighbor in CDPneigh:
            nlist = ' '.join(neighbor[2]).lower()
            if (('switch' in nlist) or
                    ('router' in nlist)):
                return False

        if not (switchportMode.lower() in ['access', 'unknown']):
            return False
        else:
            return True

    def get_edge(self):
        return self._get_edge(self.CDPneigh, self.switchportMode)
    edge = property(get_edge)

    def __repr__(self):
        return ('SwitchPort(Name={0}, Switch={1}, switchportMode={2},'
                'CDPneigh={3}, Devices={4})'
                ''.format(self.name, self.switch, self.switchportMode,
                          len(self.CDPneigh), len(self.devices)))

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return (self.name == str(other))

    def __ne__(self, other):
        return not (self == other)


def ProcessEndDevices(switches, creds=None, defaultgateway=None, maxThreads=1):
    '''
        call GetEndDevices for given host(s), resolve IPs and DNS information
        return list
    '''
    metrics.DebugPrint('sshutil.py:ProcessEndDevices()', 2)
    metrics.DebugPrint('::hosts:{0}\n::defaultgateway:{1}\n::maxThreads:{2}'
                       ''.format(switches, defaultgateway, maxThreads), 1)
    global CREDENTIALS
    global CURRENT_SWITCH
    global DEFAULT_GATEWAY
    if defaultgateway is None:
        defaultgateway = DEFAULT_GATEWAY
    else:
        DEFAULT_GATEWAY = defaultgateway
    # if defaultgateway is None:
    #     raise Exception('No Default Gateway!')

    endDevices = []
    switches = Listify(switches)

    if creds is None:
        creds = CREDENTIALS
    else:
        CREDENTIALS = creds

    for switch in switches:
        DebugPrint('Collecting End Devices from: {0}'
                   ''.format(str(switch)), 2)
        endDevices += switch.GetEndDevices()
        DebugPrint('ProcessEndDevices.{0}.endDevices: {1}'
                   ''.format(str(switch), str(endDevices)), 0)

    if (endDevices is None) or len(endDevices) == 0:
        DebugPrint('ProcessEndDevices.NoEndDevicesFound!', 3)
        return []

    if defaultgateway is None:
        DebugPrint('No default gateway.  Skipping IP and DNS resolution!', 3)
        return endDevices

    DebugPrint('Resolving MAC addresses', 2)
    for endDevice in endDevices:
        endDevice.ip = ResolveMAC(endDevice.mac)

    DebugPrint('Resolving DNS names', 2)
    ResolveIPsMT(endDevices, maxThreads)
    return endDevices


def ResolveIP(ip):
    '''
        Given an IP address, return appropriate DNS entry, if any
    '''
    try:
        DebugPrint('Resolving IP: ' + str(ip), 0)
        dns = (socket.gethostbyaddr(ip))[0]
    except:
        dns = ''
    return dns


def ResolveIPsMT(endDevices, maxThreads=4):

    '''
        Given list of clEndDevices, use pool of subprocesses
        (count determined by MAX_THREADS) to call ResolveIP()
    '''
    ips = []
    dns = []
    DebugPrint('ResolveIPsMT.maxThreads: ' + str(maxThreads))
    DebugPrint('ResolveIPsMT.endDevices: ' + str(endDevices), 0)
    for ed in endDevices:
        ips.append(ed.ip)
    DebugPrint('ResolveIPsMT.IPs: ' + str(ips), 0)
    pool_size = maxThreads
    pool = multiprocessing.Pool(processes=pool_size)
    dns = pool.map(ResolveIP, ips)
    pool.close()
    pool.join()
    for n in range(len(ips)):
        if ips[n] == endDevices[n].ip:  # sanity check
            endDevices[n].dns = dns[n]
        else:
            DebugPrint('Sanity Check failed during ResolveIPsMT()', 3)
            pass


def GetMACAddressTable(host=None, interface=None):
    '''
        Returns either the entire MAC address table, or entries
        for an individual interface, depending upon input
    '''
    if host is None:
        if CURRENT_SWITCH is None:
            raise Exception('CURRENT_SWITCH not set!')
        else:
            host = CURRENT_SWITCH

    command = 'sh mac address-table'
    if interface is not None:
        command += ' int {0}'.format(interface)
    # command += ' | inc dynamic'

    UpdateMetric('GetMacAddressTable')
    try:
        lines = sshrunP(command=command, host=host, creds=CREDENTIALS)
    except:
        return []
    return '\n'.join([x for x in lines.splitlines() if 'dynamic' in x.lower()])


def ClassifyPorts(host=None):
    '''
        Given host, return list of ports that are:
        UP, UP, and switchport mode access
    '''
    if host is None:
        if CURRENT_SWITCH is None:
            raise Exception('CURRENT_SWITCH not set!')
        else:
            host = CURRENT_SWITCH

    name = ''
    switchport = ''
    mode = ''
    ports = []
    command = 'sh int switchport'
    UpdateMetric('ClassifyPort')
    try:
        rBuffer = sshrunP(command=command, host=host, creds=CREDENTIALS)
    except:
        raise
    spLines = rBuffer.splitlines()
    for line in spLines:
        if 'Name:' in line:
            name = line.split()[-1]
        elif 'Switchport:' in line:
            switchport = line.split()[-1]
        elif 'Operational Mode:' in line:
            mode = line.split()[-1]
            if switchport == 'Enabled' and mode == 'access':
                ports.append(FormatInterfaceName(name))
    return ports


def ResolveMAC(mac=None, defaultgateway=None, ip=None, creds=None):
    '''
        Given a MAC or IP address and the appropriate subnet default gateway,
        SSH into the default gateway and use arp table to resolve between MAC
        and IP
    '''
    lines = []
    command = 'sh arp'
    global ARP_TABLE
    if defaultgateway is None:
        defaultgateway = DEFAULT_GATEWAY
    if defaultgateway is None:
        raise Exception('Default Gateway not set!')
    if creds is None:
        creds = CREDENTIALS
    if not (mac or ip):
        raise Exception('No MAC or IP Address specified to resolve!')
    # DebugPrint('ResolveMAC.defaultgateway: ' + str(defaultgateway))
    # DebugPrint('ResolveMAC.creds[0]: ' + creds[0])
    if ARP_TABLE == []:
        UpdateMetric('ResolveMAC')
        try:
            ARP_TABLE = sshrunP(command=command, host=defaultgateway,
                                creds=creds)
        except:
            DebugPrint("Couldn't pull ARP Table from gw: {0}"
                       "".format(defaultgateway), 3)
            return "Not Found"

        # print 'looking for' , mac , 'in\n', ARP_TABLE
    target = mac or ip
    lines = [l for l in ARP_TABLE.splitlines() if target in l]

    if lines == [] or lines[0] == '':
        return "Not Found"
    else:
        if mac:
            rslt = lines[0].split()[1]
        else:
            rslt = lines[0].split()[3]
        return rslt
