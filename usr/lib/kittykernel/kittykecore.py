#!/usr/bin/python3

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
#  Core routines for kittykernel, e.g. downloading a list of kernels
#
# 
#  Warning: Don't read this  source file if  you are annoyed by too many
#           comments. Read source code  of other FOSS projects  instead.
#

import os
import subprocess
import apt
import sys
import platform
import tempfile
import gettext
_ = gettext.gettext


# Debug mode; show exception data when set to True
debugmode = False

# APT Cache object
cache = apt.Cache()

# Architecture of platform; 64bit?
platformis64bit = (platform.architecture()[0] == "64bit")


# Convert a number of bytes to a string with respective quantities. This
# uses SI units (Ki, Mi, etc); implementation from Stackflow (Fred Cirera)
# <https://stackoverflow.com/questions/1094841/>
def sizeof_fmt(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f %s%s" % (num, 'Yi', suffix)


# This function returns the size in bytes of the /boot directory/partition
# as tuple: (free, total); returns (0, 0) when something went wrong
def sizeof_boot():
    global debugmode
    try:
        # call df to get the size of /boot
        output_lines = subprocess.check_output("df -B 1 /boot", shell = True).decode("utf-8").strip().split('\n')

        # Should be at least two lines
        if len(output_lines) < 2:
            return (0, 0)

        # Get second line and split
        columns = list(filter(None, output_lines[1].split(' ')))

        # There should be at least 4 columns
        if len(columns) < 4:
            return (0, 0)

        # Return the 4th column (free space) and the 2nd column (total space) as integers
        return (int(columns[3]), int(columns[1]))

    # When something went really wrong...
    except Exception as e:
        if debugmode:
            print (e)
        return (0, 0)


# Updates and reopens the cache; this version uses synaptic
def refresh_cache(xwindow_id = 0):
    global cache
    # Starting synaptic with all the necessary parameters
    cmd = ["gksudo", "--", "/usr/sbin/synaptic", "--hide-main-window", "--update-at-startup", "--non-interactive", "--parent-window-id", "%d" % xwindow_id]
    comnd = subprocess.Popen(' '.join(cmd), shell=True)
    comnd.wait()

    # Reopens the list; necessary after updating
    cache.open(None)

# Just rereads the cache (reopens)
def reopen_cache():
    cache.open(None)

# Returns the current kernel as string in the format "4.10.0-28-generic"; "unknown" is returned if an exception occurred
def get_current_kernel():
    global debugmode
    try:
        # call uname to get the current kernel; truncate a little bit
        return subprocess.check_output("uname -r", shell = True).decode("utf-8").strip()
    except Exception as e:
        if debugmode:
            print (e)
        return "unknown"

# Strips the kernel version off everything except the pure numbers; allows to select maximum for subversions in resulting string;
# it removes everything after a '+' and ':' atm - probably needs better version in future
def strip_kernel_version(version, maxsubversion = 10):
    version = version.split("+", 1)[0]
    version = version.split(":", 1)[0]
    versions = version.replace("linux-image-", "").replace("-", ".").split(".")
    intversions = []

    # Test each member if it is a digit/number
    for index, ver in enumerate(versions):
        if ver.isdigit() and index < maxsubversion:
            intversions.append(ver)    

    # Return joined version as string
    return ".".join(intversions)


# Downloads and returns a list of kernels; an empty string is returned if an exception occurred
def get_kernels():
    global cache, debugmode, platformis64bit
    try:
        # First, get the current version
        current_version = get_current_kernel()        

        # DEBUG only
        if debugmode:
            print("Current architecture of system (True if 64bit): ", platform.architecture()[0], platformis64bit)

        # Create empty list to return
        kernel_list = []

        # Check the packages in the cache
        for pkg in cache:
            # Pkg is 64bit?
            pkgis64bit = (pkg.architecture() == "amd64")

            # If the package has not the right architecture... we will just go on
            if pkgis64bit != platformis64bit:
                continue

            # Create an empty dictionary object
            kernel = { 'version_major': '', 'version': '', 'package': pkg.name, 'pkg_version': '',
                       'size': 0, 'installed_size': 0, 'origins': [], 'fullname': pkg.fullname,
                       'active': False, 'installed': False, 'downloaded': False }

            # Kernel package? Check for versions 1 to 5 (the 6 is exclusive!) here
            if kernel['package'].startswith( tuple(["linux-image-"+str(x) for x in range(1,6)]) ):

                # Print name and version in debug mode
                if debugmode:
                    print(kernel['package'], strip_kernel_version(kernel['package']), pkg.architecture() )

                # Save full version and major version of package
                kernel['version'] = strip_kernel_version(kernel['package'])
                if len(kernel['version'].split('.')) > 2:
                    kernel['version_major'] = kernel['version'].split('.')[0] + "." + kernel['version'].split('.')[1]
                else:
                    # This is probably a generic image; ignore it for now
                    continue

                # Get all the flags
                kernel['active'] = (kernel['package'].replace("linux-image-", "") == current_version)
                kernel['installed'] = pkg.is_installed
                kernel['downloaded'] = pkg.has_config_files

                # Package version is either the version installed or the candidate version; no pkg_version means = not available
                if kernel['installed']:
                    kernel['pkg_version'] = pkg.installed.version                    
                elif pkg.candidate and pkg.candidate.downloadable:
                    kernel['pkg_version'] = pkg.candidate.version

                # Sizes of package
                if pkg.candidate:
                    kernel['size'] = pkg.candidate.size
                    kernel['installed_size'] = pkg.candidate.installed_size

                # Copy the origins
                for origin in pkg.candidate.origins:
                    # Ignore "now" archives
                    if origin.archive != "now":
                        kernel['origins'].append("%s (%s, %s, %s)" % (origin.label, origin.archive, origin.site, [_("trusted") if origin.trusted else _("not trusted")][0]) )

                # Join in single string
                kernel['origins'] = ", ".join(kernel['origins'])

                # Add kernel dictionary to list
                kernel_list.append(kernel)

        # Sort list by version and return it
        return sorted(kernel_list, key=lambda item: list(map(int, item['version'].split('.')))) 

    # If something is wrong, return an empty list
    except Exception as e:
        if debugmode:
            print (e)
            print(sys.exc_info())
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
        return []

# Gets the kernel changelog as unicode string; string is empty, if something went wrong
def get_kernel_changelog(fullname):
    global cache
    try:
        # Is package in cache? Then, try to retrieve and return changelog
        if fullname in cache:
            return cache[fullname].get_changelog()
        else:
            return ""

    # If something is wrong, return an empty list
    except Exception as e:
        if debugmode:
            print (e)
            print(sys.exc_info())
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
        return ""


# Invokes synaptic with gksudo to do something with packages; operations is a list of tuples such as
# ('install', pkg1), ('remove', pkg2), or ('purge', pkg3); this function does not check for additional
# packages to be installed or removed (just the dependencies)
def pkg_perform_operations(operations, xwindow_id = 0):
    print(operations)
    if type(operations) is not list:
        return -1

    if type(operations[0]) is not tuple:
        return -2

    try:
        # Write the list of packages in a temp file            
        f = tempfile.NamedTemporaryFile()

        # Create entry for each operation
        for op in operations:

            # Check if operation is allowed
            if op[0] not in ['install', 'remove', 'purge']:
                continue

            # Write to temp file
            f.write( ("%s\t%s\n" % (op[1], op[0])).encode("utf-8") )

            print(op)

        # Write everything to the file
        f.flush()

        # Synaptic command with gksudo
        cmd = ["gksudo", "--", "/usr/sbin/synaptic", "--hide-main-window", "--non-interactive", "--parent-window-id", "%s" % xwindow_id, "-o", "Synaptic::closeZvt=true",
                                                     "--progress-str", "\"" + _("Installing kernel packages. Please wait, this can take some time.") + "\"", 
                                                     "--finish-str", "\"" + _("The kernel was installed.") + "\"",
                                                     "--set-selections-file", f.name]

        out = subprocess.Popen(' '.join(cmd), shell=True)

        # get output
        stdout, stderr = out.communicate()

        print(stdout.read())
        print(stderr.read())

        return 0
        

    # If something is wrong, return error code
    except Exception as e:
        if debugmode:
            print (e)
            print(sys.exc_info())
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
        return -3


# Installs/Removes/Purges a list of kernels with extra package (if available) and headers
def perform_kernels(fullnames, verb, xwindow_id = 0, headers = True, extras = True):
    global cache
    try:        
        print("test", fullnames, verb)
        # Our operation list
        operations = []

        # For each package name check if headers and extras are available and add to list
        for pkg in fullnames:

            # Is package in cache? Then, ask synaptic to install it
            if pkg in cache:
                # Add to operations
                operations.append( (verb, cache[pkg].name) )

                header_name = cache[pkg].name.replace("-image-", "-image-extra-")
                if headers and header_name in cache:
                    operations.append( (verb, header_name) )

                extras_name = cache[pkg].name.replace("-image-", "-image-extra-")
                if extras and extras_name in cache:
                    operations.append( (verb, extras_name) )

        # Perform actions
        return pkg_perform_operations(operations, xwindow_id)         

    # If something is wrong, return an empty list
    except Exception as e:
        if debugmode:
            print (e)
            print(sys.exc_info())
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
        return -1


# Script file is run directly... then let's have some test outputs here
if __name__ == '__main__':
    print("Script was called directly. Testing...")

    # Test kernel stripping
    print("Kernel strip for 'linux-image-4.8.0-46-generic' results in: ", strip_kernel_version("linux-image-4.8.0-46-generic"))

    # Debug mode on
    debugmode = True

    # Root?
    if os.getuid() == 0:
        print("Script was called as root.")
        refresh_cache()

    print("Current kernel: ", get_current_kernel())
    print("Size of boot: ", sizeof_boot())
    kernels = get_kernels()
    print("Kernel list: ", )

    if len(kernels) > 0:
        print("Changelog of first entry %s:" % kernels[0]["fullname"], get_kernel_changelog(kernels[0]["fullname"]))

