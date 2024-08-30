from datetime import datetime
import requests
import json
import time
from datetime import date
import os
import os.path
from sungrow_websocket import SungrowWebsocket
import aiohttp
import subprocess

# json with the tokens { "access_token": "", "refresh_token": "", "id_token": "", "expires_in: , "token_type": "Bearer"}
LOCAL_TOKEN_FILENAME = "./tesla_token_api.json" 

# client id from the tesla api
CLIENT_ID = "" 

# url to your tesla server "eu" or "us"
URL = 'https://fleet-api.prd.eu.vn.cloud.tesla.com/api/1/vehicles'

# public and private key for the APN service. Apple developer account required to create a private key. 
CERTIFICATE_FILE_NAME="./public.cer" 
CERTIFICATE_KEY_FILE_NAME="./private.pem" 

# device token used for sending APNs
DEVICE_TOKEN=""

# gps coordinate from your sungrow inverter
LATITUDE = 42.51218 
LONGITUDE = 6.72589 

# ip or hostname of your sungrow inverter
HOST = "192.168.8.50" 


###############################################
# path for log file, the log file is in scv format
global dir_path 
dir_path = os.path.dirname(os.path.realpath(__file__)) # by default the path of this script

# function get access token
def getAccess_Token():
    with open (LOCAL_TOKEN_FILENAME, 'r') as f:
        token = json.load(f)
    return token["access_token"]

# function to refresh the token
def refreshToken():
    # Load current token stored in local file
    with open(LOCAL_TOKEN_FILENAME, 'r') as f:
        token = json.load(f)
    refresh_token = token["refresh_token"]
    refresh_json = {
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "refresh_token": refresh_token,
                "scope": "openid email offline_access vehicle_device_data vehicle_cmds vehicle_charging_cmds"
    }
    token = requests.post('https://auth.tesla.com/oauth2/v3/token', json=refresh_json)
    if token.status_code != 200:
        raise requests.exceptions.ConnectionError("couldn't refresh token, status_code: " + str(token.status_code))
    else:
        print("refresh token success")
        # Save refreshed token to local text file
        with open(LOCAL_TOKEN_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(token.json(), f, ensure_ascii=False, indent=4)

# function to get all vehicles, used to get the id for further requests and to get the state (online, offline or asleep)
class Vehicle:
    def __init__(self, vehicles, pos):
        self.id = vehicles[pos]["id"]  # Extract car ID - if you have more than one car this need to be modified
        self.state = vehicles[pos]["state"]

def getVehicle(access_token, pos):
    headers = {"User-Agent": "TesyCharging", "content-type": "application/json; charset=UTF-8", 'Authorization': 'Bearer {}'.format(access_token)}
    response = requests.get(URL, headers=headers) #.json()
    if response.status_code != 200:
        raise requests.exceptions.ConnectionError("getVehicle: request status code: " + str(response.status_code))
    else:
        response_json = response.json()
        return Vehicle(response_json["response"], pos)

# function to get the charging status (Charging, Disconnected, ...)
class Charge_State:
    def __init__(self, charge_state):
        self.charging_state = charge_state["charging_state"]
        self.charge_amps = charge_state["charge_amps"]
        self.charger_actual_current = charge_state["charger_actual_current"]
        self.charge_current_request = charge_state["charge_current_request"]
        self.charger_power = charge_state["charger_power"]
        self.charger_voltage = charge_state["charger_voltage"]
        self.charge_current_request_max = charge_state["charge_current_request_max"]
        self.csvLine = str(self.charger_actual_current) + "\t" + str(self.charger_power) + "\t" + str(self.charger_voltage) + "\t" + str(self.charge_current_request_max) + "\t"
        #print("++Charge_State++")
        #print("charging_state: " + self.charging_state)
        #print("charge_amps: " + str(self.charge_amps))
        #print("charger_actual_current: " + str(self.charger_actual_current))
        #print("charge_current_request: " + str(self.charge_current_request))
        #print("charger_power: " + str(self.charger_power))
        #print("charger_voltage: " + str(self.charger_voltage))
        #print("charge_current_request_max: " + str(self.charge_current_request_max))
        #print("++++")

def chargingStatus(access_token, id):
    headers = {"User-Agent": "TesyCharging", "content-type": "application/json; charset=UTF-8", 'Authorization': 'Bearer {}'.format(access_token)}
    url_vehicle = URL + "/" + str(id) + "/vehicle_data"
    response = requests.get(url_vehicle, headers=headers)
    if response.status_code != 200:
        raise requests.exceptions.ConnectionError("chargingStatus: requests status code: " + str(response.status_code))
    else:
        response_json = response.json()
        return Charge_State(response_json["response"]["charge_state"])

# function to check if the car is at home
def isHome(access_token, id):
    headers = {"User-Agent": "TesyCharging", "content-type": "application/json; charset=UTF-8", 'Authorization': 'Bearer {}'.format(access_token)}
    url_location_data = URL + "/" + str(id) + "/vehicle_data?endpoints=location_data"
    response = requests.get(url_location_data, headers=headers)
    if response.status_code != 200:
        raise requests.exceptions.ConnectionError("isHome: request status code: " + str(response.status_code))
    else:
        response_json = response.json()
    lat: float = response_json["response"]["drive_state"]["latitude"]
    lon: float  = response_json["response"]["drive_state"]["longitude"]
    latitude_ = round(LATITUDE, 3)
    longitude_ = round(LONGITUDE, 3)
    lat = round(lat, 3)
    lon = round(lon, 3)
    if lat == latitude_ and lon == longitude_:
        return True
    else:
        print("Tesla is at " + str(lat) + ", " + str(lon))
        return False

# function to set the current
def setCharge_Amps(access_token, id, charging_amps):
    headers = {"User-Agent": "TesyCharging", "content-type": "application/json; charset=UTF-8", 'Authorization': 'Bearer {}'.format(access_token)}
    url_charger_amps = URL + "/" + str(id) + "/command/set_charging_amps"
    params = {"charging_amps": charging_amps}
    response = requests.post(url_charger_amps, data=json.dumps(params), headers=headers).json()
    #print(response)

# function to honk
def honk(access_token, id):
    headers = {"User-Agent": "TesyCharging", "content-type": "application/json; charset=UTF-8", 'Authorization': 'Bearer {}'.format(access_token)}
    url_honk = URL + "/" + str(id) + "/command/honk_horn"
    params = {}
    response = requests.post(url_honk, data=json.dumps(params), headers=headers).json()
    #print(response)

 # function to read the data from sungrow
class SungrowData:
    def __init__(self, host):
        sg = SungrowWebsocket(host)
        data = sg.get_data()
        self.battery_soc = float(data["battery_soc"][2])
        self.batteryChargingPower = float(data["config_key_3907"][2])
        self.batteryDischargingPower = float(data["config_key_3921"][2])
        self.dcPower = float(data["total_dcpower"][2])
        self.activePower = float(data["total_active_power"][2])
        self.totalLoadPower = float(data["load_total_active_power"][2])
        self.gridPower = round((self.dcPower - self.totalLoadPower - self.batteryChargingPower + self. batteryDischargingPower) * -1, 2)
        self.csvLine = str(self.battery_soc) + "\t" + str(self.batteryChargingPower) + "\t" + str(self.batteryDischargingPower) + "\t" + str(self.dcPower) + "\t" + str(self.totalLoadPower) + "\t" + str(self.activePower) + "\t" + str(self.gridPower) + "\t"
        #print("++SungrowData++")
        #print("battery_soc: " + str(self.battery_soc))
        #print("batteryChargingPower " + str(self.batteryChargingPower))
        #print("batteryDischargingPower " + str(self.batteryDischargingPower))
        #print("acPower " + str(self.dcPower))
        #print("activePower " + str(self.activePower))
        #print("totalLoadPower " + str(self.totalLoadPower))
        #print("gridPower " + str(self.gridPower))
        #print("++++")       

    @staticmethod
    def apnsMessageBody(self):
        batteryPower = ""
        if self.batteryChargingPower > 0:
            batteryPower = "; charging: " + str(self.batteryChargingPower) + "kW"
        elif self.batteryDischargingPower > 0:
            batteryPower = "; discharging: " + str(self.batteryDischargingPower) + "kW"
        else:
            batteryPower = ""
        return "battery: " + str(self.battery_soc) + "%" + batteryPower

    @staticmethod
    def apnsMessageSubtitle(self):
        return "PV: " + str(self.dcPower) + "kW; Load: " + str(self.totalLoadPower) + "kW; Grid: " + str(self.gridPower) + "kW"

# function to write the data to sungr
class SungrowJSON:
    def __init__(self):
        file = dir_path + "/sungrow.json"
        if os.path.isfile(file):
            # Load sungrow.json
            with open(file, 'r') as f:
                jsonfile = json.load(f)
            self.battery_soc = jsonfile["battery_soc"]
            self.gridPower = jsonfile["gridPower"] 
        else:
            self.battery_soc = 0
            self.gridPower = 5 

    @staticmethod
    def writeFile(battery_soc, gridPower):
        soc = str(battery_soc)
        grid = str(gridPower)
        jsonfile = '{"battery_soc":' + soc + ',"gridPower":' + grid + '}'
        # Save sungrow.json to local text file
        file = dir_path + "/sungrow.json" 
        with open(file, 'w', encoding='utf-8') as f:
            f.write(f'{jsonfile}')

def calculatePossibleCurrent(sgData, charge_state):
    if sgData.battery_soc > 80:
        print("Sungrow Battery has over 80%")
        powerUsedFromTesla = charge_state.charger_actual_current * charge_state.charger_voltage / 1000
        print("Tesla is charing with " + str(powerUsedFromTesla) + " kW")
        current_max = round(((powerUsedFromTesla - sgData.gridPower) * 1000 / charge_state.charger_voltage), 0)
        print("possible current_max: " +str(current_max))
        if current_max > charge_state.charge_current_request_max:
            current_max = charge_state.charge_current_request_max
            return current_max
        else:
            return current_max
    else:
        print("Battery below 80%")
        return 0

def sendAPNs(title, subtitle, body, relevance, sound="coin.aiff"):
    # add "-v" for verbose
    curlcommand = 'curl \
      --cert "' + CERTIFICATE_FILE_NAME + '" \
      --cert-type DER \
      --key "' + CERTIFICATE_KEY_FILE_NAME + '" \
      --key-type PEM \
      --header "apns-topic: com.david.tesychargingng" \
      --header "apns-push-type: alert" \
      --header "apns-priority: 10" \
      --header "apns-expiration: 0" \
      --data \'{"aps":{"alert":{"title":"' + title + '","subtitle":"' + subtitle + '","body":"' + body + '"},"sound":"' + sound + '","relevance-score":'+ str(relevance) +',"category": "sungrow"}}\' \
      --http2  https://api.push.apple.com:443/3/device/' + DEVICE_TOKEN
    result = subprocess.Popen(curlcommand, shell=True, stderr=subprocess.PIPE).stdout

def writeCVS(line):
    file = dir_path + "/" +str(date.today()) + "_sungrow.csv"
    if not os.path.isfile(file):
        # create a file
        title_line = "date            \tbattery\tchar\tdischar\tdc\tload\tactive\tgrid\tcurrent\tpower\tvoltage\tmax\tset A\t"
        with open(file, 'w', encoding='utf-8') as f:
            f.write(f'{title_line}')
    # append a line
    with open(file, 'a', encoding='utf-8') as f:
        f.write(f'\n{line}')


##################
requestToTesla = True
apns_title = "sungrow"
apns_subtitle = ""
apns_body = ""
apns_warning = ""
now = datetime.now() # current date and time
date_time = now.strftime("%Y-%m-%d %H:%M")
print(date_time)
line = date_time + "\t"
try:
    sungrowfile = SungrowJSON()
    sgData = SungrowData(HOST)
    apns_subtitle = sgData.apnsMessageSubtitle(sgData)
    apns_body = sgData.apnsMessageBody(sgData)
    line = line + sgData.csvLine
    if sgData.gridPower > 0 and sungrowfile.gridPower <= 0:
        apns_warning = "consuming power from the grid (" + str(sgData.gridPower) + "kW)"
    elif sgData.gridPower < 0 and sungrowfile.gridPower >= 0:
        apns_warning = "providing power to the grid (" + str(sgData.gridPower) + "kW)"
    if sgData.battery_soc > 95 and sungrowfile.battery_soc <= 95:
        if apns_warning == "":
            apns_warning = apns_warning + "\\n"
        apns_warning = apns_warning + "sungrow battery is full (" + str(sgData.battery_soc) + "%)"
    elif sgData.battery_soc < 20 and sungrowfile.battery_soc >= 20:
        if apns_warning == "":
            apns_warning = apns_warning + "\\n"
        apns_warning = apns_warning + "sungrow battery is below 20% (" + str(sgData.battery_soc) + "%)"
    sungrowfile.writeFile(sgData.battery_soc, sgData.gridPower)
    if requestToTesla:
        refreshToken()
        access_token = getAccess_Token()
        vehicle = getVehicle(access_token, 0)

        if vehicle.state == "online":
            print("Tesla is online")
            charge_state = chargingStatus(access_token, vehicle.id)
            if charge_state.charging_state == "Charging":
                # check if the car is at home
                if isHome(access_token, vehicle.id):
                    print("Tesla is at home and charging")
                    line = line + charge_state.csvLine
                    current = calculatePossibleCurrent(sgData, charge_state)
                    #if current != charge_state.charge_amps:
                    if current != charge_state.charger_actual_current:
                        setCharge_Amps(access_token, vehicle.id, current)
                        print("current is changed from " + str(charge_state.charger_actual_current) + " A to " + str(current) + " A is set")
                        line = line + str(current) + "\t"
                        apns_title = "charging @home changed from " + str(charge_state.charger_actual_current) + "A to " + str(current) + "A"
                        #notify that current changed
                        #honk(access_token, vehicle.id)
                    else:
                        print("don't need to change anything")
                        apns_title = "charging @home with " + str(current) + "A - " + str(current * charge_state.charger_voltage / 1000) + "kW"
                else:
                    print("Tesla is not at home")
                    line = line + "Tesla is not charging at home\t"
                    apns_title = "charing with " + str(current * charge_state.charger_voltage / 1000) + "kW"
            else:
                print("Tesla is " + charge_state.charging_state)
                line = line + "Tesla is " + charge_state.charging_state + "\t"
        else:
            print("Tesla is " + vehicle.state)
            line = line + "Tesla is " + vehicle.state + "\t"
            apns_body = apns_body + " Tesla is " + vehicle.state
    else:
        line = line + "Tesla was not requested\t"
except requests.exceptions.RequestException as err:
    print ("Request Error:", str(err))
    apns_title = str(err)
    apns_warning = apns_warning + "request error"
    line = line + str(err) + "\t"
except requests.exceptions.HTTPError as errh:
    print ("Http Error:",errh)
    apns_title = errh
    apns_warning = apns_warning + "request error"
    line = line + errh + "\t"
except requests.exceptions.ConnectionError as errc:
    print ("Error Connecting:",errc)
    apns_title = errc
    apns_warning = apns_warning + "request error"
    line = line + errc + "\t"
except requests.exceptions.Timeout as errt:
    print ("Timeout Error:",errt) 
    apns_title = errt
    apns_warning = apns_warning + "request error"
    line = line + errt + "\t"    
except KeyError as keyerr:
    print ("Key Error:",keyerr)
    apns_title = keyerr
    apns_warning = apns_warning + "request error"
    line = line + keyerr + "\t"
except FileNotFoundError as fileError:
    print ("File not found:",fileError)
    apns_title = str(fileError)
    apns_warning = apns_warning + "request error"
    line = line + str(fileError) + "\t"
except aiohttp.client_exceptions.ServerDisconnectedError as discon:
    print ("Server Disconnected:",discon, HOST)
    apns_title = discon
    apns_warning = apns_warning + "request error"
    line = line + discon + "\t"
except aiohttp.client_exceptions.ClientConnectorError as clientcon:
    print ("Client Disconnected:",clientcon)
    apns_title = str(clientcon)
    apns_warning = apns_warning + "request error"
    line = line + str(clientcon) + "\t"
if apns_warning == "":
    sendAPNs(apns_title, apns_subtitle, apns_body, 0.1, "")
else:
    sendAPNs(apns_title, apns_subtitle, apns_body + "\\n" + apns_warning, 1.0)
writeCVS(line)
print("---")
command = 'cat ' + dir_path + '/' +str(date.today()) + '_sungrow.csv'
subprocess.Popen(command, shell=True)
