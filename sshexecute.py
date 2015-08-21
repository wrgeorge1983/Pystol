"""
Created on Dec 1, 2014

@author: William.George
"""
# Standard Library Imports
import time

# External Library Imports
import paramiko

# Imports from other scripts in this project
from metrics import UpdateMetric
from metrics import DebugPrint

# These are terrible.
# Global lists that hold persistent connection information.
# TODO: UnTerriblize
DEBUG = False


class SSHConnection(object):
    """Wrapper for paramiko ssh connections.

        If created with `interactive=True` will create and maintain a persistant
    session in self.session.  Session is still subject to timeout by remote
    host, but SSHConnection will transparently recreate as necessary.  Do not
    depend on this to preserve state long term.  Primarily intended to save on
    setup/teardown costs.

        Interactive mode works and is appropriate for 'multi-line commands' that
    require answering prompts from the remote host, e.g. cisco: `copy file scp:`
    """

    def __init__(self, ip, credentials, interactive=False, autoflush=True):
        """

        :param ip:
        :param credentials:
        :param interactive:
        :param autoflush: automatically flush buffers before new interactive commands.
        :return:
        """
        self.ip = ip
        self.credentials = credentials
        self.interactive = interactive
        self.autoflush = autoflush
        self.TextOnly = True
        self.session = None
        self.channel = None
        self.connectionTimeout = 5
        self.rcvTimeout = 1.5
        self.trim = True
        self.stdIn = None
        self.stdOut = None
        self.stdErr = None

    def run(self, command, timeout=None, trim=None, flush=None):
        """
        Run a command, interactive or not
        """

        if flush is None:
            flush = self.autoflush

        self._connect()
        if self.interactive:
            if flush:
                self.buffer_flush()
            return self._run_p(command, timeout, trim)
        else:
            return self._run(command)

    def _run_p(self, command, timeout=None, trim=None):
        """
        Run a command in interactive mode
        """
        UpdateMetric('_run_p()')
        chan = self.channel
        if not timeout:
            timeout = self.rcvTimeout
        rbuffer = ''
        if trim is None:
            trim = self.trim
        if not command[-1] == '\n':
            command += '\n'

        chan.send(command)

        n = 0
        # Max time to wait in any given stretch is timeout seconds
        # Sleep .05s at a time, timeout/.05 intervals
        interval = .05
        DebugPrint('_run_p.host: {0}'.format(self.ip, True))
        DebugPrint('_run_p.command: {0}'.format(command, True))
        while True:
            if not chan.recv_ready():
                if n == timeout/interval:
                    UpdateMetric('Delay : {0}'.format(n))
                    break
                if n > 3 and len(rbuffer) > 0 and rbuffer[-1] == '#':
                    break
                n += 1
                time.sleep(interval)
                if DEBUG:
                    print ("waiting for data... ", n)
            else:
                rbuffer += chan.recv(1000)
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

    def _run(self, command):
        """
        Run a command without interactive mode
        """

        UpdateMetric('_run()')
        DebugPrint("_run.host: {0}".format(self.ip), 0)
        DebugPrint("_run.command: {0}".format(command), 0)
        self.stdIn, self.stdOut, self.stdErr = self.session.exec_command(
            command)
        if self.TextOnly:
            rslt = self.stdOut.read()
            return rslt
        pass

    def _connect(self):
        """
        Create and properly initialize session and channel as necessary
        """
        
        if not self.session or \
                (self.interactive and
                    (not self.channel or
                     not self.channel.transport.is_active() or
                     self.channel.closed)
                    ):
            self._new_ssh()

    def _new_ssh(self):
        """
        Create a new SSH Connection
        """

        UpdateMetric('SSHConnection.NewSSH()')
        ip = self.ip
        username, password = self.credentials
        interactive = self.interactive
        DebugPrint('NewSSH.ip: ' + str(ip), 0)
        DebugPrint('NewSSH.username: ' + str(username), 0)
        DebugPrint('NewSSH.interactive: ' + str(interactive), 0)

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(self.ip, username=username, password=password,
                        timeout=5)
        except:
            raise Exception('Couldn\'t Connect to {host}!'.format(host=ip))

        self.session = ssh
        if interactive:
            self.channel = ssh.invoke_shell()
            self.disable_paging_h()

    def disable_paging_h(self):
        """
        disable paging behavior for interactive cisco sessions
            "press any key to continue" etc...
        """

        command = "terminal length 0\n"
        self.run(command)

    def buffer_flush(self):
        rslt = ''
        while self.channel.recv_ready():
            rslt += self.channel.recv(1000)
        return rslt
