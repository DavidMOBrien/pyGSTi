from __future__ import division, print_function, absolute_import, unicode_literals
#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation
#    This Software is released under the GPL license detailed
#    in the file "license.txt" in the top-level pyGSTi directory
#*****************************************************************
""" End-to-end functions for performing long-sequence GST """

import os as _os
import warnings as _warnings
import numpy as _np
import sys as _sys
import time as _time
import collections as _collections
import pickle as _pickle
from scipy.stats import chi2 as _chi2

from .. import algorithms as _alg
from .. import construction as _construction
from .. import objects as _objs
from .. import io as _io
from .. import tools as _tools
from ..tools import compattools as _compat


def do_long_sequence_gst(dataFilenameOrSet, targetGateFilenameOrSet,
                         prepStrsListOrFilename, effectStrsListOrFilename,
                         germsListOrFilename, maxLengths, gaugeOptParams=None,
                         advancedOptions=None, comm=None, memLimit=None,
                         output_pkl=None, verbosity=2):
    """
    Perform end-to-end GST analysis using Ls and germs, with L as a maximum
    length.

    Constructs gate strings by repeating germ strings an integer number of
    times such that the length of the repeated germ is less than or equal to
    the maximum length set in maxLengths.  The LGST estimate of the gates is
    computed, gauge optimized, and then used as the seed for either LSGST or
    MLEGST.
    LSGST is iterated ``len(maxLengths)`` times with successively larger sets
    of gate strings.  On the i-th iteration, the repeated germs sequences
    limited by ``maxLengths[i]`` are included in the growing set of strings
    used by LSGST.  The final iteration will use MLEGST when ``objective ==
    "logl"`` to maximize the true log-likelihood instead of minimizing the
    chi-squared function.
    Once computed, the gate set estimates are optionally gauge optimized to
    the CPTP space and then to the target gate set (using `gaugeOptRatio`
    and `gaugeOptItemWeights`). A :class:`~pygsti.report.Results`
    object is returned, which encapsulates the input and outputs of this GST
    analysis, and can generate final end-user output such as reports and
    presentations.

    Parameters
    ----------
    dataFilenameOrSet : DataSet or string
        The data set object to use for the analysis, specified either directly
        or by the filename of a dataset file (assumed to be a pickled `DataSet`
        if extension is 'pkl' otherwise assumed to be in pyGSTi's text format).

    targetGateFilenameOrSet : GateSet or string
        The target gate set, specified either directly or by the filename of a
        gateset file (text format).

    prepStrsListOrFilename : (list of GateStrings) or string
        The state preparation fiducial gate strings, specified either directly
        or by the filename of a gate string list file (text format).

    effectStrsListOrFilename : (list of GateStrings) or string or None
        The measurement fiducial gate strings, specified either directly or by
        the filename of a gate string list file (text format).  If ``None``,
        then use the same strings as specified by prepStrsListOrFilename.

    germsListOrFilename : (list of GateStrings) or string
        The germ gate strings, specified either directly or by the filename of a
        gate string list file (text format).

    maxLengths : list of ints
        List of integers, one per LSGST iteration, which set truncation lengths
        for repeated germ strings.  The list of gate strings for the i-th LSGST
        iteration includes the repeated germs truncated to the L-values *up to*
        and including the i-th one.
        
    gaugeOptParams : dict, optional
        A dictionary of arguments to :func:`gaugeopt_to_target`, specifying
        how the final gauge optimization should be performed.  The keys and
        values of this dictionary may correspond to any of the arguments
        of :func:`gaugeopt_to_target` *except* for the first `gateset` 
        argument, which is specified internally.  The `targetGateset` argument,
        *can* be set, but is specified internally when it isn't.  If `None`,
        then the dictionary `{'itemWeights': {'gates':1.0, 'spam':0.001}}`
        is used.  If `False`, then then *no* gauge optimization is performed.

    advancedOptions : dict, optional
        Specifies advanced options most of which deal with numerical details of
        the objective function or expert-level functionality.  The allowed keys
        and values include:
        - objective = {'chi2', 'logl'}
        - gateLabels = list of strings
        - gsWeights = dict or None
        - starting point = "LGST" (default) or  "target" or GateSet
        - depolarizeStart = float (default == 0)
        - contractStartToCPTP = True / False (default)
        - cptpPenaltyFactor = float (default = 0)
        - tolerance = float
        - maxIterations = int
        - minProbClip = float
        - minProbClipForWeighting = float (default == 1e-4)
        - probClipInterval = tuple (default == (-1e6,1e6)
        - radius = float (default == 1e-4)
        - useFreqWeightedChiSq = True / False (default)
        - nestedGateStringLists = True (default) / False
        - includeLGST = True / False (default is True if starting point == LGST)
        - distributeMethod = "gatestrings" or "deriv" (default)
        - profile = int (default == 1)
        - check = True / False (default)
        - gateLabelAliases = dict (default = None)
        - alwaysPerformMLE = bool (default = False)
        - truncScheme = "whole germ powers" (default) or "truncated germ powers"
                        or "length as exponent"
        - appendTo = Results (default = None)
        - estimateLabel = str (default = "default")
        - missingDataAction = {'drop','raise'} (default = 'drop')
        - stringManipRules = list of (find,replace) tuples

    comm : mpi4py.MPI.Comm, optional
        When not ``None``, an MPI communicator for distributing the computation
        across multiple processors.

    memLimit : int or None, optional
        A rough memory limit in bytes which restricts the amount of memory 
        used (per core when run on multi-CPUs).

    output_pkl : str or file, optional
        If not None, a file(name) to `pickle.dump` the returned `Results` object
        to (only the rank 0 process performs the dump when `comm` is not None).

    verbosity : int, optional
       The 'verbosity' option is an integer specifying the level of 
       detail printed to stdout during the calculation.
       - 0 -- prints nothing
       - 1 -- shows progress bar for entire iterative GST
       - 2 -- show summary details about each individual iteration
       - 3 -- also shows outer iterations of LM algorithm
       - 4 -- also shows inner iterations of LM algorithm
       - 5 -- also shows detailed info from within jacobian
              and objective function calls.

    Returns
    -------
    Results
    """

    #gateLabels : list or tuple
    #    A list or tuple of the gate labels to use when generating the sets of
    #    gate strings used in LSGST iterations.  If ``None``, then the gate
    #    labels of the target gateset will be used.  This option is useful if
    #    you only want to include a *subset* of the available gates in the LSGST
    #    strings (e.g. leaving out the identity gate).
    #
    #weightsDict : dict, optional
    #    A dictionary with ``keys == gate strings`` and ``values ==
    #    multiplicative`` scaling factor for the corresponding gate string. The
    #    default is no weight scaling at all.
    #
    #gaugeOptRatio : float, optional
    #    The ratio spamWeight/gateWeight used for gauge optimizing to the target
    #    gate set.
    #
    #gaugeOptItemWeights : dict, optional
    #   Dictionary of weighting factors for individual gates and spam operators
    #   used during gauge optimization.   Keys can be gate, state preparation,
    #   POVM effect, or spam labels.  Values are floating point numbers.  By
    #   default, gate weights are set to 1.0 and spam weights to gaugeOptRatio.
    #profile : int, optional
    #    Whether or not to perform lightweight timing and memory profiling.
    #    Allowed values are:
    #    
    #    - 0 -- no profiling is performed
    #    - 1 -- profiling enabled, but don't print anything in-line
    #    - 2 -- profiling enabled, and print memory usage at checkpoints
    #truncScheme : str, optional
    #    Truncation scheme used to interpret what the list of maximum lengths
    #    means. If unsure, leave as default. Allowed values are:
    #
    #    - ``'whole germ powers'`` -- germs are repeated an integer number of
    #      times such that the length is less than or equal to the max.
    #    - ``'truncated germ powers'`` -- repeated germ string is truncated
    #      to be exactly equal to the max (partial germ at end is ok).
    #    - ``'length as exponent'`` -- max. length is instead interpreted
    #      as the germ exponent (the number of germ repetitions).

    if advancedOptions is None: advancedOptions = {}

    #Get/load fiducials
    if _compat.isstr(prepStrsListOrFilename):
        prepStrs = _io.load_gatestring_list(prepStrsListOrFilename)
    else: prepStrs = prepStrsListOrFilename

    if effectStrsListOrFilename is None:
        effectStrs = prepStrs #use same strings for effectStrs if effectStrsListOrFilename is None
    else:
        if _compat.isstr(effectStrsListOrFilename):
            effectStrs = _io.load_gatestring_list(effectStrsListOrFilename)
        else: effectStrs = effectStrsListOrFilename

    #Get/load germs
    if _compat.isstr(germsListOrFilename):
        germs = _io.load_gatestring_list(germsListOrFilename)
    else: germs = germsListOrFilename

    #Get/load target gateset
    if _compat.isstr(targetGateFilenameOrSet):
        gs_target = _io.load_gateset(targetGateFilenameOrSet)
    else:
        gs_target = targetGateFilenameOrSet #assume a GateSet object

    #Get starting point (so we know whether to include LGST strings)
    LGSTcompatibleGates = all([(isinstance(g,_objs.FullyParameterizedGate) or
                                isinstance(g,_objs.TPParameterizedGate))
                               for g in gs_target.gates.values()])
    if  LGSTcompatibleGates:
        startingPt = advancedOptions.get('starting point',"LGST")
    else:
        startingPt = advancedOptions.get('starting point',"target")

    #Get dataset for checking below
    if _compat.isstr(dataFilenameOrSet):
        if comm is None or comm.Get_rank() == 0:
            if _os.path.splitext(dataFilenameOrSet)[1] == ".pkl":
                with open(dataFilenameOrSet,'rb') as pklfile:
                    dschk = _pickle.load(pklfile)
            else:
                dschk = _io.load_dataset(dataFilenameOrSet, True, "aggregate", None, verbosity)
            if comm is not None: comm.bcast(dschk, root=0)
        else:
            dschk = comm.bcast(None, root=0)
    else:
        dschk = dataFilenameOrSet

    #Construct gate sequences
    actionIfMissing = advancedOptions.get('missingDataAction','drop')
    gateLabels = advancedOptions.get(
        'gateLabels', list(gs_target.gates.keys()))
    lsgstLists = _construction.stdlists.make_lsgst_structs(
        gateLabels, prepStrs, effectStrs, germs, maxLengths,
        truncScheme = advancedOptions.get('truncScheme',"whole germ powers"),
        nest = advancedOptions.get('nestedGateStringLists',True),
        includeLGST = advancedOptions.get('includeLGST', startingPt == "LGST"),
        gateLabelAliases = advancedOptions.get('gateLabelAliases',None),
        sequenceRules = advancedOptions.get('stringManipRules',None),
        dscheck=dschk, actionIfMissing=actionIfMissing, verbosity=verbosity)
    
    assert(len(maxLengths) == len(lsgstLists))
    
    return do_long_sequence_gst_base(dataFilenameOrSet, targetGateFilenameOrSet,
                                     lsgstLists, gaugeOptParams,
                                     advancedOptions, comm, memLimit,
                                     output_pkl, verbosity)




def do_long_sequence_gst_base(dataFilenameOrSet, targetGateFilenameOrSet,
                              lsgstLists, gaugeOptParams=None,
                              advancedOptions=None, comm=None, memLimit=None,
                              output_pkl=None, verbosity=2):
    """
    A more fundamental interface for performing end-to-end GST.

    Similar to :func:`do_long_sequence_gst` except this function takes 
    `lsgstLists`, a list of either raw gate string lists or of `LsGermsStruct`
    gate-string-structure objects to define which gate seqences are used on
    each GST iteration.

    Parameters
    ----------
    dataFilenameOrSet : DataSet or string
        The data set object to use for the analysis, specified either directly
        or by the filename of a dataset file (assumed to be a pickled `DataSet`
        if extension is 'pkl' otherwise assumed to be in pyGSTi's text format).

    targetGateFilenameOrSet : GateSet or string
        The target gate set, specified either directly or by the filename of a
        gateset file (text format).

    lsgstLists : list of lists or of LsGermsStructs
        An explicit list of either the raw gate string lists to be used in
        the analysis or of LsGermsStruct objects, which additionally contain
        the max-L, germ, and fiducial pair structure of a set of gate strings.
        
    gaugeOptParams : dict, optional
        A dictionary of arguments to :func:`gaugeopt_to_target`, specifying
        how the final gauge optimization should be performed.  The keys and
        values of this dictionary may correspond to any of the arguments
        of :func:`gaugeopt_to_target` *except* for the first `gateset` 
        argument, which is specified internally.  The `targetGateset` argument,
        *can* be set, but is specified internally when it isn't.  If `None`,
        then the dictionary `{'itemWeights': {'gates':1.0, 'spam':0.001}}`
        is used.  If `False`, then then *no* gauge optimization is performed.

    advancedOptions : dict, optional
        Specifies advanced options most of which deal with numerical details of
        the objective function or expert-level functionality.  See 
        :func:`do_long_sequence_gst` for a list of the allowed keys, with the
        exception  "nestedGateStringLists", "gateLabelAliases",
        "includeLGST", and "truncScheme".

    comm : mpi4py.MPI.Comm, optional
        When not ``None``, an MPI communicator for distributing the computation
        across multiple processors.

    memLimit : int or None, optional
        A rough memory limit in bytes which restricts the amount of memory 
        used (per core when run on multi-CPUs).

    output_pkl : str or file, optional
        If not None, a file(name) to `pickle.dump` the returned `Results` object
        to (only the rank 0 process performs the dump when `comm` is not None).

    verbosity : int, optional
       The 'verbosity' option is an integer specifying the level of 
       detail printed to stdout during the calculation.
       - 0 -- prints nothing
       - 1 -- shows progress bar for entire iterative GST
       - 2 -- show summary details about each individual iteration
       - 3 -- also shows outer iterations of LM algorithm
       - 4 -- also shows inner iterations of LM algorithm
       - 5 -- also shows detailed info from within jacobian
              and objective function calls.

    Returns
    -------
    Results
    """

    tRef = _time.time()

    #Note: *don't* specify default dictionary arguments, as this is dangerous
    # because they are mutable objects
    if advancedOptions is None: advancedOptions = {}
    if gaugeOptParams is None: 
        gaugeOptParams = {'itemWeights': {'gates':1.0, 'spam':0.001}}

    profile = advancedOptions.get('profile',1)

    if profile == 0: profiler = _objs.DummyProfiler()
    elif profile == 1: profiler = _objs.Profiler(comm,False)
    elif profile == 2: profiler = _objs.Profiler(comm,True)
    else: raise ValueError("Invalid value for 'profile' argument (%s)"%profile)

    if 'verbosity' in advancedOptions: #for backward compatibility
        _warnings.warn("'verbosity' as an advanced option is deprecated." +
                       " Please use the 'verbosity' argument directly.")
        verbosity = advancedOptions['verbosity'] 
    if 'memoryLimitInBytes' in advancedOptions: #for backward compatibility
        _warnings.warn("'memoryLimitInBytes' as an advanced option is deprecated." +
                       " Please use the 'memLimit' argument directly.")
        memLimit = advancedOptions['memoryLimitInBytes']

    printer = _objs.VerbosityPrinter.build_printer(verbosity, comm)

    #Get/load target gateset
    if _compat.isstr(targetGateFilenameOrSet):
        gs_target = _io.load_gateset(targetGateFilenameOrSet)
    else:
        gs_target = targetGateFilenameOrSet #assume a GateSet object

    #Get/load dataset
    if _compat.isstr(dataFilenameOrSet):
        default_dir = _os.path.dirname(dataFilenameOrSet) #default directory for reports, etc
        default_base = _os.path.splitext( _os.path.basename(dataFilenameOrSet) )[0]        
        if comm is None or comm.Get_rank() == 0:
            if _os.path.splitext(dataFilenameOrSet)[1] == ".pkl":
                with open(dataFilenameOrSet,'rb') as pklfile:
                    ds = _pickle.load(pklfile)
            else:
                ds = _io.load_dataset(dataFilenameOrSet, True, "aggregate", None, printer)
            if comm is not None: comm.bcast(ds, root=0)
        else:
            ds = comm.bcast(None, root=0)            
    else:
        ds = dataFilenameOrSet #assume a Dataset object
        default_dir = default_base = None

    gate_dim = gs_target.get_dimension()

    tNxt = _time.time()
    profiler.add_time('do_long_sequence_gst: loading',tRef); tRef=tNxt

    
    #Starting Point - compute on rank 0 and distribute
    LGSTcompatibleGates = all([(isinstance(g,_objs.FullyParameterizedGate) or
                                isinstance(g,_objs.TPParameterizedGate))
                               for g in gs_target.gates.values()])
    if isinstance(lsgstLists[0],_objs.LsGermsStructure) and LGSTcompatibleGates:
        startingPt = advancedOptions.get('starting point',"LGST")
    else:
        startingPt = advancedOptions.get('starting point',"target")
        
    #Compute starting point
    if startingPt == "LGST":
        assert(isinstance(lsgstLists[0], _objs.LsGermsStructure)), \
               "Cannot run LGST: fiducials not specified!"
        specs = _construction.build_spam_specs(prepStrs=lsgstLists[0].prepStrs,
                                               effectStrs=lsgstLists[0].effectStrs,
                                               prep_labels=gs_target.get_prep_labels(),
                                               effect_labels=gs_target.get_effect_labels())
        gateLabels = advancedOptions.get('gateLabels', list(gs_target.gates.keys()))
        gs_start = _alg.do_lgst(ds, specs, gs_target, gateLabels, svdTruncateTo=gate_dim,
                                gateLabelAliases=lsgstLists[0].aliases,
                                verbosity=printer) # returns a gateset with the *same*
                                                   # parameterizations as gs_target

        #In LGST case, gauge optimimize starting point to the target
        # (historical; sometimes seems to help in practice, since it's gauge
        # optimizing to physical gates (e.g. something in CPTP)
        gs_start = _alg.gaugeopt_to_target(gs_start, gs_target, comm=comm) 
          #Note: use *default* gauge-opt params when optimizing

        # Also reset the POVM identity to that of the target.  Essentially,
        # we declare that this basis (gauge) has the same identity as the
        # target (typically the first basis element).
        gs_start.povm_identity = gs_target.povm_identity.copy()

    elif startingPt == "target":
        gs_start = gs_target.copy()
    elif isinstance(startingPt, _objs.GateSet):
        gs_start = startingPt
        startingPt = "User-supplied-GateSet" #for profiler log below
    else:
        raise ValueError("Invalid starting point: %s" % startingPt)
        
    tNxt = _time.time()
    profiler.add_time('do_long_sequence_gst: Starting Point (%s)'
                      % startingPt,tRef); tRef=tNxt                

    #Post-processing gs_start : done only on root proc in case there is any nondeterminism.
    if comm is None or comm.Get_rank() == 0:
        #Advanced Options can specify further manipulation of starting gate set
        if advancedOptions.get('contractStartToCPTP',False):
            gs_start = _alg.contract(gs_start, "CPTP")
        if advancedOptions.get('depolarizeStart',0) > 0:
            gs_start = gs_start.depolarize(gate_noise=advancedOptions.get('depolarizeStart',0))
    
        if comm is not None: #broadcast starting gate set
            comm.bcast(gs_start, root=0)
    else:
        gs_start = comm.bcast(None, root=0)

    tNxt = _time.time()
    profiler.add_time('do_long_sequence_gst: Prep Initial seed',tRef); tRef=tNxt

    # lsgstLists can hold either gatestring lists or structures - get
    # just the lists for calling core gst routines (structure is used only
    # for LGST and post-analysis).
    rawLists = [ l.allstrs if isinstance(l,_objs.LsGermsStructure) else l
                 for l in lsgstLists ]

    aliases = lsgstLists[-1].aliases if isinstance(
        lsgstLists[-1], _objs.LsGermsStructure) else None
    aliases = advancedOptions.get('gateLabelAliases',aliases)
    
    #Run Long-sequence GST on data
    objective = advancedOptions.get('objective', 'logl')
    
    if objective == "chi2":
        gs_lsgst_list = _alg.do_iterative_mc2gst(
            ds, gs_start, rawLists,
            tol = advancedOptions.get('tolerance',1e-6),
            cptp_penalty_factor = advancedOptions.get('cptpPenaltyFactor',0),
            spam_penalty_factor = advancedOptions.get('spamPenaltyFactor',0),
            maxiter = advancedOptions.get('maxIterations',100000),
            minProbClipForWeighting=advancedOptions.get(
                'minProbClipForWeighting',1e-4),
            probClipInterval = advancedOptions.get(
                'probClipInterval',(-1e6,1e6)),
            returnAll=True, 
            gatestringWeightsDict=advancedOptions.get('gsWeights',None),
            gateLabelAliases=aliases,
            verbosity=printer,
            memLimit=memLimit,
            useFreqWeightedChiSq=advancedOptions.get(
                'useFreqWeightedChiSq',False), profiler=profiler,
            comm=comm, distributeMethod=advancedOptions.get(
                'distributeMethod',"deriv"),
            check_jacobian=advancedOptions.get('check',False),
            check=advancedOptions.get('check',False))

    elif objective == "logl":
        gs_lsgst_list = _alg.do_iterative_mlgst(
          ds, gs_start, rawLists,
          tol = advancedOptions.get('tolerance',1e-6),
          cptp_penalty_factor = advancedOptions.get('cptpPenaltyFactor',0),
          spam_penalty_factor = advancedOptions.get('spamPenaltyFactor',0),
          maxiter = advancedOptions.get('maxIterations',100000),
          minProbClip = advancedOptions.get('minProbClip',1e-4),
          probClipInterval = advancedOptions.get('probClipInterval',(-1e6,1e6)),
          radius=advancedOptions.get('radius',1e-4),
          returnAll=True, verbosity=printer,
          memLimit=memLimit, profiler=profiler, comm=comm,
          useFreqWeightedChiSq=advancedOptions.get(
                'useFreqWeightedChiSq',False), 
          distributeMethod=advancedOptions.get(
                'distributeMethod',"deriv"),
          check=advancedOptions.get('check',False),
          gatestringWeightsDict=advancedOptions.get('gsWeights',None),
          gateLabelAliases=aliases,
          alwaysPerformMLE=advancedOptions.get('alwaysPerformMLE',False)
        )
    else:
        raise ValueError("Invalid objective: %s" % objective)

    tNxt = _time.time()
    profiler.add_time('do_long_sequence_gst: total long-seq. opt.',tRef); tRef=tNxt

    #Get or Create the Resuts object we'll ultimately return
    ret = advancedOptions.get('appendTo',None)
    if ret is None:
        ret = _objs.Results()
        ret.init_dataset(ds)
        ret.init_gatestrings(lsgstLists)
    else:
        assert(ret.dataset is ds), "DataSet inconsistency: cannot append!"
        assert(len(lsgstLists) == len(ret.gatestring_structs['iteration'])), \
            "Iteration count inconsistency: cannot append!"

      #set parameters
    parameters = _collections.OrderedDict()
    parameters['objective'] = objective
    parameters['defaultDirectory'] = default_dir
    parameters['defaultBasename'] = default_base
    parameters['memLimit'] = memLimit
    parameters['starting point'] = startingPt
    parameters['profiler'] = profiler

      #from advanced options
    parameters['minProbClip'] = \
        advancedOptions.get('minProbClip',1e-4)
    parameters['minProbClipForWeighting'] = \
        advancedOptions.get('minProbClipForWeighting',1e-4)
    parameters['probClipInterval'] = \
        advancedOptions.get('probClipInterval',(-1e6,1e6))
    parameters['radius'] = advancedOptions.get('radius',1e-4)
    parameters['weights'] = advancedOptions.get('gsWeights',None)
    parameters['cptpPenaltyFactor'] = advancedOptions.get('cptpPenaltyFactor',0)
    parameters['spamPenaltyFactor'] = advancedOptions.get('spamPenaltyFactor',0)
    parameters['distributeMethod'] = advancedOptions.get('distributeMethod','deriv')
    parameters['depolarizeStart'] = advancedOptions.get('depolarizeStart',0)
    parameters['contractStartToCPTP'] = advancedOptions.get('contractStartToCPTP',False)
    parameters['tolerance'] = advancedOptions.get('tolerance',1e-6)
    parameters['maxIterations'] = advancedOptions.get('maxIterations',100000)
    parameters['useFreqWeightedChiSq'] = advancedOptions.get('useFreqWeightedChiSq',False)
    parameters['nestedGateStringLists'] = advancedOptions.get('nestedGateStringLists',True)
    parameters['profile'] = advancedOptions.get('profile',1)
    parameters['check'] = advancedOptions.get('check',False)
    parameters['truncScheme'] = advancedOptions.get('truncScheme', "whole germ powers")
    parameters['gateLabelAliases'] = advancedOptions.get('gateLabelAliases',None)
    parameters['includeLGST'] = advancedOptions.get('includeLGST', startingPt == "LGST")
        
    #add estimate to Results
    estlbl = advancedOptions.get('estimateLabel','default')
    ret.add_estimate(gs_target, gs_start, gs_lsgst_list, parameters, estlbl)

    #Do final gauge optimization to *final* iteration result only
    if gaugeOptParams != False:
        gaugeOptParams = gaugeOptParams.copy() #so we don't modify the caller's dict
        if "targetGateset" not in gaugeOptParams:
            gaugeOptParams["targetGateset"] = gs_target
        if "comm" not in gaugeOptParams:
            gaugeOptParams["comm"] = comm

        go_gs_final = _alg.gaugeopt_to_target(gs_lsgst_list[-1],**gaugeOptParams)
        ret.estimates[estlbl].add_gaugeoptimized(gaugeOptParams, go_gs_final,
                                                 None, printer)

        tNxt = _time.time()
        profiler.add_time('do_long_sequence_gst: gauge optimization',tRef); tRef=tNxt

    #Perform extra analysis if a bad fit was obtained
    badFitThreshold = advancedOptions.get('badFitThreshold',20)
    if ret.estimates[estlbl].misfit_sigma() > badFitThreshold:
        onBadFit = advancedOptions.get('onBadFit',"scale data") # 'do nothing'
        if onBadFit in ("scale data","scale data and reopt") \
           and parameters['weights'] is None:
        
            expected = (len(ds.get_spam_labels())-1) # == "k"
            dof_per_box = 1; nboxes = len(rawLists[-1])
            pc = 0.95 #hardcoded confidence level for now -- make into advanced option w/default
            threshold = _np.ceil(_chi2.ppf(1 - pc/nboxes, dof_per_box))
    
            if objective == "chi2":
                fitQty = _tools.chi2_terms(ds, gs_lsgst_list[-1], rawLists[-1],
                                           advancedOptions.get('minProbClipForWeighting',1e-4),
                                           advancedOptions.get('probClipInterval',(-1e6,1e6)),
                                           False, False, memLimit,
                                           advancedOptions.get('gateLabelAliases',None))
            else:
                maxLogL = _tools.logl_max_terms(ds, rawLists[-1],
                                                gateLabelAliases=advancedOptions.get('gateLabelAliases',None))
                logL = _tools.logl_terms(gs_lsgst_list[-1], ds, rawLists[-1],
                                         advancedOptions.get('minProbClip',1e-4),
                                         advancedOptions.get('probClipInterval',(-1e6,1e6)),
                                         advancedOptions.get('radius',1e-4),
                                         gateLabelAliases=advancedOptions.get('gateLabelAliases',None))
                fitQty = 2*(maxLogL - logL)
                
            fitQty = _np.sum(fitQty, axis=0) # sum over spam labels
            gsWeights = {}
            for i,gstr in enumerate(rawLists[-1]):
                if fitQty[i] > threshold:
                    gsWeights[gstr] = expected/fitQty[i] #scaling factor
    
            scale_params = parameters.copy()
            scale_params['weights'] = gsWeights

            if onBadFit == "scale data and reopt":
                raise NotImplementedError("This option isn't implemented yet!")
                # Need to re-run final iteration of GST with weights computed above,
                # and just keep (?) old estimates of all prior iterations (or use "blank"
                # sentinel once this is supported).
                
            ret.add_estimate(gs_target, gs_start, gs_lsgst_list, scale_params, estlbl + ".robust")

            #Do final gauge optimization to data-scaled estimate also
            if gaugeOptParams != False:
                gaugeOptParams = gaugeOptParams.copy() #so we don't modify the caller's dict
                #if onBadFit == "scale data and reopt": # then will need to re-gauge-opt too, like:
                #    if "targetGateset" not in gaugeOptParams:
                #        gaugeOptParams["targetGateset"] = gs_target
                #    if "comm" not in gaugeOptParams:
                #        gaugeOptParams["comm"] = comm
                #
                #    go_gs_final = _alg.gaugeopt_to_target(gs_lsgst_list[-1],**gaugeOptParams)
                #    ret.estimates[estlbl].add_gaugeoptimized(gaugeOptParams, go_gs_final, None, printer)
                #    
                #    tNxt = _time.time()
                #    profiler.add_time('do_long_sequence_gst: robust gauge optimization',tRef); tRef=tNxt
                #else:
                
                # add same gauge-optimized result as above
                ret.estimates[estlbl + ".robust"].add_gaugeoptimized(gaugeOptParams, go_gs_final,
                                                                     None, printer)


        elif onBadFit == "do nothing":
            pass
        else:
            raise ValueError("Invalid onBadFit value: %s" % onBadFit)
            
    profiler.add_time('do_long_sequence_gst: results initialization',tRef)

    #Write results to a pickle file if desired
    if output_pkl and (comm is None or comm.Get_rank() == 0):
        if _compat.isstr(output_pkl):
            with open(output_pkl, 'wb') as pklfile:
                _pickle.dump(ret, pklfile)
        else:
            _pickle.dump(ret, output_pkl)
        
    return ret




def do_stdpractice_gst(dataFilenameOrSet,targetGateFilenameOrSet,
                       prepStrsListOrFilename, effectStrsListOrFilename,
                       germsListOrFilename, maxLengths, modes="TP,CPTP,Target",
                       gaugeOptSuite=('toggleValidSpam','unreliable2Q'),
                       gaugeOptTarget=None, comm=None, memLimit=None,
                       advancedOptions=None, output_pkl=None, verbosity=2):

    """
    Perform end-to-end GST analysis using standard practices.

    This routines is an even higher-level driver than 
    :func:`do_long_sequence_gst`.  It performs bottled, typically-useful,
    runs of long sequence GST on a dataset.  This essentially boils down
    to running :func:`do_long_sequence_gst` one or more times using different
    gate set parameterizations, and performing commonly-useful gauge
    optimizations, based only on the high-level `modes` argument.

    Parameters
    ----------
    dataFilenameOrSet : DataSet or string
        The data set object to use for the analysis, specified either directly
        or by the filename of a dataset file (assumed to be a pickled `DataSet`
        if extension is 'pkl' otherwise assumed to be in pyGSTi's text format).

    targetGateFilenameOrSet : GateSet or string
        The target gate set, specified either directly or by the filename of a
        gateset file (text format).

    prepStrsListOrFilename : (list of GateStrings) or string
        The state preparation fiducial gate strings, specified either directly
        or by the filename of a gate string list file (text format).

    effectStrsListOrFilename : (list of GateStrings) or string or None
        The measurement fiducial gate strings, specified either directly or by
        the filename of a gate string list file (text format).  If ``None``,
        then use the same strings as specified by prepStrsListOrFilename.

    germsListOrFilename : (list of GateStrings) or string
        The germ gate strings, specified either directly or by the filename of a
        gate string list file (text format).

    maxLengths : list of ints
        List of integers, one per LSGST iteration, which set truncation lengths
        for repeated germ strings.  The list of gate strings for the i-th LSGST
        iteration includes the repeated germs truncated to the L-values *up to*
        and including the i-th one.

    modes : str, optional
        A comma-separated list of modes which dictate what types of analyses
        are performed.  Currently, these correspond to different types of 
        parameterizations/constraints to apply to the estimated gate set.
        The default value is usually fine.  Allowed values are:

        - "full" : full (completely unconstrained)
        - "TP"   : TP-constrained
        - "CPTP" : Lindbladian CPTP-constrained
        - "H+S"  : Only Hamiltonian + Stochastic errors allowed (CPTP)
        - "S"    : Only Stochastic errors allowed (CPTP)
        - "Target" : use the target (ideal) gates as the estimate

    gaugeOptSuite : str or list or dict, optional
        Specifies which gauge optimizations to perform on each estimate.  A
        string or list of strings (see below) specifies built-in sets of gauge
        optimizations, otherwise `gaugeOptSuite` should be a dictionary of
        gauge-optimization parameter dictionaries, as specified by the
        `gaugeOptParams` argument of :func:`do_long_sequence_gst`.  The key
        names of `gaugeOptSuite` then label the gauge optimizations within
        the resuling `Estimate` objects.  The built-in suites are:

          - "single" : performs only a single "best guess" gauge optimization.
          - "varySpam" : varies spam weight and toggles SPAM penalty (0 or 1).
          - "varySpamWt" : varies spam weight but no SPAM penalty.
          - "varyValidSpamWt" : varies spam weight with SPAM penalty == 1.
          - "toggleValidSpam" : toggles spame penalty (0 or 1); fixed SPAM wt.
          - "unreliable2Q" : adds branch to a spam suite that weights 2Q gates less
          - "none" : no gauge optimizations are performed.

    gaugeOptTarget : GateSet, optional
        If not None, a gate set to be used as the "target" for gauge-
        optimization (only).  This argument is useful when you want to 
        gauge optimize toward something other than the *ideal* target gates
        given by `targetGateFilenameOrSet`, which are used as the default when
        `gaugeOptTarget` is None.

    comm : mpi4py.MPI.Comm, optional
        When not ``None``, an MPI communicator for distributing the computation
        across multiple processors.

    memLimit : int or None, optional
        A rough memory limit in bytes which restricts the amount of memory 
        used (per core when run on multi-CPUs).

    advancedOptions : dict, optional
        Specifies advanced options most of which deal with numerical details of
        the objective function or expert-level functionality.  Keys of this 
        dictionary can be any of the modes being computed (see the `modes`
        argument) or 'all', which applies to all modes.  Values are
        dictionaries of advanced arguements - see :func:`do_long_sequence_gst`
        for a list of the allowed keys for each such dictionary.

    output_pkl : str or file, optional
        If not None, a file(name) to `pickle.dump` the returned `Results` object
        to (only the rank 0 process performs the dump when `comm` is not None).

    verbosity : int, optional
       The 'verbosity' option is an integer specifying the level of 
       detail printed to stdout during the calculation.

    Returns
    -------
    Results
    """
    printer = _objs.VerbosityPrinter.build_printer(verbosity, comm)
    
    #Get/load target gateset
    if _compat.isstr(targetGateFilenameOrSet):
        gs_target = _io.load_gateset(targetGateFilenameOrSet)
    else:
        gs_target = targetGateFilenameOrSet #assume a GateSet object

    #Get/load dataset
    if _compat.isstr(dataFilenameOrSet):
        if comm is None or comm.Get_rank() == 0:
            if _os.path.splitext(dataFilenameOrSet)[1] == ".pkl":
                with open(dataFilenameOrSet,'rb') as pklfile:
                    ds = _pickle.load(pklfile)
            else:
                ds = _io.load_dataset(dataFilenameOrSet, True, "aggregate", None, printer)
            if comm is not None: comm.bcast(ds, root=0)
        else:
            ds = comm.bcast(None, root=0)            
    else:
        ds = dataFilenameOrSet #assume a Dataset object

    ret = None
    modes = modes.split(",")
    with printer.progress_logging(1):
        for i,mode in enumerate(modes):
            printer.show_progress(i, len(modes), prefix='-- Std Practice: ', suffix=' (%s) --' % mode)

            if mode == "Target":
                if ret == None:
                    ret = _objs.Results()
                    ret.init_dataset(ds)
                    #ret.init_gatestrings(lsgstLists) #TODO
                    raise NotImplementedError("Cannot use 'Target' as the first mode (yet).")
                tgt_params = _collections.OrderedDict()
                tgt_params['objective'] = 'logl'
                tgt_params['minProbClip'] = 1e-4
                nIters = len(maxLengths) if (maxLengths[0] != 0) else len(maxLengths)-1
                est_label = mode
                ret.add_estimate(gs_target, gs_target, [gs_target]*nIters, tgt_params, est_label)
                
            else: #assume mode is a parameterization
                
                est_label = parameterization = mode #for now, 1-1 correspondence
                tgt = gs_target.copy(); tgt.set_all_parameterizations(parameterization)

                #prepare advanced options dictionary
                if advancedOptions is not None:
                    advanced = advancedOptions.get('all',{})
                    advanced.update( advancedOptions.get(mode,{}) )
                else: advanced = {}
                advanced.update( {'appendTo': ret, 'estimateLabel': est_label } )
                
                ret = do_long_sequence_gst(ds, tgt, prepStrsListOrFilename,
                                           effectStrsListOrFilename, germsListOrFilename,
                                           maxLengths, False, advanced, comm, memLimit,
                                           None, printer-1)

            #Get gauge optimization dictionary
            gaugeOptSuite_dict = gaugeopt_suite_to_dictionary(gaugeOptSuite, tgt, printer-1)

            if gaugeOptTarget is not None:
                assert(isinstance(gaugeOptTarget,_objs.GateSet)),"`gaugeOptTarget` must be None or a GateSet"
                for goparams in gaugeOptSuite_dict.values():
                    if 'targetGateset' in goparams:
                        _warnings.warn(("`gaugeOptTarget` argument is overriding"
                                        "user-defined targetGateset in gauge opt"
                                        "param dict(s)"))
                    goparams.update( {'targetGateset': gaugeOptTarget } )
                
            #Gauge optimize to list of gauge optimization parameters
            for goLabel,goparams in gaugeOptSuite_dict.items():
                
                printer.log("-- Performing '%s' gauge optimization on %s estimate --" % (goLabel,est_label),2)
                tGO = _time.time()
                ret.estimates[est_label].add_gaugeoptimized(goparams, None, goLabel, printer-2)
                printer.log("-- Done gauge optimizing (%gs) -- " % (_time.time()-tGO),2)

                #Gauge optimize data-scaled estimate also
                if est_label + ".robust" in ret.estimates:
                    printer.log("-- Performing '%s' gauge optimization on %s estimate --" % (goLabel,est_label+".robust"),2)
                    tGO = _time.time()
                    ret.estimates[est_label + ".robust"].add_gaugeoptimized(goparams, None, goLabel, printer-2)
                    printer.log("-- Done gauge optimizing (%gs) --" % (_time.time()-tGO),2)

    #Write results to a pickle file if desired
    if output_pkl and (comm is None or comm.Get_rank() == 0):
        if _compat.isstr(output_pkl):
            with open(output_pkl, 'wb') as pklfile:
                _pickle.dump(ret, pklfile)
        else:
            _pickle.dump(ret, output_pkl)

    return ret


def gaugeopt_suite_to_dictionary(gaugeOptSuite, gs_target, verbosity=0):
    """
    Constructs a dictionary of gauge-optimization parameter dictionaries based
    on "gauge optimization suite" name(s).  

    This is primarily a helper function for :func:`do_stdpractice_gst`, but can
    be useful in its own right for constructing the would-be gauge optimization 
    dictionary used in :func:`do_stdpractice_gst` and modifying it slightly before
    before passing it in (`do_stdpractice_gst` will accept a raw dictionary too).

    Parameters
    ----------
    gaugeOptSuite : str or dict, optional
        Specifies which gauge optimizations to perform on each estimate.  An
        string (see below) specifies a built-in set of gauge optimizations,
        otherwise `gaugeOptSuite` should be a dictionary of gauge-optimization
        parameter dictionaries, as specified by the `gaugeOptParams` argument 
        of :func:`do_long_sequence_gst`.  The key names of `gaugeOptSuite` then
        label the gauge optimizations within the resuling `Estimate` objects.
        The built-in gauge optmization suites are:

          - "single" : performs only a single "best guess" gauge optimization.
          - "varySpam" : varies spam weight and toggles SPAM penalty (0 or 1).
          - "varySpamWt" : varies spam weight but no SPAM penalty.
          - "varyValidSpamWt" : varies spam weight with SPAM penalty == 1.
          - "toggleValidSpam" : toggles spame penalty (0 or 1); fixed SPAM wt.
          - "unreliable2Q" : adds branch to a spam suite that weights 2Q gates less
          - "none" : no gauge optimizations are performed.

    gs_target : GateSet
        A gate set which specifies the dimension (i.e. parameterization) of the
        gauge-optimization and the basis.  Usually this is set to the *ideal*
        `target gate set` for the gate set being gauge optimized.
    
    verbosity : int
        The verbosity to attach to the various gauge optimization parameter
        dictionaries.

    Returns
    -------
    dict 
        A dictionary whose keys are the labels of the different gauge
        optimizations to perform and whose values are the corresponding
        dictionaries of arguments to :func:`gaugeopt_to_target` (or lists
        of such dictionaries for a multi-stage gauge optimization).
    """
    printer = _objs.VerbosityPrinter.build_printer(verbosity)
    
    #Build ordered dict of gauge optimization parameters
    if isinstance(gaugeOptSuite, dict):
        gaugeOptSuite_dict = _collections.OrderedDict()
        for lbl, goparams in gaugeOptSuite.items():
            gaugeOptSuite_dict[lbl] = goparams.copy()
            gaugeOptSuite_dict[lbl].update( {'verbosity': printer } )
            
    else:
        gaugeOptSuite_dict = _collections.OrderedDict()
        if _compat.isstr(gaugeOptSuite):
            gaugeOptSuites = [gaugeOptSuite]
        else:
            gaugeOptSuites = gaugeOptSuite[:] #assumes gaugeOptSuite is a list/tuple of strs

        for suiteName in gaugeOptSuites:
            if suiteName == "single":
                #OLD
                #gaugeOptSuite_dict['single'] = {'itemWeights': {'gates':1, 'spam':1e-3},
                #                                'verbosity': printer}
                
                stages = [ ] #multi-stage gauge opt
                gg = gs_target.default_gauge_group
                
                if gg is not None:

                    #Stage 1: plain vanilla gauge opt to get into "right ballpark"
                    if gg.name in ("Full", "TP"):
                        stages.append(
                            {
                                'itemWeights': {'gates': 1.0, 'spam': 1.0},
                                'verbosity': printer
                            })
    
                    #Stage 2: unitary gauge opt that tries to nail down gates (at
                    #         expense of spam if needed)
                    stages.append(
                        {
                            'itemWeights': {'gates': 1.0, 'spam': 0.0},
                            'gauge_group': _objs.UnitaryGaugeGroup(gs_target.dim, gs_target.basis),
                            'verbosity': printer
                        })
    
                    #Stage 3: spam gauge opt that fixes spam scaling at expense of
                    #         non-unital parts of gates (but shouldn't affect these
                    #         elements much since they should be small from Stage 2).
                    s3gg = _objs.SpamGaugeGroup if (gg.name == "Full") else \
                           _objs.TPSpamGaugeGroup
                    stages.append(
                        {
                            'itemWeights': {'gates': 0.0, 'spam': 1.0},
                            'gauge_group': s3gg(gs_target.dim),
                            'verbosity': printer
                        })
                    
                    gaugeOptSuite_dict['single'] = stages #can be a list of stage dictionaries
    
        
            elif suiteName in ("varySpam", "varySpamWt", "varyValidSpamWt", "toggleValidSpam"):
        
                itemWeights_bases = _collections.OrderedDict()
                itemWeights_bases[""] = {'gates': 1}

                if "unreliable2Q" in gaugeOptSuites and gs_target.dim == 16:
                    if advancedOptions is not None:
                        advanced = advancedOptions.get('all',{}) #'unreliableGates' can only be specified in 'all' options
                    else: advanced = {}
                    unreliableGates = advanced.get('unreliableGates',['Gcnot','Gcphase','Gms','Gcn','Gcx','Gcz'])
                    if any([gl in gs_target.gates.keys() for gl in unreliableGates]):
                        base = {'gates': 1}
                        for gl in unreliableGates:
                            if gl in gs_target.gates.keys(): base[gl] = 0.01
                        itemWeights_bases["-2QUR"] = base
                            
                if suiteName == "varySpam":
                    vSpam_range = [0,1]; spamWt_range = [1e-4,1e-1]
                elif suiteName == "varySpamWt":
                    vSpam_range = [0]; spamWt_range = [1e-4,1e-1]
                elif suiteName == "varyValidSpamWt":
                    vSpam_range = [1]; spamWt_range = [1e-4,1e-1]
                elif suiteName == "toggleValidSpam":
                    vSpam_range = [0,1]; spamWt_range = [1e-3]
        
                for postfix,baseWts in itemWeights_bases.items():
                    for vSpam in vSpam_range:
                        for spamWt in spamWt_range:
                            lbl = "Spam %g%s%s" % (spamWt, "+v" if vSpam else "", postfix)
                            itemWeights = baseWts.copy()
                            itemWeights['spam'] = spamWt
                            gaugeOptSuite_dict[lbl] = {
                                'itemWeights': itemWeights,
                                'spam_penalty_factor': vSpam, 'verbosity': printer }

            elif suiteName == "unreliable2Q":
                assert( any([nm in ("varySpam", "varySpamWt", "varyValidSpamWt", "toggleValidSpam")
                            for nm in gaugeOptSuite])), "'unreliable2Q' suite must be used with a spam suite."

            elif suiteName == "none":
                pass #add nothing

            else:
                raise ValueError("Invalid `gaugeOptSuite` argument - unknown suite '%s'" % suiteName)

    return gaugeOptSuite_dict
