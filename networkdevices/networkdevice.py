
__author__ = 'William.George'

from collections import namedtuple
import re
import time
from metrics import UpdateMetric, DebugPrint
import metrics
import sshexecute
from sshutil import format_mac_address, format_interface_name, deduplicate_list

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
        if not isinstance(self.switch, CiscoIOS):
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
        # needs to be an actual CiscoIOS or None or String
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


class DispatchMeta(type):
    """
    Metaclass for registering NetworkDevice subclasses
    'mcs' == this metaclass
    'cls' == class being created
    """
    def __init__(cls, cls_name, cls_bases, cls_dict):
        # Base class *IS* included in registry to serve as a default
        registry = cls_dict.setdefault('registry', set())
        registry.add(cls)

        super(DispatchMeta, cls).__init__(cls_name, cls_bases, cls_dict)


class DispatchableClass(object, metaclass=DispatchMeta):
    """
    Base class to build class registry.  Classes override these methods
    """

    def __init__(self):
        raise NotImplementedError

    @classmethod
    def match_class(cls, instance):
        """
        Can this class handle this device?
        Subclasses should only use interfaces and attributes explicitly known to be
               defined by their parents

        Subclasses should be allowed to fall-through, but never this far.
        """

        if 'DispatchableClass' not in cls.__name__:
            return NotImplementedError

        return False

    def search_registry(self):
        matches = [cls for cls in self.registry if cls.match_class(self)]
        best_match = matches[0]
        for match in matches[1:]:
            if len(match.mro()) > len(best_match.mro()):
                best_match = match

        return match

class NetworkDevice(DispatchableClass):

    def __init__(self, ip='None', creds=None):  # str ip
        self._ip = 'None'
        self.ip = ip
        if creds is None:
            raise SyntaxError('No Credentials Specified')
        self.credentials = creds
        self.goodstates = ['UNK', 'UP']
        self.state = 'UNK'  # valid states: ['UNK', 'UP', 'DOWN']
        self.connection = None

    @property
    def ip(self):
        return self._ip

    @ip.setter
    def ip(self, arg):
        # TODO: implement ipaddress class, at that time evaluate permitting integer values
        if type(arg) in [str, type(None)]:
            self._ip = str(arg)
        else:
            raise Exception('can\'t set \'CiscoIOS({0}).ip\' to {1}'
                            ''.format(self, type(arg)))

    def _connect(self):
        if self.connection is None:
            self.connection = sshexecute.SSHConnection(self.ip,
                                                         self.credentials,
                                                         True)

    def execute(self, command, trim=True, timeout=1.5):
        """
        Connect to switch and execute 'command'
        """
        self._connect()
        UpdateMetric('CiscoIOS.execute')
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

    @classmethod
    def match_class(cls, instance):
        """
        Always assumed to be an option
        """
        return True


class Riverbed(NetworkDevice):
    @classmethod
    def match_class(cls, instance):
        regex = re.compile(r'Product model:\s+CX\d{3}\n').search
        return bool(regex(instance.execute('sh ver', timeout=5)))


class CiscoIOS(NetworkDevice):
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

    @classmethod
    def match_class(cls, instance):
        version_string = instance.execute('sh ver').strip()
        return version_string.startswith('Cisco IOS Software')

    @property
    def hostname(self):
        """
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
    def supervisor(self):
        """
        Cisco Specific
        :return:
        """
        if not self.supported:
            return 'UNK'

        _supervisor = getattr(self, '_supervisor', None)
        if _supervisor is not None:
            return _supervisor

        _supervisor = ''
        for line in self.execute('show module').splitlines():
            if 'supervisor' in line.lower():
                _supervisor = line.split()[-2]
        self._supervisor = _supervisor
        return self._supervisor

    @property
    def flash(self):
        """
        Cisco Specific
        :return:
        """
        if not self.supported:
            return 'UNK'
        _flash = getattr(self, '_flash', None)
        if _flash is not None:
            return _flash

        FlashSpace = namedtuple('FlashSpace', 'free, total')
        # filesystems = ['bootdisk:', 'flash:', 'bootflash:',
        #                'sup-bootflash:', 'slot0:']

        rslt = self.execute('dir')
        if any([word in rslt.lower() for word in ('invalid', 'error')]):
            return 'UNK'

        rslt = rslt.splitlines()[-1]
        fs = FlashSpace(*reversed([int(sub.split()[0]) for sub in rslt.split('(')]))
        # FlashSpace(free=xxxx, total=yyyy)
        self._flash = fs
        return self._flash

        # for filesystem in reversed(filesystems):
        #     rslt = self.execute('dir {0}'.format(filesystem))
        #     if 'Invalid input' not in rslt and 'Error' not in rslt:
        #         line = rslt.splitlines()[-1]
        #         #fs = FreeSpace(line.split()[-3].strip('('),
        #         #               line.split()[0])
        #         #return fs
        #         return filesystem, line, self.execute('dir').splitlines()[-1]

    @property
    def available_ram(self):
        """
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
        Deduces this switches model number from 'sh ver' output.
        This will fail gracefully to 'UNK', but 'CiscoIOS.supported' will return False in
            this case and many features will refuse to run.
        :return:
        """
        if self.state in self.goodstates:
            for line in self.version.splitlines():
                if 'bytes of' in line.lower():
                    return line.split()[1]
        return 'UNK'

    @property
    def supported(self):
        if self.model == 'UNK':
            return False

        return True

    @property
    def stacked(self):
        """
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
        if not self.supported:
            return 'UNK'

        try:
            return self._license
        except AttributeError:
            self._collect_license()
            return self._license

    def _collect_license(self):

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
        Will return string in form: "(featureset, featureset)" if multiple valid
        featuresets found.  Otherwise "featureset".
        :return:
        """
        sh_license = self.execute('sh license')
        index = 0
        licenses = {}
        rslts = []

        if '% Incomplete' in sh_license:
            license_options = self.execute('sh license ?')

            if 'summary' in license_options:
                sh_license = self.execute('sh license summary')
            elif 'right-to-use' in license_options:
                rtu = self.execute('sh license right-to-use')
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
        Cisco Specific
        :return:
        """
        self._startup_config = self.execute('show startup-config')

    def _collect_version(self, data=False):
        """
           Pull Version info
        """
        command = 'sh ver'
        UpdateMetric('CiscoIOS._collect_version')
        try:
            rBuffer = self.execute(command)
        except:
            raise

        self._version = rBuffer

    @property
    def ports(self):
        return self._ports

    @ports.setter
    def ports(self, arg):
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
            raise Exception('can\'t set \'CiscoIOS({0}).ports\''
                            'with {1}'.format(self, type(arg)))

    @property
    def devices(self):
        return self._devices

    @devices.setter
    def devices(self, arg):
        if type(arg) == list:
            self._devices = arg
        else:
            raise Exception('can\'t set \'CiscoIOS({0}).devices\' with {1}'
                            ''.format(self, type(arg)))

    def populate(self):
        """
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
        Connect to switch and pull MAC Address table
        """
        command = 'sh mac address-table'
        UpdateMetric('CiscoIOS.collect_mac_table')
        lines = self.execute(command)
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
        Return all interfaces on a switch, including stats
        """
        command = 'show interface'
        UpdateMetric('CiscoIOS._get_interfaces')
        if not data:
            try:
                lines = self.execute(command).splitlines()
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
           Apply CDP neighbor information to self.ports[]
           ex. switch.ports[1].CDPneigh[0] == (
               NeighborID,
               NeighborIP,
               NeighborCapabilities,
               NieghborPort)
        """
        command = 'sh cdp ne det'
        UpdateMetric('CiscoIOS._collect_cdp_information')
        try:
            rBuffer = self.execute(command)
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
            Classify ports by switchport mode.
            ('access', 'trunk')
        """
        name = ''
        switchport = ''
        mode = ''
        command = 'sh int switchport'
        UpdateMetric('CiscoIOS._classify_ports')
        if data:
            rBuffer = data.strip()
        else:
            if self.state not in self.goodstates:
                return
            try:
                rBuffer = self.execute(command)
            except:
                raise

        spLines = rBuffer.splitlines()
        DebugPrint('CiscoIOS.ports: {0}'.format(self.ports))
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
            Apply existing interface descriptions to
            switch.ports[] ex. switch.ports[1].description = 'Trunk to
            ABQCore1'
        """
        command = 'sh int description'
        UpdateMetric('_collect_interface_descriptions')
        if not (self.state in self.goodstates):
            return

        try:
            rBuffer = self.execute(command)
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
        rslt = []
        scrubbedInterfaceList = []
        scrubbedMACAddressTable = []

        for port in self.ports:
            metrics.DebugPrint('[{0}].[{1}].edge:  {2}'.format(self.ip,
                                                               port.name,
                                                               port.edge))
            if port.edge:
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

        for interface in scrubbedInterfaceList:
            for line in macAddressTable.splitlines():
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
        return ('CiscoIOS(ip={0}, Ports={1}, Devices={2})'
                ''.format(self.ip, len(self.ports), len(self.devices)))

    def __str__(self):
        return self.ip

    def __eq__(self, other):
        return (self.ip == str(other))

    def __ne__(self, other):
        return not (self == other)


class CiscoASA(NetworkDevice):
    @classmethod
    def match_class(cls, instance):
        version_string = instance.execute('sh ver').strip()
        return version_string.startswith('Cisco Adaptive Security Appliance Software')


class CiscoNXOS(NetworkDevice):
    @classmethod
    def match_class(cls, instance):
        version_string = instance.execute('sh ver').strip()
        return version_string.startswith('Cisco Nexus Operating System')


class SwitchPort(object):
    """
        Represent ports attached to a CiscoIOS.  Contains
        EndDevice objects and reference to its parent
        CiscoIOS.
    """

    def __init__(self, name=None, switch=None, switchportMode=None,
                 detail=None):
        # str ip, CiscoIOS switch
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
        return ('SwitchPort(Name={0}, CiscoIOS={1}, switchportMode={2},'
                'CDPneigh={3}, Devices={4})'
                ''.format(self.name, self.switch, self.switchportMode,
                          len(self.CDPneigh), len(self.devices)))

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return (self.name == str(other))

    def __ne__(self, other):
        return not (self == other)