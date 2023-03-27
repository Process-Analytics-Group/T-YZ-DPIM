"""
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
"""

from enum import Enum
import pm4py
from pm4py.algo.discovery.dfg import algorithm as discover_dfg
from pm4py.algo.discovery.inductive.variants.im_clean.cuts import sequence as sequence_cut, xor as xor_cut, \
    concurrency as concurrent_cut, loop as loop_cut
from pm4py.algo.discovery.inductive.variants.im_clean.fall_throughs import activity_once_per_trace, activity_concurrent, \
    strict_tau_loop, tau_loop
from pm4py.algo.discovery.minimum_self_distance import algorithm as msd_algo
from pm4py.algo.discovery.minimum_self_distance import utils as msdw_algo
from pm4py.objects.dfg.utils import dfg_utils
from pm4py.objects.log.obj import EventLog
from pm4py.objects.log.util import log as log_util
from pm4py.objects.process_tree import obj as pt
from pm4py.statistics.end_activities.log import get as get_ends
from pm4py.statistics.start_activities.log import get as get_starters
from pm4py.util import constants


# dicts to count cuts
traceDict = dict()
cutDict = dict()

checkList = list()

xorCount = 0
sequenceCount = 0
loopCount = 0
parallelCount = 0

numCuts = 0


class Parameters(Enum):
    ACTIVITY_KEY = constants.PARAMETER_CONSTANT_ACTIVITY_KEY

    def __get_cutCount(self, log, dfg, threshold, root, act_key, use_msd, remove_noise=False):

        # for all traces count the occurens of each activity in a trace and save a list of the activities
        for trace in log:
            # list all acitivities of the trace and remove duplicates
            trActivities = list(map(lambda e: e[act_key], trace))
            revDuplicates = [*set(trActivities)]

            revDuplicates = sorted(revDuplicates)

            # get the keys of the trace dict
            traceKeys = list(traceDict.keys())

            # check if the list of the activities is already in the dict
            if tuple(revDuplicates) not in traceKeys:
                traceDict.update({tuple(revDuplicates): 1})
            elif tuple(revDuplicates) in traceKeys:
                traceDict[tuple(revDuplicates)] += 1

        self.__cut_recursive(log, dfg, threshold, root, act_key, use_msd, remove_noise=False)
        return(cutDict, numCuts)

    # check cut for each element in event log
    def __cut_recursive(self, log, dfg, threshold, root, act_key, use_msd, remove_noise=False):
        tree = self.__check_cut(log, dfg, threshold, root, act_key, use_msd, remove_noise)
        return tree

    # check for cuts and increment the corresponding cut by one
    def __check_cut(self, log, dfg, threshold, root, act_key, use_msd, remove_noise=False):
        global xorCount, sequenceCount, parallelCount, loopCount
        global numCuts

        alphabet = pm4py.get_event_attribute_values(log, act_key)
        if threshold > 0 and remove_noise:
            end_activities = get_ends.get_end_activities(log,
                                                         parameters={constants.PARAMETER_CONSTANT_ACTIVITY_KEY: act_key})

            dfg = self.__filter_dfg_on_threshold(dfg, end_activities, threshold)

        original_length = len(log)
        log = pm4py.filter_log(lambda t: len(t) > 0, log)

        # revised EMPTYSTRACES
        if original_length - len(log) > original_length * threshold:
            activities = list()
            numCuts += 1

            for key in list(alphabet.keys()):
                activities.append({key})

            # if activities not in checkList:
            xorCount += 1

            # .append(activities)
            count = self.__count_traces(activities)

            cutDict.update({'xor'+str(xorCount): count})

            return self.__recursion(pt.ProcessTree(pt.Operator.XOR, root), threshold, act_key,
                                                 [EventLog(), log],
                                                 use_msd)

        start_activities = get_starters.get_start_activities(log, parameters={
            constants.PARAMETER_CONSTANT_ACTIVITY_KEY: act_key})
        end_activities = get_ends.get_end_activities(log, parameters={constants.PARAMETER_CONSTANT_ACTIVITY_KEY: act_key})

        if self.__is_base_case_act(log, act_key) or self.__is_base_case_silent(log):
            return self.__apply_base_case(log, root, act_key)
        pre, post = dfg_utils.get_transitive_relations(dfg, alphabet)

        # changes from here on
        cut = sequence_cut.detect(alphabet, pre, post)
        # if sequence cut should be made
        if cut is not None:

            numCuts += 1
            sequenceCount += 1
            count = self.__count_traces_seq(cut)
            cutDict.update({'sequence'+str(sequenceCount): count})

            return self.__recursion(pt.ProcessTree(pt.Operator.SEQUENCE, root), threshold, act_key,
                                                 sequence_cut.project(log, cut, act_key), use_msd)

        cut = xor_cut.detect(dfg, alphabet)
        # if xor cut should be made
        if cut is not None:
            numCuts += 1

            # if cut not in checkList:
            xorCount += 1
            count = self.__count_traces(cut)
            cutDict.update({'xor'+str(xorCount): count})

            return self.__recursion(pt.ProcessTree(pt.Operator.XOR, root), threshold, act_key,
                                                 xor_cut.project(log, cut, act_key), use_msd)

        cut = concurrent_cut.detect(dfg, alphabet, start_activities, end_activities,
                                    msd=msdw_algo.derive_msd_witnesses(log, msd_algo.apply(log, parameters={
                                        constants.PARAMETER_CONSTANT_ACTIVITY_KEY: act_key}), parameters={
                                        constants.PARAMETER_CONSTANT_ACTIVITY_KEY: act_key}) if use_msd else None)
        # if parrallel cut should be made
        if cut is not None:
            numCuts += 1
            parallelCount+= 1
            count = self.__count_traces(cut)
            cutDict.update({'parallel'+str(parallelCount): count})

            return self.__recursion(pt.ProcessTree(pt.Operator.PARALLEL, root), threshold, act_key,
                                                 concurrent_cut.project(log, cut, act_key), use_msd)

        cut = loop_cut.detect(dfg, alphabet, start_activities, end_activities)
        # if loop cut should be made
        if cut is not None:
            numCuts += 1
            loopCount += 1
            count = self.__count_traces(cut)
            cutDict.update({'loop'+str(loopCount): count})

            return self.__recursion(pt.ProcessTree(pt.Operator.LOOP, root), threshold, act_key,
                                                 loop_cut.project(log, cut, act_key), use_msd)

        aopt = activity_once_per_trace.detect(log, alphabet, act_key)
        if aopt is not None:

            numCuts += 1
            parallelCount += 1
            # get num of traces that voted for the cut
            count = 0
            for k, v in traceDict.items():
                for i in range(len(k)):
                    # aopt is a string of one activity
                    if k[i] == aopt:
                        count += v

            cutDict.update({'parallel'+str(parallelCount): count})
            operator = pt.ProcessTree(operator=pt.Operator.PARALLEL, parent=root)
            return self.__recursion(operator, threshold, act_key,
                                                 activity_once_per_trace.project(log, aopt, act_key), use_msd)

        act_conc = activity_concurrent.detect(log, alphabet, act_key, use_msd)
        if act_conc is not None:

            numCuts += 1
            parallelCount += 1
            # get num of traces that want to do the cut
            count = 0
            for k, v in traceDict.items():
                for i in range(len(k)):
                    # aopt is a string of one activity
                    if k[i] == aopt:
                        count += v

            cutDict.update({'parallel'+str(parallelCount): count})
            return self.__recursion(pt.ProcessTree(pt.Operator.PARALLEL, root), threshold, act_key,
                                                 activity_concurrent.project(log, act_conc, act_key), use_msd)

        stl = strict_tau_loop.detect(log, start_activities, end_activities, act_key)
        if stl is not None:
            return self.__recursion(pt.ProcessTree(pt.Operator.LOOP, root), threshold, act_key,
                                                 [stl, EventLog()],
                                                 use_msd)

        tl = tau_loop.detect(log, start_activities, act_key)
        if tl is not None:
            return self.__recursion(pt.ProcessTree(pt.Operator.LOOP, root), threshold, act_key,
                                                 [tl, EventLog()],
                                                 use_msd)

        if threshold > 0 and not remove_noise:
            return self.__cut_recursive(log, dfg, threshold, root, act_key, use_msd, remove_noise=True)

        return self.__flower(alphabet, root)

    # do recursion on the event-log, to count all cuts
    def __recursion(self, threshold, act_key, logs, use_msd):
        if self.operator != pt.Operator.LOOP:
            for log in logs:
                self.__cut_recursive(log, discover_dfg.apply(log, parameters={
                    constants.PARAMETER_CONSTANT_ACTIVITY_KEY: act_key}), threshold, self, act_key, use_msd)
        else:
            self.__cut_recursive(logs[0], discover_dfg.apply(logs[0], parameters={
                constants.PARAMETER_CONSTANT_ACTIVITY_KEY: act_key}), threshold, self, act_key, use_msd)
            logs = logs[1:]
            if len(logs) == 1:
                self.__cut_recursive(logs[0], discover_dfg.apply(logs[0], parameters={
                    constants.PARAMETER_CONSTANT_ACTIVITY_KEY: act_key}), threshold, self, act_key, use_msd)

    def __is_base_case_act(log, act_key):
        if len(list(filter(lambda t: len(t) == 1, log))) == len(log):
            if len(frozenset(log_util.get_event_labels(log, act_key))) == 1:
                return True
        return False

    def __is_base_case_silent(log):
        return len(log) == 0

    def __apply_base_case(log, root, act_key):
        if len(log) == 0:
            operator = pt.ProcessTree(parent=root)
            return operator
        else:
            operator = pt.ProcessTree(parent=root, label=log[0][0][act_key])
            return operator

    def __count_traces(activities):
        count = 0
        actList = list()
        viewedTraces = list()

        # convert list of sets to list of activities
        for group in activities:
            for elem in group:
                actList.append(elem)

        for act in actList:
            for k, v in traceDict.items():
                if act in k and k not in viewedTraces:
                    count += v
                    viewedTraces.append(k)
        return count

    def __count_traces_seq(activities):
        count = 0
        viewedTraces = list()

        seqGroup = activities[0]

        # convert list of sets to list of activities
        for act in seqGroup:
            for k, v in traceDict.items():
                if act in k and k not in viewedTraces:
                    count += v
                    viewedTraces.append(k)
        return count

    # counting num traces that vote for cut
    def __count_traces_loop(posActs, act_key):
        count = 0
        actList = list()
        viewedTraces = list()

        # get the events of all looped traces
        for group in posActs:
            trActivities = list(map(lambda e: e[act_key], group))
            for act in trActivities:
                if act not in actList:
                    actList.append(act)

        # count the traces in which a loop is done
        for act in actList:
            for k, v in traceDict.items():
                if act in k and k not in viewedTraces:
                    count += v
                    viewedTraces.append(k)
        return count
