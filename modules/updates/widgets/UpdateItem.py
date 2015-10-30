# -*- coding: utf-8 -*-
#
# updates - Semplice update preferences
# Copyright (C) 2015  Eugenio "g7" Paolantonio
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# Authors:
#    Eugenio "g7" Paolantonio <me@medesimo.eu>
#

import os

from gi.repository import Gtk, AppStream

from ..core.common import Database

ICON_SEARCH_WIDTH = 64
ICON_SEARCH_HEIGHT = 64

PACKAGE_ICON_NAME = "package-x-generic"

icon_theme = Gtk.IconTheme.get_default()

class UpdateItem(Gtk.Box):
	
	"""
	An UpdateItem represents a package that has an update available.
	
	--------------------------------------------------------------------
	| BOX ICON NAME - VERSION                  CHANGELOG SIZE/PROGRESS |
	|                                                                  |
	|     ComponentItem1 - VERSION                       SIZE/PROGRESS |
	|     ComponentItem2 - VERSION                       SIZE/PROGRESS |
	|     ComponentItem3 - VERSION                       SIZE/PROGRESS |
    --------------------------------------------------------------------
	"""

	def __init__(self, package_name):
		"""
		Initializes the widget.
		"""
		
		super().__init__(orientation=Gtk.Orientation.VERTICAL)
		
		# Get the AppStream component if available
		self.component = Database.find_components_by_term("pkg:%s" % package_name)
		if self.component:
			self.component = self.component[0] # we search by package name
		
		# Main container
		self.main_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
		
		# Checkbutton
		self.checkbutton = Gtk.CheckButton()
		
		# Icon
		self.icon = Gtk.Image()
		use_generic_icon = not self.component
		if self.component:
			url = self.component.get_icon_url(ICON_SEARCH_WIDTH, ICON_SEARCH_HEIGHT)
			if url:				
				icon_name = ".".join(os.path.basename(url).replace("%s_" % package_name, "", 1).split(".")[:-1])
				if icon_theme.has_icon(icon_name):
					self.icon.set_from_icon_name(icon_name, Gtk.IconSize.LARGE_TOOLBAR)
				elif url.startswith("/"):
					# FIXME: Should handle resizing
					self.icon.set_from_file(url)
			else:
				use_generic_icon = True
		
		if use_generic_icon:
			pass
			#self.icon.set_from_icon_name(PACKAGE_ICON_NAME, Gtk.IconSize.LARGE_TOOLBAR)
		
		# Name
		self.name = Gtk.Label()
		self.name.set_markup("<b>%s</b>" % (package_name if not self.component else self.component.get_name()))
		
		# Add widgets to the main container
		#self.main_container.pack_start(self.checkbutton, False, False, 2)
		#self.main_container.pack_start(self.icon, False, False, 2)
		#self.main_container.pack_start(self.name, True, True, 2)
		
		# Finally...
		self.pack_start(self.main_container, True, True, 2)
		
		self.component = None
		
		self.show_all()
		
		
