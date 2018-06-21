""" Defines the AutoGator class and supporting functions."""
from __future__ import division, print_function, absolute_import, unicode_literals
#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation
#    This Software is released under the GPL license detailed
#    in the file "license.txt" in the top-level pyGSTi directory
#*****************************************************************

from . import gatesetmember as _gsm
from . import gate as _gate
from ..baseobjs import label as _label

class AutoGator(_gsm.GateSetChild):
    """
    TODO: docstrings in this module
    Currently this class is essentially a function,
    but we want allow room for future expansion.
    """

    def __init__(self,parent):
        super(AutoGator,self).__init__(parent)
        
    def __call__(self, existing_gates, gatelabel):
        """
        Create a Gate for `gateLabel` using existing gates.

        Parameters
        ----------
        existing_gates : dict
            A dictionary with keys = gate labels and values = Gate 
            objects.

        gateLabel : Label
            The gate label to construct a gate for.

        Returns
        -------
        Gate
        """
        raise NotImplementedError("Derived classes should implement this!")



class SimpleCompositionAutoGator(AutoGator):
    """
    TODO: docstring
    Just composes existing gates together to form 
    """

    def __init__(self, parent):
        super(SimpleCompositionAutoGator,self).__init__(parent)

    def __call__(self, existing_gates, gatelabel):
        """
        Create a Gate for `gateLabel` using existing gates.

        Parameters
        ----------
        existing_gates : dict
            A dictionary with keys = gate labels and values = Gate 
            objects.

        gateLabel : Label
            The gate label to construct a gate for.

        Returns
        -------
        Gate
        """

        dense = bool(self.parent._sim_type == "matrix") # whether dense matrix gates should be created
        Composed = _gate.ComposedGate if dense else _gate.ComposedGateMap
        #print("DB: SimpleCompositionAutoGator building gate %s for %s" %
        #      (('matrix' if dense else 'map'), str(gatelabel)) )
        if isinstance(gatelabel, _label.LabelTupTup):
            factor_gates = [ existing_gates[l] for l in gatelabel.components ]
            ret = Composed(factor_gates)
            self.parent._init_virtual_obj(ret) # so ret's gpindices get set
            return ret
        else: raise ValueError("Cannot auto-create gate for label %s" % str(gatelabel))
        
    
class SharedIdleAutoGator(AutoGator):
    """
    TODO: docstring

    Assumes each non-idle gate is a ComposedGateMap of the form
    `Composed([fullTargetOp,fullIdleErr,fullLocalErr])`, and that
    parallel gates should be combined by composing the target ops
    and local errors but keeping just a single idle error (which
    should be the same for all the gates).
    """

    def __init__(self, parent):
        super(SimpleCompositionAutoGator,self).__init__(parent)

    def __call__(self, existing_gates, gatelabel):
        """
        Create a Gate for `gateLabel` using existing gates.

        Parameters
        ----------
        existing_gates : dict
            A dictionary with keys = gate labels and values = Gate 
            objects.

        gateLabel : Label
            The gate label to construct a gate for.

        Returns
        -------
        Gate
        """

        dense = bool(self.parent._sim_type == "matrix") # whether dense matrix gates should be created
        Composed = _gate.ComposedGate if dense else _gate.ComposedGateMap
        #print("DB: SharedIdleAutoGator building gate %s for %s" %
        #      (('matrix' if dense else 'map'), str(gatelabel)) )
        if isinstance(gatelabel, _label.LabelTupTup):
            gates = [ existing_gates[l] for l in gatelabel.components ]
            #each gate in gates is Composed([fullTargetOp,fullIdleErr,fullLocalErr])
            # so we compose 1st & 3rd factors of parallel gates and keep just a single 2nd factor...
            
            targetOp = Composed([g.factorgates[0] for g in gates])
            idleErr = gates[0].factorgate[1]
            localErr = Composed([g.factorgates[2] for g in gates])
            
            ret = Composed([targetOp,idleErr,localErr])
            self.parent._init_virtual_obj(ret) # so ret's gpindices get set
            return ret
        else: raise ValueError("Cannot auto-create gate for label %s" % str(gatelabel))
