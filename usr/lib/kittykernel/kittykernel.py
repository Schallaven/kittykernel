#!/usr/bin/env python3

#  kittykernel
#  
#  Copyright (C) 2017 by Sven Kochmann, available at Github:
#  <https://www.github.com/Schallaven/kittykernel/>
#  
#  This program is free software;  you can redistribute it and/or modify
#  it under the terms of the  GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or (at
#  your option) any later version.
#  
#  This program is  distributed in the hope that it  will be useful, but
#  WITHOUT  ANY   WARRANTY;  without   even  the  implied   warranty  of
#  MERCHANTABILITY  or FITNESS FOR  A PARTICULAR  PURPOSE.  See  the GNU
#  General Public License for more details.
#  
#  You should  have received  a copy of  the GNU General  Public License
#  along with this program. If not, see <http://www.gnu.org/licenses/>.
#
#
#  Entry point for kittykernel; just check  if there is another instance
#  running. If not, open the main window.
#
# 
#  Warning: Don't read this  source file if  you are annoyed by too many
#           comments. Read source code  of other FOSS projects  instead.
#

import os
import sys
import gettext
import setproctitle
import subprocess
import argparse

# All the beautiful arguments kittykernel supports
parser = argparse.ArgumentParser(prog = "kittykernel", description = "Kittykernel - Maow all your kernel needs")

parser.add_argument("-c", "--console", help = "use console user interface even if X-server is available", action='store_true')
parser.add_argument("-g", "--gui", help = "use graphical user interface even if X-server is not detected", action='store_true')

args = vars(parser.parse_args())

# Check for another instance of kittykernel; if there is one, then just exit this process
try:
    numKittyKernel = subprocess.check_output("ps -A | grep kittykernel_main_proc | wc -l", shell = True).decode("utf-8").strip()
    if (numKittyKernel != "0"):
        sys.exit(0)
except Exception as e:
    print (e)
    print(sys.exc_info()[0])
    sys.exit(-1)

# Set the process title to something more descriptive (shown by ps); should be the same as above, so it can be replaced
setproctitle.setproctitle("kittykernel_main_proc")

# Load the language-definitions (i18n) for kittykernel
gettext.install("kittykernel", "/usr/share/kittykernel/locale")

# GUI should be used
use_GUI = False

# X is running => Start GUI
if "DISPLAY" in os.environ:
    if len(os.environ["DISPLAY"]) > 0:
        use_GUI = True

# User insists on console UI?
if args["console"] == True:
    use_GUI = False

if args["gui"] == True:
    use_GUI = True

# Start Gui or console version of kittykernel: it is important to only import the GUI or console UI modules here, otherwise
# kittykernel will not run when run in the wrong environment
if use_GUI == True:
    from kittykemain import KittykeMainWindow    
else:
    from kittykeconsole import KittykeMainWindow

KittykeMainWindow()


