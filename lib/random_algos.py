# Copyright (C) 2016-2018  Sogo Mineo
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

import importlib

from .misc import PoppingOrderedDict

def _import_algo(name):
    """
    Performs "from .algo.{name} import Algo_{name}"
    @return class Algo_{name} imported from .algo.{name}
    """
    return getattr(
        importlib.import_module("..algo." + name, __name__),
        "Algo_" + name,
    )


random_algos = PoppingOrderedDict(
    (_name, _import_algo(_name))
    for _name in (
        "random_coord",
        "pix",
        "sky",
        "base_InputCount",
        "random_base_PixelFlags",
        "random_base_SdssShape",
    )
)

random_algos_ignored = [
    "footprint",
    "base_PeakCentroid_",
]
