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

from veracc.widgets.UnlockBar import UnlockBar, ActionResponse
from gi.repository import Gio, GObject, Gtk, Gdk, Pango

from .widgets import UpdateList, UpdateItem, CircularProgressBar

from .core.common import Database, Follower
from .core.handler import UpdateHandler

import os

import time

import quickstart

# As this is a separate VeraCC module, we need to load translations separately...
TRANSLATION = quickstart.translations.Translation("vera-control-center-module-updates")
TRANSLATION.load()
TRANSLATION.bind_also_locale()

_ = TRANSLATION._

APT_LOGFILE = "/var/log/channels/systemupdate.log"

VARIANT_FILE = "/etc/semplice_variant"

BASE_PROVIDER = "semplice-base.provider"
CURRENT_CHANNEL = "semplice-current"
PROPOSED_COMPONENT = "proposed"
DEVELOPMENT_CHANNEL = "semplice-devel"

BUS_NAME = "org.semplicelinux.channels"

@quickstart.builder.from_file("./modules/updates/updates.glade")
class Scene(quickstart.scenes.BaseScene):
	""" Desktop preferences. """
	
	events = {
		"changed" : ["selected_channel"],
		"toggled" : ["enable_proposed_updates", "enable_development_updates", "show_details_button"],
		"clicked" : ["refresh_button", "download_button", "install_button"],
		"realize" : ["install_scene"],
		"size-allocate" : ["details_textview"],
	}
	
	# Used to define the currently-enabled semplice-base channel. 
	base_channel_enabled = None
	
	# Current variant
	current_variant = "current"
	
	building = False
	
	package_transactions = {}
	
	def on_scene_asked_to_close(self):
		"""
		Do some cleanup
		"""
		
		# If we are in the install scene, return to the main one,
		# but only if the installation has been completed
		if self.objects.main.get_visible_child() == self.objects.install_scene and not self.handler.props.installing:
			self.objects.main.set_visible_child(self.objects.summary)
			
			# Clear list
			self.update_list.clear()
			
			# Check for updates
			self.handler.check(force=True)
			
			return False
		
		# This is relatively safe
		self.bus_cancellable.cancel()
		
		return True
	
	def prepare_scene(self):
		"""
		Fired when doing the scene setup.
		"""
				
		self.scene_container = self.objects.main
		
		# Connect to the handler
		self.handler = UpdateHandler()
		
		# Convenience variable that houses the "installing" state.
		# Used when checking whether to continue following the apt log,
		# without flooding the DBus bus.
		self._installing = False
		
		# Determines if we are following the log or not
		self.following_log = False
		
		# APT_LOG follower (FIXME: should move it elsewhere)
		self.follower = None
		
		# Determines if the log has been fully written to the buffer
		self.log_written = False

		# Set appropriate font size and weight for the "Distribution upgrades" label
		context = self.objects.distribution_upgrade_label.create_pango_context()
		desc = context.get_font_description()
		desc.set_weight(Pango.Weight.LIGHT) # Weight
		desc.set_size(Pango.SCALE*13) # Size
		self.objects.distribution_upgrade_label.override_font(desc)
		
		# Do the same for the "Application updates" label
		self.objects.application_updates_label.override_font(desc)
		
		# ...and for the "The software is up-to-date" one
		self.objects.application_updates_status.override_font(desc)
		
		# ..and for the error_description
		desc.set_size(Pango.SCALE*10)
		self.objects.error_description.override_font(desc)
		
		# ...and for the "Semplice is installing the updates" one
		desc.set_size(Pango.SCALE*20)
		self.objects.install_label.override_font(desc)

		# Create unlockbar
		self.unlockbar = UnlockBar("org.semplicelinux.channels.manage")
		self.objects.summary.pack_start(self.unlockbar, False, False, 0)

		# Set-up channel combobox
		renderer = Gtk.CellRendererText()
		self.objects.selected_channel.pack_start(renderer, True)
		self.objects.selected_channel.add_attribute(renderer, "text", 1)
		self.objects.selected_channel.add_attribute(renderer, "sensitive", 2)
		
		# Create update list
		self.update_list = UpdateList()
		self.objects.application_updates_scroll.add(self.update_list)
		#self.objects.application_updates_content.pack_start(self.update_list, True, True, 5)
		#self.update_list.prepend(Gtk.Label("HAAA"))
		#print(len(self.update_list), self.update_list.props.empty, self.update_list.props.selection_mode)
		self.update_list.show_all()
		
		# Open AppStream database
		Database.open()
		
		#for item in ["glade", "pokerth", "banshee", "gnome-software"]:
		#	self.update_list.add_item(-1, item, "XX", "upgrade", True)
		
		# FIXME
		self.objects.distribution_upgrade.hide()
		
		# Connect to status-toggled
		self.update_list.connect("status-toggled", self.on_status_toggled)
		
		# Connect to lock failed:
		self.handler.connect("lock-failed", self.on_lock_failed)
		
		# Connect to generic failure:
		self.handler.connect("generic-failure", self.on_generic_failure)
		
		# Connect to update found:
		self.handler.connect("update-found", self.on_update_found)
		
		# Connect to package-status-changed
		self.handler.connect("package-status-changed", self.on_package_status_changed)
		
		# Connect to package-fetch signals
		self.handler.connect("package-fetch-started", self.on_package_fetch_started)
		self.handler.connect("package-fetch-failed", self.on_package_fetch_failed)
		self.handler.connect("package-fetch-finished", self.on_package_fetch_finished)

		# React when checking changes
		self.handler.connect("notify::checking", self.on_checking_changed)
		
		# React when refreshing
		self.handler.connect("notify::refreshing", self.on_refreshing_changed)
		
		# React when downloading
		self.handler.connect("notify::downloading", self.on_downloading_changed)
		
		# React when installing
		self.handler.connect("notify::installing", self.on_installing_changed)
		
		# React when we know the total size to download
		self.handler.connect("notify::update-required-download", self.on_update_required_download_changed)
		
		# Ensure that the updates_frame is not sensitive when the settings
		# are locked...
		self.unlockbar.bind_property(
			"lock",
			self.objects.settings_frame,
			"sensitive",
			GObject.BindingFlags.INVERT_BOOLEAN
		)
		
		# Show the up-to-date container if the update list is empty
		self.update_list.bind_property(
			"empty",
			self.objects.application_updates_status,
			"visible",
			GObject.BindingFlags.DEFAULT | GObject.BindingFlags.SYNC_CREATE
		)
		self.handler.bind_property(
			"status-scene",
			self.objects.application_updates_status,
			"visible_child_name",
			GObject.BindingFlags.DEFAULT | GObject.BindingFlags.SYNC_CREATE
		)
		#self.handler.bind_property(
		#	"cache-operation",
		#	self.objects.application_updates_checking_container,
		#	"visible",
		#	GObject.BindingFlags.DEFAULT | GObject.BindingFlags.SYNC_CREATE
		#)
		#self.objects.application_updates_checking_container.bind_property(
		#	"visible",
		#	self.objects.software_uptodate_container,
		#	"visible",
		#	GObject.BindingFlags.INVERT_BOOLEAN | GObject.BindingFlags.SYNC_CREATE
		#)
		self.update_list.bind_property(
			"empty",
			self.objects.application_updates_scroll,
			"visible",
			GObject.BindingFlags.INVERT_BOOLEAN | GObject.BindingFlags.SYNC_CREATE
		)
		self.update_list.bind_property(
			"empty",
			self.objects.application_updates_actions,
			"visible",
			GObject.BindingFlags.INVERT_BOOLEAN | GObject.BindingFlags.SYNC_CREATE
		)
				
		# Show download indicators when the cache is refreshing
		self.handler.bind_property(
			"cache-operation",
			self.objects.spinner,
			"active",
			GObject.BindingFlags.SYNC_CREATE
		)
		self.handler.bind_property(
			"download-operation",
			self.objects.download_rate,
			"visible",
			GObject.BindingFlags.SYNC_CREATE
		)
		self.handler.bind_property(
			"download-operation",
			self.objects.download_eta,
			"visible",
			GObject.BindingFlags.SYNC_CREATE
		)
		self.handler.bind_property(
			"download-rate",
			self.objects.download_rate,
			"label",
			GObject.BindingFlags.DEFAULT
		)
		self.handler.bind_property(
			"download-eta",
			self.objects.download_eta,
			"label",
			GObject.BindingFlags.DEFAULT
		)
		self.handler.bind_property(
			"download-current-item",
			self.objects.download_rate,
			"tooltip_text",
			GObject.BindingFlags.DEFAULT
		)
		self.handler.bind_property(
			"cache-operation",
			self.objects.refresh_button,
			"sensitive",
			GObject.BindingFlags.INVERT_BOOLEAN | GObject.BindingFlags.SYNC_CREATE
		)
		self.handler.bind_property(
			"cache-operation",
			self.update_list,
			"sensitive",
			GObject.BindingFlags.INVERT_BOOLEAN | GObject.BindingFlags.SYNC_CREATE
		)
		self.handler.bind_property(
			"cache-operation",
			self.objects.application_updates_actions,
			"sensitive",
			GObject.BindingFlags.INVERT_BOOLEAN | GObject.BindingFlags.SYNC_CREATE
		)
		
		# Remove sensitiveness on checkbuttons when downloading
		self.handler.bind_property(
			"downloading",
			self.update_list.package_checkbox,
			"sensitive",
			GObject.BindingFlags.INVERT_BOOLEAN | GObject.BindingFlags.SYNC_CREATE
		)
		
		# Update labels in the action buttons accordingly to the current mode
		self.handler.bind_property(
			"download-operation-label",
			self.objects.download_button,
			"label",
			GObject.BindingFlags.SYNC_CREATE
		)
		self.handler.bind_property(
			"install-operation-label",
			self.objects.install_button,
			"label",
			GObject.BindingFlags.SYNC_CREATE
		)
		
		# Update sensitiveness of the install_button when downloading
		self.handler.bind_property(
			"downloading",
			self.objects.install_button,
			"sensitive",
			GObject.BindingFlags.INVERT_BOOLEAN | GObject.BindingFlags.SYNC_CREATE
		)
		
		# Update the installation_scene label
		self.handler.bind_property(
			"install-scene-label",
			self.objects.install_label,
			"label",
			GObject.BindingFlags.SYNC_CREATE
		)
		
		# Show the log textview when "Show details" has been pressed
		self.objects.show_details_button.bind_property(
			"active",
			self.objects.details_scrolled,
			"visible",
			GObject.BindingFlags.SYNC_CREATE
		)
		
		# Switch into the installation mode if channels is already installing
		if self.handler.props.installing:
			self.on_installing_changed()
		else:
			# Check for updates
			if not self.handler.props.refreshing:
				self.handler.check()
			
			# Downloading? Enable the mode
			if self.handler.props.downloading:
				#self.on_downloading_changed()
				self.update_list.enable_downloading_mode()
	
	def on_install_scene_realize(self, widget):
		"""
		Fired when the install_progress is going to be realized.
		"""
				
		# Create a circular progress bar, and add it to the stack
		self.install_progress = CircularProgressBar()
		self.objects.progress_stack.add_named(self.install_progress, "progress")
		
		self.handler.bind_property(
			"install-progress",
			self.install_progress,
			"fraction",
			GObject.BindingFlags.SYNC_CREATE
		)
		
		# Resize the CircularProgressBar so that it has the same requested
		# width and height of the details_scrolled
		width, height = self.objects.details_scrolled.get_size_request()
		self.install_progress.set_size_request(width, height)
		
		# Ensure that the CircularProgressBar stays visible when the
		# details textview is not
		self.objects.details_scrolled.bind_property(
			"visible",
			self.install_progress,
			"visible",
			GObject.BindingFlags.INVERT_BOOLEAN | GObject.BindingFlags.SYNC_CREATE
		)
		
		
		#self.install_progress.show()
		
		#self.objects.show_details_button.set_active(True)
	
	def on_show_details_button_toggled(self, button):
		"""
		Fired when the show_details_button has been toggled.
		"""
		
		if button.props.active and not self.following_log and not self.log_written:
			self.follow_log()
	
	@quickstart.threads.on_idle
	def append_text(self, line):
		"""
		Appends the text to the details_buffer.
		"""
		
		self.objects.details_buffer.insert(
			self.objects.details_buffer.get_end_iter(),
			line
		)
	
	@quickstart.threads.thread
	def follow_log(self):
		"""
		Follows the APT logfile
		"""
		
		self.following_log = True
		
		# Wait until it has been properly created
		while not os.path.exists(APT_LOGFILE) and self._installing:
			time.sleep(1)
		
		if self._installing:
			self.follower = Follower(APT_LOGFILE)
			for line in self.follower:
				Gdk.threads_enter()
				self.append_text(line)
				Gdk.threads_leave()
		else:
			# Not installed anymore, the upgrade process completed
			# So directly dump the entire file:
			with open(APT_LOGFILE) as f:
				for line in f:
					Gdk.threads_enter()
					self.append_text(line)
					Gdk.threads_leave()
			self.log_written = True
		
		self.following_log = False
	
	def on_details_textview_size_allocate(self, textview, allocation):
		"""
		Fired when the new text has been properly allocated.
		"""
		
		adj = self.objects.details_scrolled.get_vadjustment()
		adj.set_value(adj.props.upper - adj.props.page_size)

	
	def on_installing_changed(self, handler=None, value=None):
		"""
		Fired when the service began the package installation.
		"""
		
		# FIXME: Remove that once proper DBus proprieties caching
		# has been implemented
		self._installing = self.handler.props.installing
		
		# FIXME: Should move that elsewhere
		if not self._installing and self.following_log and self.follower:
			# Stop the follower
			print("Stopping follower")
			self.follower.stop()
			self.log_written = True
			self.follower = None
		
		if self._installing:
			# New installation, ensure that we are in a somewhat clean state
			self.log_written = False
			
			# Hide the details scrolled for now
			self.objects.details_scrolled.hide()
			
			# Finally, show the scene!
			self.scene_container.set_visible_child(self.objects.install_scene)

	def on_generic_failure(self, handler, error, description):
		"""
		Fired when the APT Lock failed.
		"""
		
		dialog = Gtk.MessageDialog(
			self.objects.main.get_toplevel(),
			Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
			Gtk.MessageType.ERROR,
			Gtk.ButtonsType.CLOSE,
			error
		)
		dialog.set_title(_("Error"))
		dialog.format_secondary_text(description)
		
		dialog.run()
		dialog.destroy()

	def on_lock_failed(self, handler):
		"""
		Fired when the APT Lock failed.
		"""
		
		return self.on_generic_failure(
			handler,
			_("Unable to lock the APT database"),
			_("Please close the active package managers.")
		)
	
	@quickstart.threads.on_idle
	def on_update_found(self, handler, id, name, version, reason, status, size):
		"""
		Fired when an update has been found.
		"""
		
		self.update_list.add_item(id, name, version, reason, status, size)
	
	@quickstart.threads.on_idle
	def on_package_status_changed(self, handler, id, reason):
		"""
		Fired when a package status has been changed.
		"""
		
		print("STATUS!")
		self.update_list.update_status(id, reason)
	
	def on_package_fetch_started(self, handler, transaction_id, description, shortdesc):
		"""
		Fired when a package is being fetched.
		"""
		
		if not shortdesc in self.update_list.names_with_id:
			# wat?
			return

		# Get package id from the UpdateList			
		id = self.update_list.names_with_id[shortdesc]
		
		# Associate transaction with the id
		self.package_transactions[transaction_id] = id
		
		# Finally update the status on the list
		self.update_list.set_downloading(id, True)
	
	def on_package_fetch_failed(self, handler, transaction_id):
		"""
		Fired when a package failed to download.
		"""
		
		# FIXME: should notify the user!
		
		if not transaction_id in self.package_transactions:
			return
		
		self.update_list.set_downloading(self.package_transactions[transaction_id], False)

	def on_package_fetch_finished(self, handler, transaction_id):
		"""
		Fired when a package has been downloaded.
		"""
				
		if not transaction_id in self.package_transactions:
			return
		
		self.update_list.set_downloading(self.package_transactions[transaction_id], False)
	
	def on_downloading_changed(self, handler, value):
		"""
		Fired when handler's downloading property changed.
		"""
		
		if handler.props.downloading:
			self.update_list.enable_downloading_mode()
		else:
			self.update_list.disable_downloading_mode()
			self.package_transactions = {}
	
	def on_status_toggled(self, updatelist, id, reason):
		"""
		Fired when a package status changed locally.
		"""
		
		print(id, reason)
		
		self.handler.change_status(id, reason)
	
	def on_download_button_clicked(self, button):
		"""
		Fired when the download button has been clicked.
		"""
		
		if not self.handler.props.downloading:
			# Start fetching
			self.handler.fetch()
		else:
			# Stop fetching
			self.handler.fetch_stop()
	
	def on_install_button_clicked(self, button):
		"""
		Fired when the install button has been clicked.
		"""
		
		if not self.handler.props.downloading:
			# Start fetching
			self.handler.fetch(trigger_installation=True)
	
	def on_refresh_button_clicked(self, button):
		"""
		Fired when the refresh button has been clicked.
		"""
		
		# Clear list
		self.update_list.clear()
		
		self.handler.refresh()
	
	def on_checking_changed(self, handler, value):
		"""
		Fired when handler's checking property changed.
		"""
		
		print("Checking changed!")
		
		if not self.handler.props.checking:
			# Expand the update_list
			self.update_list.expand_all()
	
	def on_refreshing_changed(self, handler, value):
		"""
		Fired when handler's refreshing property changed.
		"""
		
		if not self.handler.props.refreshing:
			# Check for updates
			self.handler.check()
	
	def on_update_required_download_changed(self, handler, value):
		"""
		Fired when handler's update-required-download property changed.
		"""
		
		self.objects.download_size.show()
		self.objects.download_size.set_text(
			_("Total download size: %s") % self.handler.props.update_required_download
		)

	def on_selected_channel_changed(self, combobox):
		"""
		Fired when the selected channel has been changed.
		"""
		
		if self.building:
			return
		
		new_channel = self.objects.semplice_base_channels.get_value(combobox.get_active_iter(), 0)
		
		self.Channels.Enable("(s)", new_channel)
		
		# Store the new choice
		self.base_channel_enabled = new_channel
		
		# Check for features
		self.check_for_features()
		

	def on_enable_proposed_updates_toggled(self, checkbutton):
		"""
		Fired when the Enable proposed updates checkbutton has been toggled.
		"""
		
		if self.building:
			return
		
		(self.Channels.EnableComponent if checkbutton.get_active() else self.Channels.DisableComponent)("(ss)", self.base_channel_enabled, PROPOSED_COMPONENT)
	
	def on_enable_development_updates_toggled(self, checkbutton):
		"""
		Fired when the Enable development updates checkbutton has been toggled.
		"""
		
		if self.building:
			return
		
		(self.Channels.Enable if checkbutton.get_active() else self.Channels.Disable)("(s)", DEVELOPMENT_CHANNEL)

	@quickstart.threads.on_idle
	def check_for_features(self):
		"""
		"Enable proposed updates" and "Enable development updates" are
		available only on semplice-current.
		
		This method ensures that those checkbuttons are not sensitive if
		the selected base channel is not semplice-current and loads their
		settings if it is.
		"""
		
		self.building = True
		
		if self.base_channel_enabled == CURRENT_CHANNEL:			
			self.objects.enable_development_updates.set_sensitive(True)
			if self.Channels.GetEnabled("(s)", DEVELOPMENT_CHANNEL):
				self.objects.enable_development_updates.set_active(True)
			else:
				self.objects.enable_development_updates.set_active(False)
		else:
			self.objects.enable_development_updates.set_sensitive(False)
			self.objects.enable_development_updates.set_active(False)

		# Check if the "proposed" channel is available
		if self.Channels.HasComponent("(ss)", self.base_channel_enabled, PROPOSED_COMPONENT):
			self.objects.enable_proposed_updates.set_sensitive(True)
			
			if self.Channels.GetComponentEnabled("(ss)", self.base_channel_enabled, PROPOSED_COMPONENT):
				self.objects.enable_proposed_updates.set_active(True)
			else:
				self.objects.enable_proposed_updates.set_active(False)
		else:
			self.objects.enable_proposed_updates.set_sensitive(False)
			self.objects.enable_proposed_updates.set_active(False)
		
		self.building = False
		
	@quickstart.threads.on_idle
	def load(self):
		"""
		Reloads the semplice_base_channels ListStore.
		"""
		
		self.building = True
		
		self.objects.semplice_base_channels.clear()
		
		for channel in self.Providers.WhatProvides("(s)", BASE_PROVIDER):
			details = self.Channels.GetDetails("(sas)", channel, ["name"])
			itr = self.objects.semplice_base_channels.append(
				[
					channel,
					details["name"] if "name" in details else channel,
					False if self.current_variant == "current" and channel != CURRENT_CHANNEL else True
				]
			)
			
			if self.Channels.GetEnabled("(s)", channel):
				self.objects.selected_channel.set_active_iter(itr)
				self.base_channel_enabled = channel
		
		self.check_for_features()
		
		# self.building will be restored by check_for_features()

	def on_scene_called(self):
		"""
		Fired when the scene has been called.
		"""
		
		# Load current variant
		if os.path.exists(VARIANT_FILE):
			with open(VARIANT_FILE, "r") as f:
				self.current_variant = f.read().strip()

		# Enter in the bus
		self.bus_cancellable = Gio.Cancellable()
		self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, self.bus_cancellable)
		self.Channels = Gio.DBusProxy.new_sync(
			self.bus,
			0,
			None,
			BUS_NAME,
			"/org/semplicelinux/channels/channels",
			"org.semplicelinux.channels.channels",
			self.bus_cancellable
		)
		self.Providers = Gio.DBusProxy.new_sync(
			self.bus,
			0,
			None,
			BUS_NAME,
			"/org/semplicelinux/channels/providers",
			"org.semplicelinux.channels.providers",
			self.bus_cancellable
		)

		# We are locked
		self.unlockbar.emit("locked")
		
		self.load()
