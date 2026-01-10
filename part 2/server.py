import socket
import threading

# Server IP address (this computer)
HOST = "127.0.0.1"

# Server port number
PORT = 10000

# Max clients allowed in the chat
MAX_CLIENTS = 5

clients = {}  # socket -> name
clients_lock = threading.Lock()  # protects the clients dict
next_client_id = 0  # simple counter for logging
id_lock = threading.Lock()  # protects next_client_id


def broadcast(message, exclude_conn=None):
    # Send a message to all clients except one (optional).
    data = (message + "\n").encode("utf-8")
    with clients_lock:
        recipients = [conn for conn in clients.keys() if conn != exclude_conn]
    for conn in recipients:
        try:
            conn.sendall(data)
        except OSError:
            with clients_lock:
                clients.pop(conn, None)

def send_user_list():
    # Send the full list of connected names to every client.
    with clients_lock:
        names = list(clients.values())
        recipients = list(clients.keys())
    payload = "__users__ " + ",".join(names) + "\n"
    data = payload.encode("utf-8")
    for conn in recipients:
        try:
            conn.sendall(data)
        except OSError:
            with clients_lock:
                clients.pop(conn, None)


def send_private(sender, recipients, message, sender_conn):
    # Send a private message to one or more named users.
    with clients_lock:
        name_to_conn = {name: conn for conn, name in clients.items()}

    for recipient in recipients:
        conn = name_to_conn.get(recipient)
        if not conn:
            # Tell the sender if the user name is not found.
            try:
                sender_conn.sendall(
                    f"user not found: {recipient}\n".encode("utf-8")
                )
            except OSError:
                pass
            continue
        formatted = f"{sender} : {recipient} - {message}\n"
        try:
            conn.sendall(formatted.encode("utf-8"))
        except OSError:
            with clients_lock:
                clients.pop(conn, None)


def handle_client(conn, addr):
    global next_client_id
    # Give this connection a simple id for logs.
    with id_lock:
        next_client_id += 1
        client_id = next_client_id
    print(f"client {client_id} connected in : {addr}")

    try:
        # Welcome + ask for name.
        conn.sendall("welcome to the chat\n".encode("utf-8"))
        conn.sendall("enter name: ".encode("utf-8"))
        name_data = conn.recv(1024)
        if not name_data:
            return
        name = name_data.decode("utf-8").strip()
        if not name:
            # Fallback name if the user typed nothing.
            name = f"{addr[0]}:{addr[1]}"

        with clients_lock:
            clients[conn] = name
            online = len(clients)
        print(f"client online {online}")
        send_user_list()

        # Let everyone else know.
        broadcast(f"{name} joined the chat", exclude_conn=conn)

        # Main loop: read messages from this client.
        while True:
            data = conn.recv(1024)
            if not data:
                break
            message = data.decode("utf-8").strip()
            if message.lower() == "exit":
                break
            # Format: "name[,name] - message"
            if " - " in message:
                recipient_part, body = message.split(" - ", 1)
                recipients = [
                    part.strip()
                    for part in recipient_part.split(",")
                    if part.strip()
                ]
                if recipients and body.strip():
                    send_private(name, recipients, body.strip(), conn)
                    continue
            # If the format is wrong, guide the user.
            try:
                conn.sendall(
                    "use: recipient[,recipient] - message\n".encode("utf-8")
                )
            except OSError:
                break

    except ConnectionResetError:
        print(f"client {client_id} disconnected {addr}")
    finally:
        # Remove client and notify others.
        with clients_lock:
            left_name = clients.pop(conn, None)
        if left_name:
            broadcast(f"{left_name} left the chat", exclude_conn=conn)
        send_user_list()
        print(f"client {client_id} disconnect")
        conn.close()

def start_server():
    # Create TCP socket (IPv4 + TCP)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Bind socket to IP address and port
    server_socket.bind((HOST, PORT))

    # Start listening for incoming connections
    server_socket.listen()

    print(f"server listen in : {HOST}: {PORT}")

    # Accept clients forever
    while True:
        # Wait for a new client connection
        conn, addr = server_socket.accept()

        with clients_lock:
            if len(clients) >= MAX_CLIENTS:
                # Reject extra clients if the server is full.
                try:
                    conn.sendall("server full, try later\n".encode("utf-8"))
                finally:
                    conn.close()
                continue

        # Handle each client in its own thread.
        client_thread = threading.Thread(target=handle_client, args=(conn, addr))
        client_thread.start()

# Run the server file
if __name__ == "__main__":
    start_server()
