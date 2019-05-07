# Copyright notice??
from yaml import load as yload
import re
from .misc import PoppingOrderedDict
from .misc import warning
from .sourcetable import Field
from .dbimage import DbImage
from .expressions import rpn_eval
import numpy as np

class Assumptions(object):
    """
    Maintain information describing a priori assumptions about
    tables in a database and inputs which may or may not be used to
    generate columnes.   Typically initialize by reading a yaml file
    with up to three dict entries for symbols (governing possible 
    substitutions in column names), ignores (describe input columns
    to ignore) and tables.  

    """

    def __init__(self, infile):
        """
        Initialize an Assumptions object
        
        Parameters
        ----------
        infile : str
            yaml file describing assumptions

        """
        self.inf = infile        # string or  file pointer to yaml text file
        self.parsed = None
        self.ignores = None            # store compiled
        # will be dict of table info.  One entry per table. Value is
        # a dict of fields,  key =  name, but without data
        self.finals = None 
        self.constraints = None

    def parse(self):
        """
        Store information from yaml file internally

        """
        if self.parsed:  return self.parsed

        with open(self.inf) as f:
            self.parsed = yload(f)
        self._verify()

    def _verify(self):
        """
        Check that parsed input is not totally off the wall.
        Could do more.
        """
        parsed = self.parsed
        if type(parsed) != type({}):
            raise TypeError("Input is not a dict")
        for k in parsed:
            if k not in ['symbols', 'ignores', 'tables']:
                warning("Assumptions.__verify: Unknown field ", k,
                        " will be ignored ")
                continue
            if type(parsed[k]) != type([]):
                raise TypeException("Contents of {} is not a list!".format(k))
            if k == 'tables':
                for t_elt in parsed['tables']:
                    if type(t_elt) != type({}):
                        raise TypeException("Improper table definition")
                    if 'table' not in t_elt:
                        raise ValueException("Improper table defintion")
                    if 'name' not in t_elt['table']:
                        raise TypeException("Table definition missing name field")
                    #for field in t_elt['table']:
                    #    print('key: ',str(field),' value: ', str(t_elt['table'][field]) )
    def apply(self, raw,  schema_name, **kw):
        """
        'Apply' assumptions to information from an input data file

        Parameters
        ----------
        raw  : SourceTable instance 
             Typically initialized from FITS file
        schema_name : str
        kw   :  dict
            Key-value pairs which may be assoc. with input but not explicitly
            as fields in the SourceTable, such as e.g. visit, raft and sensor

        Returns
        -------
        dict of DbImages, keyed by table name.

        For now only handle case where everything goes in a single DbImage

        """
        print('assumptions.apply kw arguments: ')
        for k in kw:
            print('key is ', k, ' value is ', kw[k])

        # apply ignores
        self._compile_ignores()
        if self.ignores != None:
            remaining = PoppingOrderedDict()
            for key, f in raw.fields.items():
                matched = False
                for p in self.ignores:
                    if p.fullmatch(key):
                        matched = True
                        break;
                if not matched: remaining[key] = f



        #  The dict `remaining` now contains only fields we expect to use.
        #  field name is used for dict key, as in SourceTable.fields

        #  Compute data length from the first field, needed for compute fields
        for k in remaining:
            data_len = len(remaining[k].data)
            break

        fields = PoppingOrderedDict()
        table_name = self.parsed['tables'][0]['table']['name']

        column_dicts, column_group_dicts = self._get_names(0)

        for key, f in remaining.items():
            # check each one matches a column name or column group in our table
            # (For now assume we have only one table)
            matched = False
            for i in range(len(column_dicts)):
                if column_dicts[i]['name'] == key:
                    matched = True
                    fields[key] = f
                    del(column_dicts[i])
                    break
            if matched: continue
            for c in column_group_dicts:
                if re.fullmatch(c['name_re'], key):
                    matched = True
                    fields[key] = f
                    break
            if not matched:
                print("Column ", key, " unknown to Assumptions file")
                # and maybe raise exception?


        # If there are any entries left in column_dicts they better have
        # the compute attribute
        for d in column_dicts:
            if 'compute' in d:
                c_list = d['compute']
                cf_list = []
                for i in range(len(c_list)):
                    cf_list.append(str(c_list[i]).format(**kw))

                s_val = rpn_eval([], cf_list)
                print('computed value ', s_val)
                val = s_val
                if 'int' in d['dtype']: 
                    val = int(s_val)
                    #print('int val ', val)
                if 'float' in d['dtype']: 
                    val = int(s_val)
                    #print('float val ', val)
                dat = np.full([data_len], int(val), np.int64)


                field = Field(d['name'], d['type'], None, dat, d['doc'], 
                              d['compute'])
                fields[d['name']] = field
            else:
                print("Field ", key, 
                      ", known to Assumptions, not found in input")


        dbimage = DbImage(table_name, fields, schema_name)
        dbimage.set_filters([""])

        # If we know about double precision fields which should stay
        # double precision, this would be the place to call
        # dbimage.append_doubles(list-of-names)

        self.finals = PoppingOrderedDict()    
        self.finals[table_name] = dbimage
        
        return self.finals
        
    def _get_names(self, table_index):
        """
        Parameter
        ---------
        table_index : int
            Index of table as it appears in Assumptions

        Returns
        -------
        two lists: one of column names and one of column_group names
        """
        columns = self.parsed['tables'][table_index]['table']['columns']
        column_names = []
        column_group_names = []
        for c in columns:
            if c['column_type'] == 'column' :
                column_names.append(c)
            else:
                column_group_names.append(c)
        return column_names, column_group_names

    def _get_ignores(self):
        if not self.parsed: self.parse()
        
        if 'ignores' in self.parsed: return self.parsed['ignores']
        return None

    def _compile_ignores(self):
        igs = self._get_ignores()
        if igs == None: return
        self.ignores = []
        for ig in igs:
            self.ignores.append(re.compile(ig))

    def get_tables(self):
        """
        Returns
        -------
        list of strings
           Each string is a table name mentioned in the Assumptions
        """
        if not self.parsed: self.parse()
        if 'tables' not in self.parsed: return None

        table_names = []
        for t in self.parsed['tables']:
            table_names.append(t['table']['name'])
        
        return table_names

    def _get_constraints(self):
        if not self.parsed: self.parse()
        
        if 'constraints' in self.parsed: return self.parsed['constraints']
        return None

    def get_foreign_keys(self):
        """
        Returns
        _______
        A list of foreign key definitions
        """
        constraints = _get_constraints
        if constraints is None: return []
        foreign = []
        for c in constraints:
            if c['constraint_type'] == 'fk':
                foreign.append(c)
        return foreign


    def get_indexes(self):
        """
        Returns
        -------
        A list of index definitions
        """
        return []                #   **** TO-DO ****
