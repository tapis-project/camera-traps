from jsonschema import validate
import json

def generate_summary():
    # validate 
    validate_metadata_schema("example_metadata.json")
    # validate_log_schema("example_cpu.json")

def validate_metadata_schema(metadata_path):
    """
    Validate incoming metadata json file is of correct form
    """
    # open metadata file
    try:
        with open(metadata_path, 'r') as file:
            metadata_file = json.load(file)
    except FileNotFoundError:
        exit()

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
                                    "power_generating_plugin"
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
                            # any way to specify more?
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
                                # enum?
                            },
                            "tool_params": {
                                "type": "string",
                                # enum?
                            },
                            "power_units": {
                                "type": "string",
                                # include enum or no?
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

def validate_log_schema(log_path):
    """
    Validate incoming log json file is of correct form
    """
    # open log file
    try:
        with open(log_path, 'r') as file:
            log_file = json.load(file)
    except FileNotFoundError:
        exit()

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
    validate_metadata_schema("example_metadata.json")
    validate_log_schema("example_cpu.json")
