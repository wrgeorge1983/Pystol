#! /usr/bin/python
"""
Created on Mar 26, 2015

@author: William.George

wrapper around _iactive.py to so that we can `relaod(_iactive)` interactively.
So Meta.
"""

# I defend this usage on the premise that this is by definition an interactive session
# and so getting everything into the namespace is really the point
from _iactive import *


# But then I do this anyway, so that `reload(_iactive)` is easier further down the line.

import _iactive


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

# run users pythonrc\
filename = pythonrc()
try:
    try:
        execfile(filename)
    except NameError:
        with open(filename) as f:
            code = compile(f.read(), filename, 'exec')
            exec(code)
except:
    print('Couldn\'t include ~/.pythonrc.py')


creds = sshutil.get_credentials()
clintSwitch.credentials = creds
clintSwitch.site = DEFAULT_SW_IP
if __name__ in ("__main__", "__console__"):
    pass
else:
    print(__name__)
    print("There is no good reason you should be using this in anything BUT an interactive mode, so stop it!")
    exit()
