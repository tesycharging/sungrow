# sungrow
python script to read the data from a sungrow inverter and change the tesla charging power to consume power from the PV only.

## install
I recommend to run it as a cron job.
```
pip install sungrow-websocket
```
if you use python 3.7 you have to replace the "__init__.py" with the file "__init__py" file in this repo. The folder is propably "/usr/local/lib/python3.7/dist-packages/sungrow_websocket"

```
pip install requests
pip install json
pip install time
pip install aiohttp
```
set the variables
### json with the tokens { "access_token": "", "refresh_token": "", "id_token": "", "expires_in: , "token_type": "Bearer"}
```
LOCAL_TOKEN_FILENAME = "./tesla_token_api.json" 
```
### client id from the tesla api
```
CLIENT_ID = "" 
```

### url to your tesla server "eu" or "us"
```
URL = 'https://fleet-api.prd.eu.vn.cloud.tesla.com/api/1/vehicles'
```

### public and private key for the APN service. Apple developer account required to create a private key. 
```
CERTIFICATE_FILE_NAME="./public.cer" 
CERTIFICATE_KEY_FILE_NAME="./private.pem" 
```

### device token used for sending APNs
```
DEVICE_TOKEN=""
```

### gps coordinate from your sungrow inverter
```
LATITUDE = 45.51218 
LONGITUDE = 2.72589 
```

### ip or hostname of your sungrow inverter
```
HOST = "192.168.8.50" 
```
