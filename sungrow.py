import sys, getopt
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
import configparser

###############################################
# path for log file, the log file is in scv format
global dir_path 
dir_path = os.path.dirname(os.path.realpath(__file__)) # by default the path of this script
    
# class of settings, best to provide from the iOS App TesyCharging
class Settings():
    def __init__(self):
        file = dir_path + "/sungrow.setting"
        if os.path.isfile(file):
            # Load sungrow.setting
            with open(file, 'r') as f:
                jsonfile = json.load(f)
            self.authentication_token = jsonfile["authentication_token"] # used for Apple Push Notification (one our valid)
            self.device_token = jsonfile["device_token"] # used for Apple Push Notification (one our valid)
            self.inverter_host = jsonfile["inverter_host"]
            self.latitude = jsonfile["latitude"] # coordinate of the inverter
            self.longitude = jsonfile["longitude"] # coordinate of the inverter
        else:
            raise FileNotFoundError("create the file \"sungrow.setting\" with TesyCharging iOS APP\n")
            
# class for authentication of Tesla API, token can be provided from iOS App TesyCharging
class TeslaAPI():
    def __init__(self, pos = 0):
        self.error = "--"
        self.hasError = False
        file = dir_path + "/tesla.token"
        with open (file, 'r') as f:
            tesla_token = json.load(f)
        self.access_token = tesla_token["access_token"]
        self.refresh_token = tesla_token["refresh_token"]
        self.client_id = tesla_token["client_id"]
        self.region_url = tesla_token["region_url"]
        
        refresh_json = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "refresh_token": self.refresh_token,
            "scope": "openid email offline_access vehicle_device_data vehicle_cmds vehicle_charging_cmds"
        }
        token = requests.post('https://auth.tesla.com/oauth2/v3/token', json=refresh_json)
        if token.status_code != 200:
            #raise requests.exceptions.ConnectionError("couldn't refresh token, status_code: " + str(token.status_code))
            self.error = "Token ERR: " + str(token.status_code)
            self.hasError = True
        else:
            # Save refreshed token to local text file
            data = token.json()
            data.update({"client_id":self.client_id})
            data.update({"region_url":self.region_url})
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            self.access_token = token.json()["access_token"]
            headers = {"User-Agent": "TesyCharging", "content-type": "application/json; charset=UTF-8", 'Authorization': 'Bearer {}'.format(self.access_token)}
            url_vehicles = self.region_url + "/api/1/vehicles"
            response = requests.get(url_vehicles, headers=headers) #.json()
            if response.status_code != 200:
                #raise requests.exceptions.ConnectionError("getVehicle: request status code: " + str(response.status_code))
                self.error = "Vehicles Err: " + str(response.status_code)
                self.hasError = True
            else:
                vehicles = response.json()
                self.id = vehicles["response"][pos]["id"]  # Extract car ID - if you have more than one car this need to be modified
                self.state = vehicles["response"][pos]["state"]
    
    # function to get the charging status (Charging, Disconnected, ...)    
    def vehicleChargeState(self):
        if self.state == "online" and not self.hasError:
            headers = {"User-Agent": "TesyCharging", "content-type": "application/json; charset=UTF-8", 'Authorization': 'Bearer {}'.format(self.access_token)}
            url_vehicle = self.region_url + "/" + str(self.id) + "/vehicle_data"
            response = requests.get(url_vehicle, headers=headers)
            if response.status_code != 200:
                #raise requests.exceptions.ConnectionError("vehicleChargeState requests status code: " + str(response.status_code))
                self.error = "ChargeState Err: " + str(response.status_code)
                return None
            else:
                chargeState = response.json()
                self.error = "Charge_State requested"
                return Charge_State(chargeState["response"]["charge_state"])
        else:
            return None     
    
    # function to check if the car is at home
    def vehicleIsHome(self, latitude, longitude):
        if self.state == "online" and not self.hasError:
            headers = {"User-Agent": "TesyCharging", "content-type": "application/json; charset=UTF-8", 'Authorization': 'Bearer {}'.format(self.access_token)}
            url_location_data = self.region_url + "/" + str(self.id) + "/vehicle_data?endpoints=location_data"
            response = requests.get(url_location_data, headers=headers)
            if response.status_code != 200:
                #raise requests.exceptions.ConnectionError("vehicleIsHome: request status code: " + str(response.status_code))
                self.error = "Is Home: Err: " + str(response.status_code)
                return False
            else:
                location = response.json()
                lat: float = location["response"]["drive_state"]["latitude"]
                lon: float  = location["response"]["drive_state"]["longitude"]
                latitude_ = round(latitude, 3)
                longitude_ = round(longitude, 3)
                lat = round(lat, 3)
                lon = round(lon, 3)
                if lat == latitude_ and lon == longitude_:
                    return True
                else:
                    return False
        else:
            return False
            
    # Comands
    # function to set the current
    def setCharge_Amps(self, charging_amps):
        if self.state == "online":
            headers = {"User-Agent": "TesyCharging", "content-type": "application/json; charset=UTF-8", 'Authorization': 'Bearer {}'.format(self.access_token)}
            url_charger_amps = self.region_url + "/" + str(self.id) + "/command/set_charging_amps"
            params = {"charging_amps": charging_amps}
            response = requests.post(url_charger_amps, data=json.dumps(params), headers=headers).json()
            if response.status_code != 200:
                self.error = "Charging Amp Err: " + str(response.status_code)
        else:
            self.error = "Charging Amp Err: " + self.state
    
    # function to start charging
    def startCharging(self):
        if self.state == "online":
            headers = {"User-Agent": "TesyCharging", "content-type": "application/json; charset=UTF-8", 'Authorization': 'Bearer {}'.format(self.access_token)}
            url_charger_amps = self.region_url + "/" + str(self.id) + "/command/charge_start"
            response = requests.post(url_charger_amps, headers=headers).json()
            if response.status_code != 200:
                self.error = "Start Charging Err: " + str(response.status_code)
        else:
            self.error = "Start Charging Err: " + self.state

    # function to stop charging
    def stopCharging(self):
        if self.state == "online":
            headers = {"User-Agent": "TesyCharging", "content-type": "application/json; charset=UTF-8", 'Authorization': 'Bearer {}'.format(self.access_token)}
            url_charger_amps = self.region_url + "/" + str(self.id) + "/command/charge_stop"
            response = requests.post(url_charger_amps, headers=headers).json()
            if response.status_code != 200:
                self.error = "Stop Charging Err: " + str(response.status_code)
        else:
            self.error = "Stop Charging Err: " + self.state

    # function to honk
    def honk(self):
        if self.state == "online":
            headers = {"User-Agent": "TesyCharging", "content-type": "application/json; charset=UTF-8", 'Authorization': 'Bearer {}'.format(self.access_token)}
            url_honk = self.region_url + "/" + str(self.id) + "/command/honk_horn"
            params = {}
            response = requests.post(url_honk, data=json.dumps(params), headers=headers).json() 
            if response.status_code != 200:
                self.error = "Honk Err: " + str(response.status_code)
        else:
            self.error = "Honk Err: " + self.state            

# function to get the charging status (Charging, Disconnected, ...)
class Charge_State:
    def __init__(self, charge_state):
        self.charging_state = charge_state["charging_state"]
        self.charger_actual_current = charge_state["charger_actual_current"]
        self.charge_current_request = charge_state["charge_current_request"]
        self.charger_power = charge_state["charger_power"]
        self.charger_voltage = charge_state["charger_voltage"]
        self.charge_current_request_max = charge_state["charge_current_request_max"]

 # function to read the data from sungrow
class SungrowData:
    def __init__(self, host, locale, chargeState, force):
        file = dir_path + "/sungrow.json"
        if os.path.isfile(file):
            # Load sungrow.json
            with open(file, 'r') as f:
                jsonfile = json.load(f)
            self.lc_battery_soc = jsonfile["battery_soc"]
            self.lc_batteryDischarge = jsonfile["batteryDischarge"]
            self.lc_gridPower = jsonfile["gridPower"] 
            self.lc_socketPower = jsonfile["socketPower"]
            self.lc_chargingPower = jsonfile["chargingPower"] 
            if not force:
                self.lc_forced = jsonfile["forced"] 
            else:
                self.lc_forced = True
        else:
            self.lc_battery_soc = 0
            self.lc_batteryDischarge = 0
            self.lc_gridPower = 5 
            self.lc_socketPower = 2.3
            self.lc_chargingPower = 0
            self.lc_forced = force
        if not(chargeState == None):
            self.lc_socketPower = round(chargeState.charger_voltage * chargeState.charge_current_request_max / 1000, 1)
            self.lc_chargingPower = round(chargeState.charger_voltage * chargeState.charger_actual_current / 1000, 1)
        # read webservice from Inverter    
        sg = SungrowWebsocket(host,locale=locale)
        self.data = sg.get_data()
        self.battery_soc = float(self.data["battery_soc"][2])
        self.batteryChargingPower = float(self.data["config_key_3907"][2])
        self.batteryDischargingPower = float(self.data["config_key_3921"][2])
        self.dcPower = float(self.data["total_dcpower"][2])
        self.activePower = float(self.data["total_active_power"][2])
        self.totalLoadPower = float(self.data["load_total_active_power"][2])
        self.gridPower = round((self.dcPower - self.totalLoadPower - self.batteryChargingPower + self. batteryDischargingPower) * -1, 2)
        self.output = str(self.battery_soc) + "\t" + str(self.batteryChargingPower) + "\t" + str(self.batteryDischargingPower) + "\t" + str(self.dcPower) + "\t" + str(self.totalLoadPower) + "\t" + str(self.activePower) + "\t" + str(self.gridPower) + "\t"
        #check Thresholds
        hasPowerFromGrid = self.gridPower > 0.05 and self.lc_gridPower <= 0.05
        givesPowerToGrid = self.gridPower < -0.05  and self.lc_gridPower >= -0.05
        #self.couldBeCharging = self.lc_chargingPower == 0 and self.gridPower < -(self.lc_socketPower + 0.2) and self.lc_gridPower >= -(self.lc_socketPower + 0.2) and not self.lc_forced
        self.couldBeCharging = False #otherwise too many request to tesla
        takesBatteryPower = self.batteryDischargingPower > 0.05 and self.lc_batteryDischarge <= 0.05
        hasLowBattery = self.battery_soc < 20 and self.lc_battery_soc >= 20
        hasFullBattery = self.battery_soc > 80 and self.lc_battery_soc <= 80
        if givesPowerToGrid or self.lc_chargingPower == 0:
            self.lc_forced = "False"
        self.shouldStopCharging = hasPowerFromGrid and not hasFullBattery and not self.lc_forced and self.lc_chargingPower > 0 
        self.thresholdFlag = ""
        if hasPowerFromGrid:
            self.thresholdFlag = "G" + self.thresholdFlag
        if givesPowerToGrid:
            self.thresholdFlag = "P" + self.thresholdFlag
        if self.couldBeCharging:
            self.thresholdFlag = "C" + self.thresholdFlag
        if takesBatteryPower:
            self.thresholdFlag = "D" + self.thresholdFlag
        if hasLowBattery:
            self.thresholdFlag = "L" + self.thresholdFlag
        if hasFullBattery:
            self.thresholdFlag = "F" + self.thresholdFlag
        if self.shouldStopCharging:
            self.thresholdFlag = "S" + self.thresholdFlag
        
        #update sungrow.json file
        data = {"battery_soc":self.battery_soc,
                "batteryDischarge":self.batteryDischargingPower,
                "gridPower":self.gridPower,
                "socketPower":self.lc_socketPower,
                "chargingPower":self.lc_chargingPower,
                "forced":self.lc_forced}
        # Save sungrow.json to local text file 
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        #prepare APNs messages
        self.sungrowStatus = "PV: " + str(self.dcPower) + "kW; Load: " + str(self.totalLoadPower) + "kW; Grid: " + str(self.gridPower) + "kW"
        self.batteryPower = "battery: " + str(self.battery_soc) + "%"
        if self.batteryChargingPower > 0:
            self.batteryPower = self.batteryPower + "; charging: " + str(self.batteryChargingPower) + "kW"
        elif self.batteryDischargingPower > 0:
            self.batteryPower = self.batteryPower + "; discharging: " + str(self.batteryDischargingPower) + "kW"
        else:
            self.batteryPower = self.batteryPower + "; charging/discharging 0kW"
        if self.lc_chargingPower > 0:
            self.batteryPower = self.batteryPower + "; Tesla is charging"
        self.messageThreshold = ""
        if hasPowerFromGrid:
            self.messageThreshold = "takes power from the grid (" + str(self.gridPower) + "kW)"
        elif givesPowerToGrid:
            self.messageThreshold = "gives power to the grid (" + str(self.gridPower) + "kW)"
        if takesBatteryPower:
            self.messageThreshold = "takes power from battery. " + self.messageThreshold
        self.messageWarning = ""
        if hasLowBattery:
            self.messageWarning = "sungrow battery is below 20% (" + str(self.battery_soc) + "%)"
        elif hasFullBattery:
            self.messageWarning = "sungrow battery is above 80% (" + str(self.battery_soc) + "%)"     
        if self.shouldStopCharging:
            if self.messageThreshold == "":
                self.messageThreshold = "Tesla should stop charing "
            else:
                self.messageWarning = "Tesla should stop charing " + self.messageWarning

    # calculate the possible charging current that no power is taken from the grid
    def calculatePossibleCurrent(self, charge_state):
        if charge_state.charging_state == "Charging":
            if self.battery_soc > 80:
                powerUsedFromTesla = charge_state.charger_actual_current * charge_state.charger_voltage / 1000
                current_max = round(((powerUsedFromTesla - self.gridPower - self.batteryDischargingPower) * 1000 / charge_state.charger_voltage), 0)
                if current_max > charge_state.charge_current_request_max:
                    current_max = charge_state.charge_current_request_max
                    return current_max
                else:
                    return current_max
            else:
                return 0
        else:
            return 0
            
# class to send Apple Push Notifications
class APNs():
    def __init__(self, setting, title, subtitle, body, relevance, sound="coin.aiff"):
        publicKey = dir_path + "/public.cer"
        privateKey = dir_path + "/private.pem"
        if os.path.isfile(publicKey) and os.path.isfile(privateKey):
            curlcommand = 'curl \
              --cert "' + publicKey + '" \
              --cert-type DER \
              --key "' + privateKey + '" \
              --key-type PEM \
              --header "apns-topic: com.david.tesychargingng" \
              --header "apns-push-type: alert" \
              --header "apns-priority: 10" \
              --header "apns-expiration: 0" \
              --data \'{"aps":{"alert":{"title":"' + title + '","subtitle":"' + subtitle + '","body":"' + body + '"}}}\' \
              --http2  https://api.push.apple.com:443/3/device/' + setting.device_token
            result = subprocess.Popen(curlcommand, shell=True, stderr=subprocess.PIPE).stdout
        else:
            curlcommand = 'curl \
              --header "authorization: bearer "' + setting.authentication_token + '" \
              --header "apns-topic: com.david.tesychargingng" \
              --header "apns-push-type: alert" \
              --header "apns-priority: 10" \
              --header "apns-expiration: 0" \
              --data \'{"aps":{"alert":{"title":"' + title + '","subtitle":"' + subtitle + '","body":"' + body + '"}}}\' \
              --http2  https://api.push.apple.com:443/3/device/' + setting.device_token
            result = subprocess.Popen(curlcommand, shell=True, stderr=subprocess.PIPE).stdout    
            print(result)
               

def writeCVS(line):
    file = dir_path + "/" +str(date.today()) + "_sungrow.csv"
    if not os.path.isfile(file):
        # create a file
        title_line = "date            \tthr\tbattery\tchar\tdischar\tdc\tload\tactive\tgrid\ttesla\t"
        with open(file, 'w', encoding='utf-8') as f:
            f.write(f'{title_line}')
    # append a line
    with open(file, 'a', encoding='utf-8') as f:
        f.write(f'\n{line}')
        
def readCVS(line):
    file = dir_path + "/" +str(date.today()) + "_sungrow.csv"
    if not os.path.isfile(file):
        # there is no file
        print("date            \tthr\tbattery\tchar\tdischar\tdc\tload\tactive\tgrid\ttesla\t")
        print(line)
    else:
        # Load sungrow.csv
        f = open(file, 'r')
        # Using for loop
        for fileline in f:
            print("{}".format(fileline.strip()))
        # Closing files
        f.close()    
        

##################
requestToTesla = False
debug = False
host = None
charge_state = None
update_current = False
logging = False
showJSON = False
force = False
locale = "en_US"

teslaAPI = None
messageTesla = ""
messageThreshold = ""
sungrowStatus = ""
batteryPower = ""
messageWarning = ""
thresholdFlag = ""
output = ""
outputdata = {}

# Remove 1st argument from the
# list of command line arguments
argumentList = sys.argv[1:]

# Options

options = "hrds:t:ulof"

# Long options
long_options = ["help", "request", "debug", "sungrow_host=", "tesla_charge_state=", "update_current", "logging", "output_json", "force_charging", "locale="]

try:
    # Parsing argument
    arguments, values = getopt.getopt(argumentList, options, long_options)
    
    # checking each argument
    for currentArgument, currentValue in arguments:
        if currentArgument in ("-h", "--help"):
            print("Displaying Help")
            print("\t-h; --help: show this help")
            print("\t-r; --request: force a request to your Tesla")
            print("\t-d; --debug: send in every run a APNs message, even when no request to Tesla was done.")
            print("\t-s<host>; --sungrow_host<host>: IP or hostname of your sungrow inverter")
            print("\t-t<json>; --tesla_charge_state<json>: provides the tesla charging state in json, provided by the iOS App TesyCharging")
            print("\t-l; --logging: write sungrow data into a log file")
            print("\t-o; --output_json: gives output in json format")
            print("\t-f; --force_charging: don't stop charging even power is given to the grid")
            print("\t--locale=<language>: e.g. en_US")
            sys.exit(2)
        elif currentArgument in ("-r", "--request"):
            requestToTesla = True
        elif currentArgument in ("-d", "--debug"):
            debug = True
        elif currentArgument in ("-s", "--sungrow_host"):
            host = currentValue
        elif currentArgument in ("-t", "--tesla_charge_state"):
            try: 
                data = json.loads(currentValue)
                charge_state = Charge_State(data)
                showJSON = True
            except json.decoder.JSONDecodeError:
                print("{\"error\": \"charge_state is not in json format\"}")
                sys.exit(2)
            except KeyError as keyerr:
                print("{\"error: charge_state: " + str(keyerr) + "\"}")
                sys.exit(2)
                
        elif currentArgument in ("-u", "--update_current"):
            update_current = True
        elif currentArgument in ("-l", "--logging"):
            logging = True
        elif currentArgument in ("-o", "--output_json"):
            showJSON = True
        elif currentArgument in ("-f", "--force_charging"):
            force = True
        elif currentArgument in ("--locale"):
            locale = currentValue 
            
except getopt.error as err:
    # output error, and return with an error code
    print (str(err))
    print("-h; --help: to show help")
    sys.exit(2)

try:
    now = datetime.now() # current date and time
    date_time = now.strftime("%Y-%m-%d %H:%M")
    setting = Settings()
    if (requestToTesla and charge_state == None) or (update_current and charge_state == None):
        teslaAPI = TeslaAPI(0)
        if teslaAPI.vehicleIsHome(setting.latitude, setting.longitude):
            charge_state = teslaAPI.vehicleChargeState()
    if host == None:
        host = setting.inverter_host
    sgData = SungrowData(host, locale, charge_state, force)
    outputdata.update(sgData.data)
    output = output + sgData.output
    messageThreshold = sgData.messageThreshold
    sungrowStatus = sgData.sungrowStatus
    batteryPower = sgData.batteryPower
    messageWarning = sgData.messageWarning
    thresholdFlag = sgData.thresholdFlag
    if update_current or (sgData.couldBeCharging or sgData.shouldStopCharging):
        if charge_state == None and not requestToTesla:
            teslaAPI = TeslaAPI()
            if teslaAPI.vehicleIsHome(setting.latitude, setting.longitude):
                charge_state = teslaAPI.vehicleChargeState()
        current = sgData.calculatePossibleCurrent(charge_state)
        if charge_state.charging_state == "Charging":
            if not teslaAPI.hasError:
                if current <= 0:
                    if not requestToTesla:
                        teslaAPI = TeslaAPI()
                    teslaAPI.stopCharging()
                    messageTesla = "Charging of Tesla is stopped"
                    output = output + "stopped"
                elif current != charge_state.charger_actual_current:
                    if not requestToTesla:
                        teslaAPI = TeslaAPI()
                    teslaAPI.setCharge_Amps(current)
                    messageTesla = "Charging current of Tesla is changed to " + str(current) + "A"
                    output = output + "set " + str(current) + "A"
                else:
                    messageTesla = "Charging of Tesla with " + str(charge_state.charger_power) + "kW"
                    output = output + "charging"
            elif charge_state() .charging_state == "stopped":
                teslaAPI.startCharging()
                messageTesla = "Charging of Tesla is started"
                output = output + "started"
        else:
            output = output + "not charging"
    elif sgData.shouldStopCharging and not charge_state == None:
        if charge_state.charging_state == "Charging":
            if not requestToTesla:
                teslaAPI = TeslaAPI()
            teslaAPI.stopCharging()
            messageTesla = "Charging of Tesla is stopped"
            output = output + "stopped"
        else: 
            output = output + charge_state.charging_state
    elif not teslaAPI == None:
        output = output + teslaAPI.error
    else:
        output = output + "connection was not required"
    if not teslaAPI == None:
        outputdata["error"] = teslaAPI.error
except requests.exceptions.RequestException as err:
    messageTesla = str(err)
    messageWarning = messageWarning + "request error"
    output = output + "Request Error: " +str(err) + "\t"
    outputdata["error"] = "Request Error: " + str(error).replace("\'", "")
except requests.exceptions.HTTPError as errh:
    messageTesla = errh
    messageWarning = messageWarning + "request error"
    output = output + "Http Error: " + errh + "\t"
    outputdata["error"] = "Http Error: " + errh
except requests.exceptions.ConnectionError as errc:
    messageTesla = errc
    messageWarning = messageWarning + "request error"
    output = output + "Error Connecting: " + errc + "\t"
    outputdata["error"] = "Error Connecting: " + errc
except requests.exceptions.Timeout as errt:
    messageTesla = errt
    messageWarning = messageWarning + "request error"
    output = output + "Timeout Error: " + errt + "\t" 
    outputdata["error"] = "Timeout Error: " + errt
except KeyError as keyerr:
    messageTesla = str(keyerr)
    messageWarning = messageWarning + "request error"
    output = output + "Key Error: " + str(keyerr) + "\t"
    outputdata["error"] = "Key Error: " + str(keyerr).replace("\'", "")
except FileNotFoundError as fileError:
    messageTesla = str(fileError)
    messageWarning = messageWarning + "request error"
    output = output + "File not found: " + str(fileError) + "\t"
    outputdata["error"] = "Filenot founde: " + str(fileError).replace("\'", "")
except aiohttp.client_exceptions.ServerDisconnectedError as discon:
    messageTesla = discon
    messageWarning = messageWarning + "request error"
    output = output + "Server Disconnected: " + discon + "\t"
    outputdata["error"] = "Server Disconnected: " + discon
except aiohttp.client_exceptions.ClientConnectorError as clientcon:
    messageTesla = str(clientcon)
    messageWarning = messageWarning + "request error"
    output = output + "Client Disconnected: " + str(clientcon) + "\t"
    outputdata["error"] = "Client Disconnected: " + str(clientcon).replace("\'", "")
if thresholdFlag == "":
    if debug:
        APNs(setting, sungrowStatus, messageTesla, batteryPower + "\\n" + messageWarning, 0.1, "")
    output = thresholdFlag + "\t" + output
else:
    APNs(setting, messageThreshold, sungrowStatus, batteryPower + "\\n" + messageWarning + "\\n" + messageTesla, 1)   
    output = thresholdFlag + " \t" + output
output = date_time + " \t" + output
if logging:
    writeCVS(output)    
if showJSON:
    print(outputdata)
else:
    readCVS(output)
