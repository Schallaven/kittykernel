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
#  Includes  all expensive working  thread  functions. No GTK3  stuff is
#  allowed here!
#
# 
#  Warning: Don't read this  source file if  you are annoyed by too many
#           comments. Read source code  of other FOSS projects  instead.
#

import threading
import kittykecore
import time


# Worker for loading the blacklist from file
class Worker_Load_Blacklist(threading.Thread):
    blacklist = []

    def __init__(self): 
        threading.Thread.__init__(self) 

    def run(self):  
        # Get blacklist from file
        self.blacklist = kittykecore.load_blacklist() 
        return

# Worker for loading the support times from file
class Worker_Load_Supporttimes(threading.Thread):
    support_times = []

    def __init__(self): 
        threading.Thread.__init__(self) 

    def run(self):  
        # Get support times from file
        self.support_times = kittykecore.get_kernel_support_times()
        return

# Worker for loading the kernel information from the repo
class Worker_Load_Kernels(threading.Thread):
    _blacklist = []
    kernels = []

    def __init__(self, blacklist): 
        threading.Thread.__init__(self) 
        self._blacklist = blacklist

    def run(self):  
        # Load kernels
        self.kernels = kittykecore.get_kernels()

        # Apply blacklist to the kernel list
        self.kernels = kittykecore.apply_blacklist(self.kernels, self._blacklist)
        return

# Worker for loading the changelogs from the repos
class Worker_Load_Changelogs(threading.Thread):
    _kernels = []
    changelogs = []

    def __init__(self, kernels): 
        threading.Thread.__init__(self) 
        self._kernels = kernels

    def run(self):  
        # Load changelog for every major version        
        self.changelogs = kittykecore.get_kernel_changelogs(self._kernels)
        return

# Worker for updating the Ubuntu kernel information from the web
class Worker_Load_Ubuntu_Kernels(threading.Thread):
    _blacklist = []
    kernels_ubuntu = []

    def __init__(self, blacklist): 
        threading.Thread.__init__(self) 
        self._blacklist = blacklist

    def run(self):  
        self.kernels_ubuntu = kittykecore.get_ubuntu_kernels()
        self.kernels_ubuntu = kittykecore.apply_blacklist(self.kernels_ubuntu, self._blacklist)

        for index, kernel in enumerate(self.kernels_ubuntu):
            self.kernels_ubuntu[index]['version_major'] = 'ubuntu mainline'
        return


