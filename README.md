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
set the config files 
### the file sungrow.setting in json format
```
{
  "authentication_token": "",
  "device_token": "",
  "inverter_host": "",
  "latitude": 43.51205,
  "longitude": 12.72584
}
```
### the file tesla.token with the token for the Tesla API in json format
```
{
  "access_token":"",
  "region_url":"https:\/\/fleet-api.prd.eu.vn.cloud.tesla.com",
  "id_token":"",
  "expires_in":28800,
  "token_type":"Bearer",
  "refresh_token":"",
  "client_id":""
}
```

### public and private key for the APN service. Apple developer account required to create a private key. 
```
CERTIFICATE_FILE_NAME="./public.cer" 
CERTIFICATE_KEY_FILE_NAME="./private.pem" 
```

