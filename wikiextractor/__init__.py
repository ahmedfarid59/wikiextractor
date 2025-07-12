#!/usr/bin/env python
# -*- coding: utf-8 -*-

# =============================================================================
#  Version: 3.0 (January 24, 2023)
#  Author: Giuseppe Attardi (attardi@di.unipi.it), University of Pisa
#
#  Contributors:
#   Antonio Fuschetto (fuschett@aol.com)
#   Leonardo Souza (lsouza@amtera.com.br)
#   Juan Manuel Caicedo (juan@cavorite.com)
#   Humberto Pereira (begini@gmail.com)
#   Siegfried-A. Gevatter (siegfried@gevatter.com)
#   Pedro Assis (pedroh2306@gmail.com)
#   Wim Muskee (wimmuskee@gmail.com)
#   Radics Geza (radicsge@gmail.com)
#   Nick Ulven (nulven@github)
#
# =============================================================================
#  Copyright (c) 2009-2023. Giuseppe Attardi (attardi@di.unipi.it).
# =============================================================================
#  This file is part of Tanl.
#
#  Tanl is free software; you can redistribute it and/or modify it
#  under the terms of the GNU Affero General Public License, version 3,
#  as published by the Free Software Foundation.
#
#  Tanl is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
# =============================================================================

"""Wikipedia Extractor:
Extracts and cleans text from a Wikipedia database dump and stores output in a
number of files of similar size in a given directory.
Each file will contain several documents in the format:

	<doc id="" url="" title="">
		...
		</doc>

If the program is invoked with the --json flag, then each file will                                            
contain several documents formatted as json ojects, one per line, with                                         
the following structure

	{"id": "", "revid": "", "url": "", "title": "", "text": "..."}

The program performs template expansion by preprocesssng the whole dump and
collecting template definitions.
"""
