# iperf3 Connection Logger

This repository contains my internship project for measuring and logging network connection speed using **iperf3**.

The project started as a Bash script and was later extended with a simple Python (Tkinter) graphical interface.

## Tech Stack

- Linux
- Bash
- Python
- Tkinter
- iperf3
- PowerShell
- WSL2

## Features

- Measures network connection speed with `iperf3`
- Saves test results into `connect_log.txt`
- Uses Bash scripts for automation
- Includes a simple Python GUI
- Supports command-line execution

## Repository structure

```text
iperf3-connection-logger/
├── README.md
├── bash/
├── python/
├── logs/
└── screenshots/
```

## Workflow

```text
User
   │
   ▼
Python GUI / Bash Script
   │
   ▼
iperf3 Client
   │
   ▼
Connection Test
   │
   ▼
connect_log.txt
```

## Project walkthrough

### 1. Installing iperf3

![Installing iperf3](screenshots/01-iperf3-installation.png)

### 2. Starting the server

![Server listening](screenshots/02-server-listening.png)

### 3. Checking iperf3 status

![Status check](screenshots/03-iperf3-status-check.png)

### 4. Creating the log file

![Log file](screenshots/04-log-file-created.png)

### 5. Running the logger

![Running script](screenshots/05-script-running.png)

### 6. Demonstration

![Demonstration](screenshots/06-demonstration.png)

### 7. Log output

![Log output](screenshots/07-log-output.png)

### 8. Python GUI

![GUI](screenshots/08-gui-interface.png)

## What I learned

During this project I practiced:

- writing Bash scripts
- working with iperf3
- logging data to files
- debugging shell scripts
- creating a simple GUI with Tkinter
- automating network testing
