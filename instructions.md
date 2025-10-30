# Instructions to run the server

## Set up the virtual environment and install dependencies
```
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install aiohttp
pip install cloudflared
```

## Run the server with the following command
```
python3 ./server.py --host 0.0.0.0 --port 8080 --static ./static
```

## Start cloudflared with the following command
```./run.sh```

When cloudflared is running, `games.arthurlimpens.com` will route to your local server.

## Notes / troubleshooting
- Ensure the credentials JSON for the named tunnel exists under `~/.cloudflared` and the `credentials-file` path in the env file points to it.

Originally we used ngrok to create a tunnel:
```
~/ngrok http 8080
```
