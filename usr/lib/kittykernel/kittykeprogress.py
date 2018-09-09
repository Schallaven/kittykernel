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
#  Defines and setups the progress dialog of kittykernel.
#
# 
#  Warning: Don't read this  source file if  you are annoyed by too many
#           comments. Read source code  of other FOSS projects  instead.
#

import sys
import time
import threading
import gettext
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('GdkX11', '3.0')  

from gi.repository import Gtk, Gdk, GdkPixbuf, GdkX11, Gio, Pango, GLib
_ = gettext.gettext

# Define class for progress dialog
class KittyKeProgressDialog():

    # Setup progress dialog
    def __init__(self, parent, process, can_abort = True):
        try:
            # Setup builder and load file
            self._builder = Gtk.Builder()
            self._builder.add_from_file("/usr/lib/kittykernel/kittyprogress.ui")
            self._builder.connect_signals(self)

            # Get all the controls
            self._dialogbox = self._builder.get_object("dialog_progress")
            self._progresslabel = self._builder.get_object("label_progress")
            self._actionlabel = self._builder.get_object("label_progress_action")
            self._progressbar = self._builder.get_object("progressbar1")

            # Save and set the parent window
            self._parent = parent
            self._dialogbox.set_transient_for(self._parent)

            # True if user clicked 'abort'
            self._builder.get_object("button_abort").set_sensitive(can_abort)
            self._abort = False

            # Show dialog
            self._dialogbox.show()

            # Set initial values            
            self._progresslabel.set_label(process)
            self.update(0.0, _("Preparing..."))        

        except Exception as e:
            print (e)
            print(sys.exc_info()[0])
            sys.exit(-1)

    # Destroys the window when the object is deleted
    def __del__(self):
        self.destroy()

    # Destroys the dialog and stops the thread
    def destroy(self):
        try:
            # Hide and destroy the dialog box
            self._dialogbox.destroy()

        except Exception as e:
            print (e)
            print(sys.exc_info()[0])
            sys.exit(-1)       

    # Updates a erforms a run of the main loop
    def update(self, fraction, nextaction):
        self._actionlabel.set_label(nextaction)
        self._progressbar.set_fraction(fraction)

    # Called when abort button is clicked
    def on_abort(self, widget):
        self._abort = True
        
    # Does the user want to abort operation?
    def should_abort(self):
        return self._abort


# Helper thread class that runs the event loop
class KittyKeProgressThread(threading.Thread):
    def __init__(self):
        super(KittyKeProgressThread, self).__init__()
        self._running = True

    def run(self):
        print("running")
        Gdk.threads_enter()
        while(self._running):
            Gtk.main_iteration_do(True)
        Gdk.threads_leave()
        print("stopping")

    def stop(self):
        self._running = False


# Script file is run directly... have a test run here
if __name__ == '__main__':
    dlg = KittyKeProgressDialog(None, "KittyKernel updates kernel information", False)
    dlg.update(0.0, "Loading repository information...")

    for i in range(10):
        time.sleep(1)
        dlg.update((i+1)/10, "Step " + str(i+1))

        if dlg.should_abort():
            break

    dlg.update(1.0, "Finished.")

    del dlg