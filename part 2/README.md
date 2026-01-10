# Client-to-Client Chat via Server (Up to 5 Users, Private Conversations)

# About-
This project has two parts:
1) Part 1: network traffic analysis with Wireshark captures and a notebook.
2) Part 2: a simple TCP chat server with a terminal client and a NiceGUI web UI.

The chat supports private messages to one or more users and keeps a live list of
connected names for the UI.

## Part 1 - Network Analysis
**Files**
- `Part 1/Capture from Wireshark.pcapng`
- `Part 1/wiresharkhttp (1).pcapng`
- `Part 1/group_http_input.csv`
- `Part 1/raw_tcp_ip_notebook_fallback_annotated-v1-NewFinal.ipynb`

**What it is**
- Packet captures to inspect HTTP/TCP traffic in Wireshark.
- A Jupyter notebook with analysis and notes.
- A CSV input file used by the notebook.

**How to use**
1) Open the `.pcapng` files with Wireshark.
2) Open the notebook with Jupyter (`jupyter notebook`) and run the cells.

## Part 2 - TCP Chat App
**Files**
- `Part 2/server.py` (chat server)
- `Part 2/client.py` (terminal client)
- `Part 2/nicegui_client.py` (NiceGUI web UI)
- `Part 2/Capture client server Wireshark.pcapng` (traffic capture)
- `Part 2/clientserver.txt` (notes / logs)

**Main features**
- Up to 5 clients connected at the same time.
- Private messages: `recipient[,recipient] - message`
- Live user list for the UI drop-down.
- Join/leave messages shown as small system banners in the UI.

**How to run (terminal client)**
1) Start the server:
   - `python "Part 2/server.py"`
2) Start one or more clients:
   - `python "Part 2/client.py"`
3) Send a message in this format:
   - `Ronny,Ofir - hello`
4) Type `exit` to leave.

**How to run (NiceGUI UI)**
1) Install dependency:
   - `pip install nicegui`
2) Start the server:
   - `python "Part 2/server.py"`
3) Start the UI client:
   - `python "Part 2/nicegui_client.py"`
4) Open the link shown in the terminal (usually `http://localhost:8080`).

**Notes**
- Server host/port are set in the code: `127.0.0.1:10000`.
- If the server is full, new clients are rejected.
- The UI "to" menu shows only currently connected users.
