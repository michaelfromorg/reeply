"""
Ad-hoc script for my shenanigans. Right now, just used to generate test data.
"""
import os
import random
import xml.etree.ElementTree as ET

SMS_BACKUP_PATH = r"/mnt/c/Users/mdema/Dropbox/Apps/SMSBackupRestore"
DEBUG = True

def format_size(size: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"

def list_sms_backup_files() -> list[tuple[str, str]]:
    files = os.listdir(SMS_BACKUP_PATH)
    xml_files = [f for f in files if f.endswith(".xml") and f.startswith("sms-")]
    if DEBUG:
        xml_files = [f for f in xml_files if f.startswith("test_")]
    else:
        xml_files = [f for f in xml_files if not f.startswith("test_")]
    return [(f, format_size(os.path.getsize(os.path.join(SMS_BACKUP_PATH, f)))) 
            for f in xml_files]

def generate_test_file(input_file: str, num_messages: int) -> str:
    tree = ET.parse(os.path.join(SMS_BACKUP_PATH, input_file))
    root = tree.getroot()
    
    # Get all SMS messages
    messages = root.findall('sms')
    
    # Select random messages
    selected = random.sample(messages, min(num_messages, len(messages)))
    
    # Create new XML structure
    new_root = ET.Element('smses')
    new_root.set('count', str(len(selected)))
    for msg in selected:
        new_root.append(msg)
    
    # Write to new file
    output_file = 'test_' + input_file
    output_path = os.path.join(SMS_BACKUP_PATH, output_file)
    tree = ET.ElementTree(new_root)
    tree.write(output_path, encoding='UTF-8', xml_declaration=True)
    
    return output_file



def main():
    print("Hello from reeply!")
    print("SMS Backup & Restore path: ", SMS_BACKUP_PATH)
    files = list_sms_backup_files()
    print("Files: ", files)

    # Generate test file
    # input_file = files[0][0]
    # output_file = generate_test_file(input_file, 10)
    # print("Generated test file: ", output_file)





if __name__ == "__main__":
    main()
