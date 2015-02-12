'''
Created on Dec 1, 2014

@author: William.George
'''
# Standard Library Imports
import time

# External Libarary Imports
import paramiko

# Imports from other scripts in this project
from metrics import UpdateMetric
from metrics import DebugPrint

# These are terrible.
# Global lists that hold persistent connection information.
# TODO: UnTerriblize
SSH_SESSIONS = []
SSH_CHANNELS = []
SSH_HOSTS = []
DEBUG = False


def NewSSH(host, creds, interactive=False):
    """Initialize ssh connection object to specified host"""
    UpdateMetric('NewSSH')
    DebugPrint('NewSSH.host: ' + str(host), 0)
    DebugPrint('NewSSH.creds: ' + str(creds[0]), 0)
    DebugPrint('NewSSH.interactive: ' + str(interactive), 0)

    if creds is None:
        raise Exception('No Credentials for {host}'.format(host=host))

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(host, username=creds[0], password=creds[1], timeout=5)
    except:
        raise Exception('Couldn\'t Connect to {host}!'.format(host=host))

    if not interactive:
        return ssh
    else:
        chan = ssh.invoke_shell()
        # DisablePagingC(chan)
        return ssh, chan


def DisablePagingC(chan):
    '''
       OLD IMPLEMENTATION
       disable paging behavior for interactive cisco sessions
       "press any key to continue" etc...
    '''
    chan.send("terminal length 0\n")
    time.sleep(.25)
    # print('buffer:', chan.recv(1500))
    chan.recv(1500)


def DisablePagingH(host, creds):
    '''
        disable paging behavior for interactive cisco sessions
        "press any key to continue" etc...
    '''
    command = "terminal length 0\n"
    sshrunP(command, host, creds)


def sshrun(command, host=None, creds=None, ssh=None, TextOnly=True):
    """Run a single command on a single host via SSH_SESSIONS.

    command  -- string defining command to be ran (e.x. 'show run | inc vty')
    host     -- hostname or IP address.  Only valid if ssh is None
    creds    -- credentials to use to connect.  Only valid if ssh is None
    ssh      -- PreInitialized ssh object to use in lieu of host, cred pair
                  Should be used to preserve and re-use connections for
                  efficiency
    TextOnly -- Returns text only result of command, versus stdIn,stdOut,StdErr
        tuple.  Default is True
    """
    UpdateMetric('sshrun')
    DebugPrint("sshrun.host: {0}".format(host), 0)
    DebugPrint("sshrun.command: {0}".format(command), 0)
    try:
        if ssh is None:
            if host is not None:
                # print "connecting to: {0}".format(host)
                ssh = NewSSH(host, creds)
            else:
                raise Exception('No valid connection!')
    except:
        ssh = None
        raise

    stdIn, stdOut, stdErr = ssh.exec_command(command)
    if TextOnly:
        rslt = stdOut.read()
        return rslt
    else:
        return stdIn, stdOut, stdErr


def sshrunP(command, host, creds, trim=True, chan=False):
    """
        Run a command within a persistent session via SSH_SESSIONS, initialize
        as necessary.  THE SESSION IS SUBJECT TO TIMEOUT, and WILL EXPIRE.  If
        session expires, it will be recreated the next time a command is ran.

        command  -- string defining command to be ran (e.x.
            'show run | inc vty')
        host     -- hostname or IP address.  Only valid if ssh is None
        creds    -- credentials to use to connect.  Only valid if ssh is None

    """
    global SSH_SESSIONS
    global SSH_CHANNELS
    rbuffer = ''
    UpdateMetric('sshrunP')
    if not command[-1] == '\n':
        command += '\n'
    if host in SSH_HOSTS:
        index = SSH_HOSTS.index(host)
    else:
        index = len(SSH_HOSTS)
        try:
            bssh, bchan = NewSSH(host, creds, interactive=1)
            # DisablePagingC(bchan)
        except:
            raise
        else:
            SSH_SESSIONS.append(bssh)
            SSH_CHANNELS.append(bchan)
            SSH_HOSTS.append(host)
            DisablePagingH(host, creds)
        if DEBUG:
            print index
            print SSH_SESSIONS
            print SSH_CHANNELS
            print SSH_HOSTS

    if not SSH_CHANNELS[index].transport.is_active():
        SSH_SESSIONS[index], SSH_CHANNELS[index] = NewSSH(host, creds,
                                                          interactive=1)

    SSH_CHANNELS[index].send(command)
    n = 0
    # Max time to wait in any given stretch is 1.5 seconds
    # Sleep .05s at a time, 30 intervals
    interval = .05
    DebugPrint('sshrunP.host: {0}'.format(host, True))
    DebugPrint('sshrunP.command: {0}'.format(command, True))
    while True:
        if not SSH_CHANNELS[index].recv_ready():
            if n == 30:
                UpdateMetric('Delay : {0}'.format(n))
                break
            if n > 3 and len(rbuffer) > 0 and rbuffer[-1] == '#':
                break
            n += 1
            time.sleep(interval)
            if DEBUG:
                print ("waiting for data... ", n)
        else:
            rbuffer += SSH_CHANNELS[index].recv(1000)
            if n > 0:
                UpdateMetric('Delay : {0}ms'.format((n * 1000)*interval))
            n = 0

    if trim:
        rslt = '\n'.join(rbuffer.splitlines()[1:-1])
    else:
        rslt = rbuffer
    if DEBUG:
        print(rbuffer)
    return rslt

if __name__ == '__main__':
    pass
