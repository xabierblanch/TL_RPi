from picamera2 import Picamera2
from libcamera import controls
import datetime
import time
import os
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import RPi.GPIO as GPIO

camera = "RPi01"
num_of_pics = 2

SCOPES = ['https://www.googleapis.com/auth/drive']

now = datetime.datetime.now() 
datestamp = now.strftime("%Y%m%d_%H%M")
file_name = camera + "_" + datestamp
root = "/home/pi"

def select_function(now):
  if now.hour == 11:
    maintenance_mode = True
    print(f"Camera mode: {num_of_pics} will be captured")
    print(f"Maintenance mode: The system will be on for 20 minutes")
  else:
    maintenance_mode = False
    print(f"Camera mode: {num_of_pics} will be captured")
  return maintenance_mode

def select_gdrive_parent():
  if camera == "RPi01":
    parent = ["1rF9qrQ25FYYecWMrbfLKvBb20xoPiNBi"]
  elif camera == "RPi02":
    parent = ["1WeLTkpTcmpuH0uX5-z-WzO1qyr_CBNdx"]
  elif camera == "RPi03":
    parent = ["1da00GwcDrvvu7XpgDuiNdV_Y-D4nuriq"]
  elif camera == "RPi04":
    parent = ["1bHfYitEiyOhq5IFAEBGfoYKwFDMFoE28"]
  return parent

def create_folder():
  output_path = os.path.join(root,"to_gdrive")
  os.makedirs(output_path, exist_ok=True)
  return output_path

def capture_image(output_path, num_of_pics):
  try:
    picam2 = Picamera2()
    picam2.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": 0.1}) #10 meters
    camera_info = picam2.camera_properties
    max_resolution = camera_info["PixelArraySize"]
    config = picam2.create_still_configuration(main={"size": max_resolution})
    picam2.configure(config)
    picam2.options["quality"] = 100
    picam2.start() 
    time.sleep(2)
    
    for i in range(num_of_pics):
      picam2.capture_file(os.path.join(output_path, file_name + "_" + str(i+1) + ".jpg"))
      print(f"Image {file_name}_{i+1}.jpg captured")
      time.sleep(1)
      
  except Exception as e:
    print(f"ERROR: Image not captured: {e}")

def google_upload(creds, output_path, parent):
  try:
    for file in os.listdir(output_path):
      service = build("drive", "v3", credentials=creds)
      file_metadata = {"parents": parent, "name":  file}
      media = MediaFileUpload(os.path.join(output_path,file), mimetype="image/jpg")
      # pylint: disable=maybe-no-member
      file_gdrive = (service.files().create(body=file_metadata, media_body=media, fields="id").execute())
      print(f'File ID: {file_gdrive.get("id")}')
      if file_gdrive.get("id"):
        os.remove(os.path.join(output_path,file))

  except HttpError as error:
    print(f"ERROR: An error occurred: {error}")
    
def shutdown():
  try:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(4, GPIO.OUT)
    GPIO.output(4, GPIO.LOW)
    print("GPIO Shutdown executed successfully")
    
  except Exception as e:
    print(f"ERROR: executing GPIO commands: {e}")
    
  finally:
    GPIO.cleanup()

def upload_logs(creds, parent):
  parent = select_gdrive_parent()
  wittyPi_log = "/home/pi/wittypi/wittyPi.log"
  file_id = upload_logs_core(creds, wittyPi_log, parent)
  schedule_log = "/home/pi/wittypi/schedule.log"
  file_id = upload_logs_core(creds, schedule_log, parent)
    
def upload_logs_core(creds, file_path, parent):
  try:
    service = build("drive", "v3", credentials=creds)
    media = MediaFileUpload(file_path, mimetype='text/plain')
    file_name = os.path.basename(file_path)
    query = f"name='{file_name}' and '{parent[0]}' in parents and trashed=false"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    file_metadata = {'name': os.path.basename(file_path), "addParents": parent}
    
    if items:
      file_id = items[0]['id']
      try:
        updated_file = service.files().update(fileId=file_id, body=file_metadata, media_body=media).execute()
        print(f'Updated File ID: {updated_file.get("id")}')
      except:
        updated_file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        print(f'Uploaded File ID: {updated_file.get("id")}')
        
    else:
      updated_file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
      print(f'Uploaded File ID: {updated_file.get("id")}')

  except HttpError as error:
    print(f"ERROR: An error occurred: {error}")
    
def log_in_google():
  creds = None
  if os.path.exists("/home/pi/token.json"):
    creds = Credentials.from_authorized_user_file("/home/pi/token.json", SCOPES)
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
     flow = InstalledAppFlow.from_client_secrets_file("/home/pi/credentials.json", SCOPES)
     creds = flow.run_local_server(port=0)
     # Save the credentials for the next run
    with open("/home/pi/token.json", "w") as token:
      token.write(creds.to_json())
  return creds  

if __name__ == "__main__":
  time.sleep(10) 
  
  maintenance_mode = select_function(now)
  output_path = create_folder()
  parent = select_gdrive_parent()
  creds = log_in_google()
  capture_image(output_path, num_of_pics)
  google_upload(creds, output_path, parent)
  upload_logs(creds, parent)
  
  time.sleep(10)
      
  if not maintenance_mode:
    shutdown()
