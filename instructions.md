# Instructions to run the server
## We use ngrok to expose the server to the internet
```
~/ngrok http 8080
```

## Set up the virtual environment and install dependencies
```
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install aiohttp
```

## Finally run the server with the following command
```
python3 ./server.py --host 0.0.0.0 --port 8080 --static ./static
```
When this is done, you should be able to access the server at the URL provided by ngrok. On your phone you can open the gyro page, and on your computer you can open the game page. By tilting the phone, you should be able to control the game.