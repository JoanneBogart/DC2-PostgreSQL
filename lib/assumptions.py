# Copyright notice??
from yaml import load as yload
import re
from .misc import PoppingOrderedDict
from .misc import warning
from .sourcetable import Field

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
        self.inf = infile        # string or  file pointer to yaml text file
        self.parsed = None
        self.ignores = None            # store compiled
        # will be dict of table info.  One entry per table. Value is
        # a dict of fields,  key =  name, but without data
        self.finals = None 
        

    def parse(self):
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
    def apply(raw, input_params, input_type=None):
        """
        @param raw           A SourceTable instance, typically read from hdu
        @param input_params  key-value pairs associated with the input
        @param input_type    If more than one type of input file is read in for
                             ingest, indicate which type it is. If used should 
                             match value of 'source' keyword for one or more 
                             tables described in Assumptions instance
        @return              dict of DbImages, 
                             obtained by applying operations as described in
                             our assumptions.
                             For now only handle case where everything
                             goes in a single DbImage
        
        """
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

        #  The dict `remaining` now contains only fields we expect to use
        fields = PoppingOrderedDict()
        table_name = self.parsed['tables'][0]['table']['name']

        column_dicts, column_group_dicts = self._get_columns(0)

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
                field = Field(d['name'], d['dtype'], None, None, d['doc'])
                field = {'name': d['name'], 'type' : d['dtype']}
                fields[d['name']] = field
            else:
                print("Field ", key, 
                      ", known to Assumptions, not found in input")


        dbimage = DbImage(table_name, self, fields)
        dbimage.set_filters([""])

        self.finals = PoppingOrderDict()    
        self.finals[table_name] = dbimage
        
                
        
    def _get_names(self, table_index):
        """
        @param table_index   Index of table as it appears in Assumptions
        Return two lists: one of column names and one of column_group names
        """
        columns = self.parsed['tables'][table_index]['table']['columns']
        column_names = []
        column_group_names = []
        for c in columns:
            if 'column' in c :
               column_names.append(c['name'])
           else:
               column_group_names.append(c['name'])
        return column_names, column_group_names
    def _get_ignores(self):
        if not self.parsed: self.parse()
        
        if 'ignores' in self.parsed: return self.parsed['ignores']
        return None

    def _compile_ignores(self):
        igs = self.get_ignores()
        if igs == None: return
        self.ignores = []
        for ig in igs:
            self.append(re.compile(ig))

    def get_tables(self):
        if not self.parsed: self.parse()
        if 'tables' not in self.parsed: return None

        table_names = []
        for t in self.parsed['tables']:
            table_names.append(t['table']['name'])
        
        return table_names

if __name__=='__main__':
    import sys
    if len(sys.argv) > 1:
        yaml_file = sys.argv[1]
    else:
        yaml_file = 'assumptions.yaml'

    assump = Assumptions(yaml_file)
    #assump.parse()

    tables = assump.get_tables()

    for t in tables:
        print(t)
