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

from gi.repository import Gtk, Pango, PangoCairo

import cairo

import quickstart

import math
import time

class CircularProgressBar(Gtk.ProgressBar):
	"""
	A Circular progress bar.
	"""
	
	__gtype_name__ = "CircularProgressBar"
	
	LINE_WIDTH = 2
	RADIUS_PAD = 36
	FONT_SIZE = 24
	
	def _calculate_radius(self):
		
		ret = 2 * self.RADIUS_PAD
		
		return ret
	
	def do_draw(self, cr):
		"""
		Hey.
		"""
		
		bg_color = self.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
		cr.set_source_rgba(*list(bg_color))
		cr.paint()
		
		cr.set_line_width(0.5)
		
		allocation = self.get_allocation()
		center_x = allocation.width / 2
		center_y = allocation.height / 2
		fg_color = self.get_style_context().get_color(Gtk.StateFlags.INSENSITIVE)
		cr.set_source_rgba(*list(fg_color))
		cr.arc(
			center_x,
			center_y,
			self._calculate_radius() - self.LINE_WIDTH / 2,
			0,
			2 * math.pi
		)
		cr.stroke()
		cr.save()
		
		cr.set_line_width(2)
		cr.set_line_cap(cairo.LINE_CAP_ROUND)

		angle1 = math.pi * (3.0/2.0)
		angle2 = angle1 + math.pi*2*self.props.fraction

		fg_color = self.get_style_context().get_background_color(Gtk.StateFlags.SELECTED)
		cr.set_source_rgba(*list(fg_color))
		cr.arc(
			center_x,
			center_y,
			self._calculate_radius() - self.LINE_WIDTH / 2,
			angle1,
			angle2
			#0.5 * 3.14
		)
		cr.stroke()
		cr.save()

		cr.set_source_rgba(*list(fg_color))
		
		layout = self.create_pango_layout("%d%%" % int(self.props.fraction*100))
		description = layout.get_context().get_font_description()
		description.set_weight(Pango.Weight.LIGHT) # Weight
		description.set_size(Pango.SCALE*self.FONT_SIZE) # Size
		layout.set_font_description(description)
		width, height = layout.get_pixel_size()
		cr.move_to(center_x - width/2, center_y - height/2)
		PangoCairo.show_layout(cr, layout)
		
		#cr.set_line_width(1)
		#cr.set_line_cap(cairo.LineCap.ROUND)
	
	def __init__(self):
		"""
		Initializes the class.
		"""
		
		super().__init__()
		
		self.set_size_request(self.RADIUS_PAD*4, self.RADIUS_PAD*4)
