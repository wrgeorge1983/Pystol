"""Library of classes and functions for managing
Created on Nov 13, 2014

Library of functions and classes to use in other scripts.

@author: William.George
"""
# Standard Library Imports

from collections import namedtuple
import getpass
from itertools import product, chain
import json
import time
import multiprocessing
import socket
import re

# Imports from other scripts in this project
from metrics import UpdateMetric
from depreciated.dep_sshexecute import sshrunP
import sshexecute
from metrics import DebugPrint
import metrics


# TODO:  FIX THIS MESS
DEBUG = True
ARP_TABLE = []
DEFAULT_GATEWAY = None
CREDENTIALS = None  # SET THESE IN MAIN()!
CURRENT_SWITCH = None

FlashSpace = namedtuple('FlashSpace', 'free, total')


def deduplicate_list(oList, tag=None):
    """Given oList, search for duplicates.
    If found, print information to screen to assist in troubleshooting

    """
    nList = []
    for item in oList:
        if item in nList:
            index = nList.index(item)
            if DEBUG:
                print('******\n{2}\nDuplicate Entry!!\nOld:{0}\nNew:{1}\n'
                      '******'.format(repr(nList[index]), repr(item), tag))
            nList[index] = item
        else:
            nList.append(item)
    return nList


def listify(obj):
    """Return obj if it's already a list, package it in a list and return it if
    it's not.
    """
    if type(obj) == list:
        rslt = obj
    else:
        rslt = [obj]
    return rslt


def format_mac_address(oMac):
    """Ensure a MAC address (or fragment) is formatted consistent with the
    
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


def format_interface_name(oInterface, short=False):
    """
       Ensure consistent formatting of interface names.
       long form unless short == True
    """
    # TODO: The whole way this works is dumb, and will match any string that starts with the letter 'e'.

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


def get_credentials(user=None):
    """
       Prompt user for password.  Use username if provided,
       otherwise, assume current logged in user.
    """
    password = None
    if user is None or user == '':
        user = getpass.getuser()
    while password is None or password == '':
        password = getpass.getpass('Password:')
    return (user, password)


def DateTime():
    """Return current time as dd/mm/yyyy - hh:mm:ss"""
    DTFormat = "%d/%m/%Y - %H:%M:%S"
    rslt = time.strftime(DTFormat)
    return rslt


def Date():
    """Return current Date as dd/mm/yyyy"""
    DTFormat = "%d/%m/%Y"
    rslt = time.strftime(DTFormat)
    return rslt


class EndDevice(object):
    """Represent an end device"""
    def __init__(self, mac=None, ip=None, switchport=None, switch=None,
                 dns=None):
        self.mac = mac
        self.ip = ip
        self._switch = switch
        self._switchport = switchport
        self.dns = dns

    @property
    def mac(self):
        return self._mac

    @mac.setter
    def mac(self, value):
        self._mac = format_mac_address(value)

    @property
    def switchport(self):
        return self._switchport

    @switchport.setter
    def switchport(self, port):  # could be SwitchPort or str
        if not isinstance(self.switch, Switch):
            self._switchport = format_interface_name(str(port))
            # if switch is str, this must also be str
            return
            # raise Exception('can\'t set \'EndDevice({0}).switchport({1})\'
            # before .switch has a real object '.format(self,port))
        if type(port) == str:
            port = format_interface_name(port)
            # if it's a string, make sure it's formatted properly
        # even if it's a string, we don't create an object yet, because it
        # could already be created and in place
        if port not in self.switch.ports:
            if type(port) == str:
                self.switch.ports += [SwitchPort(name=port)]
            else:
                self.switch.ports += port
        index = self.switch.ports.index(port)
        devices = self.switch.ports[index].devices

        if self not in devices:
            devices += [self]
        self._switchport = self.switch.ports[index]

    @property
    def switch(self):
        return self._switch

    @switch.setter
    def switch(self, switch):
        # needs to be an actual Switch or None or String
        if type(switch) == str:
            self._switch = switch
            return
            # raise Exception('Need to pass an actual switch object to
            # EndDevice.switch')
        self._switch = switch
        if self._switch is None:
            return
        devices = self.switch.devices
        if self not in devices:
            self.switch.devices += [self]
        else:
            self.switch.devices[self.switch.devices.index(self)] = self

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


class NetworkDevice(object):

    prompt_test = lambda _, x: False

    def __init__(self, ip='None', creds=None):  # str ip
        self._ip = 'None'
        self.ip = ip
        if creds is None:
            raise SyntaxError('No Credentials Specified')
        self.credentials = creds
        self.goodstates = ['UNK', 'UP']
        self.state = 'UNK'  # valid states: ['UNK', 'UP', 'DOWN']
        self.connection = None
        self.data = {}

    @property
    def ip(self):
        return self._ip

    @ip.setter
    def ip(self, arg):
        # TODO: implement ipaddress class, at that time evaluate permitting integer values
        if type(arg) in [str, type(None)]:
            self._ip = str(arg)
        else:
            raise Exception('can\'t set \'Switch({0}).ip\' to {1}'
                            ''.format(self, type(arg)))

    def _connect(self):
        if self.connection is None:
            self.connection = sshexecute.SSHConnection(self.ip,
                                                         self.credentials,
                                                         True)
        self.connection.prompt_test = self.prompt_test

    def execute(self, command, trim=True, timeout=1.5):
        """
                    INTERFACED: FALSE

        Connect to switch and execute 'command'
        """
        self._connect()
        UpdateMetric('Switch.execute')
        try:
            lines = self.connection.run(command=command,
                                        trim=trim,
                                        timeout=timeout)
        except Exception:
            self.state = 'DOWN'
            raise
        else:
            self.state = 'UP'
            return lines

    def ifce_execute(self, command, trim=True, timeout=1.5, data=None, force=False):
        """
        INTERFACED: TRUE

        Connect to remote device and execute 'command'
        """
        if data is None:
            data = {}

        data_cm = dict(chain(self.data.items(), data.items()))

        try:
            if force:
                raise KeyError
            e_rslt = self.data[command] = data_cm[command]
        except KeyError:
            e_rslt = self.data[command] = self.execute(command)
        return e_rslt

    def jloads(self, jsons):
        data = json.loads(jsons)
        self.data.update(data)
        return data

    def jdumps(self):
        data = self.data
        return json.dumps(data)



class Riverbed(NetworkDevice):
    pass


class Switch(NetworkDevice):
    """
        represent a switch, contains clSwitchPorts and references
        to their clEndDevices
    """
    def __init__(self, ip='None', creds=None):  # str ip
        NetworkDevice.__init__(self, ip, creds)
        self.ports = []
        self.devices = []
        self.cdp_information = {}
        self._mac_address_table = ''
        self.populate_lite_time = None

    @property
    def hostname(self):
        """
        INTERFACED: Safe
        Cisco Specific
        :return:
        """
        if not self.supported:
            return 'UNK'

        for line in self.startup_config.splitlines():
            if 'hostname' in line:
                return line.split()[-1]
        return ''

    @property
    def supervisor(self, data=False):
        """
        INTERFACED: TRUE
        Cisco Specific
        :return:
        """
        # cache check

        try:
            _supervisor = self._supervisor
        except AttributeError:
            _supervisor = self._supervisor = self._collect_supervisor()

        return _supervisor

    def _collect_supervisor(self, data=None, force=False):
        """
        INTERFACED: TRUE
        :param data:
        :return:
        """

        _supervisor = 'UNK'

        # support check
        if not self.supported:
            return _supervisor

        # data check
        command = 'show module'
        e_rslt = self.ifce_execute(command)

        # process data
        for line in e_rslt.splitlines():
            if 'supervisor' in line.lower():
                _supervisor = line.split()[-2]

        return _supervisor

    @property
    def flash(self):
        """
        INTERFACED: True
        Cisco Specific
        :return:
        """
        try:
            _flash = self._flash
        except AttributeError:
            _flash = self._flash = self._collect_flash()

        return _flash

    def _collect_flash(self, data=None, force=False):
        """
        INTERFACED: TRUE
        :param data:
        :return:
        """
        _flash = 'UNK'

        # support check
        if not self.supported:
            return _flash

        command = 'dir'
        e_rslt = self.ifce_execute(command)


        if any([word in e_rslt.lower() for word in ('invalid', 'error')]):
            return _flash

        e_rslt = e_rslt.splitlines()[-1]

        # FlashSpace(free=xxxx, total=yyyy)

        fs = FlashSpace(*reversed([int(sub.split()[0]) for sub in e_rslt.split('(')]))

        _flash = self._flash = fs
        return _flash

    @property
    def available_ram(self):
        """
        INTERFACED: SAFE
        Cisco Specific
        :return:
        """
        if not self.supported:
            return 'UNK'

        regex = re.compile(r'[^K/0-9.]').search
        search = lambda x: 'K' in x and not bool(regex(x))
        # looking for '#####K' or '#####K/#####K' etc.
        for line in self.version.splitlines():
            if 'bytes of memory' in line or \
                    'bytes of physical memory' in line:
                for word in line.split():
                    if search(word):
                        break
                break
        else:
            return ''
        word = word.split('/')
        add = lambda x, y: x + int(y.strip('K'))
        rslt = reduce(add, word, 0)
        return rslt

    @property
    def model(self):
        """
        INTERFACED: SAFE
        Deduces this switches model number from 'sh ver' output.
        This will fail gracefully to 'UNK', but 'Switch.supported' will return False in
            this case and many features will refuse to run.
        :return:
        """
        if self.state == 'UP':
            for line in self.version.splitlines():
                if 'bytes of' in line.lower():
                    return line.split()[1]
        return 'UNK'

    @property
    def supported(self):
        """
        INTERFACED: SAFE
        """
        if self.model == 'UNK':
            return False

        return True

    @property
    def stacked(self):
        """
        INTERFACED: SAFE
        whether or not the switch represents or is a member of a stack
        :return: bool
        """
        if not self.supported:
            return 'UNK'

        version = self.version
        stackable = False
        stacklines = []
        for index, line in enumerate(version.splitlines()):
            if stackable:
                if not line:
                    break
                elif '-' in line.split()[0]:
                    continue
                stacklines.append(line)
                continue
            if 'switch ports model' in line.lower():
                stackable = True

        if len(stacklines) > 1:
            return True
        return False

    @property
    def license(self):
        """
        INTERFACED: SAFE
        """
        if not self.supported:
            return 'UNK'

        try:
            return self._license
        except AttributeError:
            self._collect_license()
            return self._license

    def _collect_license(self):
        """

        INTERFACED: SAFE
        :return:
        """

        regex = re.compile(r'\(..*\),')

        try:
            word = regex.findall(self.version)[0]
        except IndexError:
            word = 'UNK'
        else:
            # sanity checks, if we're not sure, just suppress.
            for char in ['(', ')', ',']:
                if word.count(char) > 1:
                    word = 'UNK'
                    break
            else:
                word = word.split('-')[1]
                if 'UNIVERSAL' in word.upper():
                    rslt = self._read_universal_license()
                    word = '{0} ({1})'.format(word, rslt)

        self._license = word

    def _read_universal_license(self):
        """
        INTERFACED: TRUE
        Will return string in form: "(featureset, featureset)" if multiple valid
        featuresets found.  Otherwise "featureset".
        :return:
        """
        sh_license = self.ifce_execute('sh license')
        index = 0
        licenses = {}
        rslts = []

        if '% Incomplete' in sh_license:
            license_options = self.ifce_execute('sh license ?')

            if 'summary' in license_options:
                sh_license = self.ifce_execute('sh license summary')
            elif 'right-to-use' in license_options:
                rtu = self.ifce_execute('sh license right-to-use')
                for line in rtu.splitlines():
                    if 'permanent' in line:
                        return line.split()[1]
                # return 'UNK'
                raise Exception(rtu)

        for line in sh_license.splitlines():
            words = [word.strip() for word in line.split(':')]
            if line.startswith('Index'):
                index = words[0].split()[1]
                feature = words[-1]
                licenses[index] = {'feature': feature}
                continue
            licenses[index][words[0].lower()] = words[-1]

        for license in licenses.values():
            t_words = {'License State': 'active', 'License Type': 'permanent'}  # words to test for, all must hit

            for key, value in t_words.items():
                if value not in license.get(key.lower(), '').lower():
                    break
            else:
                rslts.append(license['feature'])

        if len(rslts) == 1:
            return rslts[0]
        elif len(rslts) > 1:
            return str(rslts)
        else:
            return 'UNK'

    @property
    def software_version(self):
        """
            INTERFACED: True """
        if not self.supported:
            return 'UNK'

        _sw_version = getattr(self, '_sw_version', None)
        if _sw_version is not None:
            return _sw_version

        version = self.version
        if 'IOS-XE' in version:
            regex = re.compile(r'Version.*RELEASE')
        else:
            regex = re.compile(r'Version.*,')

        _sw_version = regex.findall(self.version)[0].strip(',').split()[1]
        self._sw_version = _sw_version
        return _sw_version

    @property
    def version(self):
        """
        INTERFACED: TRUE
        Cisco Specific
        :return:
        """
        try:
            return self._version
        except AttributeError:
            self._collect_version()
            return self._version

    @property
    def startup_config(self):
        """
        INTERFACED: TRUE
        Cisco Specific
        :return:
        """
        try:
            return self._startup_config
        except AttributeError:
            self._collect_startup_config()
            return self._startup_config

    def _collect_startup_config(self):
        """
        INTERFACED: TRUE
        Cisco Specific
        :return:
        """
        self._startup_config = self.ifce_execute('show startup-config')

    def _collect_version(self, data=False):
        """
            INTERFACED: TRUE
           Pull Version info
        """
        command = 'sh ver'
        UpdateMetric('Switch._collect_version')
        try:
            rBuffer = self.ifce_execute(command)
        except:
            raise

        self._version = rBuffer

    @property
    def ports(self):
        """

            INTERFACED: TRUE
        :return:
        """
        return self._ports

    @ports.setter
    def ports(self, arg):
        """
        INTERFACED: TRUE
        """
        if type(arg) == list:
            self._ports = arg
            i = 0
            while i < len(arg):
                if isinstance(arg[i], basestring):
                    self.ports[i] = SwitchPort(name=self.ports[i],
                                                 switch=self)
                elif (self.ports[i].switch != self):
                    self.ports[i].switch = self
                i += 1
        else:
            raise Exception('can\'t set \'Switch({0}).ports\''
                            'with {1}'.format(self, type(arg)))

    @property
    def devices(self):
        """
        INTERFACED: TRUE
        """
        return self._devices

    @devices.setter
    def devices(self, arg):
        """
        INTERFACED: TRUE
        """
        if type(arg) == list:
            self._devices = arg
        else:
            raise Exception('can\'t set \'Switch({0}).devices\' with {1}'
                            ''.format(self, type(arg)))

    def populate(self):
        """
        INTERFACED: TRUE
        Run all of this switches 'collect' methods.  Typically faster
        than running them one by one at different times because you never
        have to rebuild the connection, etc...
        """
        metrics.DebugPrint('[{0}].populate()'.format(self.ip))

        # need an IP and creds to start.
        if self.ip == 'None' or not self.credentials:
            metrics.DebugPrint('Attempt to populate switch data missing IP'
                               'and/or creds', 3)
            raise Exception('missing IP or creds')

        metrics.DebugPrint('[{0}].._get_interfaces()'.format(self.ip))
        self._get_interfaces()
        if self.state not in self.goodstates:
            metrics.DebugPrint('[{0}].populate failed!  State: {1}'
                               ''.format(self.ip, self.state))
            return self.state

        metrics.DebugPrint('[{0}].._classify_ports()'.format(self.ip))
        self._classify_ports()

        metrics.DebugPrint('[{0}].._collect_cdp_information()'.format(self.ip))
        self._collect_cdp_information()

        metrics.DebugPrint('[{0}]..collect_mac_table()'.format(self.ip))
        self.collect_mac_table()

        metrics.DebugPrint('[{0}].._collect_interface_descriptions()'
                           ''.format(self.ip))
        self._collect_interface_descriptions()
        self._collect_version()

        return self.state

    def populate_lite(self):
        """
        INTERFACED: TRUE
        """

        if self.ip == 'None' or not self.credentials:
            metrics.DebugPrint('Attempt to populate switch data missing IP'
                               'and/or creds', 3)
            raise Exception('missing IP or creds')

        start_time = time.time()
        self._collect_startup_config()
        self._collect_version()
        self._collect_license()
        self.populate_lite_time = time.time() - start_time
        _ = self.flash
        _ = self.supervisor

    def collect_mac_table(self):
        """
        INTERFACED: TRUE
        Connect to switch and pull MAC Address table
        """
        command = 'sh mac address-table'
        UpdateMetric('Switch.collect_mac_table')
        lines = self.ifce_execute(command)
        self._mac_address_table = '\n'.join(
            [x for x in lines.splitlines() if 'dynamic' in x.lower()])

    @property
    def mac_table(self):
        if not self._mac_address_table:
            self.collect_mac_table()
        table = self._mac_address_table
        return table

    def _get_interfaces(self, data=False):
        """
        INTERFACED: TRUE
        Return all interfaces on a switch, including stats
        """
        command = 'show interface'
        UpdateMetric('Switch._get_interfaces')
        if not data:
            try:
                lines = self.ifce_execute(command).splitlines()
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
                format_interface_name(line.split()[0], True)
            except Exception:
                pass
            else:
                if (not first and 'line protocol' in line):
                    port = SwitchPort(detail=('\n'.join(detail)),
                                        switch=self)
                    self.ports.append(port)
                    detail = []
                else:
                    first = False
            detail.append(line)
        # Don't forget the last one...
        port = SwitchPort(detail=('\n'.join(detail)), switch=self)
        self.ports.append(port)

    def _collect_cdp_information(self, data=False):
        """
        INTERFACED: TRUE
           Apply CDP neighbor information to self.ports[]
           ex. switch.ports[1].CDPneigh[0] == (
               NeighborID,
               NeighborIP,
               NeighborCapabilities,
               NieghborPort)
        """
        command = 'sh cdp ne det'
        UpdateMetric('Switch._collect_cdp_information')
        try:
            rBuffer = self.ifce_execute(command)
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
        self.cdp_information = CDPEntries

    def _classify_ports(self, data=False):
        """
        INTERFACED: TRUE
        Classify ports by switchport mode.
        ('access', 'trunk')
        """
        name = ''
        switchport = ''
        mode = ''
        command = 'sh int switchport'
        UpdateMetric('Switch._classify_ports')
        if data:
            rBuffer = data.strip()
        else:
            if self.state not in self.goodstates:
                return
            try:
                rBuffer = self.ifce_execute(command)
            except:
                raise

        spLines = rBuffer.splitlines()
        DebugPrint('Switch.ports: {0}'.format(self.ports))
        for line in spLines:
            if 'Name:' in line:
                name = format_interface_name(line.split()[-1])
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

    def _collect_interface_descriptions(self, data=False):
        """
        INTERFACED: TRUE
        Apply existing interface descriptions to
        switch.ports[] ex. switch.ports[1].description = 'Trunk to
        ABQCore1'
        """
        command = 'sh int description'
        UpdateMetric('_collect_interface_descriptions')
        if not (self.state in self.goodstates):
            return

        try:
            rBuffer = self.ifce_execute(command)
        except:
            raise
        spLines = rBuffer.splitlines()[1:]
        for switchport in self.ports:
            name = format_interface_name(str(switchport), short=True)
            try:
                line = next(x for x in spLines if name in x)
            except StopIteration:
                #print 'Unexpected StopIteration!'
                #print 'switch =', self.ip
                #print 'Port = ', name
                #print 'Data:'
                #print spLines
                raise Exception('Failure in _collect_interface_descriptions')

            spLine = re.split('\s\s+', line)
            if len(spLine) >= 4:
                description = '  '.join(spLine[3:]).strip()
            else:
                description = ''
            switchport.description = description

    def _get_end_devices(self):
        """
        INTERFACED: TRUE
        """
        rslt = []
        scrubbedInterfaceList = []
        scrubbedMACAddressTable = []

        for port in self.ports:
            metrics.DebugPrint('[{0}].[{1}].edge:  {2}'.format(self.ip,
                                                               port.name,
                                                               port.edge))
            if port.edge:  # INTERFACED: FALSE
                scrubbedInterfaceList.append(port)
        DebugPrint('[{0}]._get_end_devices.len(scrubbedInterfaceList): {1}'
                   ''.format(self.ip, len(scrubbedInterfaceList)), 1)
        DebugPrint('[{0}]._get_end_devices.scrubbedInterfaceList: {1}'
                   ''.format(self.ip, scrubbedInterfaceList), 0)

        macAddressTable = self.mac_table
        DebugPrint('[{0}]._get_end_devices.len(macAddressTable): {1}'
                   ''.format(self.ip, len(macAddressTable.splitlines())), 1)
        DebugPrint('[{0}]._get_end_devices.macAddressTable: {1}'
                   ''.format(self.ip, macAddressTable), 0)

        for interface, line in product(scrubbedInterfaceList,
                                       macAddressTable.splitlines()):
            if line.strip().endswith(format_interface_name(str(interface),
                                                         short=True)):
                scrubbedMACAddressTable.append(line.strip())

        for line in scrubbedMACAddressTable:
            mac = format_mac_address(line.split()[1])
            port = line.split()[-1]
            ed = EndDevice()
            ed.mac = mac
            ed.switch = self
            ed.switchport = port
            rslt.append(ed)
        rslt = deduplicate_list(rslt, 'returning from _get_end_devices')
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


class SwitchPort(object):
    """
        Represent ports attached to a Switch.  Contains
        EndDevice objects and reference to its parent
        Switch.
    """

    def __init__(self, name=None, switch=None, switchportMode=None,
                 detail=None):
        # str ip, Switch switch
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

    @property
    def CDPneigh(self):
        return self._CDPneigh

    @CDPneigh.setter
    def CDPneigh(self, arg):
        if type(arg) == list or arg is None:
            self._CDPneigh = arg
        else:
            raise Exception('can\'t set \'SwitchPort({0}).CDPneigh\' with '
                            '{1}'.format(self, type(arg)))

    @property
    def devices(self):
        return self._devices

    @devices.setter
    def devices(self, arg):
        if type(arg) == list:
            self._devices = arg
            i = 0
            while i < len(arg):
                if type(self.devices[i]) == str:
                    self.devices[i] = EndDevice(mac=self.devices[i],
                                                  switch=self)
                elif (self.devices[i].swtich != self):
                    self.devices[i].switch = self
                i += 1
        else:
            raise Exception('can\'t set \'SwitchPort({0}).devices\' with '
                            '{1}'.format(self, type(arg)))

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if value is None:
            self._name = value
        else:
            self._name = format_interface_name(value)

    @property
    def switchportMode(self):
        if self._switchportMode:
            return self._switchportMode
        else:
            return 'access'

    @switchportMode.setter
    def switchportMode(self, value):
        if type(value) == str:
            value = value.lower()

        if value in ('access', 'trunk', None):
            self._switchportMode = value
        else:
            self._switchportMode = 'unknown'

    @property
    def detail(self):
        return self._detail

    @detail.setter
    def detail(self, value):
        UpdateMetric('SwitchportSetDetail')
        if type(value) is not str and not (len(value) > 0):
            raise Exception('can\'t set \'SwitchPort({0}).detail with '
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
            #print self._detail
            raise e

    def _get_edge(self, CDPneigh=[], switchportMode='access'):
        """
            'edge' in this context means
            'not connected to a switch or router, determined via CDP'
            AND
            'switchport mode == access'
        """
        for neighbor in CDPneigh:
            nlist = ' '.join(neighbor[2]).lower()
            if (('switch' in nlist) or
                    ('router' in nlist)):
                return False

        if not (switchportMode.lower() in ['access', 'unknown']):
            return False
        else:
            return True

    @property
    def edge(self):
        return self._get_edge(self.CDPneigh, self.switchportMode)

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


def process_end_devices(switches, creds=None, defaultgateway=None, maxThreads=1):
    """
        call _get_end_devices for given host(s), resolve IPs and DNS information
        return list
    """
    metrics.DebugPrint('sshutil.py:process_end_devices()', 2)
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
    switches = listify(switches)

    if creds is None:
        creds = CREDENTIALS
    else:
        CREDENTIALS = creds

    for switch in switches:
        DebugPrint('Collecting End Devices from: {0}'
                   ''.format(str(switch)), 2)
        endDevices += switch._get_end_devices()
        DebugPrint('process_end_devices.{0}.endDevices: {1}'
                   ''.format(str(switch), str(endDevices)), 0)

    if (endDevices is None) or len(endDevices) == 0:
        DebugPrint('process_end_devices.NoEndDevicesFound!', 3)
        return []

    if defaultgateway is None:
        DebugPrint('No default gateway.  Skipping IP and DNS resolution!', 3)
        return endDevices

    DebugPrint('Resolving MAC addresses', 2)
    for endDevice in endDevices:
        endDevice.ip = resolve_mac(endDevice.mac)

    DebugPrint('Resolving DNS names', 2)
    resolve_ips_mt(endDevices, maxThreads)
    return endDevices


def resolve_ip(ip):
    """
        Given an IP address, return appropriate DNS entry, if any
    """
    try:
        DebugPrint('Resolving IP: ' + str(ip), 0)
        dns = (socket.gethostbyaddr(ip))[0]
    except:
        dns = ''
    return dns


def resolve_ips_mt(endDevices, maxThreads=4):

    """
        Given list of clEndDevices, use pool of subprocesses
        (count determined by MAX_THREADS) to call resolve_ip()
    """
    ips = []
    dns = []
    DebugPrint('resolve_ips_mt.maxThreads: ' + str(maxThreads))
    DebugPrint('resolve_ips_mt.endDevices: ' + str(endDevices), 0)
    for ed in endDevices:
        ips.append(ed.ip)
    DebugPrint('resolve_ips_mt.IPs: ' + str(ips), 0)
    pool_size = maxThreads
    pool = multiprocessing.Pool(processes=pool_size)
    dns = pool.map(resolve_ip, ips)
    pool.close()
    pool.join()
    for n in range(len(ips)):
        if ips[n] == endDevices[n].ip:  # sanity check
            endDevices[n].dns = dns[n]
        else:
            DebugPrint('Sanity Check failed during resolve_ips_mt()', 3)
            pass


def resolve_mac(mac=None, defaultgateway=None, ip=None, creds=None):
    """
        Given a MAC or IP address and the appropriate subnet default gateway,
        SSH into the default gateway and use arp table to resolve between MAC
        and IP
    """
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
    # DebugPrint('resolve_mac.defaultgateway: ' + str(defaultgateway))
    # DebugPrint('resolve_mac.creds[0]: ' + creds[0])
    if ARP_TABLE == []:
        UpdateMetric('resolve_mac')
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
