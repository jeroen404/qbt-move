from collections import defaultdict
from time import sleep
from torrent_parser import parse_torrent_file, encode, BDecoder
import os
import tarfile
from datetime import datetime
import argparse
import configparser
import psutil

class QBT_File:
    def __init__(self, torrent_file_path):
        self.torrent_file_path = torrent_file_path
        self.torrent_data = TorrentParser.parse(torrent_file_path)
        self.torrent_info = TorrentParser.get_info(self.torrent_data)
        self.files = TorrentParser.get_files(self.torrent_info)
        self.name = TorrentParser.get_name(self.torrent_info)
    # remove .torrent extension and add .fastresume
    def get_fast_resume_file_path(self):
        return self.torrent_file_path.rsplit('.', 1)[0] + '.fastresume'
    def get_fast_resume_file(self):
        return FastResumeFile(self.get_fast_resume_file_path())
    def has_fast_resume_file(self):
        return os.path.isfile(self.get_fast_resume_file_path())
    def filenames(self):
        return [file['path'] for file in self.files]
    def full_file_paths(self):
        base_dir = self.get_subdir_name() or ''
        return [os.path.join(base_dir, file['path']) for file in self.files]
    def full_file_path(self, filename):
        base_dir = self.get_subdir_name() or ''
        return os.path.join(base_dir, filename)
    def get_content_files(self):
        return [ContentFile(self.full_file_path(file['path']), file['size']) for file in self.files]
    def is_in_subdir(self):
        return len(self.filenames()) > 1
    def get_subdir_name(self):
        if self.is_in_subdir():
            return self.name
        return None
    def get_name(self):
        if self.is_in_subdir():
            return self.get_subdir_name()
        else:
            return self.name
    def print_info(self,log_level='debug'):
        Logger.log(log_level, f'Torrent File: {self.torrent_file_path}')
        Logger.log(log_level, f'Fast Resume File: {self.get_fast_resume_file_path()}')
        if self.is_in_subdir():
            Logger.log(log_level, f'Contained in Subdirectory: {self.get_subdir_name()}')
        else:
            Logger.log(log_level, 'Not contained in a subdirectory.')
        Logger.log(log_level, 'Contained Files:')
        for f in self.files:
            Logger.log(log_level, f' - {f["path"]} (Size: {f["size"]} bytes)')
        Logger.log(log_level, '---')

class FastResumeFile:
    save_path_keywords = [
        'qBt-savePath',  # represents the path where the torrent is to be saved if Automatic Torrent Management (ATM) is disabled
                         # If ATM is disabled (manual mode), this is where the torrent files belong.
                         # If ATM is enabled (default, managed by Category), this key is typically omitted from the file. 
                         # The client defaults to using the location set in the torrent's assigned category

        'qBt-downloadPath', # It stores the separate, temporary path where incomplete files are downloaded if Automatic Torrent Management (ATM) is disabled.

        'save_path',     # This is the original key used by the underlying BitTorrent engine, libtorrent
                         # Always Present: This key must be present in the .fastresume file for libtorrent to load the torrent data

        ]
    def __init__(self, fast_resume_file_path):
        self.fast_resume_file_path = fast_resume_file_path
        # Placeholder for actual fast resume file parsing
    def replace_save_paths(self, new_path):
        try:
            with open(self.fast_resume_file_path, 'rb') as file:
                bencoded_data = file.read()
                try:
                    decoder = BDecoder(data=bencoded_data)
                    # Tell the decoder that 'info-hash' should be treated as a hash field.
                    # The arguments (20, False) mean:
                    # - 20: The block length (20 bytes for a SHA-1 info hash)
                    # - False: Don't force the output into a list of strings
                    decoder.hash_field('info-hash', 20, False)
                    decoder.hash_field('peers', 6, False)  # 'peers' field is a binary string
                    data = decoder.decode()
                except Exception as e:
                    Logger.log("error", f"Error decoding fast resume file {self.fast_resume_file_path}: {e}")
                    return
            modified = False
            for key in FastResumeFile.save_path_keywords:
                if key in data:
                    old_path = data[key]
                    # skip if old_path is already the new_path
                    if os.path.abspath(old_path) == os.path.abspath(new_path):
                        Logger.log("debug", f"'{key}' path in {self.fast_resume_file_path} is already '{new_path}'. No change needed.")
                        continue
                    # skip if original is empty string
                    if old_path == '':
                        Logger.log("debug", f"'{key}' path in {self.fast_resume_file_path} is empty. Skipping replacement.")
                        continue
                    data[key] = new_path
                    Logger.log("debug", f"Replaced '{key}' path from '{old_path}' to '{new_path}' in {self.fast_resume_file_path}.")
                    modified = True
            if modified:
                new_bencoded_data = encode(data, hash_fields=['info-hash', 'peers'])
                with open(self.fast_resume_file_path, 'wb') as file:
                    file.write(new_bencoded_data)
                Logger.log("info", f"Updated save paths in fast resume file {self.fast_resume_file_path}.")
            else:
                Logger.log("warning", f"No save path keys found to update in fast resume file {self.fast_resume_file_path}.")
        except Exception as e:
            Logger.log("error", f"Error processing fast resume file {self.fast_resume_file_path}: {e}")

class ContentFile:
    def __init__(self, path, size):
        self.path = path
        self.size = size
    # check if other file matches by path and size
    # my path can be longer (subdir) but must end with other's path
    def matches(self, other):
        if self.size != other.size:
            return False
        if self.path.endswith(other.path):
            return True
        return False
        
class ContentFolder:
    def __init__(self, path):
        self.path = path
        self.files = []
    def add_file(self, content_file):
        self.files.append(content_file)
    def scan_files(self):
        for root, dirs, files in os.walk(self.path):
            for file in files:
                full_path = os.path.join(root, file)
                size = os.path.getsize(full_path)
                relative_path = os.path.relpath(full_path, self.path)
                self.files.append(ContentFile(relative_path, size))
    # def has_file(self, content_file: ContentFile):
    #     for f in self.files:
    #         if f.matches(content_file):
    #             return True
    #     return False
    def find_matching_base_path(self, content_files: list[ContentFile]):
        content_file_path_matches = defaultdict(list) # key: content_file.path, value: list of matching base path of my_file.path
        for my_file in self.files:
            for cf in content_files:
                if my_file.matches(cf):
                    my_base_path = my_file.path[:-len(cf.path)]
                    content_file_path_matches[cf.path].append(my_base_path)
        # find common base path for all content files
        common_base_paths = None
        for cf in content_files:
            if cf.path not in content_file_path_matches:
                Logger.log("trace", f'No matches found for content file {cf.path} (size: {cf.size} bytes) in content folder {self.path}.')
                return None
            if common_base_paths is None:
                common_base_paths = set(content_file_path_matches[cf.path])
            else:
                common_base_paths = common_base_paths.intersection(set(content_file_path_matches[cf.path]))
            if not common_base_paths:
                return None
        # return one of the common base paths
        return common_base_paths.pop() 

    def print_files(self,log_level='debug'):
        for file in self.files:
            Logger.log(log_level, f' - {file.path} (Size: {file.size} bytes)')

class BT_Backup_Directory:
    def __init__(self, path):
        self.path = path
        self.torrents = []
        self.load_torrents()
    def load_torrents(self):
        try:
            for filename in os.listdir(self.path):
                if filename.endswith('.torrent'):
                    torrent_file_path = os.path.join(self.path, filename)
                    qbt_file = QBT_File(torrent_file_path)
                    self.torrents.append(qbt_file)
        except Exception as e:
            print(f"Error loading torrents from {self.path}: {e}")
    def get_torrents(self):
        return self.torrents
    def iter_torrents_with_fast_resume(self):
        for torrent in self.torrents:
            if torrent.has_fast_resume_file():
                yield torrent
    def backup(self, backup_dir_path):
        time_now = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            os.makedirs(backup_dir_path, exist_ok=True)
        except Exception as e:
            Logger.log("error", f"Error creating backup directory {backup_dir_path}: {e}")
            exit(1)
        backup_path = os.path.join(backup_dir_path, os.path.basename(self.path) + time_now +'.tar.gz')
        try:
            with tarfile.open(backup_path, "w:gz") as tar:
                arcname = os.path.basename(self.path)
                tar.add(self.path, arcname=arcname)
        except Exception as e:
            Logger.log("error", f"Error creating backup at {backup_path}: {e}")
            exit(1)

class QBTorrent:
    @staticmethod
    def is_running(process_name):
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] == process_name:
                return True
        return False
    @staticmethod
    def stop(command):
        Logger.log("debug", f"Stopping QBittorrent with command: {command}")
        os.system(command)
    @staticmethod
    def start(command):
        Logger.log("debug", f"Starting QBittorrent with command: {command}")
        os.system(command)

class TorrentParser:
    @staticmethod
    def parse(file_path):
        return parse_torrent_file(file_path)
    @staticmethod
    def get_info(torrent_data):
        return torrent_data.get('info', {})
    @staticmethod
    def get_files(torrent_info):
        if 'files' in torrent_info:
            return [{ 'path': os.path.sep.join(file_dict['path']), 'size': file_dict['length'] } for file_dict in torrent_info['files']]
        elif 'name' in torrent_info:
            return [{ 'path': torrent_info['name'], 'size': torrent_info.get('length', 0) }]
        return []
    @staticmethod
    def get_name(torrent_info):
        return torrent_info.get('name', '')

class Logger:
    loglevels = {
    "trace": 0,
    "debug": 1,
    "info": 2,
    "warning": 3,
    "error": 4,
    }
    loglevel = loglevels["debug"]
    @staticmethod
    def log(severity: str, message: str):
        if severity not in Logger.loglevels:
            severity = "info"
        if Logger.loglevels[severity] >= Logger.loglevel:
            print(f"[{severity.upper()}] {message}")


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description='Update QBittorrent fast resume files based on content folders.')
    parser.add_argument('--config', type=str, default='config.ini', help='Path to configuration file')
    parser.add_argument('--log-level', type=str, default='info',help='Logging level (default: info)')
    parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without making changes')
    parser.add_argument('--delete-orphans', action='store_true', help='Delete orphaned torrents')
    args = parser.parse_args()

    if args.log_level in Logger.loglevels:
        Logger.loglevel = Logger.loglevels[args.log_level]
    else:
        print(f"Invalid log level {args.log_level}, Valid levels are: {', '.join(Logger.loglevels.keys())}")
        exit(1)

    try:
        config = configparser.ConfigParser()
        config.read(args.config)
        bt_backup_dir_path = config.get('settings', 'bt_backup_dir_path')
        content_dir_paths = [path.strip() for path in config.get('settings', 'content_dir_paths').split(',')]
        backup_bt_backup = config.getboolean('settings', 'backup_bt_backup', fallback=True)
        backup_bt_backup_path = config.get('settings', 'backup_bt_backup_path', fallback=None)
        if backup_bt_backup and not backup_bt_backup_path:
            raise Exception("Backup of BT backup directory is enabled but no backup path is specified.")
        check_qbittorrent_running = config.getboolean('settings', 'check_qbittorrent_running', fallback=True)
        qbittorrent_process_name = config.get('settings', 'qbittorrent_process_name', fallback='qbittorrent-nox')
        if check_qbittorrent_running and not qbittorrent_process_name:
            raise Exception("Check for running QBittorrent is enabled but no process name is specified.")
        qbittorrent_stop_if_running = config.getboolean('settings', 'qbittorrent_stop_if_running', fallback=False)
        qbittorrent_restart = config.getboolean('settings', 'qbittorrent_restart_after', fallback=False)
        qbittorrent_start_command = config.get('settings', 'qbittorrent_start_command', fallback=None)
        qbittorrent_stop_command = config.get('settings', 'qbittorrent_stop_command', fallback=None)
        qbittorrent_wait_after_stop = config.getint('settings', 'qbittorrent_wait_after_stop', fallback=10)
        if qbittorrent_restart and not qbittorrent_start_command:
            raise Exception("Restart of QBittorrent is enabled but no restart command is specified.")
        Logger.log("info", f"Configuration loaded from {args.config}.")
    except Exception as e:
        print(f"Error reading configuration file {args.config}: {e}")
        exit(1)

    if check_qbittorrent_running and not args.dry_run:
        if QBTorrent.is_running(qbittorrent_process_name):
            if qbittorrent_stop_if_running:
                Logger.log("info", f"QBittorrent process '{qbittorrent_process_name}' is running. Stopping it now.")
                QBTorrent.stop(qbittorrent_stop_command)
                sleep(qbittorrent_wait_after_stop)  # wait for process to stop
                if QBTorrent.is_running(qbittorrent_process_name):
                    Logger.log("error", f"Failed to stop QBittorrent process '{qbittorrent_process_name}'. Please stop it manually and try again.")
                    exit(1)
            else:
                Logger.log("error", f"QBittorrent process '{qbittorrent_process_name}' is running. Please stop it before running this script.")
                exit(1)

    bt_backup_dir = BT_Backup_Directory(bt_backup_dir_path)
    if backup_bt_backup and not args.dry_run:
        Logger.log("info", f"Backing up BT backup directory {bt_backup_dir_path} to {backup_bt_backup_path}")
        bt_backup_dir.backup(backup_bt_backup_path)
    content_dir_matches = {}
    torrent_matches = {}
    for content_dir_path in content_dir_paths:        
        content_folder = ContentFolder(content_dir_path)
        content_folder.scan_files()
        #content_folder.print_files()
        for torrent in bt_backup_dir.iter_torrents_with_fast_resume():
            torrent.print_info(log_level='trace')
            matching_base_path = content_folder.find_matching_base_path(torrent.get_content_files())
            if matching_base_path is None:
                Logger.log("debug", f'No matching base path found in content folder {content_dir_path} for torrent {torrent.get_name()}.')
                continue
            full_matching_base_path = os.path.join(content_dir_path, matching_base_path) 
            content_dir_matches[torrent] = full_matching_base_path
            torrent_matches[torrent] = True
            Logger.log("info", f'Found matching base path in content folder {content_dir_path} for torrent {torrent.get_name()}: {full_matching_base_path}')
    # report torrents with no matches
    for torrent in bt_backup_dir.iter_torrents_with_fast_resume():
        if torrent not in torrent_matches:
            Logger.log("warning", f'No matching content folder found for torrent {torrent.get_name()} (file {torrent.torrent_file_path}).')
            if args.delete_orphans and not args.dry_run:
                fast_resume_file = torrent.get_fast_resume_file()
                try:
                    os.remove(torrent.torrent_file_path)
                    Logger.log("info", f'Deleted orphaned torrent file {torrent.torrent_file_path}.')
                except Exception as e:
                    Logger.log("error", f'Error deleting orphaned torrent file {torrent.torrent_file_path}: {e}')
                try:
                    os.remove(fast_resume_file.fast_resume_file_path)
                    Logger.log("info", f'Deleted orphaned fast resume file {fast_resume_file.fast_resume_file_path}.')
                except Exception as e:
                    Logger.log("error", f'Error deleting orphaned fast resume file {fast_resume_file.fast_resume_file_path}: {e}')
    if not args.dry_run:
        for torrent, content_dir_path in content_dir_matches.items():
            fast_resume_file = torrent.get_fast_resume_file()
            new_save_path = os.path.abspath(content_dir_path)
            Logger.log("debug", f'Updating fast resume file {fast_resume_file.fast_resume_file_path} to new save path {new_save_path} (if needed).')
            fast_resume_file.replace_save_paths(new_save_path)

    if qbittorrent_restart and not args.dry_run:
        Logger.log("info", f"Restarting QBittorrent with command: {qbittorrent_start_command}")
        QBTorrent.start(qbittorrent_start_command)
    

