#!/usr/bin/env python

# Imports are copied from ingest-object-catalog.py.
# Might not need them all
import numpy  
import psycopg2
import sys

import lib.fits
import lib.misc
import lib.dbtable
import lib.sourcetable
import lib.common
import lib.config

from lib.assumptions import Assumptions
from lib.forcedsource_finder import ForcedSourceFinder

if lib.config.MULTICORE:
    from lib import pipe_printf

import glob
import io
import itertools
import os
import re
import textwrap

def main():
    import argparse
    cmdline = ' '.join(sys.argv)
    print('Invocation: ' + cmdline)

    parser = argparse.ArgumentParser(
        fromfile_prefix_chars='@',
        description='Read a rerun directory to create "forced" summary table.')

    parser.add_argument('forceddir', 
                        help="Directory from which to read data")
    parser.add_argument('schemaname', 
                        help="DB schema name in which to load data")
    # Table name(s) specified in assumptions file.  Do we need an override?
    #  Maybe something to specify name for dpdd view? Or maybe that belongs
    # in native_to_dpdd.yaml and there should be an argument for that
    # filepath
    parser.add_argument("--db-server", metavar="key=value", nargs="+", 
                        action="append", 
                        help="DB connect parms. Must come after reqd args.")
    parser.add_argument('--create-keys',  action='store_true',
       help="Create index, foreign keys (only; don't insert data)")

    parser.add_argument('--dry-run', dest='dryrun', action='store_true',
                        help="Do not write to db. Ignored for create-index", 
                        default=False)
    parser.add_argument('--no-insert', dest='no_insert', action='store_true',
                        help="Just create tables and views; no inserts", 
                        default=False)
    parser.add_argument('--visits', dest='visits', type=int, nargs='+', 
                        help="Ingest data for specified visits only if present. Else ingest all")
    parser.add_argument('--assumptions', default='forced_source_assumptions.yaml', help="Path to description of prior assumptions about data schema")

    args = parser.parse_args()

    if args.visits is not None:
        print("Processing the following visits:")
        for v in args.visits: print(v)

    if args.db_server:
        lib.config.dbServer.update(keyvalue.split('=', 1) for keyvalue in itertools.chain.from_iterable(args.db_server))

    lib.config.tableSpace = ""
    lib.config.indexSpace = ""

    assumptions = Assumptions(args.assumptions)
    if (args.create_keys):
        create_keys(args.schema, assumptions, args.dryrun)
        exit(0)
    
    finder = ForcedSourceFinder(args.forceddir)

    something = create_table(args.schemaname, finder, assumptions, 
                             args.dryrun)


    if args.no_insert: return

    for v in args.visits:
        insert_visit(args.schemaname, finder, assumptions, v, args.dryrun)

def create_keys(schema, finder, assumptions, dryrun=True):
    """
    Suppose there is an assumptions-file-parsing class
    with methods to return table name(s) and generate
    sql for creating indexes, foreign keys
    assumptions = Assumptions(assumptions_file)
    """
    # if (not dryrun):
    #     #  Get table name list from Assumptions
    #     for t in tables:
    #     if not lib.common.db_table_exists(schema, t):
    #         return False

    # Generate list of SQL commands for creating constraints
    # This should be a service of Assumptions.  Pass in schema name
    # Return a list of strings, each corresponding to one CREATE
    # command.  Or maybe lump together all those belonging to the
    # same table.  Decide what should be done in a single commit.
    if (dryrun):
        # print the list
        return True
    else:
        # Try to execute.
        # return True iff successful
        pass

    return True

def drop_keys(schema, finder, assumptions, dryrun=True):
    # Assumptions routine, given schema name, should generate the SQL
    pass

def create_table(schema, finder, assumptions, dryrun=True):
    """
    @param  schema       (Postgres) schema name
    @param  finder       Instance of class which knows how to find schema 
                         for input data and the data itself
    @param  assumptions  Instance of class describing columns to be 
                         included and excluded, among other things
    @param  dryrun       If true only print out sql.  If false, execute 
    @returns             False if not dryrun and table exists; else True
    If dryrun is False and the table already exists, do nothing.
    Otherwise
    From information in the assumptions file plus information about
    the schema for the input data (obtainable from a file or files
    found for us by the finder) determine the table definition.
    If dryrun just print it out.  Otherwise create the table.
    """

    # If not dryrun, check to see if table(s) already exists
    bNeedCreating = False

    db = lib.common.new_db_connection()

    create_schema_string = 'CREATE SCHEMA IF NOT EXISTS "{schema}"'.format(**locals())

    if not dryrun:
        aTable = assumptions.get_tables()[0]

        with db.cursor() as cursor:
            try:
                cursor.execute('SELECT 0 FROM "{schema}"."{aTable}" WHERE FALSE;'.format(**locals()))
                return False
            except psycopg2.ProgrammingError:
                bNeedCreating = True
                db.rollback()

    if bNeedCreating:
        with db.cursor() as cursor:
            cursor.execute(create_schema_string)
        db.commit()
    # Find a data file path using the finder
    remaining_tables = _get_dbimages(finder, assumptions, schema)
    #afile, determiners = finder.get_some_file()

    #hdus = lib.fits.fits_open(afile)  

    #Read fields into a SourceTable via static method SourceTable.from_hdu
    # Note this should be generalized in case there are several tables.
    # That wouldn't be hard, but still wouldn't be adequate for object
    # catalog, where input for each chunk comes from two different files
    # Simplify a bit by insisting each table stores data from only
    # one of the different files.  This is the case now for object catalog.
    #raw_table = lib.sourcetable.SourceTable.from_hdu(hdus[1])

    #  Assumptions class applies its 'ignores' to cut it down to what we need
    #  Maybe also subdivide into multiple tables if so described in yaml
    #  Also add definitions for columns not obtained from raw read-in
    #remaining_tables = assumptions.apply(raw_table, **determiners)

    # Generate CREATE TABLE string for each table in remaining_tables from 
    #the fields in the table (DbImage object)
    with db.cursor() as cursor:
        for name in remaining_tables:
            remaining_tables[name].transform()
            if dryrun:
                remaining_tables[name].create(None, schema)
            else:
                remaining_tables[name].create(cursor, schema)
    if not dryrun: db.commit()
    return True

def insert_visit(schema, finder, assumptions, visit, dryrun=True):
    """
    @param  schema       (Postgres) schema name
    @param  finder       Instance of class which knows how to find schema 
                         for input data and the data itself
    @param  assumptions  Instance of class describing columns to be 
                         included and excluded, among other things
    @param  visit        integer visit number
    @param  dryrun       If true only print out sql.  If false, insert
                         data for the visit 
    """

    # Find all data files belonging to the visit.   Many may be of
    # the minimum size which indicates they have no data.  Make a
    # list of the rest.
    visit_files = finder.get_visit_files(visit) 

    use_cursor = None
    db = lib.common.new_db_connection()
    with db.cursor() as cursor:
        if not dryrun:
            use_cursor = cursor

        print('using cursor ', str(use_cursor))
        ifile = 0             #   DEBUG
        for vf in visit_files:
            ifile += 1           # DEBUG
            if dryrun and  ifile > 3: return
            determiners = finder.get_determiner_dict(vf)

            # Call routine which looks in temp table (creating if need be)
            # to see if this bit of data has already been processed
            # Includes cursor argument.  If it is None, routine is no-op

            # Go through essentially same 
            # procedure as for create_table to determine what columns we're 
            # looking for and store the column data
            #
            hdus = lib.fits.fits_open(vf)  

            #Read fields into a SourceTable
            raw_table = lib.sourcetable.SourceTable.from_hdu(hdus[1])

            #  Assumptions class applies 'ignores' to cut it down to what we need
            #  Maybe also subdivide into multiple tables if so described in yaml
            remaining_tables = assumptions.apply(raw_table, schema, 
                                                 **determiners)

            for name in remaining_tables:
                remaining_tables[name].transform()
                insert_bit(use_cursor, schema, remaining_tables[name],
                           **determiners)

            #
            # The guts of of the insert for object catalog is in 
            # insert_patch_into_multibandtable.   It
            #    * assembles a list of column names (called `fieldNames`) an 
            #      arrays of column data (called `columns`) and generates format
            #      string (called `format`).   This information all comes from
            #      the dbtable, plus insertion of tab character between fields
            #    * If multicore, use pipe_printf.   Write to a pipe, using zip
            #      to output column-oriented inputs as rows:
            #           for tpl in zip(*columns):
            #               fout.write(format % tpl)
            #       and meanwhile start copying from the pipe to db use copy_from
            #    * otherwise write the whole thing to an in-memory byte stream,
            #      then use copy_from on that.

            #   transform

            #   insert

        # End for-loop over files in visit
        if not dryrun:
            db.commit()

def insert_bit(use_cursor, schema_name, dbimage, **determiners):
    """
    Insert data corresponding to one input file into Postgres
    
    @param   use_cursor   db cursor or None (for dryrun)
    @param   schema_name
    @dbimage DbImage instance
    @determiners  Uniquely determines this part of the data
    """

    columns = []
    field_names = []
    format = ""
    # For convenience stuff schema_name into determiners
    determiners['schema_name'] = schema_name
    dryrun = (use_cursor is None)
    if not dryrun:
        # create table to keep track of ingest if it doesn't already exist
        use_cursor.execute("""
        CREATE TABLE IF NOT EXISTS "{schema_name}"."_temp:forced_bit" (
          visit   Bigint, 
          raft int, 
          sensor int, 
          unique (visit, raft, sensor)
        )
        """.format(**locals())
        )

        # check if our entry is already there
        select_q = """
        SELECT visit FROM "{schema_name}"."_temp:forced_bit" WHERE
        visit={visit} and raft={raft} and sensor={sensor}
        """.format(**determiners)
        use_cursor.execute(select_q)
        if use_cursor.fetchone() is not None:  # bit is already there
            return
        
    first = True
    for name, fmt, cols in dbimage.get_backend_field_data(""):
        columns.extend(cols)
        field_names.append(name)
        if first:
            format = fmt
            first = False
        else:
            format += "\t" + fmt

    if dryrun:    # print a piece of the data and exit
        print("Bit raft={raft}, sensor={sensor}, visit={visit}".format(**determiners))
        #print("field names: ")
        all_fields = ' '.join(field_names)
        print('All fields: ', all_fields)

        print('Format is: \n', format)
        tsv = ''.join(format % tpl for tpl in zip(*columns))
        print('Printing tsv[:600]')
        print(tsv[:600])
        
        return

    format += "\n"
    format = format.encode("utf-8")

    if lib.config.MULTICORE:
        fin = pipe_printf.open(format, *columns)
        if use_cursor is not None:
            use_cursor.copy_from(fin,'"{}"."{}"'.format(schema_name,dbimage.name), 
                                 sep='\t', columns=field_names)
    else:
        tsv = b''.join(format % tpl for tpl in zip(*columns))
        fin = io.BytesIO(tsv)
        if use_cursor is not None:
            use_cursor.copy_from(fin, '"{}"."{}"'.format(schema_name,dbimage.name), 
                                 sep='\t', size=-1, columns=field_names)

    # Update bookkeeping table
    insert_q = """
        INSERT INTO "{schema_name}"."_temp:forced_bit"
        (visit, raft, sensor) values({visit}, {raft}, {sensor})
        """.format(**determiners)
    use_cursor.execute(insert_q)

def _get_dbimages(finder, assumptions, schema):
    """
    Several operations require knowledge of table(s) to be created
    or manipulated.   Knowledge contained in finder + assumptions
    is sufficient
    """
    afile, determiners = finder.get_some_file()
    hdus = lib.fits.fits_open(afile)  

    #Read fields into a SourceTable via static method SourceTable.from_hdu
    raw_table = lib.sourcetable.SourceTable.from_hdu(hdus[1])

    remaining_tables = assumptions.apply(raw_table, schema, **determiners)

    return remaining_tables

if __name__ == "__main__":
    main()
