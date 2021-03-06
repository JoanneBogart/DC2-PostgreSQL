# Copyright (C) 2019  LSST Dark Energy Science Collaboration (DESC)
#
# This file is part of the project DC2-PostgreSQL
# DC2-PostgreSQL is free software: you can redistribute it and/or modify
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

import re

#def __init__():
varpat = re.compile('x(\d+)$')
subspat = re.compile(r'\{[a-zA-Z_]*\}$')
funcpat = re.compile('([a-zA-Z_]+[:a-zA-Z0-9_.]*)\(\)$')
func2pat = re.compile('([a-zA-Z_]+[:a-zA-Z0-9_.]*)\(,\)$')

def rpn_to_expression(inputs, rpn):
    """
    @param inputs   list of possible variables to be substituted for expressions
    x1, x2, et.
    @param rpn      list of tokens

    @return      String to be evaluated later, e.g. by PostgreSQL as definition
    of variable in a view
    """
    argstack = []
    # varpat = re.compile('x(\d+)$')
    # subspat = re.compile(r'\{[a-zA-Z_]*\}$')
    # funcpat = re.compile('([a-zA-Z_]+[:a-zA-Z0-9_.]*)\(\)$')
    # func2pat = re.compile('([a-zA-Z_]+[:a-zA-Z0-9_.]*)\(,\)$')
    for elt in rpn:
        print("found elt {} of type {}".format(elt, type(elt)))
        try:
            s = float(elt)
            argstack.append(str(elt))
            continue
        except ValueError:
            pass
        m = varpat.match(str(elt))
        if m:
            i = int(m.group(1))
            if i > len(rpn):
                raise ValueError('RPN elt {} references non-existent input'.format(elt))
            # push onto stack
            argstack.append(inputs[i - 1])
            continue
        m = subspat.match(str(elt))
        if m:
            argstack.append(elt)
            continue
        if str(elt) in ['*', '+', '-', '/', '^', '|', '%', '&', 'or', 'and']:
            res = '({} {} {})'.format(argstack.pop(),elt,argstack.pop())
            argstack.append(res)
            continue
        if str(elt) in ['!', 'not']:
            res = '({} {})'.format(elt, argstack.pop())
            argstack.append(res)
            continue
        m = funcpat.match(str(elt))
        if m:
            f = m.group(1)
            if ':' in f:
                f = '"' + f + '"'
            res = '{}({})'.format(f, argstack.pop())
            argstack.append(res)
            continue
        m = func2pat.match(str(elt))
        if m:
            f = m.group(1)
            if ':' in f:
                f = '"' + f + '"'
            res = '{}({},{})'.format(f, argstack.pop(), argstack.pop())
            argstack.append(res)
            continue
        else:
                raise ValueError('Unknown element {} in RPN list'.format(elt))
    if (len(argstack) != 1 ):
        raise ValueError('Bad RPN list')
    return argstack.pop()    

def rpn_eval(inputs, rpn):
    """
    @param inputs   list of possible variables to be substituted for expressions
    x1, x2, et.
    @param rpn      list of tokens
    
    @return   Evaluated expression as a string (even if it's in fact numeric)
    """
    argstack = []
    for elt in rpn:
        f_ok = False
        i_ok = False
        elt_type = type(' ')
        #print("found elt {} of type {}".format(elt, type(elt)))
        try:
            f_elt = float(elt)
            f_ok = True
            elt_type = type(1.2)
        except ValueError:
            pass
        if f_ok:
            try:
                i_elt = int(elt)
                if float(i_elt) == f_elt:
                    elt_type = type(1)
                    i_ok = True
            except ValueError:
                pass

        if elt_type == type(2):
            argstack.append(i_elt)
            continue
        if elt_type == type(1.2):
            argstack.append(f_elt)
            continue

        # elt is a string.   For now the only things we recognize
        # are functions zerofill(int, width) and prepend(intro, orig)
        m = func2pat.match(str(elt))
        if m:
            f = m.group(1)
            if f == 'zerofill':
                width = argstack.pop()
                tofill = str(argstack.pop())
                fmt = '{:0' + '>' + str(width) + '}'
                res = fmt.format(tofill)
                argstack.append(res)
                continue
            if f == 'prepend':
                intro = argstack.pop()
                res = str(intro) + str(argstack.pop())
                argstack.append(res)
                continue
            raise(ValueError, 'Unknown function ' + f)
        else:                  
            argstack.append(str(elt))
            continue
    if (len(argstack) != 1 ):
        raise ValueError('Bad RPN list')
    return argstack.pop()    
        
if __name__ =='__main__':
        
    dets = {'raft' : 23, 'sensor' : 2, 'visit' : '03455567'}
    for k in dets:
        print('Key: ', k, '  Value: ', dets[k])
    
    rpn_list = ['{visit}', 8, 'zerofill(,)', '{sensor}', 2, 'zerofill(,)', 
                'prepend(,)', '{raft}', 1, 'zerofill(,)', 'prepend(,)']
    for i in range(len(rpn_list)):
        rpn_list[i] = str(rpn_list[i]).format(**dets)
        print('Element ', i, ' is ', rpn_list[i])

    res = rpn_eval([], rpn_list)

    print('result is ', res)
    
    
