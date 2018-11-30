from __future__ import division, print_function, absolute_import, unicode_literals
#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation
#    This Software is released under the GPL license detailed
#    in the file "license.txt" in the top-level pyGSTi directory
#*****************************************************************
"""
Variables for working with the a model containing Idle, X(pi/2) and Y(pi/2) gates.
"""

import sys as _sys
from . import circuitconstruction as _strc
from . import modelconstruction as _setc
from . import stdtarget as _stdtarget
from collections import OrderedDict as _OrderedDict

#Qubit 1 == spectator
description = "Idle, X(pi/2), and Y(pi/2) gates"

gates = ['Gii','Gxi','Gyi']
fiducials = _strc.circuit_list( [ (), ('Gxi',), ('Gyi',), ('Gxi','Gxi') ] )
#                                     ('Gxi','Gxi','Gxi'), ('Gyi','Gyi','Gyi') ] ) # for 1Q MUB
prepStrs = effectStrs = fiducials

germs = _strc.circuit_list( [('Gii',), ('Gxi',), ('Gyi',), ('Gxi', 'Gyi'),
                                ('Gxi', 'Gyi', 'Gii'), ('Gxi', 'Gii', 'Gyi'), ('Gxi', 'Gii', 'Gii'), ('Gyi', 'Gii', 'Gii'),
                                  ('Gxi', 'Gxi', 'Gii', 'Gyi'), ('Gxi', 'Gyi', 'Gyi', 'Gii'),
                                  ('Gxi', 'Gxi', 'Gyi', 'Gxi', 'Gyi', 'Gyi')] )

#Construct a target model: Identity, X(pi/2), Y(pi/2)
target_model = _setc.build_model([2],[('Q0',)], ['Gii','Gxi','Gyi'],
                                [ "I(Q0)","X(pi/2,Q0)", "Y(pi/2,Q0)"],
                                effectLabels=['00','01','10','11'], effectExpressions=["0","1","2","3"])

_gscache = { ("full","auto"): target_model }
def copy_target(parameterization_type="full", sim_type="auto"):
    """ 
    Returns a copy of the target model in the given parameterization.

    Parameters
    ----------
    parameterization_type : {"TP", "CPTP", "H+S", "S", ... }
        The gate and SPAM vector parameterization type. See 
        :function:`Model.set_all_parameterizations` for all allowed values.
        
    sim_type : {"auto", "matrix", "map", "termorder:X" }
        The simulator type to be used for model calculations (leave as
        "auto" if you're not sure what this is).
    
    Returns
    -------
    Model
    """
    return _stdtarget._copy_target(_sys.modules[__name__],parameterization_type,
                                   sim_type, _gscache)


clifford_compilation = _OrderedDict()
clifford_compilation['Gc1c0'] = ['Gyi', 'Gxi', 'Gii', 'Gii', 'Gii', 'Gii', 'Gii']   
clifford_compilation['Gc2c0'] = ['Gxi', 'Gxi', 'Gxi', 'Gyi', 'Gyi', 'Gyi', 'Gii']   
clifford_compilation['Gc3c0'] = ['Gxi', 'Gxi', 'Gii', 'Gii', 'Gii', 'Gii', 'Gii']     
clifford_compilation['Gc4c0'] = ['Gyi', 'Gyi', 'Gyi', 'Gxi', 'Gxi', 'Gxi', 'Gii']   
clifford_compilation['Gc5c0'] = ['Gxi', 'Gyi', 'Gyi', 'Gyi', 'Gii', 'Gii', 'Gii']
clifford_compilation['Gc6c0'] = ['Gyi', 'Gyi', 'Gii', 'Gii', 'Gii', 'Gii', 'Gii']   
clifford_compilation['Gc7c0'] = ['Gyi', 'Gyi', 'Gyi', 'Gxi', 'Gii', 'Gii', 'Gii']    
clifford_compilation['Gc8c0'] = ['Gxi', 'Gyi', 'Gii', 'Gii', 'Gii', 'Gii', 'Gii']   
clifford_compilation['Gc9c0'] = ['Gxi', 'Gxi', 'Gyi', 'Gyi', 'Gii', 'Gii', 'Gii']   
clifford_compilation['Gc10c0'] = ['Gyi', 'Gxi', 'Gxi', 'Gxi', 'Gii', 'Gii', 'Gii']   
clifford_compilation['Gc11c0'] = ['Gxi', 'Gxi', 'Gxi', 'Gyi', 'Gii', 'Gii', 'Gii']   
clifford_compilation['Gc12c0'] = ['Gyi', 'Gxi', 'Gxi', 'Gii', 'Gii', 'Gii', 'Gii']    
clifford_compilation['Gc13c0'] = ['Gxi', 'Gxi', 'Gxi', 'Gii', 'Gii', 'Gii', 'Gii']   
clifford_compilation['Gc14c0'] = ['Gxi', 'Gyi', 'Gyi', 'Gyi', 'Gxi', 'Gxi', 'Gxi']   
clifford_compilation['Gc15c0'] = ['Gyi', 'Gyi', 'Gyi', 'Gii', 'Gii', 'Gii', 'Gii']    
clifford_compilation['Gc16c0'] = ['Gxi', 'Gii', 'Gii', 'Gii', 'Gii', 'Gii', 'Gii']   
clifford_compilation['Gc17c0'] = ['Gxi', 'Gyi', 'Gxi', 'Gii', 'Gii', 'Gii', 'Gii']   
clifford_compilation['Gc18c0'] = ['Gyi', 'Gyi', 'Gyi', 'Gxi', 'Gxi', 'Gii', 'Gii']   
clifford_compilation['Gc19c0'] = ['Gxi', 'Gyi', 'Gyi', 'Gii', 'Gii', 'Gii', 'Gii']   
clifford_compilation['Gc20c0'] = ['Gxi', 'Gyi', 'Gyi', 'Gyi', 'Gxi', 'Gii', 'Gii']   
clifford_compilation['Gc21c0'] = ['Gyi', 'Gii', 'Gii', 'Gii', 'Gii', 'Gii', 'Gii']   
clifford_compilation['Gc22c0'] = ['Gxi', 'Gxi', 'Gxi', 'Gyi', 'Gyi', 'Gii', 'Gii']   
clifford_compilation['Gc23c0'] = ['Gxi', 'Gyi', 'Gxi', 'Gxi', 'Gxi', 'Gii', 'Gii']   



global_fidPairs =  [
    (0, 1), (2, 0), (2, 1), (3, 3)]

pergerm_fidPairsDict = {
  ('Gii',): [
        (1, 1), (2, 2), (3, 3)],
  ('Gxi',): [
        (1, 2), (2, 2), (3, 1), (3, 3)],
  ('Gyi',): [
        (0, 1), (1, 1), (2, 0), (3, 0)],
  ('Gxi', 'Gyi'): [
        (0, 1), (2, 0), (2, 1), (3, 3)],
  ('Gxi', 'Gyi', 'Gii'): [
        (0, 1), (2, 0), (2, 1), (3, 3)],
  ('Gxi', 'Gii', 'Gyi'): [
        (0, 1), (2, 0), (2, 1), (3, 3)],
  ('Gyi', 'Gii', 'Gii'): [
        (0, 1), (1, 1), (2, 0), (3, 0)],
  ('Gxi', 'Gii', 'Gii'): [
        (1, 2), (2, 2), (3, 1), (3, 3)],
  ('Gxi', 'Gyi', 'Gyi', 'Gii'): [
        (0, 2), (1, 0), (1, 1), (2, 0), (2, 2), (3, 3)],
  ('Gxi', 'Gxi', 'Gii', 'Gyi'): [
        (0, 0), (1, 0), (1, 1), (2, 1), (3, 2), (3, 3)],
  ('Gxi', 'Gxi', 'Gyi', 'Gxi', 'Gyi', 'Gyi'): [
        (0, 0), (0, 1), (0, 2), (1, 2)],
}
