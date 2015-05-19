# Pystol
ABOUT
-----
Collection of network management tools written in Python

Deliberately written for a pure cisco environment, but extensible to multi-vendor in the future

For now, this is a read-only package.  It will collect information and dump it to screen or text files.  That's it.  But it does this via creating ssh sessions to the devices in question and running typical cisco show commands ("sh cdp nei det"), etc... If you point it at some random device that interprets that command as "SuddenlyHalt CorruptDatabaseParameters" or something, that's on you.  

EXAMPLE
-------

I needed to monitor a switch for physical changes being implemented by a pair of hands a long way away, and the following scriptlet illustrated the rapid-utility I'm going for:

```python
import time
import sshutil
ip = '10.10.10.10'
creds = sshutil.GetCredentials()
switch = clSwitch(ip=ip, creds=creds)
cmd = 'sh env pow all'
while True:
    print switch.Execute(cmd)
    time.sleep(60)
```

The latest additions I've made have been to implement a solid 'interactive mode'.  I use it with bpython (for its syntax highlighting, tab completion, etc.), but it'l work fine in vanilla.

```
Password:
bpython version 0.14.1 on top of Python 2.6.6 /home/william.george/stage/PystolVE/bin/python
>>>



``

LICENSE
------
A fellow on reddit (/u/jdub01010101) alerted me to the fact that there was no license file, so I added one.  In the event you wish to do something with this that isn't permitted under this license (LGPL2.1), or have any argument at all as to why I should use some other license, let me know.  I will probably agree, but I'm done thinking about it for right now.

There is no disclaimer on each source file.  I will probably add one, but until then I'll be relying on Internet fairies and Reddit Karma to stop you from hurting yourself with this code.

INSTALLING AND RUNNING
-----
This code depends entirely upon Paramiko.  Available at http://www.paramiko.org/.
Paramiko itself depends on a few other packages.  All of these are available through PyPy and other python package distribution schemes. 

This is developed for and is known to run on Linux with Python 2.6.  

REQUESTS, CONTRIBUTIONS, FEEDBACK
--------------------
And this is GitHub, right?  So if you actually want to contribute, or even just see something I could be doing better, feel free to let me know.  I made this because I wanted it for myself, but if it can be useful for others as well, then so much the better.


AUTHOR
------
My name is William R. George, feel free to contact me at \[FirstInitial\]\[MiddleInitial\]\[LastName\]1983@gmail.com
