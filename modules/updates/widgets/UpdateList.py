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

from gi.repository import Gtk, GLib, GObject, AppStream

from ..core.common import Database

ICON_SEARCH_WIDTH = 64
ICON_SEARCH_HEIGHT = 64

PACKAGE_ICON_NAME = "package-x-generic"

icon_theme = Gtk.IconTheme.get_default()

class UpdateList(Gtk.TreeView):
	"""
	The package update list.
	"""
	
	__gproperties__ = {
		"empty" : (
			GObject.TYPE_BOOLEAN,
			"Empty",
			"True if the update list is empty, False if not.",
			True,
			GObject.PARAM_READABLE
		)
	}

	__gsignals__ = {
		"status-toggled" : (
			GObject.SIGNAL_RUN_FIRST,
			None,
			(int, str)
		),
	}
	
	dirty = False
	
	iters_with_id = {}
	names_with_id = {}
	
	currently_downloading = []
	download_timeout = 0
	download_pulse_value = 0
	
	def __init__(self):
		"""
		Initializes the class.
		"""
		
		super().__init__()
		
		# Settings
		self.set_headers_visible(False)
		
		# Create model
		self.model = Gtk.TreeStore(
			str, # Reason
			bool, # Status
			str, # Icon
			int, # ID
			str, # Name
			str, # Version
			str, # Size/Download status
			bool, # Downloading
			int, # Downloading pulse
			bool, # Checkbox and package_name visibility
			bool, # Icon visibility
		)
		self.set_model(self.model)
		
		# Create columns
		
		# Package
		self.package_column = Gtk.TreeViewColumn("Package")
		self.package_column.set_expand(True)

		self.package_checkbox = Gtk.CellRendererToggle()
		self.package_checkbox.set_activatable(True)
		self.package_column.pack_start(self.package_checkbox, False)
		self.package_column.add_attribute(self.package_checkbox, "visible", 9)
		self.package_column.add_attribute(self.package_checkbox, "active", 1)
		
		# Handle checkbox toggled signal
		self.package_checkbox.connect("toggled", self.on_status_toggled)

		self.package_icon = Gtk.CellRendererPixbuf()
		self.package_column.pack_start(self.package_icon, False)
		self.package_column.add_attribute(self.package_icon, "visible", 10)
		self.package_column.add_attribute(self.package_icon, "icon_name", 2)

		self.version_spinner = Gtk.CellRendererSpinner()
		self.package_column.pack_start(self.version_spinner, True)
		self.package_column.add_attribute(self.version_spinner, "visible", 7)
		self.package_column.add_attribute(self.version_spinner, "active", 7)
		self.package_column.add_attribute(self.version_spinner, "pulse", 8)
		
		self.package_name = Gtk.CellRendererText()
		self.package_column.pack_start(self.package_name, True)
		#self.package_column.add_attribute(self.package_name, "visible", 7)
		self.package_column.add_attribute(self.package_name, "text", 4)
		
		self.append_column(self.package_column)
		
		# Size column
		self.size_column = Gtk.TreeViewColumn("Size")
		#self.size_column.set_expand(True)

		self.version_size = Gtk.CellRendererText()
		self.size_column.pack_start(self.version_size, True)
		self.size_column.add_attribute(self.version_size, "visible", 9)
		self.size_column.add_attribute(self.version_size, "text", 6)
		
		self.append_column(self.size_column)
		
		# Version

		self.version_column = Gtk.TreeViewColumn("Version")

		#self.version_column.set_expand(True)
		self.version_version = Gtk.CellRendererText()
		self.version_column.pack_start(self.version_version, False)
		self.version_column.add_attribute(self.version_version, "text", 5)

		self.append_column(self.version_column)
		
		# Create main sections:
		# Application updates, New packages, packages to remove, package updates
		self.clear()
	
	def clear(self):
		"""
		Clears the model and creates the main sections.
		"""
		
		self.model.clear()
		self.iters_with_id = {}
		self.names_with_id = {}
		self.dirty = False
		self.notify("empty")
		
		self.application_updates = self.model.append(
			None,
			(
				"upgrade",
				None,
				None,
				-1,
				_("Application updates"),
				None,
				_("Downloaded"), # Workaround
				False,
				0,
				False,
				False,
			)
		)
		
		self.to_install = self.model.append(
			None,
			(
				"install",
				None,
				None,
				-1,
				_("Packages to install"),
				None,
				None,
				False,
				0,
				False,
				False
			)
		)
		
		self.to_remove = self.model.append(
			None,
			(
				"remove",
				None,
				None,
				-1,
				_("Packages to remove"),
				None,
				None,
				False,
				0,
				False,
				False
			)
		)
		
		self.system_updates = self.model.append(
			None,
			(
				"upgrade",
				None,
				None,
				-1,
				_("System updates"),
				None,
				None,
				False,
				0,
				False,
				False
			)
		)
	
	def add_item(self, id, package_name, version, reason, status, size):
		"""
		Adds an item.
		"""
		
		self.component = Database.find_components("pkg:%s" % package_name)
		if self.component:
			self.component = self.component[0] # we search by package name
		
		icon = PACKAGE_ICON_NAME
		if self.component:
			as_icon = self.component.get_icon_by_size(ICON_SEARCH_WIDTH, ICON_SEARCH_HEIGHT)
			if as_icon:
				icon_name = ".".join(os.path.basename(as_icon.get_name()).replace("%s_" % package_name, "", 1).split(".")[:-1])
				if icon_theme.has_icon(icon_name):
					icon = icon_name
				#elif url.startswith("/"):
				#	# FIXME: Should handle resizing
				#	self.icon.set_from_file(url)
		
		# Name
		name = (package_name if not self.component else self.component.get_name())
		
		target = None
		if self.component and reason in ["upgrade", "downgrade"]:
			target = self.application_updates
		elif reason == "install":
			target = self.to_install
		elif reason == "remove":
			target = self.to_remove
		else:
			target = self.system_updates
		
		self.iters_with_id[id] = self.model.append(
			target,
			(
				reason, # Reason
				status, # Status
				icon, # Icon
				id, # ID
				name, # Name
				version, # Version
				size, # size
				False, # Downloading
				0, # Downloading pulse
				True, # Checkbox and package_name visibility
				True, # Icon visibility
			)
		)
		self.names_with_id[package_name] = id
		
		if not self.dirty:
			self.dirty = True
			self.notify("empty")
	
	def update_status(self, id, reason):
		"""
		Updates the status of an item.
		"""
		
		if not id in self.iters_with_id:
			# What?!
			return
		
		self.model.set_value(self.iters_with_id[id], 1, False if reason == "keep" else True)
	
	def enable_downloading_mode(self):
		"""
		Enables the 'downloading' mode.
		"""
		
		print("Entering downloading mode")
		
		if self.download_timeout == 0:
			self.download_timeout = GLib.timeout_add(50, self.on_download_timeout)
	
	def disable_downloading_mode(self):
		"""
		Disables the 'downloading' mode.
		"""
		
		if self.download_timeout > 0:
			GLib.source_remove(self.download_timeout)
			self.download_timeout = 0
		
		# Restore downloading status on currently_downloading items
		for itr in self.currently_downloading:
			# Spinner
			self.model.set_value(itr, 10, True)
			
			# Downloading
			self.model.set_value(itr, 7, False)
		
		self.currently_downloading = []
		self.download_pulse_value = 0
	
	def on_download_timeout(self):
		"""
		Increments the pulse property of every item in self.currently_downloading.
		"""
		
		self.download_pulse_value += 1
				
		for itr in self.currently_downloading:
			self.model.set_value(itr, 8, self.download_pulse_value)
		
		return True
	
	def set_downloading(self, id, status):
		"""
		Sets the download flag on the id.
		"""
		
		if not id in self.iters_with_id:
			# What?!
			return
		
		itr = self.iters_with_id[id]

		if status:
			# Add to self.currently_downloading
			self.currently_downloading.append(itr)
			
			# Hide icon
			self.model.set_value(itr, 10, False)
			
			
			
			#self.package_column.queue_resize()
			#self.version_column.queue_resize()
			self.scroll_to_cell(self.model.get_path(itr), None, False, 0.0, 0.0)
		else:
			self.currently_downloading.remove(itr)
			
			# Show icon
			self.model.set_value(itr, 10, True)
			
			#self.model.set_value(itr, 7, status)
			
			# Set downloaded status
			self.model.set_value(itr, 6, _("Downloaded"))
			
			#self.version_column.queue_resize()

		#print("Setting iter %s to download = %s" % (itr, status))
		self.model.set_value(itr, 7, status)
		
	
	def on_status_toggled(self, renderer, path):
		"""
		Fired when a status checkbutton has been toggled.
		"""
		
		itr = self.model.get_iter(path)
		
		id = self.model.get_value(itr, 3)
		reason = self.model.get_value(itr, 0)
		status = self.model.get_value(itr, 1)
		
		if status:
			# Current status is True, so the user wants to set it to False
			reason = "keep"
		
		self.emit("status-toggled", id, reason)
	
	def do_status_toggled(self, id, reason):
		"""
		Fired when a status has been changed.
		"""
		
		pass
		
	
	def do_get_property(self, property):
		"""
		Returns the value of the specified property.
		"""
		
		if property.name == "empty":
			return not self.dirty
		else:
			return super().do_get_property(property)
