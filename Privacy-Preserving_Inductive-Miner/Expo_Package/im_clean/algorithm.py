'''
    This file is part of PM4Py (More Info: https://pm4py.fit.fraunhofer.de).

    PM4Py is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    PM4Py is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with PM4Py.  If not, see <https://www.gnu.org/licenses/>.
'''
from enum import Enum
from typing import Union, Dict, Any, Optional, Tuple

import pandas as pd

from pm4py.algo.discovery.dfg import algorithm as discover_dfg
from pm4py.algo.discovery.inductive.util import tree_consistency
from pm4py.algo.discovery.inductive.variants.im_clean import dfg_im

from Expo_Package.expo_mech import expo_mech # making the pst dp 

from pm4py.algo.discovery.inductive.variants.im_clean.utils import DfgSaEaActCount
from pm4py.objects.conversion.log import converter as log_converter
from pm4py.objects.conversion.process_tree import converter as tree_converter
from pm4py.objects.log.obj import EventLog, EventStream
from pm4py.objects.petri_net.obj import PetriNet, Marking
from pm4py.objects.process_tree.obj import ProcessTree
from pm4py.objects.process_tree.utils import generic
from pm4py.util import constants, exec_utils, xes_constants
from pm4py.util import variants_util
from pm4py.objects.log.util import filtering_utils


class Parameters(Enum):
    ACTIVITY_KEY = constants.PARAMETER_CONSTANT_ACTIVITY_KEY
    NOISE_THRESHOLD = 'noise_threshold'
    USE_MSD_PARALLEL_CUT = 'use_msd_par_cut'


def apply(event_log: Union[pd.DataFrame, EventLog, EventStream],
          parameters: Optional[Dict[Union[str, Parameters], Any]] = None) -> Tuple[PetriNet, Marking, Marking]:
    if parameters is None:
        parameters = {}
    tree = apply_tree(event_log, parameters=parameters)
    net, im, fm = tree_converter.apply(tree, variant=tree_converter.Variants.TO_PETRI_NET, parameters=parameters)
    return net, im, fm


def apply_variants(variants, parameters=None):
    if parameters is None:
        parameters = {}
    tree = apply_tree_variants(variants, parameters=parameters)
    net, im, fm = tree_converter.apply(tree, variant=tree_converter.Variants.TO_PETRI_NET, parameters=parameters)
    return net, im, fm


def apply_tree_variants(variants, parameters=None):
    if parameters is None:
        parameters = {}

    log = EventLog()
    threshold = exec_utils.get_param_value(Parameters.NOISE_THRESHOLD, parameters, 0.0)

    var_keys = list(variants.keys())
    for var in var_keys:
        val = variants[var]
        if type(val) is list:
            val = len(val)
        if threshold == 0.0:
            # the inductive miner without noise needs only 1 trace per variant
            val = 1
        for i in range(val):
            trace = variants_util.variant_to_trace(var, parameters=parameters)
            log.append(trace)

    return apply_tree(log, parameters=parameters)


def apply_tree(event_log: Union[pd.DataFrame, EventLog, EventStream], epsilon,
               parameters: Optional[Dict[Union[Parameters, str], Any]] = None) -> ProcessTree:
    if parameters is None:
        parameters = {}
    event_log = log_converter.apply(event_log, variant=log_converter.Variants.TO_EVENT_LOG, parameters=parameters)
    act_key = exec_utils.get_param_value(Parameters.ACTIVITY_KEY.value, parameters,
                                         xes_constants.DEFAULT_NAME_KEY)

    threshold = exec_utils.get_param_value(Parameters.NOISE_THRESHOLD, parameters, 0.0)

    #keep one trace per variant; more performant TODO:gucken das wir das nutzten für performance
    #log = filtering_utils.keep_one_trace_per_variant(log, parameters=parameters)

    #create a DP-PST and return this tree
    tree = expo_mech.__dp_tree(event_log, epsilon, discover_dfg.apply(event_log, parameters=parameters),
                             threshold, None,
                             act_key, exec_utils.get_param_value(Parameters.USE_MSD_PARALLEL_CUT, parameters, True))

    #normalize the tree
    tree_consistency.fix_parent_pointers(tree)
    tree = generic.fold(tree)
    generic.tree_sort(tree)

    return tree


def apply_dfg(dfg: Dict[Tuple[str, str], int], start_activities: Dict[str, int], end_activities: Dict[str, int],
              activities: Dict[str, int], parameters=None):
    if parameters is None:
        parameters = {}

    tree = apply_tree_dfg(dfg, start_activities, end_activities, activities, parameters=parameters)

    net, im, fm = tree_converter.apply(tree, variant=tree_converter.Variants.TO_PETRI_NET, parameters=parameters)
    return net, im, fm


def apply_tree_dfg(dfg: Dict[Tuple[str, str], int], start_activities: Dict[str, int], end_activities: Dict[str, int],
                   activities: Dict[str, int], parameters=None):
    if parameters is None:
        parameters = {}

    dfg_sa_ea_actcount = DfgSaEaActCount(dfg, start_activities, end_activities, activities)
    threshold = exec_utils.get_param_value(Parameters.NOISE_THRESHOLD, parameters, 0.0)

    tree = dfg_im.__imd(dfg_sa_ea_actcount, threshold, None)

    tree_consistency.fix_parent_pointers(tree)
    tree = generic.fold(tree)
    generic.tree_sort(tree)

    return tree
