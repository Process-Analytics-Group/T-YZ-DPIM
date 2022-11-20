import os
import Expo_Package.discovery as disco
from pm4py.visualization.process_tree import visualizer as pt_visualizer

def initialization():
    file_path = input("Please write the path to the Event-Log file: ")
    file_path = file_path.replace('"', '')

    epsilon = float(input("Please enter the goal epsilon: "))

    #get the file type -> extension
    name, extension = os.path.splitext(file_path)

    #check type of file and go to the correct function
    if  extension.lower() == '.csv':
        __import_csv(file_path, epsilon)

    elif extension.lower() == '.xes':
        __import_xes(file_path, epsilon)

def __import_csv(file_path, epsilon):
    import csv
    import pandas as pd
    import pm4py

    #detect the delimiter of the.csv file
    with open(file_path, "r") as csvfile:
        dialect = csv.Sniffer().sniff(csvfile.readline())
    #read .csv file
    event_log = pd.read_csv(file_path, sep=dialect.delimiter)
    #define dataframe of the EventLog
    event_log = pm4py.format_dataframe(event_log, case_id='TraceID', activity_key='ActivityName', timestamp_key='TimeStamp')

    __createProcessTree(event_log, epsilon)

def __import_xes(file_path, epsilon):
    from pm4py.objects.log.importer.xes import importer as xes_importer

    #read .xes file
    event_log = xes_importer.apply(file_path)

    __createProcessTree(event_log, epsilon)

def __createProcessTree(eventLog, epsilon):
    
    dp_PST = disco.discover_process_tree_inductive(eventLog, epsilon)
    
    gviz = pt_visualizer.apply(dp_PST, parameters={pt_visualizer.Variants.WO_DECORATION.value.Parameters.FORMAT: "png"})
    pt_visualizer.view(gviz)

if __name__ == "__main__":
    initialization()