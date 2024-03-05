from jsonschema import validate
import json
from datetime import datetime

def generate_summary():
    # open metadata file
    try:
        with open("example_metadata.json", 'r') as file:
            metadata = json.load(file)
    except FileNotFoundError:
        exit()

    # open cpu file
    try:
        with open("example_cpu.json", 'r') as file:
            cpu_log = json.load(file)
    except FileNotFoundError:
        exit()

    # validate 
    validate_metadata_schema(metadata)
    validate_log_schema(cpu_log)

    # initialize summary list
    summary = summary_init(metadata)

    # start and end time
    monitor_times(cpu_log, summary)

    # sum power consumption
    sum_power_consumption(cpu_log, summary, 'cpu_consumption')
 
    # write to json file
    with open("sample_report.json", "w") as outfile: 
        json.dump(summary, outfile, indent=2)

def sum_power_consumption(log, summary, device):
    """
    sum power log, given log list of dicts, summary list of dicts, device string
    """
    for i, report in enumerate(summary):
        summary[i][device] = 0
        for entry in log:
            logs_at_time = (list(entry.values())[0]) # [[0.0, '2437322'], [1.4, '3423844'], [2.3, '4737228']]
            for j in logs_at_time:
                # if pid in log matches summary, increment power value
                if int(j[1]) == summary[i]['pid']:
                    summary[i][device] += j[0]

    return summary
    
def summary_init(metadata):
    """
    initialize summary report
    """
    summary = []
    for plugin in metadata['plugins']:
        for pid in plugin['pids']:
            summary_dict = {"pid": None, "command_line": None, 
                "start_time": None, "end_time": None, 
                "cpu_consumption": None, "gpu_consumption": None}
            summary_dict["pid"] = pid
            summary_dict["command_line"] = plugin['command_line']
            summary.append(summary_dict)

    return summary

def monitor_times(log, summary):
    """
    find start and end time
    """
    all_times = []
    starts = []
    ends = []
    # for i, report in enumerate(summary):
    #     for entry in log:
    #         datetime_object = datetime.strptime(list(entry.keys())[0], "%m/%d/%Y %I:%M:%S %p")
    #         all_times.append(datetime_object)
    #     start_time = min(all_times)
    #     end_time = max(all_times)



    print(start_time)

def validate_metadata_schema(metadata_file):
    """
    Validate incoming metadata json file is of correct form
    """
    # set schema
    metadata_schema = {
        "$schema": "http://json-schema.org/schema#",
        "type": "object",
        "properties": {
            "plugins": {
                "type":"array", 
                "items": {
                    "type":"object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "enum": [
                                    "image_scoring_plugin",
                                    "image_generating_plugin",
                                    "power_generating_plugin",
                                    "engine"
                                ]
                            },
                        "pids": {
                            "type": "array", 
                            "items": {"type":"integer"},
                            "minItems": 1,
                            "uniqueItems": True
                            },
                        "devices_measured": {
                            "type": "array",
                            "items": {
                                "type":"string", 
                                "enum": [
                                    "gpu",
                                    "cpu"
                                ]
                            }
                        },
                        "command_line":{
                            "type": "string"
                        }
                    },
                    "required": ["name", "pids", "devices_measured", "command_line"]          
                }
            },
            "tools":{
                "type": "object",
                "properties": {
                    "devices": {
                        "type": "object",
                        "properties": {
                            "device_type": {
                                "type": "string",
                                "enum": [
                                    "gpu",
                                    "cpu"
                                ]
                            },
                            "tool_name": {
                                "type": "string",
                                "enum": [
                                    "jtop",
                                    "scaph",
                                    "nvsmi"
                                ]
                            },
                            "tool_params": {
                                "type": "string",
                            },
                            "power_units": {
                                "type": "string",
                                "enum": [
                                    "watts"
                                ]
                            }
                        },
                        "required": ["device_type", "tool_name", "tool_params", "power_units"]
                    }
                },
                "required": ["devices"]
            },
            "start_time": {
                "type": "string",
                "format": "date-time"
            }
        },
        "required": ["plugins", "tools", "start_time"]
    }

    # validate schema
    try: 
        validate(instance=metadata_file, schema=metadata_schema)
    except Exception as e:
        print("Metadata validation failed:", e)
        exit()

def validate_log_schema(log_file):
    """
    Validate incoming log json file is of correct form
    """
    # set log schema
    log_schema = {
        "$schema": "http://json-schema.org/schema#",
        "type": "object",
        "properties": {
            "logs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "patternProperties": {
                        "^\\d{2}/\\d{2}/\\d{4} \\d{2}:\\d{2}:\\d{2} (AM|PM)$": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": [
                                    {"type": "number"},
                                    {"type": "string"}
                                ],
                                "minItems": 2,
                                "maxItems": 2
                            }
                        }
                    }
                }
            }   
        }
    }

    # new schema to avoid top level array error
    log_schema_object = {"logs": log_file}

    # validate schema
    try: 
        validate(instance=log_file, schema=log_schema_object)
    except Exception as e:
        print("Log validation failed:", e)
        exit()

if __name__ == "__main__":
    generate_summary()
