"""Library of classes and functions for managing
Created on Nov 13, 2014

Library of functions and classes to use in other scripts.

@author: William.George
"""
# Standard Library Imports
import getpass
import time
import multiprocessing
import socket

# Imports from other scripts in this project
from metrics import UpdateMetric
from sshexecute import sshrunP
from metrics import DebugPrint
import metrics


# TODO:  FIX THIS MESS
DEBUG = True
ARP_TABLE = []
DEFAULT_GATEWAY = None
CREDENTIALS = None  # SET THESE IN MAIN()!
CURRENT_SWITCH = None


def deduplicate_list(oList, tag=None):
    """Given oList, search for duplicates.
    If found, print information to screen to assist in troubleshooting

    """
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
