Heimdall
========

A rolling-window network usage limiter.

Suspends processes from a given list when traffic exceeds a given amount within a given time frame.

Dependencies
------------

Only hard dependency is on psutil (pip install psutil).

If you want notifications when approaching the limit and when processes have been suspended,
pync is needed on osx (pip install pync). Havent found a windows equivalent yet.

Installation
------------

**Windows*: Drop the script and the config in the boot dir (C:/Users/<Username>/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup),
or create a shortcut there to the script (a bat file with "python <path to script>" is sufficient.)
**OS X*: (not tested)
     mkdir /System/Library/StartupItems/Heimdall/
     cd /System/Library/StartupItems/Heimdall/
     ln -s /<path to script> Heimdall
     chmod +x Heimdall
**Unix*: Google "run python script on startup" for your distro. Probably just add "python <path to script>" to ~/.bash_profile
