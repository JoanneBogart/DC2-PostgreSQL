import re
import os,sys
from .finderbase import Finder

class ForcedSourceFinder(Finder):
    """
    Encapsulates information on file names and structure of file hierarchy
    containing forced source data.  That structure is:
    rootdir, containing subdirectories with names of the form
         <visit>-<filter>   
    where <visit> is an integer, zero-filled to some fixed length
    and   <filter> is one of a small set of strings. 
    Each visit directory has raft directories with names of the form
    Rmn    where m and n are digits   (also has other stuff which we ignore)
    Each raft directory has files with names of the form
      forced_<visit>-<filter>-<raft>-Sij-det
     
    Maybe should inherit from a base Finder class?
    """

    def __init__(self, rootdir, min_len=46080, dm_version=""):
        """
        @param rootdir (str)
            Path to root directory containing all forced source data
        @param min_len (int)
            Files of this length have empty data tables but are otherwise
            complete
        @param db_version (str)
            Ignored for now.  Could be used to select form of file
            hierarchy and naming conventions appropriate to a data set
        """
        self.rootdir = rootdir
        self.dm_version = ""

        self.filters = ['u', 'g', 'r', 'i', 'y', 'z' ]
        #self.visit_width = 8    # should use this instead of hard-coding
        self.visit_re = '([0-9]{8})'
        filter_string = ''.join(self.filters)
        self.visitdir_re = self.visit_re + '-[' + filter_string + ']'
        self.raft_re = 'R([0-4]{2})'
        self.ccd_re = 'S([0-2]{2})'
        self.basename_re = '-'.join(['forced_' + self.visitdir_re, self.raft_re,
                                     self.ccd_re, 'det[0-9]{3}.fits'])

        #print(self.basename_re)
        self.basename_fmt = '-'.join(['forced_{}','{}','{}'])
        self.dirs = [self.visitdir_re, self.raft_re]

        self.determiners = ['visit', 'raft', 'sensor']

        # Files of this length have no data
        self.min_len = min_len

        # Convenience to avoid recalculating
        self.__subdirs = []

    def get_determiners(self) :
        """
        Return a list of strings which are used as keyword arguments in
        subsequent 'get' routines in decreasing order of requiredness.
        For example, callers cannot supply the second one without also supply
        the first.
        """
        return self.determiners

    def get_determiner_dict(self, filepath):
        """
        @param  forced source input file
        @return dict of determiner values for specified file
        """
        fbase = os.path.basename(filepath)
        print('get_determiner_dict:  basename ', fbase)
        m = re.fullmatch(self.basename_re, fbase)
        if m:
            d = {'visit' : m.group(1),
                 'raft' : m.group(2),
                 'sensor' : m.group(3)}
            print('Found visit ', d['visit'])
            return d
        raise ValueError('get_determiner_dict: bad filepath argument ' + filepath)

    def get_file_path(self, visit, raft=None, ccd=None) :
        """
        Depending on supplied arguments, return visit directory, visit/raft
        directory, or particular file for visit, raft, ccd
        """
        if (type(visit) != type(3) ):
            raise TypeError("get_file_path: bad visit argument: " + str(visit) )
        if raft is not None:
            if re.fullmatch(self.raft_re, raft) is None:
                raise ValueError("get_file_path: bad raft argument: " + str(raft))
            if ccd is not None:
                if re.fullmatch(self.ccd_re, ccd) is None:
                    raise ValueError("get_file_path: bad ccd argument: " + str(ccd))
        visitstr = '{:08}'.format(visit)
        if len(self.__subdirs) == 0:
            self.__subdirs = os.listdir(self.rootdir)
        visit_dir = None
        for s in self.__subdirs:
            if re.match(visitstr, s):
                visit_dir = s
                break
        if visit_dir is None: return None
        if raft is None:     # Only asked for visit directory
            return os.path.join(self.rootdir, visit_dir)

        raft_dir = os.path.join(self.rootdir,visit_dir, raft)
        if ccd is None:
            return raft_dir
        files = os.listdir(raft_dir)
        for f in files:
            starts_with = self.basename_fmt.format(visit_dir, raft, ccd)
            if re.match(starts_with, f) and re.fullmatch(self.basename_re, f):
                return os.path.join(raft_dir, f)

        return None

    def get_some_file(self) :
        """
           Call in case one just wants to determine the schema
           returns:   file path and dict of determiners
        """

        if len(self.__subdirs) == 0:
            self.__subdirs = os.listdir(self.rootdir)
        for v in self.__subdirs:
            visit = v[:-2]    # strip off filter
            visit_dir = os.path.join(self.rootdir, v)
            rdirs = os.listdir(visit_dir)
            for r in rdirs:
                if re.fullmatch(self.raft_re, r):
                    raft = r[1:]
                    fs = os.listdir(os.path.join(visit_dir, r))
                    for f in fs:
                        #print('Found a file ', f)
                        m = re.fullmatch(self.basename_re, f)
                        if m:
                            d = {'visit' : m.group(1),
                                 'raft' : m.group(2),
                                 'sensor' : m.group(3)}
                            return os.path.join(visit_dir, r, f), d
                
        return None

    def get_visit_files(self, visit, nonempty=True):
        """
        Return a list of all data files belonging to a visit. If nonempty
        is true, exclude files which have empty data tables.
        """
        visitdir = self.get_file_path(visit)
        if visitdir is None: 
            return []
        print('File path for visit ', visit, ' is: ', visitdir)
        files = []
        for d in os.listdir(visitdir):
            if re.fullmatch(self.raft_re, d):
                rdir = os.path.join(visitdir, d)
                print('Found raft dir ',rdir)
                for f in os.listdir(rdir):
                    if re.fullmatch(self.basename_re, f):
                        if nonempty:
                            s = os.stat(os.path.join(rdir,f))
                            if (s.st_size <= self.min_len) : continue
                        files.append(os.path.join(rdir, f))
        return files


if __name__ == '__main__':
    finder = ForcedSourceFinder('/global/cscratch1/sd/desc/DC2/data/Run1.2p/w_2018_39/rerun/coadd-v4/forced')

    aFile = finder.get_some_file()
    if aFile is not None:
        print("Found file " + aFile)

    visit = 210472
    visitdir = finder.get_file_path(visit)
    if visitdir is not None:
        print("Found visit dir: ", visitdir)
        raftdir = finder.get_file_path(visit, raft='R01')
        if raftdir is not None:
            print("Found raft dir: ", raftdir)
            f = finder.get_file_path(visit, raft='R01', ccd='S20')
            if f is not None:
                print("Found file: ", f)


    files = finder.get_visit_files(visit)
    print("Found ", len(files), " files for visit ", visit)
    for f in files[:5]:
        print(f)
