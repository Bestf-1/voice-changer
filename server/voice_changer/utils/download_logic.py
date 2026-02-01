import os
import shutil
import json
import requests
import zipfile
from urllib.parse import urlparse
from const import UPLOAD_DIR
from ModelSlotManager import ModelSlotManager

# Ensure UPLOAD_DIR exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_manager():
    # Gets the singleton instance of the manager
    # Ensure "logs" matches your actual model directory if different
    return ModelSlotManager.get_instance("logs") 

def handle_zip_extraction(zip_filename, slot_index):
    """
    Extracts a zip file, finds .pth and .index files recursively, 
    and registers them to the specified slot.
    """
    manager = get_manager()
    extract_path = os.path.join(UPLOAD_DIR, "temp_extract")
    zip_path = os.path.join(UPLOAD_DIR, zip_filename)
    
    logs = []

    try:
        # 1. Clean and Create Temp Directory
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
        os.makedirs(extract_path)
        
        # 2. Extract Zip
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        # 3. Walk through files
        found_model = False
        for root, dirs, files in os.walk(extract_path):
            for file in files:
                # We must move files to UPLOAD_DIR because ModelSlotManager looks for them there
                
                # --- Handle .pth (Model) ---
                # Exclude G_ and D_ pretrain files if present
                if file.endswith(".pth") and not file.startswith("G_") and not file.startswith("D_"):
                    source = os.path.join(root, file)
                    dest = os.path.join(UPLOAD_DIR, file)
                    shutil.move(source, dest)
                    
                    # Register with Manager
                    params = json.dumps({
                        "file": file,
                        "slot": int(slot_index),
                        "name": "model_file" # Matches your ModelSlots attribute
                    })
                    manager.store_model_assets(params)
                    logs.append(f"Found model: {file} -> Assigned to Slot {slot_index}")
                    found_model = True

                # --- Handle .index (Index) ---
                elif file.endswith(".index"):
                    source = os.path.join(root, file)
                    dest = os.path.join(UPLOAD_DIR, file)
                    shutil.move(source, dest)
                    
                    # Register with Manager
                    params = json.dumps({
                        "file": file,
                        "slot": int(slot_index),
                        "name": "index_file" # Matches your ModelSlots attribute
                    })
                    manager.store_model_assets(params)
                    logs.append(f"Found index: {file} -> Assigned to Slot {slot_index}")

        if not found_model:
            logs.append("Warning: Zip extracted but no valid .pth model file was found.")

    except Exception as e:
        logs.append(f"Error during extraction: {str(e)}")
    finally:
        # Cleanup
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
        if os.path.exists(zip_path):
            os.remove(zip_path)

    return logs

def run_download_script(url, slot_index):
    """
    Main entry point called by the API.
    """
    try:
        # 1. Determine Filename
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path) or "download.zip"
        if "." not in filename: 
            filename += ".zip"
            
        temp_path = os.path.join(UPLOAD_DIR, filename)
        
        # 2. Download Stream
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(temp_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        # 3. Process based on extension
        if filename.endswith(".zip"):
            return handle_zip_extraction(filename, slot_index)
            
        elif filename.endswith(".pth"):
            params = json.dumps({
                "file": filename,
                "slot": int(slot_index),
                "name": "model_file"
            })
            get_manager().store_model_assets(params)
            return [f"Downloaded {filename} to Slot {slot_index}"]
            
        elif filename.endswith(".index"):
            params = json.dumps({
                "file": filename,
                "slot": int(slot_index),
                "name": "index_file"
            })
            get_manager().store_model_assets(params)
            return [f"Downloaded {filename} to Slot {slot_index}"]
            
        else:
            return ["Error: Unknown file type. Use .zip, .pth, or .index"]

    except Exception as e:
        return [f"Download Error: {str(e)}"]