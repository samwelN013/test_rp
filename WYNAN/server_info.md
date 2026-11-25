 ## `cd foldername` : to move up the folders
  ## cd foldername1\foldername2/foldername_etc : to move up the folders
## `cd foldername` : to move down the folders

# 1 Launch live server , on parent pc
`uvicorn app:app --host 127.0.0.1 --port 8000 --reload`

127.0.0.1 is a loopback address, meaning your computer only accepts connections from itself. To open it up to your other devices on the same network, follow these three steps:

 # 2 Launch live server , on parent pc , view on devices on the same network (wifi)

` uvicorn app:app --host 0.0.0.0 --port 8000 --reload`

 Find Your Host PC's Local IP Address
Open a new terminal window on the computer running the server and check its local Wi-Fi IP address:

On Windows: Run `ipconfig` and look for `IPv4 Address` under your Wireless LAN adapter (usually looks like 192.168.1.x or 192.168.43.x if using a phone hotspot).

On Linux (Ubuntu/Mint): Run `hostname -I` and take the first `192.168.x.x` address listed.

Open the URL on Your Phone, Tablet, or Second PC
On the browser of your phone, tablet, or other PC (while connected to the same Wi-Fi/hotspot), enter your host PC's IP address with port 8000 (for example):

Plaintext
http://`192.168.1.25:8000`

(Replace 192.168.1.25 with the exact IPv4 address from Step 2. (the parent device running the code))

# 3 in powershell : to activate the python venv across the system; windows 
If PowerShell blocks the activation script with a running scripts is disabled on this system error, allow local scripts for your user account once and re-run the activation command:

`Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser .\.venv_prj1\Scripts\Activate.ps1`

## in POWERSHELL

`cd C:\Users\user\Desktop\test_repo`
`.\.venv_prj1\Scripts\Activate.ps1`
`python aggtrades_updater_v2.py`

## IN CMD

`cd C:\Users\user\Desktop\test_repo`
`.venv_prj1\Scripts\activate.bat`
`python aggtrades_updater_v2.py`



## Slash Direction (\ vs. /) -- venv activationin terminals
In PowerShell: Both \ and / actually work for navigation and paths (./.venv_prj1/Scripts/Activate.ps1 works fine in modern PowerShell), though \ is the native Windows standard.

In CMD (Command Prompt): \ is strictly mandatory. If you type .venv_prj1/Scripts/activate.bat with forward slashes in CMD, it will fail because CMD interprets / as a command flag/option rather than a folder separator.

# 4 RUNNING THE SCRIPTS IN TERMINAL powershell or cmd or vscode
PowerShell
 `python main.py`

Since (.venv_prj1) is already active at the start of your prompt, python automatically uses your virtual environment's interpreter.

Quick troubleshooting:

If python isn't recognized: Use` py main.py` instead (the Windows Python launcher).

If main.py is inside a subfolder: Include the relative path (e.g., `python src/main.py`) or cd into that folder first.

# 5 TAILSCALE  # braodcasting to personal devices
Install on winows
`winget install Tailscale.Tailscale`

to start it 
`tailscale serve 8000`

using it for access of the live webpage

Copy the exact URL it prints:
Tailscale will print your permanent private address right in the terminal—it will look like:

Plaintext
`https://professor.<your-tailnet-name>.ts.net`

to stop the server 
`tailscale serve reset`
or 
`ctrl + c` in the terminal

Install Tailscale on Ubuntu Linux
Install via Tailscale's official one-line script:

Bash
`curl -fsSL https://tailscale.com/install.sh | sh`
Start Tailscale and log in (use the exact same Google/GitHub account you used on Windows):

Bash
`sudo tailscale up`
Open the authentication link printed in your terminal to link the Ubuntu machine.

Serve port 8000:
Bash
`sudo tailscale serve 8000`

# 6 CLOUDFLARED public broadcast

Install cloudflared on your `Windows PC` (run in PowerShell):

PowerShell
`winget install Cloudflare.cloudflared`
(Close and reopen PowerShell after installing so the cloudflared command is recognized.)

Keep Uvicorn running in your first terminal (`uvicorn app:app --host 127.0.0.1 --port 8000`).

Open a second terminal and start the tunnel:

PowerShell
`cloudflared tunnel --url http://127.0.0.1:8000`

(Optional: If you want to lock the link so only your email can open it via a one-time PIN, run cloudflared tunnel --url [http://127.0.0.1:8000](http://127.0.0.1:8000) --allowed-mail your_email@gmail.com.)

Open the generated link (e.g., [https://random-words.trycloudflare.com](https://random-words.trycloudflare.com)) on your phone over mobile data. It stays live as long as your PC and that terminal window stay running.