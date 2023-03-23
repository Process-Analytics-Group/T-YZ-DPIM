import numpy as np
from Expo_Package.cut_counting import __get_cutCount
from Expo_Package import log_im_modified
from pm4py.objects.process_tree import obj as pt

k_best_cut = list()


def __dp_tree(log, goalEpsilon, dfg, threshold, root, act_key, use_msd, remove_noise=False):

    # get number of executes cuts in process strucre tree
    global cutdict
    cutdict, numCuts = __get_cutCount(log, dfg, threshold, root, act_key, use_msd, remove_noise=False)

    # get the epsilon we use in the exponential mechanism below
    global epsilon
    epsilon = goalEpsilon / numCuts

    # create a differential private process tree and return it
    tree = log_im_modified.__inductive_miner(log, dfg, threshold, root, act_key, use_msd, remove_noise=False)

    # return the differential private process tree
    return tree


def choose_cut():

    global cutdict, epsilon
    
    # list of all cuts
    elements = list(cutdict.keys())

    # the computed score of all cuts -> u(D, cut)
    scores = list(cutdict.values())

    # list of exponents
    exponents = [epsilon * score / 2 for score in scores]

    #if maximum score is greater than the maximum numpy can work with -> TODO: change if numpy can work with large values under windows
    if max(exponents) > 709:
        helpList = list()
        benchmarkValue = max(exponents)
        #get percentage distance between the values to the max value
        for value in exponents:
            helpList.append(value/benchmarkValue)
        
        #create list with values numpy can work with -> we work with 700 to avoid errors
        probabilities = [700 * entry for entry in helpList]
        #get the list of exp() we need for the exponential mechanism
        probabilities = [np.exp(value) for value in probabilities]
    else:
        #get the list of exp() we need for the exponential mechanism
        probabilities = [np.exp(epsilon * score / 2) for score in scores]

    #normalizing
    probabilities = probabilities / np.linalg.norm(probabilities, ord=1)

    #choose the cut to make
    cut = np.random.choice(elements, 1, p=probabilities)[0]

    #return the cut to use and change the score, since we used the cut
    if 'sequence' in cut:
        cutdict.pop(cut)
        return pt.Operator.SEQUENCE

    elif 'xor' in cut:
        cutdict.pop(cut)
        return pt.Operator.XOR

    elif 'parallel' in cut:
        cutdict.pop(cut)
        return pt.Operator.PARALLEL

    elif 'loop' in cut:
        cutdict.pop(cut)
        return pt.Operator.LOOP