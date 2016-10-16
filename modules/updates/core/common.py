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
import time

# FIXME pending AppStream API update. See #4
#from gi.repository import AppStream
#
#Database = AppStream.Database.new() 
#Database.set_database_path("/var/cache/app-info")

class Follower:
	
	"""
	An equivalent of tail -f.
	
	Note: this performs checks on inodes, so it doesn't react when a
	file truncation happens (but does properly reload the file on a log
	rotation)
	"""
	
	def __init__(self, path):
		"""
		Initializes the class.
		
		`path` is the file path to open.
		"""
		
		self.path = path
		self.file = None
		
		self._stop = False
		
		self._load()
	
	def stop(self):
		"""
		Stops the tailer.
		"""
		
		self._stop = True
	
	def _load(self):
		"""
		Loads the file.
		"""
		
		if self.file:
			self.file.close()
		
		self.file = open(self.path)
		self.inode = os.stat(self.path).st_ino
		self.position = 0
	
	def __iter__(self):
		""""
		Returns self, as per the iterator protocol.
		"""
		
		return self
	
	def __next__(self):
		"""
		Iterates over the file.
		"""
		
		line = None
		
		while not line:
			
			if self._stop:
				# Stop
				self.file.close()
				raise StopIteration
			
			current_position = self.file.tell()
			line = self.file.readline()
			
			if line:
				return line
			else:
				# Check for rotation
				try:
					if os.stat(self.path).st_ino != self.inode:
						self._load()
						continue
				except FileNotFoundError:
					# May happen during rotation
					pass
					
				time.sleep(1)
				self.file.seek(current_position)
