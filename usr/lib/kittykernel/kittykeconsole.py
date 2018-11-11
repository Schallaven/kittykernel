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
#  Defines and setups the console main window of kittykernel.
#
# 
#  Warning: Don't read this  source file if  you are annoyed by too many
#           comments. Read source code  of other FOSS projects  instead.
#


import sys
import urwid


# KittykeMainWindow class is the main class of the application; it is responsible for the main window
class KittykeMainWindow():

    # Setup console UI and stuff
    def __init__(self):
        palette = [
            ('body', 'default', 'default'),
            ('head', 'light gray', 'dark blue', 'bold'),
            ('foot', 'light gray', 'dark blue'),
            ('key', 'white', 'dark blue', 'bold'),
            ]

        header_text = ('head', [
            "KittyKernel    "])

        footer_text = ('foot', [
            ('key', "F1"),  " Install  ",
            ('key', "F2"),  " Remove  ",
            ('key', "F3"),  " Purge  ",
            ('key', "F5"),  " Refresh  ",
            ('key', "F7"),  " Home  ",
            ('key', "F9"),  " Config  ",
            ('key', "F10"), " Quit  ",
            ])

        text = urwid.Text("TODO: Here will be the two lists", align = "center")
        text = urwid.AttrWrap(text, "body")
        text = urwid.Filler(text)

        header = urwid.AttrWrap(urwid.Text(header_text), "head")
        footer = urwid.AttrWrap(urwid.Text(footer_text), "foot")
        view = urwid.Frame(urwid.AttrWrap(text, 'body'), header=header, footer=footer)

        loop = urwid.MainLoop(view, palette, unhandled_input = self.handle_input)
        loop.run()

    # Handle input
    def handle_input(self, input):
        if input == "esc" or input == "f10":
            sys.exit(0)
       