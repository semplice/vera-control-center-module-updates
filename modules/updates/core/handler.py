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

from gi.repository import GObject, GLib, Gio

IFACE = "org.semplicelinux.channels.updates"

class UpdateHandler(GObject.Object):
	
	"""
	This is a proxy between the update UI and channels' DBus updates object.
	
	The UI is expected to use this handler to recieve informations on
	the ongoing update processes.
	
	This object will connect itself to channels' DBus updates object. The
	connection *won't* be released once the user goes back to the home
	view or switches the scene.
	"""
	
	_properties = {}
	
	__gproperties__ = {
		"cache-operation" : (
			GObject.TYPE_BOOLEAN,
			"Cache operation",
			"True if there is a cache operation, False if not.",
			False,
			GObject.PARAM_READABLE
		),
		"download-operation" : (
			GObject.TYPE_BOOLEAN,
			"Download operation",
			"True if there is a download operation, False if not.",
			False,
			GObject.PARAM_READABLE
		),
		"cache-opening" : (
			GObject.TYPE_BOOLEAN,
			"Refreshing",
			"True if the cache is being opened, False if not.",
			False,
			GObject.PARAM_READABLE
		),
		"refreshing" : (
			GObject.TYPE_BOOLEAN,
			"Refreshing",
			"True if the cache is refreshing, False if not.",
			False,
			GObject.PARAM_READABLE
		),
		"checking" : (
			GObject.TYPE_BOOLEAN,
			"Checking",
			"True if channels is checking the updates, False if not.",
			False,
			GObject.PARAM_READABLE,
		),
		"downloading" : (
			GObject.TYPE_BOOLEAN,
			"Downloading",
			"True if channels is downloading the updates, False if not.",
			False,
			GObject.PARAM_READABLE,
		),
		"download-operation-label" : (
			GObject.TYPE_STRING,
			"Download operation label",
			"The text shown in the 'Download' button.",
			"",
			GObject.PARAM_READABLE
		),
		"install-operation-label" : (
			GObject.TYPE_STRING,
			"Install operation label",
			"The text shown in the 'Download & Install' button.",
			"",
			GObject.PARAM_READABLE
		),			
		"download-current-item" : (
			GObject.TYPE_STRING,
			"Current download item",
			"The current item that is being fetched during the download.",
			"",
			GObject.PARAM_READWRITE
		),
		"download-rate" : (
			GObject.TYPE_STRING,
			"Current download rate",
			"The current download rate.",
			"",
			GObject.PARAM_READWRITE
		),
		"download-eta" : (
			GObject.TYPE_STRING,
			"Current download ETA",
			"The current download eta.",
			"",
			GObject.PARAM_READWRITE
		),
		"update-required-download" : (
			GObject.TYPE_STRING,
			"Update download size",
			"The update download size.",
			"",
			GObject.PARAM_READWRITE
		)
	}
	
	__gsignals__ = {
		"update-found" : (
			GObject.SIGNAL_RUN_FIRST,
			None,
			(int, str, str, str, bool, str)
		),
		"package-status-changed" : (
			GObject.SIGNAL_RUN_FIRST,
			None,
			(int, str)
		),
		"package-fetch-started" : (
			GObject.SIGNAL_RUN_FIRST,
			None,
			(int, str, str)
		),
		"package-fetch-finished" : (
			GObject.SIGNAL_RUN_FIRST,
			None,
			(int,)
		),
		"package-fetch-failed" : (
			GObject.SIGNAL_RUN_FIRST,
			None,
			(int,)
		),
	}
	
	download_rate_timeout = 0
	
	def __init__(self):
		"""
		Initializes the class.
		"""
		
		super().__init__()
		
		# g-signals, see below for more details
		self.signal_handlers = {
		}
		
		# Connect to the object
		self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
		self.Updates = Gio.DBusProxy.new_sync(
			self.bus,
			Gio.DBusProxyFlags.DO_NOT_AUTO_START_AT_CONSTRUCTION,
			None,
			"org.semplicelinux.channels",
			"/org/semplicelinux/channels/updates",
			IFACE,
			None
		)
		self.Properties = Gio.DBusProxy.new_sync(
			self.bus,
			Gio.DBusProxyFlags.DO_NOT_AUTO_START_AT_CONSTRUCTION,
			None,
			"org.semplicelinux.channels",
			"/org/semplicelinux/channels/updates",
			"org.freedesktop.DBus.Properties",
			None
		)
		
		# Handle DBus signals
		self.Updates.connect("g-signal", self.on_dbus_signal_changed)
	
	def refresh(self):
		"""
		Refreshes the cache.
		"""
		
		self.Updates.Refresh()
	
	def check(self):
		"""
		Checks for updates.
		"""
		
		self.Updates.CheckUpdates("(bb)", True, False) # FIXME: Handle stable
	
	def change_status(self, id, reason):
		"""
		Changes the status of a package.
		"""
		
		self.Updates.ChangeStatus("(is)", id, reason)
	
	def update_download_rate(self):
		"""
		Updates the refresh-rate property.
		"""
				
		self.set_property("download-rate", self.Properties.Get("(ss)", IFACE, "CurrentDownloadRate"))
		self.set_property("download-eta", self.Properties.Get("(ss)", IFACE, "CurrentDownloadETA"))
		
		return True
	
	def on_dbus_signal_changed(self, proxy, sender, signal, params):
		"""
		Handles DBus signals.
		"""
		
		if signal in self.signal_handlers:
			self.signal_handlers[signal](*params)
		elif signal == "UpdateFound":
			# Package update found!
			self.emit("update-found", *params)
		elif signal == "PackageStatusChanged":
			# Package status changed!
			self.emit("package-status-changed", *params)
			
			# Update required download size
			self.notify("update-required-download")
		elif signal in ("CacheUpdateStarted", "CacheUpdateStopped"):
			# Send notification on refreshing property
			self.notify("refreshing")
			self.notify("cache-operation")
			self.notify("download-operation")
		elif signal in ("CacheOpenProgress", "CacheOpenDone"):
			# Send notification in cache_opening property
			self.notify("cache-opening")
			self.notify("cache-operation")
		elif signal in ("UpdateCheckStarted", "UpdateCheckStopped"):
			# Send notification on checking and cache-opening properties
			self.notify("checking")
			self.notify("cache-operation")
			
			# Get update infos if the check has been completed
			if signal == "UpdateCheckStopped":
				self.notify("update-required-download")
		elif signal in ("PackageAcquireStarted", "PackageAcquireStopped"):
			# Send notification on downloading property
			self.notify("downloading")
			self.notify("download-operation")
			
			self.notify("download-operation-label")
			self.notify("install-operation-label")
		elif signal in ("CacheUpdateItemFetch", "PackageAcquireItemFetch"):
			self.set_property("download-current-item", params[1])
			
			# Fire package-fetch-started if PackageAcquireItemFetch
			if signal == "PackageAcquireItemFetch":
				self.emit("package-fetch-started", *params)
		elif signal == "PackageAcquireItemFailed":
			# Package fetching failed
			self.emit("package-fetch-failed", *params)
		elif signal == "PackageAcquireItemDone":
			# Package fetching finished
			self.emit("package-fetch-finished", *params)
			
			# Update download size
			self.notify("update-required-download")
		
		# Remove the download rate refresh operation if it has stopped
		if signal in ("CacheUpdateStopped", "PackageAcquireStopped") and self.download_rate_timeout > 0:
			GLib.source_remove(self.download_rate_timeout)
			self.download_rate_timeout = 0
	
	#def do_update_property(self, id, name, version, reason, status):
	#	"""
	#	Nothing.
	#	"""
	#	
	#	pass
	
	def do_get_property(self, property):
		"""
		Returns the value of the specified property.
		"""
		
		if property.name in ("refreshing", "downloading"):
			value = self.Properties.Get("(ss)", IFACE, property.name.capitalize())
			
			# Refresh the download rate if value == True
			if value == True and self.download_rate_timeout == 0:
				self.download_rate_timeout = GLib.timeout_add(200, self.update_download_rate)
			
			return value
		elif property.name == "download-operation-label":
			if self.props.downloading:
				return _("Stop download")
			else:
				return _("Download")
		elif property.name == "install-operation-label":
			# FIXME: Handle situations where the operation has been tirggered
			if self.props.downloading:
				return _("Trigger installation")
			else:
				return _("Download & Install")
		elif property.name == "update-required-download":
			return self.Updates.GetUpdateInfos()[0]
		elif property.name == "cache-opening":
			return self.Properties.Get("(ss)", IFACE, "CacheOpening")
		elif property.name == "checking":
			return self.Properties.Get("(ss)", IFACE, "Checking")
		elif property.name == "cache-operation":
			# cache_operation == cache_opening || refreshing
			if self.props.refreshing or self.props.cache_opening or self.props.checking:
				return True
			else:
				return False
		elif property.name == "download-operation":
			# download_operation == downloading || refreshing
			return (self.props.downloading or self.props.refreshing)
		else:
			#return GObject.Object.do_get_property(self, property)
			return self._properties[property.name]
	
	def do_set_property(self, property, value):
		"""
		Sets the property.
		"""
		
		self._properties[property.name] = value

