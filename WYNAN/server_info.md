 # 1 Launch live server , on parent pc
uvicorn app:app --host 127.0.0.1 --port 8000 --reload

127.0.0.1 is a loopback address, meaning your computer only accepts connections from itself. To open it up to your other devices on the same network, follow these three steps:

 # 2 Launch live server , on parent pc , view on devices on the same network
 uvicorn app:app --host 0.0.0.0 --port 8000 --reload

 Find Your Host PC's Local IP Address
Open a new terminal window on the computer running the server and check its local Wi-Fi IP address:

On Windows: Run ipconfig and look for IPv4 Address under your Wireless LAN adapter (usually looks like 192.168.1.x or 192.168.43.x if using a phone hotspot).

On Linux (Ubuntu/Mint): Run hostname -I and take the first 192.168.x.x address listed.

Open the URL on Your Phone, Tablet, or Second PC
On the browser of your phone, tablet, or other PC (while connected to the same Wi-Fi/hotspot), enter your host PC's IP address with port 8000 (for example):

Plaintext
http://192.168.1.25:8000
(Replace 192.168.1.25 with the exact IPv4 address from Step 2.)