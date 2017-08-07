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
#  Defines and setups the main window of kittykernel.
#
# 
#  Warning: Don't read this  source file if  you are annoyed by too many
#           comments. Read source code  of other FOSS projects  instead.
#

import os
import sys
import gi
import subprocess
from enum import Enum;

gi.require_version('Gtk', '3.0')
gi.require_version('GdkX11', '3.0')  

from gi.repository import Gtk, Gdk, GdkPixbuf, GdkX11, Gio, Pango, GLib

import kittykecore


# Identifiers for columns and their data
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
            # Config should be read from a file or GTK config later
            self.config = dict()

            # This sets some colors for the treeview; should move later in some config file
            self.config['active_color'] = "#600000"
            self.config['installed_color'] = "#006000"
            self.config['downloaded_color'] = "#000060"

            # Create the GtkBuilder with the respective glade file of our main window
            self.builder = Gtk.Builder()
            self.builder.add_from_file("/usr/lib/kittykernel/kittykernel.ui")
            self.builder.connect_signals(self)

            # Save the current theme
            self.theme = Gtk.IconTheme.get_default()                            

            # Setup the treeview
            self.setup_treeview()

            # The changelog needs a monospace font
            self.changelogview = self.builder.get_object("changelogview")
            self.changelogview.modify_font(Pango.FontDescription("Monospace")) 

            # Main window handle
            self.window = self.builder.get_object("kittykewindow")
            self.window.set_icon_from_file("/usr/lib/kittykernel/kittykernel.svg")
            self.window.show_all()  

            # Update some things initially
            self.update_infobar()         

            # Hesitate a little bit with updating, so that the user sees the window before the actual first update happens
            GLib.timeout_add(1000, self.init_refresh)            

            # Start main loop
            Gtk.main()

        except Exception as e:
            print (e)
            print(sys.exc_info()[0])
            sys.exit(-1)

    # Initial refresh after startup
    def init_refresh(self):
        self.do_refresh(False)
        return False

    # This function setups the cellrenderers of the treeview
    def setup_treeview(self):
        # Save the handle to the treeview
        self.kerneltree = self.builder.get_object("treeview_kernels")

        # This is the iter of the current kernel row
        self.currentkerneliter = None

        # The changelog; there is only one currently - the highest kernel will have the full changelog including everything else
        self.changelog = ""

        # Construct the column list for columns 1 to 7 (range is exclusive on the upper bound)
        columns = [self.builder.get_object(item) for item in ["tree_kernels_column"+str(x) for x in range(1,8)]]

        # Clear the cell renderer for each column
        for col in columns:
            col.clear()

        # First columns: Icon + Text 
        cr = Gtk.CellRendererPixbuf()
        columns[0].pack_start(cr, expand=False)
        columns[0].add_attribute(cr, 'pixbuf', Columns.KITTYKE_KERNEL_ICON.value)

        cr = Gtk.CellRendererText()
        columns[0].pack_start(cr, expand=True)
        columns[0].add_attribute(cr, 'text', Columns.KITTYKE_KERNEL.value)

        # Second column is a pixbuf
        cr = Gtk.CellRendererPixbuf()
        columns[1].pack_start(cr, expand=False)
        columns[1].add_attribute(cr, 'pixbuf', Columns.KITTYKE_INSTALLED.value)

        # Add markup-text renderes for the rest
        for index in range(2,7):
            cr = Gtk.CellRendererText()
            columns[index].pack_start(cr, False)
            columns[index].add_attribute(cr, 'markup', Columns.KITTYKE_KERNEL.value + index)

    # Fill treeview (for example after a refresh)   
    def fill_kernel_list(self):
        try:
            # Unset current model, if set; this will empty the list
            self.kerneltree.set_model(None)

            # Setup a new model: Icon, Major version, Icon (installed), Info, Download Size, Installed Size, Origins, Data index
            model = Gtk.TreeStore(GdkPixbuf.Pixbuf, str, GdkPixbuf.Pixbuf, str, str, str, str, str, int) 

            # Get kernels
            self.kernels = kittykecore.get_kernels()

            # Add kernels to model
            for index, kernel in enumerate(self.kernels):   
                # Check if there is already a parent with this major version
                parent = None
                for row in model:
                    # If there is a parent, get its 'iter'
                    if row.parent == None and row[1] == kernel['version_major']:
                        parent = row.iter
                        break

                # Should there be no parent, than add a new one with this major version and a cog symbol; data index should be -1
                if parent == None:
                    parent = model.append(None, [self.theme.load_icon("gtk-execute", 22, 0), kernel['version_major'], None, "", "", "", "", "", -1])

                # Show a symbol if the kernel is installed (checkmark)
                pixbufinstalled = [self.theme.load_icon("gtk-yes", 22, 0) if kernel["installed"] else None][0]

                # Prepare extra info for title
                titleadds = []

                if kernel['active']:
                    titleadds.append("<i><small><span foreground='%s'>%s</span></small></i>" % (self.config['active_color'], "active"))

                if kernel['installed']:
                    titleadds.append("<i><small><span foreground='%s'>%s</span></small></i>" % (self.config['installed_color'], "installed"))

                if kernel['downloaded']:
                    titleadds.append("<i><small><span foreground='%s'>%s</span></small></i>" % (self.config['downloaded_color'], "downloaded"))

                # Prepare title (package + extra info)
                title = kernel['package'] + "\n" + ", ".join(titleadds)

                # Add row to model
                iterindex = model.append(parent, [None, "", pixbufinstalled, kernel['version'], title, 
                                         kittykecore.sizeof_fmt(kernel['size']), kittykecore.sizeof_fmt(kernel['installed_size']), kernel['origins'], int(index)])

                # Current kernel? Let's save the entry
                if kernel['active']:
                    self.currentkerneliter = iterindex        

            # Download kernel of highest version
            if len(self.kernels) > 0:
                self.changelog = kittykecore.get_kernel_changelog(self.kernels[-1]['fullname'])    

            # Set the treeview model to show the new list
            self.kerneltree.set_model(model)

            # Delete model
            del model

        except Exception as e:
            print (e)
            print(sys.exc_info())
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)

    # Update the info bar with current kernel and size of /boot
    def update_infobar(self):
        # Size of /boot
        sizeofboot = kittykecore.sizeof_boot()

        # Construct the text
        self.builder.get_object("current_kernel").set_label( _("Current kernel version") + 
                                                             ": <b>" + kittykecore.get_current_kernel() + "</b>. " +
                                                             _("Free space on /boot") +
                                                             ": <b>%s</b> (%s in total)" % (kittykecore.sizeof_fmt(sizeofboot[0]), kittykecore.sizeof_fmt(sizeofboot[1])) )

    # Updates the changelog (mainly the colors)
    def update_changelog(self):
        self.changelogview.get_buffer().set_text(self.changelog)
        pass

    # Closes the window and exits kittykernel
    def close_window(self, window, event):
        Gtk.main_quit()
        return True

    # Quits the program
    def on_quit(self, widget):
        self.window.close()

    # Will show the preferences
    def on_preferences(self, widget):
        dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.WARNING, Gtk.ButtonsType.CLOSE, "Not implemented yet.")
        dialog.format_secondary_text("Sorry, but the preferences dialog is not implemented, yet.")
        dialog.run()
        dialog.destroy()

    # Sets text and fraction of progressbar; performs a Gtk iteration to update
    def set_progress(self, text, fraction):
        self.builder.get_object("statusprogress").set_fraction(fraction)
        self.builder.get_object("statustext").set_label(text)
        while Gtk.events_pending(): Gtk.main_iteration_do(False)

    # Do a refresh, with or without cache-update
    def do_refresh(self, update = False):      
        # Remove all items from the Treeview
        self.kerneltree.set_model(None)      

        # Refresh cache by the method provided by the core functions
        if update:
            self.set_progress( _("Updating cache..."), 0.20)    
            kittykecore.refresh_cache(self.window.get_window().get_xid())

        # Update the info bar with current kernel and size of /boot
        self.set_progress( _("Updating current kernel and /boot..."), 0.40)    
        self.update_infobar()

        # Fill the kernel list
        self.set_progress( _("Filling kernel list..."), 0.60)   
        kittykecore.reopen_cache() 
        self.fill_kernel_list()

        # Update changelog
        self.set_progress( _("Update change log..."), 0.80)    
        self.update_changelog()

        # Finish
        self.set_progress( _("Ready."), 1.00)    

    # Refreshes the cache
    def on_refresh(self, widget):    
        self.do_refresh(False)

    # Refreshes and updates the cache
    def on_refresh_apt(self, widget):
        self.do_refresh(True)

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
        dlg.set_version("1.0")

        # Read in the GPL file to display the license text and button
        try:
            gpl = ""
            with open('/usr/share/common-licenses/GPL','r') as licensefile:
                gpl = licensefile.read()            
            dlg.set_license(gpl)
        except Exception as e:
            print (e)
            print(sys.exc_info()[0])

        # Run and destroy dialog afterwards        
        dlg.run()
        dlg.destroy()

    # Open cve tracker in browser
    def on_cvetracker(self, widget):
        Gtk.show_uri(None, "https://people.canonical.com/~ubuntu-security/cve/pkg/linux.html", Gtk.get_current_event_time())

    # Open kernel.org
    def on_goto_kernelorg(self, widget):
        Gtk.show_uri(None, "https://www.kernel.org/", Gtk.get_current_event_time())

    # Collapses all entries in the treeview
    def on_collapse_all(self, widget):
        self.kerneltree.collapse_all()

    # Collapses the current group
    def on_collapse(self, widget):
        # No kernels in list?
        if len(self.kernels) == 0:
            return

        # Get selection
        model, treeiter = self.kerneltree.get_selection().get_selected()

        # Has parent?
        if self.kerneltree.get_model().iter_parent(treeiter) != None:
            treeiter = self.kerneltree.get_model().iter_parent(treeiter)

        # Expand parent (or the group itself)
        self.kerneltree.collapse_row(self.kerneltree.get_model().get_path(treeiter))

    # Expands all entries in the treeview
    def on_expand_all(self, widget):
        self.kerneltree.expand_all()

    # Expands the current group
    def on_expand(self, widget):
        # No kernels in list?
        if len(self.kernels) == 0:
            return

        # Get selection
        model, treeiter = self.kerneltree.get_selection().get_selected()

        # Has parent?
        if self.kerneltree.get_model().iter_parent(treeiter) != None:
            treeiter = self.kerneltree.get_model().iter_parent(treeiter)

        # Expand parent (or the group itself)
        self.kerneltree.expand_row(self.kerneltree.get_model().get_path(treeiter), True)

    # Scrolls to a specific entry in the treeview
    def go_to_entry(self, iter):
        # Make sure the parent of the entry is expanded
        self.kerneltree.expand_row(self.kerneltree.get_model().get_path(self.kerneltree.get_model().iter_parent(iter)), True)

        # Scroll to entry
        self.kerneltree.scroll_to_cell(self.kerneltree.get_model().get_path(iter))

        # Select entry
        self.kerneltree.get_selection().select_iter(iter)


    # Finds and selects current kernel
    def on_go_home(self, widget):       
        # Set?
        if self.currentkerneliter:
            self.go_to_entry(self.currentkerneliter)
            

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

    # Check for mouse buttons in tree view
    def on_tree_button_press(self, widget, event):
        # No kernels in list?
        if len(self.kernels) == 0:
            return

        # Get mmodel
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

            # Kernel menu   
            menu = self.builder.get_object("menu_kernel")

            # Actually, the data value is -1, i.e. kernel list
            if index == -1:
                menu = self.builder.get_object("menu_kernel_group")

            # This is a special case, when the selected item is the current kernel
            if model[treeiter][Columns.KITTYKE_DATA_INDEX.value] == model[self.currentkerneliter][Columns.KITTYKE_DATA_INDEX.value]:
                menu = Gtk.Menu()
                menuItem = Gtk.MenuItem.new_with_label(_("This is the current kernel. Look but do not touch!")) 
                menuItem.set_sensitive(False)      
                menu.attach_to_widget (widget, None)         
                menu.append(menuItem)

            # Show the menu!
            menu.show_all()
            menu.popup(None, None, None, None, event.button, event.time)


    # Installs a kernel
    def on_kernel_install(self, widget):
        # No kernels in list?
        if len(self.kernels) == 0:
            return

        # Get selection
        model, treeiter = self.kerneltree.get_selection().get_selected()

        # Is something selected?
        if treeiter != None:
            index = model[treeiter][Columns.KITTYKE_DATA_INDEX.value]

            # Is this kernel _not_ installed?
            if not self.kernels[index]['installed']:
                kittykecore.perform_kernels( [self.kernels[index]['fullname']], 'install', self.window.get_window().get_xid())
                self.do_refresh(False)

    # Removes a kernel
    def on_kernel_remove(self, widget):
        # No kernels in list?
        if len(self.kernels) == 0:
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
                kittykecore.perform_kernels( [self.kernels[index]['fullname']], 'remove', self.window.get_window().get_xid())
                self.do_refresh(False)

    # Purges a kernel
    def on_kernel_purge(self, widget):
        # No kernels in list?
        if len(self.kernels) == 0:
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
                kittykecore.perform_kernels( [self.kernels[index]['fullname']], 'purge', self.window.get_window().get_xid())
                self.do_refresh(False)

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
                kernels_to_purge.append(kernel['fullname'])

        # No kernels selected? Display a messagebox
        if len(kernels_to_purge) == 0:
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.CLOSE, _("Nothing to purge"))
            dialog.format_secondary_text( _("No kernels were purged since only the active one is currently installed on the system."))
            dialog.run()
            dialog.destroy()

        # Send to purge function and refresh list afterwards
        else:
            kittykecore.perform_kernels( kernels_to_purge, 'purge', self.window.get_window().get_xid())
            self.do_refresh(False)

    # Removes all kernels from a specific group
    def on_remove_group(self, widget):
        # No kernels in list?
        if len(self.kernels) == 0:
            return

        # Get selection
        model, treeiter = self.kerneltree.get_selection().get_selected()

        # Has parent?
        if model.iter_parent(treeiter) != None:
            treeiter = model.iter_parent(treeiter)

        # Start with first child
        treeiter = model.iter_children(treeiter)

        # Prepare list
        kernels_to_remove = []

        # Iterate over childs
        while(treeiter != None):
            index = model[treeiter][Columns.KITTYKE_DATA_INDEX.value]

            # This is a special case, when the item is the current kernel -> continue
            if model[treeiter][Columns.KITTYKE_DATA_INDEX.value] == model[self.currentkerneliter][Columns.KITTYKE_DATA_INDEX.value]:
                treeiter = model.iter_next(treeiter)
                continue

            # Kernel should be installed; if yes -> add
            if self.kernels[index]['installed']:
                kernels_to_remove.append(self.kernels[index]['fullname'])

            # Next element
            treeiter = model.iter_next(treeiter)           

        # No kernels selected? Display a messagebox
        if len(kernels_to_remove) == 0:
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.CLOSE, _("Nothing to remove"))
            dialog.format_secondary_text( _("There are no kernels to remove from this tree."))
            dialog.run()
            dialog.destroy()

        # Send to purge function and refresh list afterwards
        else:
            kittykecore.perform_kernels( kernels_to_remove, 'remove', self.window.get_window().get_xid())
            self.do_refresh(False)


    # Purges all kernels from a specific group
    def on_purge_group(self, widget):
        # No kernels in list?
        if len(self.kernels) == 0:
            return

        # Get selection
        model, treeiter = self.kerneltree.get_selection().get_selected()

        # Has parent?
        if model.iter_parent(treeiter) != None:
            treeiter = model.iter_parent(treeiter)

        # Start with first child
        treeiter = model.iter_children(treeiter)

        # Prepare list
        kernels_to_purge = []

        # Iterate over childs
        while(treeiter != None):
            index = model[treeiter][Columns.KITTYKE_DATA_INDEX.value]

            # This is a special case, when the item is the current kernel -> continue
            if model[treeiter][Columns.KITTYKE_DATA_INDEX.value] == model[self.currentkerneliter][Columns.KITTYKE_DATA_INDEX.value]:
                treeiter = model.iter_next(treeiter)
                continue

            # Kernel should be installed; if yes -> add
            if self.kernels[index]['installed'] or self.kernels[index]['downloaded']:
                kernels_to_purge.append(self.kernels[index]['fullname'])

            # Next element
            treeiter = model.iter_next(treeiter)           

        # No kernels selected? Display a messagebox
        if len(kernels_to_purge) == 0:
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.CLOSE, _("Nothing to purge"))
            dialog.format_secondary_text( _("There are no kernels to purge from this tree."))
            dialog.run()
            dialog.destroy()

        # Send to purge function and refresh list afterwards
        else:
            kittykecore.perform_kernels( kernels_to_purge, 'purge', self.window.get_window().get_xid())
            self.do_refresh(False)






