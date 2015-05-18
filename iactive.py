#! /usr/bin/python
'''
Created on Mar 26, 2015

@author: William.George

wrapper around _iactive.py to so that we can `relaod(_iactive)` interactively.
So Meta.
'''
# I defend this usage on the premis that this is by definition an interactive session
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

# run users pythonrc
try:
    execfile(pythonrc())
except:
    print 'Couldn\'t include ~/.pythonrc.py'
    raise

creds = sshutil.GetCredentials()
clintSwitch.credentials = creds
clintSwitch.site = DEFAULT_SW_IP
if __name__ == "__console__":
    # interact()
    # run_interactive_interpreter()
    pass
else:
    print __name__
    print "There is no good reason you should be usinging this in anything BUT an interactive mode, so stop it!"
    exit()
