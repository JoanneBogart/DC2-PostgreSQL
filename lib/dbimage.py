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
#
# Adapted from dbtable.py
from . import common
from . import config
from .assumptions import Assumptions
from .sourcetable import Field

class DBImage(object):
    """
    This is a class that represents a table in the database.
    By default, the table is assumed to be multiband; in other words,
    the columns in it is a direct product of filters x columns.
    (For band-independent table, use DBTable_BandIndependent).

    However, this class holds columns of a *single* band only.
    To achieve multiband table, use a list of instances of this class.

    For forced source there only is one table and it's band-independent.

    DBTable is a list of algorithms (Algo's). Much of its functionality
    is delegated to class Algo.   But probably won't do this for DBImage.
    Almost all functionality of Algos is not needed

    The only transformation DBImage needs to perform is to establish
    which floating point fields should be single precision and which
    double

    DBImage is responsible for:
        * Generating SQL to creating table
        [* Creating/dropping indexes.  Or may do this elsewhere]
        * Preparing data to be inserted. 
           ** determine floating point precision
           ** add data for 'compute' columns
    """
    __slots__ = ["name", "filters", "assumptions", "fields"]

    def __init__(self, name, assumptions, fields):
        """
        @param  name     Table name
        @param  assumptions The part of Assumptions concerning this table. 
                It's a dict
        @param  fields    Dict mapping field name to a Field (named tuple)
        """
        self.name    = name
        self.filters = None
        self.fields = fields
        # Save that part of Assumptions pertaining to this table
        self.assumptions = assumptions

    def set_filters(self, filters):
        """
        Set list of filters.
        This function must be called before creating table.
        For non-multiband set to [""]

        @param filters (list of str)
        """
        filters = list(filters)
        self.filters = filters


    def transform(self, rerunDir, tract, patch, filter, coord):
        """
        Transform to the style in the DB the fields passed in on construction.
        The parameters are additional information that can be used in the transformation.
        @param rerunDir
            Path to the rerun directory from which to generate the master table
        @param tract
            Tract number.
        @param patch
            Patch number (x*100 + y)
        @param filter
            Filter name
        @param coord
            {"ra": numpy.array, "dec": numpy.array}.
            The angles are in degrees.
        """
        #if 'position' in self.name:
        #    print("# of algorithms: ", len(self.algos.values()))
        for algo in self.algos.values():
            #if 'position' in self.name:
            #    print("Calling transform for alg ", str(algo))
            #if  'ref_coord' in str(type(algo)):
            #    print("Calling transform for ref_coord")
            #    fields = algo.sourceTable.fields
            #    print('about to transform ref_coord. Original stuff:')
            #    for k in fields:  print(k, fields[k])
            algo.transform(rerunDir, tract, patch, filter, coord)
            #if  'ref_coord' in str(type(algo)):
            #    print("Done calling transform for ref_coord")
            #    fields = algo.sourceTable.fields
            #    print('Done transforming ref_coord. New stuff:')
            #    for k in fields:  print(k, fields[k])

    def create(self, cursor, schemaName):
        """
        Create table in the database.
        A primary key "object_id" will be included
        in addition to the fields in the Algo's.
        @param cursor
            DB connection's cursor object
            If None don't actually write to db; just to stdout
        @param schemaName
            Name of the schema in which to locate the master table
        """
        ### members = ['object_id Bigint']

        for filter in self.filters:
            #filt = common.filterToShortName[filter] + "_" if filter else ""
            filt = filter + "_" if filter else ""
            for algo in self.algos.values():
                for name, type in algo.get_backend_fields(filt):
                    members.append("{name}  {type}".format(**locals()))

        members = """,
        """.join(members)

        tableSpace = config.get_table_space()

        create_string = """
        CREATE TABLE "{schemaName}"."{self.name}" (
            {members}
        )
        {tableSpace}
        """.format(**locals())

        if cursor is not None:
            cursor.execute(create_string)
        else:
            print(create_string)

    def create_index(self, cursor, schemaName):
        """
        Create indexes on this table.
        @param cursor
            DB connection's cursor object
        @param schemaName
            Name of the schema in which to locate the master table
        """
        indexSpace = config.get_index_space()

        cursor.execute("""
        CREATE UNIQUE INDEX
            "{self.name}_pkey"
        ON
            "{schemaName}"."{self.name}" (object_id)
        {indexSpace}
        """.format(**locals())
        )
        cursor.execute("""
        ALTER TABLE
            "{schemaName}"."{self.name}"
        ADD PRIMARY KEY USING INDEX
          "{self.name}_pkey"
        """.format(**locals())
        )

    def drop_index(self, cursor, schemaName):
        """
        Drop indexes from this table.
        @param cursor
            DB connection's cursor object
        @param schemaName
            Name of the schema in which to locate the master table
        """
        cursor.execute("""
        ALTER TABLE
            "{schemaName}"."{self.name}"
        DROP CONSTRAINT IF EXISTS
          "{self.name}_pkey"
        """.format(**locals())
        )
        cursor.execute("""
        ALTER TABLE
            "{schemaName}"."{self.name}"
        ALTER COLUMN
            object_id
        DROP NOT NULL
        """.format(**locals())
        )

    def get_backend_field_data(self, filter):
        """
        Get field data for the backend table.
        @param filter (str)
            Filter name.
        @return list of (fieldname, printf_format, [column]).
            'column' is a numpy.array. An example of the return value is:
            ("i_point", "(%.16e,%.16e)", [x, y]),
            in which x and y are numpy.array.
        """
        filt = common.filterToShortName[filter] + "_" if filter else ""
        members = []

        for algo in self.algos.values():
            members += algo.get_backend_field_data(filt)

        return members


    def get_exported_fields(self, filter):
        """
        Get field data for the frontend view.
        @param filter (str)
            Filter name.
        @return list of (fieldname, definition, unit, document).
            Each field can be exported as:
                {definition} AS {fieldname}.
        """
        filt = common.filterToShortName[filter] + "_" if filter else ""
        members = []

        for algo in self.algos.values():
            members += algo.get_frontend_fields(filt)

        return members


class DBImage_BandIndependent(DBImage):
    """
    Band-independent variant of class DBImage.
    Fields in this table are independent of bands:
    they, the same values, are shared by all bands.
    """
    __slots__ = []

    def create(self, cursor, schemaName):
        filters = self.filters
        self.filters = [""]
        try:
            return DBImage.create(self, cursor, schemaName)
        finally:
            self.filters = filters
