#! /usr/bin/python
'''
Created on Nov 4, 2014

@author: William.George
'''
# Standard Library Imports
import sys
import getopt

# Imports from other scripts in this project
from sshutil import Listify, GetCredentials, DateTime
from sshexecute import sshrun




DEBUG = False


def main(argv):
    """
    Run a single command on one or more hosts via ssh.

    sshrun.py -h | (-c <command> (-t <host> | -T <hostfile) [-u <username>]))

    --command or -c  -- string defining command to be ran (e.x. 'show run |
        inc vty') *Will prompt if not provided.
    --host or -t     -- hostname or IP address *Will prompt if neither host nor
        hostfile are provided.
    --hostfile or -T -- file containing list of hostnames or IP addresses, one
        per line.
    --username or -u -- username to use to connect. *Will assume currently
        logged in user if not provided.
    --help or -h -- print this usage information.

    """
    command = None
    hosts = None
    username = None
    hostfile = None
    # GSSP = False

    try:
        opts, args = getopt.getopt(argv, "hc:t:T:u:", ["command=",
                                                       "host=",
                                                       "hostfile=",
                                                       "username=",
                                                       "help"])
    except getopt.GetoptError:
        print 'error in processing arguments'
        sys.exit(2)

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            print main.__doc__
            sys.exit()
        elif opt in ("-c", "--command"):
            command = arg
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

    if hostfile is not None:
        with open(hostfile, 'r') as fHosts:
            hosts = fHosts.readlines()
    elif hosts is None:                    # Prompt for host if none present
        hosts = raw_input('Enter single hostname or IP address (If you want '
                          'multiple hosts, re-run with -T or --hostfile:\n')

    hosts = Listify(hosts)

    if not command:                 # Prompt for command if none present
        command = raw_input('Enter the command you would like to run on the'
                            ' destination machine(s)\n')

    # Get Credentials, use provided username if available
    creds = GetCredentials(username)

    for host in hosts:
        print ("""**Time: {0}
**Running: {1}
**Host: {2}
""".format(DateTime(), command, host))

        try:
            print(sshrun(command=command, host=host.strip(), creds=creds))
        except Exception as E:
            print('Failure to connect or run command!')
            print(host.strip())
            print(command)
            print(creds)
            print(type(E))
            print(E)


if __name__ == '__main__':
    main(sys.argv[1:])
