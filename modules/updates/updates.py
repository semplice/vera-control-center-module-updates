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
from gi.repository import Gio, GObject, Gtk

import os

import quickstart

# As this is a separate VeraCC module, we need to load translations separately...
TRANSLATION = quickstart.translations.Translation("vera-control-center-module-updates")
TRANSLATION.load()
TRANSLATION.bind_also_locale()

_ = TRANSLATION._

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
		"toggled" : ["enable_proposed_updates", "enable_development_updates"]
	}
	
	# Used to define the currently-enabled semplice-base channel. 
	base_channel_enabled = None
	
	# Current variant
	current_variant = "current"
	
	building = False
	
	def on_scene_asked_to_close(self):
		"""
		Do some cleanup
		"""
		
		self.bus_cancellable.cancel()
		
		return True
	
	def prepare_scene(self):
		"""
		Fired when doing the scene setup.
		"""
				
		self.scene_container = self.objects.main

		# Create unlockbar
		self.unlockbar = UnlockBar("org.semplicelinux.channels.manage")
		self.objects.main.pack_start(self.unlockbar, False, False, 0)

		# Set-up channel combobox
		renderer = Gtk.CellRendererText()
		self.objects.selected_channel.pack_start(renderer, True)
		self.objects.selected_channel.add_attribute(renderer, "text", 1)
		self.objects.selected_channel.add_attribute(renderer, "sensitive", 2)
		
		# Ensure that the updates_frame is not sensitive when the settings
		# are locked...
		self.unlockbar.bind_property(
			"lock",
			self.objects.updates_frame,
			"sensitive",
			GObject.BindingFlags.INVERT_BOOLEAN
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
					False if (
						(self.current_variant == "current" and channel != CURRENT_CHANNEL) or
						(self.current_variant == "workstation" and channel == CURRENT_CHANNEL)
					) else True
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
