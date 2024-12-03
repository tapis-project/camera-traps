# Power Measure Plugin
----
Power consumption in inferencing AI models is a critical consideration, particularly for edge devices. High power consumption can lead to reduced battery life, increased costs, and more frequent charging or battery replacement intervals. For AI models to be effectively integrated and operational in real-world scenarios, they need to be efficient, with minimal power demands. Efficient models enable faster computation, longer device uptime, and wider adoption in applications where constant power sources are unavailable. As AI continues to penetrate various sectors, optimizing power consumption during inferencing ensures the sustainable growth and usability of AI-driven solutions in our everyday lives.

Power measuring tools play a pivotal role in monitoring the power consumption of AI models during inference, especially in edge devices. As these models process data and make decisions in real time, understanding their power demands becomes crucial. By accurately gauging power usage, developers and system managers can dynamically adjust workloads, balance system resources, and optimize model parameters for energy efficiency. This real-time adjustment ensures that devices remain responsive, maximize battery life, and avoid potential overheating or other power-related issues. Furthermore, consistent power monitoring provides invaluable data for refining algorithms and hardware architectures. In essence, power measuring not only guarantees optimal performance during AI inference but also informs future advancements in AI hardware and software design, ensuring sustainable and efficient AI integration in various applications.

----
## Designs
When inference AI models, we consider two important pieces of hardware that can consume most of the power on the device, i.e. CPU and GPU. CPU participates in data loading, pre-processing, post-processing, etc., while GPU will handle all the computation in AI models. Therefore, this plugin provides fine-grained monitoring of them.

| **Hardware** | **Requirements**     | **Backend API**     | **Sample Rate (per second)** | **Notes**                         |
| ------------ | -------------------- | ------------------- | ----------------------       | --------------------------------- |
| CPU          | Intel RAPL interface | Scaphandre          |  2                           | Process-level monitoring          |
| GPU          | NVIDIA               | NVML                |  2 (configurable)            | On-chip power monitoring          | 

The plugin spawns two threads at launching. 
- Thread 0 will spin on the socket to check if new power-measuring events are coming, if so, it adds them to the event queue.
- Thread 1 will spin on the event queue, and read out events with the necessary information, e.g. monitoring type, duration, PIDs, start_time, etc.

The plugin uses the system-level process to directly run the backend APIs and capture the output. By default, CPU-level monitoring can be fine-grained at the individual processes, while GPU only logs the overall power on chip.

----
## Usage
In other plugins where you want to measure power,
```
from ctevents.ctevents import send_power_measure_fb_event
import os

pids = [os.getpid(), ]                                   # Could be any pids you want to measure
monitor_type = [0, ]                                     # 0 for CPU & GPU, 1 for CPU, 2 for GPU  (TODO: 3 for DRAM)
monitor_duration = 10                                    # Seconds
send_power_measure_fb_event(socket, pids, monitor_type, monitor_duration)
```

Default log files will be saved under `~/logs`, and CPU and GPU logs will be separated. 

We provide a test case in our plugin, set the environment `TRAPS_TEST_POWER_FUNCTION=1`, and the plugin will log its own power consumption for 10 seconds.

----
## Example of output
`~/logs/CPU.json`:
```
{"2023-08-25 05:50:59": [8.369286, "337263", "python"], "2023-08-25 05:51:02": [8.153751, "337263", "python"], "2023-08-25 05:51:04": [7.726121, "337263", "python"], "2023-08-25 05:51:06": [8.300131, "337263", "python"]}
```
The dict keys are the time stamps, for every process, the first element is the power in Watts, the second is the PID, and the third is the process name.

`~/logs/GPU.json`:
```
{"2023-08-25 05:50:57": 48.57, "2023-08-25 05:51:00": 47.49, "2023-08-25 05:51:02": 53.4, "2023-08-25 05:51:04": 47.5, "2023-08-25 05:51:06": 49.96}
```
The dict keys are the time stamps, since NVIDIA does not support process-level monitoring, we only record the overall on-chip power(in Watts).
