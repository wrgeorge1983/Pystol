#! /usr/bin/python
'''
Created on Mar 26, 2015

@author: William.George

Credit to /r/Python for the non-wasteful and sensible handling of oldInit and
    newInit
'''
# Standard Library Imports
import os
import sys
import json
from pprint import pprint  # Not used here, but we want it in interactive mode.
import time
from subprocess import Popen
sys.path += [os.getcwd()]  # 

# Imports from other modules in this project
import sshutil

# Imports from third party modules
# import phpipam

# File class from user fdb on StackOverflow
# http://stackoverflow.com/questions/5896079/python-head-tail-and-backward-read-by-lines-of-a-text-file

# We're going to define some "constants", really just variables.  We define them here, then attempt to import a file that will overwrite them.
#    If the file exists, great, it works and will overwrite them, otherwise they'll keep the values defined here.  The upshot is we get to 
#    publish this on github without worrying exposing sensitive data.  ** Make sure to git ignore iactiveconstants.py **

DEFAULT_SW_IP = '10.10.10.10'
DEFAULT_HOST_IP = '10.10.10.10'

try:
    import iactiveconstants
    DEFAULT_SW_IP = iactiveconstants.DEFAULT_SW_IP
    DEFAULT_HOST_IP = iactiveconstants.DEFAULT_HOST_IP
except ImportError:
    pass

class File(file):
    """ An helper class for file reading  """
    
    def __init__(self, *args, **kwargs):
        super(File, self).__init__(*args, **kwargs)
        self.BLOCKSIZE = 4096
        
    def head(self, lines_2find=1):
        self.seek(0)                                               # Rewind file
        return [super(File, self).next() for x in xrange(lines_2find)]
        
    def tail(self, lines_2find=1):
        self.seek(0, 2)                                      # Go to end of file
        bytes_in_file = self.tell()
        lines_found, total_bytes_scanned = 0, 0
        while (lines_2find + 1 > lines_found and
               bytes_in_file > total_bytes_scanned):
            byte_block = min(
                self.BLOCKSIZE,
                bytes_in_file - total_bytes_scanned)
            self.seek(-(byte_block + total_bytes_scanned), 2)
            total_bytes_scanned += byte_block
            lines_found += self.read(self.BLOCKSIZE).count('\n')
        self.seek(-total_bytes_scanned, 2)
        line_list = list(self.readlines())
        return line_list[-lines_2find:]
        
    def backward(self):
        self.seek(0, 2)                         #Go to end of file
        blocksize = self.BLOCKSIZE
        last_row = ''
        while self.tell() != 0:
            try:
                self.seek(-blocksize, 1)
            except IOError:
                blocksize = self.tell()
                self.seek(-blocksize, 1)
            block = self.read(blocksize)
            self.seek(-blocksize, 1)
            rows = block.split('\n')
            rows[-1] = rows[-1] + last_row
            while rows:
                last_row = rows.pop(-1)
                if rows and last_row:
                    yield last_row
        yield last_row


def ipm(site, ipt):
    '''
        ipm(site, ipt):
            site: An IP or Network address in dotted-decimal in a string.
                e.g. "10.10.8.6" or "10.10.0.0"
            ipt: 'input', trailing octets to be merged with site
                as string:
                    e.g. "7" or "9.1.3"
                or as int or float:
                    e.g. 7 or 3.8
            Returns: trailing octets defined by ipt super-imposed on site
                e.g. site("10.10.8.6", "1.2.3") == "10.1.2.3"
                     site("10.10.8.6", 5.1) == "10.10.5.1"
            Note: It's possible that 'site' can be specified as 3 or fewer
                ('10.3', etc...) but this is probably not smart.
            Note: This works exclusively by manipulating a string of octets
                in dotted decimal format, and does not in any way account for
                any real subnetting operations, etc...
    '''
    ipt = str(ipt).split('.')
    site = site.split('.')
    return '.'.join(site[:4-len(ipt)] + ipt)


def pull_subnets():
    ipam = phpipam.PHPIPAM('ipam', 'Pystol',
                           '00fc27a19df2efd9e06d8b0480498910')
    rslt = ipam.read_subnets()
    jload = json.loads(rslt)
    subnets = jload['data']
    return subnets


def site_lookup(sfilter):
    subnets = pull_subnets()
    return [subnets[x] for x in range(0, len(subnets) - 1) if sfilter in
            subnets[x]['description']]


class clintSwitch(sshutil.clSwitch):
    def __init__(self, ip=None, creds=None, timeout=None):
        if timeout:
            self.timeout = timeout
        elif not hasattr(self, 'timeout'):
            self.timeout = None
        
        if creds:
            clintSwitch.credentials = creds
        else:
            if not hasattr(self, "credentials"):
                raise SyntaxError("Credentials must be provided at least once.")
            creds = self.credentials
        if ip:
            ip = str(ip)
            site = ip
            ips = ip.split('.')
            if len(ips) == 4:
                clintSwitch.site = site
            else:
                if not hasattr(self, 'site'):
                    raise SyntaxError("Full IP must be provided at least once.")
                ip = ipm(clintSwitch.site, ip)
                clintSwitch.site = ip
        else:
            ip = 'None'
        sshutil.clSwitch.__init__(self, ip, creds)
        
    def pexecute(self, cmd, trim=True, timeout=None):
        args = [cmd, trim]
        if not timeout:
            timeout = self.timeout
            
        if timeout:
            args.append(timeout)

        print self.Execute(*args)

#    def interact():q
#        Popen(


def pythonrc():
    home = os.path.expanduser('~/')
    return home + '.pythonrc.py'

# run users pythonrc
try:
    execfile(pythonrc())
except:
    print 'Couldn\'t include ~/.pythonrc.py'
    raise


def retrieve_pcaps(sw):
    destcreds = sshutil.GetCredentials()
    host = DEFAULT_HOST_IP
    lines = sw.Execute('sh flash: | i pcap').splitlines()
    files = [line.split()[-1] for line in lines]
    for fil in files:
        command = 'copy {0} scp:'.format(fil)
        sw.timeout = 2
        print 'pulling {0}...'.format(fil)
        sw.pexecute(command)
        sw.pexecute(host)
        sw.pexecute('\n')
        sw.pexecute('\n')
        sw.pexecute(destcreds[1], 5)


creds = sshutil.GetCredentials()
clintSwitch.credentials = creds
clintSwitch.site = DEFAULT_SW_IP
if __name__ == "__main__":
    # interact()
    # run_interactive_interpreter()
    pass

