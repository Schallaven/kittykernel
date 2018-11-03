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
#  Defines and setups the main window of kittykernel.
#
# 
#  Warning: Don't read this  source file if  you are annoyed by too many
#           comments. Read source code  of other FOSS projects  instead.
#

import threading
import time
import os
import sys
import gi
import re
import subprocess
from enum import Enum;

gi.require_version('Gtk', '3.0')
gi.require_version('GdkX11', '3.0')  

from gi.repository import Gtk, Gdk, GdkPixbuf, GdkX11, Gio, Pango, GLib, GObject
GObject.threads_init()
Gdk.threads_init()

import kittykecore
import kittykeprogress
import kittykethreads


# Identifiers for columns of the kernel group list
class Group_columns(Enum):
    KITTYKE_GROUP_ICON = 0
    KITTYKE_GROUP_NAME = 1
    KITTYKE_GROUP_VERSION = 2

# Identifiers for columns and their data for the main list
class Columns(Enum):
    KITTYKE_KERNEL_ICON = 0
    KITTYKE_KERNEL = 1
    KITTYKE_INSTALLED = 2
    KITTYKE_VERSION = 3
    KITTYKE_PACKAGE = 4
    KITTYKE_SIZE_DOWNLOAD = 5
    KITTYKE_SIZE_INSTALLED = 6
    KITTYKE_ORIGIN = 7
    KITTYKE_DATA_INDEX = 8


# ittykeMainWindow class is the main class of the application; it is responsible for the main window
class KittykeMainWindow():

    # Setup the UI and some parameters
    def __init__(self):
        try:
            # Read config from file
            self.config = kittykecore.load_config()    

            # Read blacklist
            self.blacklist = kittykecore.load_blacklist()

            # Create the GtkBuilder with the respective glade file of our main window
            self.builder = Gtk.Builder()
            self.builder.add_from_file("/usr/lib/kittykernel/kittykernel.ui")
            self.builder.connect_signals(self)

            # Save the current theme
            self.theme = Gtk.IconTheme.get_default()                            

            # Setup the treeview
            self.setup_treeview()

            # Initial message for the info bar
            self.builder.get_object("current_kernel").set_label(_("Refreshing, please wait..."))

            # The changelog needs a monospace font
            self.changelogview = self.builder.get_object("changelogview")
            self.changelogview.modify_font(Pango.FontDescription("Monospace")) 

            # Main window handle
            self.window = self.builder.get_object("kittykewindow")
            self.window.set_icon_from_file("/usr/lib/kittykernel/kittykernel.svg")
            self.window.show_all()             

            # Init
            self.kernels = []
            self.kernels_ubuntu = []     

            # Do an initial refresh       
            self.init_refresh()

            # Start main loop
            Gtk.main()

        except Exception as e:
            print (e)
            print(sys.exc_info()[0])
            sys.exit(-1)

    # Initial refresh after startup
    def init_refresh(self):
        # Do the actual refresh
        self.do_refresh()

        # Only show warning until user read actually the warning text
        if self.config['Checks']['kittywarning'] == 'nokitty':
            return False

        # Show fancy messagebox with warning and explaination to the user
        warningbox = self.builder.get_object("dialog_kittywarning")
        warningbox.set_transient_for(self.window)
        warningbox.run()

        # User did NOT set the checkbox, i.e. does not want to see the warning again
        if not self.builder.get_object("check_showagain").get_active():
            self.config['Checks']['kittywarning'] = 'nokitty'
            kittykecore.save_config(self.config)

        warningbox.destroy()

        return False

    # This function setups the cellrenderers of both treeviews
    def setup_treeview(self):
        # Save the handle to the treeviews
        self.kernelgroup = self.builder.get_object("treeview_groups")
        self.kerneltree = self.builder.get_object("treeview_kernels")

        # Set handler for selection change
        self.kernelgroup.get_selection().connect("changed", self.on_kernel_major_changed)

        # The changelog; there is only one currently - the highest kernel will have the full changelog including everything else
        self.changelog = ""

        # Construct the column list for columns 1 to 7 (range is exclusive on the upper bound)
        columns = [self.builder.get_object(item) for item in ["tree_kernels_column"+str(x) for x in range(1,8)]]

        # Clear the cell renderer for each column
        for col in columns:
            col.clear()

        # First columns: Icon + Text (used in treeview group)
        cr = Gtk.CellRendererPixbuf()
        columns[0].pack_start(cr, expand=False)
        columns[0].add_attribute(cr, 'pixbuf', Columns.KITTYKE_KERNEL_ICON.value)

        cr = Gtk.CellRendererText()
        columns[0].pack_start(cr, expand=True)
        columns[0].add_attribute(cr, 'markup', Columns.KITTYKE_KERNEL.value)

        # First column is a pixbuf
        cr = Gtk.CellRendererPixbuf()
        columns[1].pack_start(cr, expand=False)
        columns[1].add_attribute(cr, 'pixbuf', Columns.KITTYKE_INSTALLED.value)

        # Add markup-text renderes for the rest
        for index in range(2,7):
            cr = Gtk.CellRendererText()
            columns[index].pack_start(cr, False)
            columns[index].add_attribute(cr, 'markup', Columns.KITTYKE_KERNEL.value + index)

    # Separator draw function for group list
    def group_separator_func(self, model, iter, data):
        return model[iter][2] == "separator"

    # Fill treeview (for example after a refresh)   
    def fill_group_list(self):
        try:
            # Unset current model, if set; this will empty the list
            self.kernelgroup.set_model(None)  
            self.kernelgroup.set_row_separator_func(self.group_separator_func, None)          

            # Setup a new model for the groups
            model_groups = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)

            # Add kernel groups
            for kernel in self.kernels:
                # Check if there is already a group with the same name and continue if so
                group_present = False

                for row in model_groups:
                    if row[Group_columns.KITTYKE_GROUP_VERSION.value] == kernel['version_major']:
                        group_present = True
                        break

                if group_present == True:
                    continue

                # No parent, then add a new one with this major version and a cog symbol
                num_available = [1 if x['version_major'] == kernel['version_major'] else 0 for x in self.kernels].count(1)
                num_downloaded = [1 if x['downloaded'] and x['version_major'] == kernel['version_major'] else 0 for x in self.kernels].count(1)
                num_installed = [1 if x['installed'] and x['version_major'] == kernel['version_major'] else 0 for x in self.kernels].count(1)                    

                # Second, is the active kernel in the current list?
                has_active_kernel = ([1 if x['active'] and x['version_major'] == kernel['version_major'] else 0 for x in self.kernels].count(1) > 0)                    

                # Third, create the string for this top-level node
                node_markup = ["<span foreground='%s'>%s</span>" % (self.config['Colors']['active'], "<b>"+kernel['version_major']+"</b>") if has_active_kernel else kernel['version_major']][0]
                node_markup += " (<span foreground='%s'>%d</span>" % (self.config['Colors']['downloaded'], num_downloaded)
                node_markup += ", <span foreground='%s'>%d</span>" % (self.config['Colors']['installed'], num_installed)
                node_markup += ", %d)" % (num_available)

                # Fourth, create a string for the 'info'-column for the number of supported month
                supporttext = '---'
                for entry in self.support_times:
                    if (kernel['origins'].find(entry['origin']+' ') != -1) and (kernel['version_major'] == entry['version']):
                        if entry['month'] > 0:
                            supporttext = "<span foreground='%s'>supported for another %.0d month(s)</span>" % (self.config['Colors']['supported'], entry['month'])
                        elif entry['month'] < 0:
                            supporttext = "<span foreground='%s'>support expired %.0d month(s) ago</span>" % (self.config['Colors']['expired'], entry['month']*-1)
                        else:
                            supporttext = "<span foreground='%s'>support will expire this month</span>" % (self.config['Colors']['toexpire'])  

                #if len(supporttext) > 0:
                node_markup += "\n" + supporttext

                # We want to sort the listbox by descending version numbers, so find the first iter, which is smaller than the current version
                iternextrow = None
                for row in model_groups:
                    if kittykecore.compare_versions(kernel['version_major'], row[2]) > 0:
                        iternextrow = row.iter
                        break

                # Add to model
                model_groups.insert_before(iternextrow, [self.theme.load_icon("gtk-execute", 22, 0), node_markup, kernel['version_major']])

            # Add empty line and Ubuntu main line kernels            
            model_groups.append([None, "", "separator"])
            model_groups.append([GdkPixbuf.Pixbuf.new_from_file_at_scale("/usr/lib/kittykernel/ubuntu.svg", 22, 22, True), 
                    "Ubuntu mainline kernels archive\nhttp://kernel.ubuntu.com", "ubuntu mainline"])

            # Set model to show
            self.kernelgroup.set_model(model_groups)   

            # Fill kernel list with first item in listbox
            if len(model_groups) > 0:
                self.kernelgroup.get_selection().select_iter(model_groups.get_iter_first())       

            # Delete model
            del model_groups            

        except Exception as e:
            print (e)
            print(sys.exc_info())
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)

    # Fill in the list of regular kernels (repo)
    def fill_kernel_list_repo(self, selected_major):
        # Unset current model, if set; this will empty the list
        self.kerneltree.set_model(None)

        # Setup a new model: Icon, Major version, Icon (installed), Info, Download Size, Installed Size, Origins, Data index
        model_kernels = Gtk.ListStore(GdkPixbuf.Pixbuf, str, GdkPixbuf.Pixbuf, str, str, str, str, str, int) 

        # Add kernels to model
        for index, kernel in enumerate(self.kernels):
            # Should be the major version given
            if not kernel['version_major'] == selected_major:
                continue

            # Show a symbol if the kernel is installed (checkmark)
            pixbufinstalled = [self.theme.load_icon("gtk-yes", 22, 0) if kernel["installed"] else None][0]

            # Prepare extra info for title
            titleadds = []

            if kernel['active']:
                titleadds.append("<i><small><span foreground='%s'>%s</span></small></i>" % (self.config['Colors']['active'], "active"))

            if kernel['installed']:
                titleadds.append("<i><small><span foreground='%s'>%s</span></small></i>" % (self.config['Colors']['installed'], "installed"))

            if kernel['downloaded']:
                titleadds.append("<i><small><span foreground='%s'>%s</span></small></i>" % (self.config['Colors']['downloaded'], "downloaded"))

            # Prepare title (package + extra info)
            title = kernel['package'] + "\n" + ", ".join(titleadds)

            # Add row to model
            iterindex = model_kernels.append([None, "", pixbufinstalled, kernel['version'], title, 
                                     kittykecore.sizeof_fmt(kernel['size']), kittykecore.sizeof_fmt(kernel['installed_size']), kernel['origins'], int(index)])        

        # Set the treeview model to show the new list
        self.kerneltree.set_model(model_kernels)

        # Delete model
        del model_kernels

    # Fill in the list of Ubuntu kernels
    def fill_kernel_list_ubuntu(self):
        # Unset current model, if set; this will empty the list
        self.kerneltree.set_model(None)

        # Load a list of Ubuntu kernels if needed
        if len(self.kernels_ubuntu) == 0:   
            self.kernels_ubuntu = kittykecore.get_ubuntu_kernels()
            self.kernels_ubuntu = kittykecore.apply_blacklist(self.kernels_ubuntu, self.blacklist)

            for index, kernel in enumerate(self.kernels_ubuntu):
                self.kernels_ubuntu[index]['version_major'] = 'ubuntu mainline'

        # Setup a new model: Icon, Major version, Icon (installed), Info, Download Size, Installed Size, Origins, Data index
        model_kernels = Gtk.ListStore(GdkPixbuf.Pixbuf, str, GdkPixbuf.Pixbuf, str, str, str, str, str, int) 

        # Add kernels to model
        for index, kernel in enumerate(self.kernels_ubuntu):  
            # Prepare extra info for title
            titleadds = []

            if kernel['downloaded_files'] == len(kernel['files']):
                titleadds.append("<i><small><span foreground='%s'>%s</span></small></i>" % (self.config['Colors']['installed'], "downloaded"))

            if kernel['downloaded_files'] > 0 and kernel['downloaded_files'] < len(kernel['files']):
                titleadds.append("<i><small><span foreground='%s'>%s</span></small></i>" % (self.config['Colors']['downloaded'], "partly downloaded"))

            # Prepare title (package + extra info)
            title = kernel['package'] + "\n" + ", ".join(titleadds)

            # Add row to model
            iterindex = model_kernels.append([None, "", None, kernel['version'], title, kittykecore.sizeof_fmt(kernel['size']), "", kernel['url'], int(index)])        

        # Set the treeview model to show the new list
        self.kerneltree.set_model(model_kernels)

        # Delete model
        del model_kernels

    # Get selected major version
    def get_kernel_major_selected(self):
         # Get model
        model, groupiter = self.kernelgroup.get_selection().get_selected()

        if groupiter is None:
            return ""

        return model[groupiter][Group_columns.KITTYKE_GROUP_VERSION.value]


    # Fill in the list of kernels based on the major version selected
    def fill_kernel_list(self, selected_major):
        if selected_major == 'ubuntu mainline':
            self.fill_kernel_list_ubuntu()
        else:
            self.fill_kernel_list_repo(selected_major)        

    # Called each time a user selects an entry in the major version list
    def on_kernel_major_changed(self, selection):
        # Get selection
        model, treeiter = selection.get_selected()

        # If there is an item behind this selection (no de-selection)
        if treeiter is not None:
            # Refill list of kernels
            self.fill_kernel_list(model[treeiter][Group_columns.KITTYKE_GROUP_VERSION.value])  

    # Get iter of specific major version: return None if not found
    def get_iter_of_kernel_major(self, version):
        # Get model
        model = self.kernelgroup.get_model()

        # Start with first child
        treeiter = model.iter_children()

        # Iterate over childs
        while(treeiter != None):
            if model[treeiter][Group_columns.KITTYKE_GROUP_VERSION.value] == str(version):
                return treeiter

            # Next element
            treeiter = model.iter_next(treeiter)      

        # Not found?
        return None

    # Update the info bar with current kernel and size of /boot
    def update_infobar(self):
        # Size of /boot
        sizeofboot = kittykecore.sizeof_boot()

        # Size of all kernels, downloaded and installed
        sizeofkernels = 0

        for kernel in self.kernels:
            if kernel['installed']:
                sizeofkernels += kernel['installed_size']
            elif kernel['downloaded']:
                sizeofkernels += kernel['size']

        # Construct the text
        self.builder.get_object("current_kernel").set_label( _("Current kernel version: <b>%s</b>. ") % (kittykecore.get_current_kernel()) \
                                                           + _("/boot: <b>%s</b> of %s free. ") % (kittykecore.sizeof_fmt(sizeofboot[0]), kittykecore.sizeof_fmt(sizeofboot[1])) \
                                                           + _("Kernels occupy <b>%s</b> of space.") % (kittykecore.sizeof_fmt(sizeofkernels)) )

    # Updates the changelog (mainly the colors)
    def update_changelog(self):
        self.changelogview.get_buffer().set_text(self.changelog)

    # Closes the window and exits kittykernel
    def close_window(self, window, event):
        Gtk.main_quit()
        return True

    # Quits the program
    def on_quit(self, widget):
        self.window.close()

    # Opens /boot in the current file manager (by xdg-open)
    def on_openboot_filemanager(self, widget):
        subprocess.call(["xdg-open", "/boot"])

    # Will show the preferences
    def on_preferences(self, widget):
        # Set the options depending on config
        # colors
        for key in self.config['Colors']:
            color_option = "color_" + key
            if self.builder.get_object(color_option) is not None:
                self.builder.get_object(color_option).set_color(Gdk.Color.parse(self.config['Colors'][key])[1])

        # checks
        for key in self.config['Checks']:
            if self.config['Checks'][key] in ['ok', 'nokitty']:
                check_option = "check_" + key
                if self.builder.get_object(check_option) is not None:
                    self.builder.get_object(check_option).set_active(True)

        # Show fancy options dialog
        prefdialog = self.builder.get_object("dialog_kittypreferences")
        prefdialog.set_transient_for(self.window)
        
        # Saves the options if the users presses ok
        if prefdialog.run() == Gtk.ResponseType.OK:
            # colors
            for key in self.config['Colors']:
                color_option = "color_" + key
                if self.builder.get_object(color_option) is not None:
                    self.config['Colors'][key] = self.builder.get_object(color_option).get_color().to_string()

            # checks
            for key in self.config['Checks']:
                check_option = "check_" + key
                if self.builder.get_object(check_option) is not None:
                    if self.builder.get_object(check_option).get_active():
                        # 'nokitty' are for the 'negative' options ('Skip/Remove/...')
                        if key in ['kittywarning']:
                            self.config['Checks'][key] = 'nokitty'
                        else:
                            self.config['Checks'][key] = 'ok'
                    else:
                        self.config['Checks'][key] = ''

            # Save config and refresh
            kittykecore.save_config(self.config)

        # It is important NOT to destroy this dialog if we want to show it again
        prefdialog.hide()

    # Sets text and fraction of progressbar; performs a Gtk iteration to update
    def set_progress(self, text, fraction):
        self.builder.get_object("statusprogress").set_fraction(fraction)
        self.builder.get_object("statustext").set_label(text)
        while Gtk.events_pending(): Gtk.main_iteration_do(False)

    # Do a refresh without cache-update
    def do_refresh(self):      
        # Prepare progress window
        dlg = kittykeprogress.KittyKeProgressDialog(self.window, "KittyKernel updates kernel information", False)
        dlg.update(0.0, "Loading repository information...")

        # Prepare task list   
        tasks = [   ("Loading ~/.config/kittykernel/blacklist", kittykethreads.Worker_Load_Blacklist),
                    ("Loading /usr/lib/kittykernel/kernel_support", kittykethreads.Worker_Load_Supporttimes),
                    ("Loading kernel information from repository", kittykethreads.Worker_Load_Kernels),
                    ("Downloading changelogs", kittykethreads.Worker_Load_Changelogs),
                    ("Loading Ubuntu mainline kernel information from\nhttp://kernel.ubuntu.com/~kernel-ppa/mainline/", kittykethreads.Worker_Load_Ubuntu_Kernels) ]

        # Prepare cache and clean treeviews
        kittykecore.reopen_cache() 
        self.kerneltree.set_model(None)      
        self.kernelgroup.set_model(None)

        # Run each task in a thread
        for index, task in enumerate(tasks):
            # Update the progressbar fraction and text
            dlg.update(index/len(tasks), task[0])
            
            # Prepare thread
            if index in [2, 4]:
                thread = task[1](self.blacklist)
            elif index == 3:
                thread = task[1](self.kernels)
            else:
                thread = task[1]()

            # And start it
            thread.start()                   
            
            # Until the thread is finished, process input (mainly for the dialog)
            while thread.is_alive():
                while Gtk.events_pending(): Gtk.main_iteration_do(False)

            # Gather information from threads
            if index == 0:
                self.blacklist = thread.blacklist
            elif index == 1:
                self.support_times = thread.support_times
            elif index == 2:
                self.kernels = thread.kernels
            elif index == 3:
                self.changelog = thread.changelogs[0]
            elif index == 4:
                self.kernels_ubuntu = thread.kernels_ubuntu

        # Clean up
        dlg.update(1.0, "Finished.")
        dlg.destroy()
        del dlg

        # Fill the GUI stuff
        self.fill_group_list()
        self.update_infobar()

        return      

    # Refreshes the cache
    def on_refresh(self, widget):    
        self.do_refresh()

    # Updates the cache and refreshes
    def on_refresh_apt(self, widget):
        kittykecore.refresh_cache(self.window.get_window().get_xid())  
        self.do_refresh()

    # Refreshes the Ubuntu kernels
    def on_refresh_ubuntu(self, widget):
        self.do_refresh_ubuntu()

    # Show the help window
    def on_help(self, widget):
        os.system('yelp help:kittykernel')

    # Shows the about dialog
    def on_about(self, widget):
        # Setup the about dialog with all the important information
        dlg = Gtk.AboutDialog()
        dlg.set_title(_("About") + " - " + "KittyKernel")
        dlg.set_program_name("kittykernel")
        dlg.set_comments(_("Kernel manager"))
        dlg.set_authors(["Sven Kochmann"])
        dlg.set_icon_from_file("/usr/lib/kittykernel/kittykernel.svg")
        dlg.set_default_icon_from_file("/usr/lib/kittykernel/kittykernel.svg")
        dlg.set_logo(GdkPixbuf.Pixbuf.new_from_file_at_scale("/usr/lib/kittykernel/kittykernel.svg", 256, 256, True))
        dlg.set_website("http://www.github.com/schallaven/kittykernel")
        dlg.set_transient_for(self.window)        
        dlg.set_version("1.4")
        dlg.set_license_type(Gtk.License.GPL_3_0)

        # Contributors, who contributed in form of PRs
        dlg.add_credit_section("Github contributors", ["Fred-Barclay"])

        # Contributors, who contributed from #linux on Spotchat
        dlg.add_credit_section("#linux (Spotchat) contributors", ["Mr W.", "Mr T.", "jeremy31", "zcot"])

        # Run and destroy dialog afterwards        
        dlg.run()
        dlg.destroy()

    # Open cve tracker in browser
    def on_cvetracker(self, widget):
        Gtk.show_uri(None, "https://people.canonical.com/~ubuntu-security/cve/pkg/linux.html", Gtk.get_current_event_time())

    # Open kernel.org
    def on_goto_kernelorg(self, widget):
        Gtk.show_uri(None, "https://www.kernel.org/", Gtk.get_current_event_time())

    # Opens default editor for editing the blacklist
    def on_blacklistedit(self, widget):
        subprocess.call(["xdg-open", os.path.expanduser("~/.config/kittykernel/blacklist")])

    # Get iter of active kernel in the current list; returns None if not in current list/not found
    def get_iter_of_current_kernel(self):
        if self.get_kernel_major_selected() == 'ubuntu mainline':
            return None

        # Get models
        model = self.kerneltree.get_model()

        # Start with first child
        treeiter = model.iter_children()

        # Iterate over childs
        while(treeiter != None):
            index = model[treeiter][Columns.KITTYKE_DATA_INDEX.value]

            # Is it in kernels?            
            if 0 <= index < len(self.kernels):
                if self.kernels[index]['active']:
                    return treeiter

            # Next element
            treeiter = model.iter_next(treeiter)      

        # Not found?
        return None

    # Scrolls to a specific entry in the kernel list
    def go_to_entry(self, iter):
        # Scroll to entry
        self.kerneltree.scroll_to_cell(self.kerneltree.get_model().get_path(iter))

        # Select entry
        self.kerneltree.get_selection().select_iter(iter)

    # Finds and selects current kernel
    def on_go_home(self, widget):       
        # First, select current kernels major version on the left list
        groupiter = self.get_iter_of_kernel_major(kittykecore.get_current_kernel_major())

        if groupiter is None:
            return

        # Select (fills list)
        self.kernelgroup.get_selection().select_iter(groupiter)    

        # Find kernel in filled list
        kerneliter = self.get_iter_of_current_kernel()

        if kerneliter is None:
            return

        # Select
        self.go_to_entry(kerneliter)            

    # Another kernel selected?
    def on_kernelselect(self, selection):
        # No kernels in list?
        if len(self.kernels) == 0:
            return
            
        # Get selection
        model, treeiter = selection.get_selected()

        # Is something selected?
        if treeiter != None:
            index = model[treeiter][Columns.KITTYKE_DATA_INDEX.value]

            # Is it a kernel?
            if 0 <= index < len(self.kernels):
                # Selected kernel version; remove iterative parts separated by ~ until a package is found, i.e.
                # it will look for "(4.10.0-28.32~16.04.2", then for "4.10.0-28.32", and then for "(4.10"
                searchlist = self.kernels[index]['pkg_version'].split('~')

                # Add an extra index for 'worst'-case: look for major version
                for n in range(len(searchlist)+1):
                    searchstr = "~".join(searchlist[:len(searchlist)-n])

                    # Slice empty? Then use major version
                    if searchstr == "":
                        searchstr = self.kernels[index]['version_major']

                    # Add bracket to find sections instead of just every string
                    searchstr = "(" + searchstr

                    # Find first entry, backwards
                    found = self.changelogview.get_buffer().get_start_iter().forward_search(searchstr, 0, None) 

                    # Found? Then select and scroll to line
                    if found:
                        match_start, match_end = found
                        self.changelogview.get_buffer().select_range(match_start, match_end)
                        self.changelogview.scroll_to_iter(match_start, 0.0, True, 0.5, 0.5)
                        break

    # Check for mouse buttons in kernel list
    def on_tree_button_press(self, widget, event):
        # No kernels in list?
        if len(self.kernels) == 0 and len(self.kernels_ubuntu) == 0:
            return

        # Get model
        model = self.kerneltree.get_model()

        # Get path at cursor position
        path = self.kerneltree.get_path_at_pos(event.x, event.y)

        if path == None:
            return

        # The path is actually just the first value
        path = path[0]

        # Get iter from path
        treeiter = self.kerneltree.get_model().get_iter(path)

        # Is something selected?
        if treeiter == None:
            return

        # Index of selected item
        index = model[treeiter][Columns.KITTYKE_DATA_INDEX.value]

        # Right mouse button
        if event.button == 3:     

            # Standard kernel menu   
            menu = self.builder.get_object("menu_kernel")

            # This is a special case, when the selected item is the current kernel
            if self.kernels[index]['active']:
                menu = Gtk.Menu()
                menuItem = Gtk.MenuItem.new_with_label(_("This is the current kernel. Look but do not touch!")) 
                menuItem.set_sensitive(False)      
                menu.attach_to_widget (widget, None)         
                menu.append(menuItem)

            # Ubuntu kernel?
            if self.get_kernel_major_selected() == 'ubuntu mainline':
                menu = self.builder.get_object("menu_kernel_ubuntu")            

            # Show the menu!
            menu.show_all()
            menu.popup(None, None, None, None, event.button, event.time)

    # Check for mouse buttons in kernel group list
    def on_treeview_groups_button_press_event(self, widget, event):
        # No kernels in list?
        if len(self.kernels) == 0 and len(self.kernels_ubuntu) == 0:
            return

        # Right mouse button
        if event.button == 3 and not self.get_kernel_major_selected() == 'ubuntu mainline':    

            # Show kernel group menu   
            menu = self.builder.get_object("menu_kernel_group")
            menu.show_all()
            menu.popup(None, None, None, None, event.button, event.time)


    # Installs a kernel
    def on_kernel_install(self, widget):
        # No kernels in list?
        if len(self.kernels) == 0 and len(self.kernels_ubuntu) == 0:
            return

        # Get selection
        model, treeiter = self.kerneltree.get_selection().get_selected()

        # Is something selected?
        if treeiter != None:
            index = model[treeiter][Columns.KITTYKE_DATA_INDEX.value]

            # Ubuntu kernel
            if self.get_kernel_major_selected() == 'ubuntu mainline':
                # Download kernel and install it then
                kittykecore.debugmode = True
                kittykecore.download_ubuntu_kernel(self.kernels_ubuntu[index])


            # Repo kernel
            else:
                # Is this kernel _not_ installed?
                if not self.kernels[index]['installed']:
                    # Check free space on /boot
                    freeonboot = kittykecore.sizeof_boot()[0]

                    # Warning, when /boot has less than 80 MiB free.
                    if freeonboot < 80000000:
                        dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.WARNING, Gtk.ButtonsType.YES_NO, "Low disk space on /boot")
                        dialog.format_secondary_text(_("/boot is running out of free disk space (%s free). A kernel approximately requires 60-70 MiB. "
                                                       "Please remove kernels you don't need anymore. It is suggested to keep the last working kernel. "
                                                       "\n\nDo you want to continue installing the new kernel?") % (kittykecore.sizeof_fmt(freeonboot)))
                        
                        if dialog.run() == Gtk.ResponseType.NO:
                            dialog.destroy()
                            return

                        dialog.destroy()

                    kittykecore.perform_kernels( [self.kernels[index]['package']], 'install', self.window.get_window().get_xid())
                    self.do_refresh()


    # Removes a kernel
    def on_kernel_remove(self, widget):
        # No kernels in list?
        if len(self.kernels) == 0 and len(self.kernels_ubuntu) == 0:
            return

        # Get selection
        model, treeiter = self.kerneltree.get_selection().get_selected()

        # Is something selected?
        if treeiter != None:
            index = model[treeiter][Columns.KITTYKE_DATA_INDEX.value]

            # Current kernel? Don't touch!
            if self.kernels[index]['active']:
                return

            # Is this kernel installed?
            if self.kernels[index]['installed']:
                kittykecore.perform_kernels( [self.kernels[index]['package']], 'remove', self.window.get_window().get_xid())
                self.do_refresh()

    # Purges a kernel
    def on_kernel_purge(self, widget):
        # No kernels in list?
        if len(self.kernels) == 0:
            return

        # No function for Ubuntu kernels
        if self.get_kernel_major_selected() == 'ubuntu mainline':
            return

        # Get selection
        model, treeiter = self.kerneltree.get_selection().get_selected()

        # Is something selected?
        if treeiter != None:
            index = model[treeiter][Columns.KITTYKE_DATA_INDEX.value]

            # Current kernel? Don't touch!
            if self.kernels[index]['active']:
                return

            # Is this kernel installed?
            if self.kernels[index]['installed'] or self.kernels[index]['downloaded']:
                kittykecore.perform_kernels( [self.kernels[index]['package']], 'purge', self.window.get_window().get_xid())
                self.do_refresh()

    # Purges all kernels except the active one
    def on_kernel_purge_all(self, widget):
        # No kernels in list?
        if len(self.kernels) == 0:
            return

        kernels_to_purge = []

        # Check each kernel
        for kernel in self.kernels:
            # Is active one? Ignore
            if kernel['active']:
                continue

            # Is installed? Then purge!
            if kernel['installed'] or kernel['downloaded']:
                kernels_to_purge.append(kernel['package'])

        # No kernels selected? Display a messagebox
        if len(kernels_to_purge) == 0:
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.CLOSE, _("Nothing to purge"))
            dialog.format_secondary_text( _("No kernels were purged since only the active one is currently installed on the system."))
            dialog.run()
            dialog.destroy()

        # Send to purge function and refresh list afterwards
        else:
            kittykecore.perform_kernels( kernels_to_purge, 'purge', self.window.get_window().get_xid())
            self.do_refresh()

    # Removes all kernels from the currently selected group
    def on_remove_group(self, widget):
        # No kernels in list?
        if len(self.kernels) == 0:
            return

        # No function for Ubuntu kernels
        if self.get_kernel_major_selected() == 'ubuntu mainline':
            return

        # Get model
        model = self.kerneltree.get_model()

        # Start with first child
        treeiter = model.iter_children()

        # Prepare list
        kernels_to_remove = []

        # Iterate over childs
        while(treeiter != None):
            index = model[treeiter][Columns.KITTYKE_DATA_INDEX.value]

            # Kernel should be installed; if yes -> add
            if self.kernels[index]['installed'] and not self.kernels[index]['active']:
                kernels_to_remove.append(self.kernels[index]['package'])

            # Next element
            treeiter = model.iter_next(treeiter)           

        # No kernels selected? Display a messagebox
        if len(kernels_to_remove) == 0:
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.CLOSE, _("Nothing to remove"))
            dialog.format_secondary_text( _("There are no kernels to remove from this group."))
            dialog.run()
            dialog.destroy()

        # Send to purge function and refresh list afterwards
        else:
            kittykecore.perform_kernels( kernels_to_remove, 'remove', self.window.get_window().get_xid())
            self.do_refresh()


    # Purges all kernels from the currently selected group
    def on_purge_group(self, widget):
        # No kernels in list?
        if len(self.kernels) == 0:
            return

        # No function for Ubuntu kernels
        if self.get_kernel_major_selected() == 'ubuntu mainline':
            return

        # Get model
        model = self.kerneltree.get_model()

        # Start with first child
        treeiter = model.iter_children()

        # Prepare list
        kernels_to_purge = []

        # Iterate over childs
        while(treeiter != None):
            index = model[treeiter][Columns.KITTYKE_DATA_INDEX.value]

            # Kernel should be installed; if yes -> add
            if (self.kernels[index]['installed'] or self.kernels[index]['downloaded']) and not self.kernels[index]['active']:
                kernels_to_purge.append(self.kernels[index]['package'])

            # Next element
            treeiter = model.iter_next(treeiter)           

        # No kernels selected? Display a messagebox
        if len(kernels_to_purge) == 0:
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.CLOSE, _("Nothing to purge"))
            dialog.format_secondary_text( _("There are no kernels to purge from this group."))
            dialog.run()
            dialog.destroy()

        # Send to purge function and refresh list afterwards
        else:
            kittykecore.perform_kernels( kernels_to_purge, 'purge', self.window.get_window().get_xid())
            self.do_refresh()






