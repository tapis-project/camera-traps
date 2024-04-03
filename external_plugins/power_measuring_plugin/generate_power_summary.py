from datetime import datetime
import json
from validate_schemas import validate_log_schema, validate_metadata_schema

def generate_power_summary():
    # open metadata file
    try:
        with open("metadata.json", 'r') as file:
            metadata = json.load(file)
    except FileNotFoundError:
        print("metadata.json not found")
        exit()

    # open cpu file
    try:
        with open("cpu.json", 'r') as file:
            cpu_log = json.load(file)
    except FileNotFoundError:
        print("cpu.json not found")
        exit()  

    # validate 
    validate_metadata_schema(metadata)
    validate_log_schema(cpu_log)

    # initialize summary list
    plugin_summary, pid_summary = summary_init(metadata)
    summary = {"plugin power summary report": plugin_summary, "pid power summary report": pid_summary}

    # start and end time
    monitor_times(cpu_log, pid_summary)

    # sum power consumption
    sum_power_consumption(cpu_log, pid_summary, plugin_summary, 'cpu_consumption')
 
    # write to json file
    with open("power_summary_report.json", "w") as outfile: 
        print("Writing to power_summary_report.json")
        json.dump(summary, outfile, indent=2)

def sum_power_consumption(log, pid_summary, plugin_summary, device):
    """
    sum power log, given log list of dicts, summary list of dicts, device string
    """
    for pid_report in pid_summary:
        pid_report[device] = 0
        for entry in log:
            logs_at_time = (list(entry.values())[0]) # [[0.0, '2437322'], [1.4, '3423844'], [2.3, '4737228']]
            for j in logs_at_time:
                # if pid in log matches summary, increment power value
                if int(j[1]) == pid_report['pid']:
                    pid_report[device] += j[0]

    for plugin_report in plugin_summary:
        plugin_report[device] = 0
        for pid_report in pid_summary:
            if plugin_report["plugin"] == pid_report['plugin_name']:
                plugin_report[device] += pid_report[device]


    return pid_summary, plugin_summary
    
def summary_init(metadata):
    """
    initialize summary report
    """
    pid_summary = []
    plugin_summary = []
    for plugin in metadata['plugins']:
        plugin_summary_dict = {"plugin": plugin['name'], "cpu_consumption": None, "gpu_consumption": None}
        plugin_summary.append(plugin_summary_dict)
        for pid in plugin['pids']:
            pid_summary_dict = {"pid": pid, "plugin_name": plugin['name'], 
                "start_time": None, "end_time": None, 
                "cpu_consumption": None, "gpu_consumption": None}
            pid_summary.append(pid_summary_dict)
        
    
    return plugin_summary, pid_summary

def monitor_times(log, summary):
    """
    find start and end time
    """
    all_times = []

    for report in summary:
        for entry in log:
            time = list(entry.keys())[0]
            logs_at_time = (list(entry.values())[0]) # [[0.0, '2437322'], [1.4, '3423844'], [2.3, '4737228']]
            for j in logs_at_time:
                # if pid in log matches summary, append start time and end
                if int(j[1]) == report['pid']:
                    log_datetime = datetime.strptime(time, "%m/%d/%Y %I:%M:%S %p")
                    if report['start_time'] is None and report['end_time'] is None:
                        report['start_time'] = time
                        report['end_time'] = time
                    else:
                        summary_starttime_datetime = datetime.strptime(report['start_time'], "%m/%d/%Y %I:%M:%S %p")
                        summary_endtime_datetime = datetime.strptime(report['end_time'], "%m/%d/%Y %I:%M:%S %p")
                        if summary_starttime_datetime > log_datetime:
                            report['start_time'] = time
                        if summary_endtime_datetime < log_datetime:
                            report['end_time'] = time

def main():
    generate_power_summary()  

if __name__ == "__main__":
    main()
