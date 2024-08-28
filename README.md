# sungrow
python script to read the data from a sungrow inverter and change the tesla charging power to consume power from the PV only.

## install
'pip install sungrow-websocket
if you use python 3.7 you have to replace the "__init__.py" with the file "__init__py" file in this repo. The folder is propably "/usr/local/lib/python3.7/dist-packages/sungrow_websocket"

'pip install requests
'pip install json
'pip install time
'pip install aiohttp

set the variables
'LOCAL_TOKEN_FILE to the file with the token json
'CLIENT_ID
'LATITUDE #with your GPS coordinates of your PV
'LONGITUDE #with you GPS coordinates of your PV
'HOST #ip of you sungrow inverter in the local network
