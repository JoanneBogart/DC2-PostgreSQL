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
#from .assumptions import Assumptions
from .sourcetable import Field
import numpy as np

class DbImage(object):
    """
    This is a class that represents a table in the database.
    By default, the table is assumed to be multiband; in other words,
    the columns in it is a direct product of filters x columns.
    (For band-independent table, use DBTable_BandIndependent).

    However, this class holds columns of a *single* band only.
    To achieve multiband table, use a list of instances of this class.

    For forced source there only is one table and it's band-independent.

    DBTable is a list of algorithms (Algo's). Much of its functionality
    is delegated to class Algo.   But probably won't do this for DbImage.
    Almost all functionality of Algos is not needed

    The only transformation DbImage needs to perform is to establish
    which floating point fields should be single precision and which
    double.

    DbImage is responsible for:
        * Generating SQL to creating table
        [* Creating/dropping indexes.  Or may do this elsewhere]
        * Preparing data to be inserted. 
           ** determine floating point precision
           ** add data for 'compute' columns
    """
    __slots__ = ["name", "filters", "fields", "schema_name", "doubles",
                 "foreign", "index"]

    def __init__(self, name,  fields, schema_name, doubles=[],
                 foreign=None, index=None):
        """
        @param  name     Table name
        @param  fields    Dict mapping field name to a Field (named tuple)
        """
        self.name    = name
        self.schema_name = schema_name
        self.fields = fields
        self.doubles = doubles  # list of names of fields preserving dbl prec.
        self.filters = None
        self.foreign = None
        self.index = None

    def set_filters(self, filters):
        """
        Set list of filters.
        This function must be called before creating table.
        For non-multiband set to [""]

        @param filters (list of str)
        """
        filters = list(filters)
        self.filters = filters

    def append_doubles(field_names):
        """
        Saves names of fields which should not be converted from double
        to single precision
        @param   field_names     A list of field names
        """
        self.doubles += field_names

    def accept_foreign(self, foreign):
        """
        Store foreign key definitions to be applied to this table

        Parameters
        ----------
        foreign  : list of dicts 
           Each contains keys `column`, `ref_table` and `ref_column`
        """
        self.foreign = foreign

    def accept_indexes(self, indexes):
        """
        Store index definitions to be applied to this table

        Parameters
        ----------
        indexes  : list of dicts 
           Each contains key `columns` (value is a list) and may contain 
           key `property` (value 'unique' or 'primary')
            
        """
        self.index = indexes

    def transform(self):
        """
        most of the arguments in the original dbtable version were there
        to make it possible to find an image file, but we're not doing
        that here.  The only thing this 'transform' does, at least
        currently, is to figure out which fields should be changed to
        single precision and which should stay double.
        """

        # In dbtable this function ended up being just the following:
        #for algo in self.algos.values():
        #    algo.transform(rerunDir, tract, patch, filter, coord)

        # Here there are no intermediaries (algos).  We operate on
        # fields directly.  And, for forced source, there is nothing
        # which needs to be double because all position information is
        # kept elsewhere.  
        # 

        for fname in self.fields:
            f = self.fields[fname]
            #print('Field ', fname, ' has dtype ', f.data.dtype.name)
            if f.data.dtype.name == "float64":
                if f.name in self.doubles:
                    pass
                else:
                    #convert to single  
                    #print("Converting field named ", f.name)
                    self.fields[fname] = f._replace(data=f.data.astype(np.float32))
        return

            

    def create(self, cursor, schema_name):
        """
        Create table in the database; save schema_name

        @param cursor
            DB connection's cursor object
            If None don't actually write to db; just to stdout
        @param schemaName
            Name of the schema in which to locate the table
        """
        ### members = ['object_id Bigint']  Don't always have this
        print('In DbImage.create( )')
        members = []
        for filter in self.filters:
            #filt = common.filterToShortName[filter] + "_" if filter else ""
            filt = filter + "_" if filter else ""
            #for algo in self.algos.values():
            #for name, type in algo.get_backend_fields(filt):
            for name, type in self._get_backend_fields(filt):
                    members.append("{name}  {type}".format(**locals()))

        members = """,
        """.join(members)

        tableSpace = config.get_table_space()

        create_string = """
        CREATE TABLE "{schema_name}"."{self.name}" (
            {members}
        )
        {tableSpace}
        """.format(**locals())

        if cursor is not None:
            cursor.execute(create_string)
        else:
            print(create_string)

    def create_primary(self, cursor):
        create_pkey_str = """
        ALTER TABLE {fulltable} ADD CONSTRAINT "{table}_pkey" PRIMARY KEY ({cols}) 
        """
        for i in self.index:
            if 'property' in i:
                if i['property'] == 'primary':
                    table = self.name 
                    fulltable = '"' + self.schema_name + '"."' + table + '"'
                    cols = ','.join(i['columns'])
                    create_pkey_q = create_pkey_str.format(**locals())
                    if cursor is None:
                        print(create_pkey_q)
                    else:
                        cursor.execute(create_pkey_q)
                    return    # can only have one primary key
                
    def drop_primary(self, cursor):
        """
        
        """
        drop_pkey_str = """
        ALTER TABLE {fulltable} DROP CONSTRAINT IF EXISTS "{table}_pkey"
        """
        for i in self.index:
            if 'property' in i:
                if i['property'] == 'primary':
                    table = '"' + self.name + '"'
                    fulltable = '"' + self.schema_name + '"."' + self.name + '"'
                    drop_pkey_q = drop_pkey_str.format(**locals())
                    if cursor is None:
                        print(drop_pkey_q)
                    else:
                        cursor.execute(drop_pkey_q)
                    return    # can only have one primary key
            # produce drop.. string
            # if cursor not None exexute; else print

    def create_foreign(self, cursor):
        create_fk_str = """
        ALTER TABLE {fulltable} ADD CONSTRAINT "{table}_{column}_fk"
        FOREIGN KEY ({column}) REFERENCES {reftable} ({refcolumn})
        """ 
        # can add NOT VALID to end of command above to defer validity
        # checking on rows already in the db
        for f in self.foreign:
            table =  self.name
            fulltable = '"' + self.schema_name + '"."' +  self.name + '"'
            column = f['column']
            reftable = '"' + self.schema_name + '"."' + f['ref_table'] + '"'
            refcolumn = f['ref_column']
            # produce create.. string
            create_fk_q = create_fk_str.format(**locals())

            # if cursor not None execute; else print
            if cursor is None:
                print(create_fk_q)
            else:
                cursor.execute(create_fk_q)


    def drop_foreign(self, cursor):
        drop_fk_str = """
        ALTER TABLE {fulltable} DROP CONSTRAINT IF EXISTS "{table}_{column}_fk" 
        """ 
        # can add NOT VALID to end of command above to defer validity
        # checking on rows already in the db
        for f in self.foreign:
            table = self.name
            fulltable = '"' + self.schema_name + '"."' +  self.name + '"'
            column = f['column']

            # produce drop.. string
            drop_fk_q = drop_fk_str.format(**locals())

            # if cursor not None execute; else print
            if cursor is None:
                print(drop_fk_q)
            else:
                cursor.execute(drop_fk_q)

    def _get_backend_fields(self, prefix):
        ret = []
        for field in self.fields.values():
            for f in field.explode(): #  Doesn't do anything in our case
                ret.append((prefix + f.name, f.get_sqltype()))

        # Compute fields will have been added in Assumptions.apply
        return ret

    # def create_index(self, cursor, schemaName):
    #     """
    #     Create indexes on this table.
    #     @param cursor
    #         DB connection's cursor object
    #     @param schemaName
    #         Name of the schema in which to locate the master table
    #     """
    #     indexSpace = config.get_index_space()

    #     cursor.execute("""
    #     CREATE UNIQUE INDEX
    #         "{self.name}_pkey"
    #     ON
    #         "{schemaName}"."{self.name}" (object_id)
    #     {indexSpace}
    #     """.format(**locals())
    #     )
    #     cursor.execute("""
    #     ALTER TABLE
    #         "{schemaName}"."{self.name}"
    #     ADD PRIMARY KEY USING INDEX
    #       "{self.name}_pkey"
    #     """.format(**locals())
    #     )

    # def drop_index(self, cursor, schemaName):
    #     """
    #     Drop indexes from this table.
    #     @param cursor
    #         DB connection's cursor object
    #     @param schemaName
    #         Name of the schema in which to locate the master table
    #     """
    #     cursor.execute("""
    #     ALTER TABLE
    #         "{schemaName}"."{self.name}"
    #     DROP CONSTRAINT IF EXISTS
    #       "{self.name}_pkey"
    #     """.format(**locals())
    #     )
    #     cursor.execute("""
    #     ALTER TABLE
    #         "{schemaName}"."{self.name}"
    #     ALTER COLUMN
    #         object_id
    #     DROP NOT NULL
    #     """.format(**locals())
    #     )

    # Write a version of this analogous to _get_backend_fields above,
    # adapted from Algo.get_backend_field_data
    #
    def get_backend_field_data(self, prefix):
        """
        Get field data for the backend table.
        @param prefix (str)
            prepend to column name  for multiband
        @return list of (fieldname, printf_format, [column]).
            'column' is a numpy.array. An example of the return value is:
            ("i_point", "(%.16e,%.16e)", [x, y]),
            in which x and y are numpy.array.
        """

        members = []
        for field in self.fields.values():
            for f in field.explode():
                members.append((prefix + f.name, f.get_print_format(),
                                f.get_columns()))
        return members

class DbImage_BandIndependent(DbImage):
    """
    Band-independent variant of class DbImage.
    Fields in this table are independent of bands:
    they, the same values, are shared by all bands.
    """
    __slots__ = []

    def create(self, cursor, schemaName):
        filters = self.filters
        self.filters = [""]
        try:
            return DbImage.create(self, cursor, schemaName)
        finally:
            self.filters = filters
