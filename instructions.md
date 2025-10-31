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

## Stop the server and cloudflared
- To stop the server, press `CTRL + C` in the terminal where the server is running.
- To stop cloudflared, press `CTRL + C` in the terminal where cloudflared is running, or use (sudo) pkill cloudflared.
