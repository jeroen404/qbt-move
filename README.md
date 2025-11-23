# QBT Move - QBittorrent Fast Resume Updater

A Python utility to update QBittorrent fast resume files when torrent content has been moved to different locations. This tool scans content directories, matches files with torrents, and updates the save paths in `.fastresume` files accordingly.

You can use it when you migrate to a new computer or when you want to move files outside of QBittorrent.

## Features

- **Automatic Path Detection**: Scans content directories to find torrent files, even in subdirectories
- **Smart Matching**: Matches torrent files by both path and size to ensure accuracy
- **Backup Support**: Optionally backs up the BT_Backup directory before making changes
- **QBittorrent Process Management**: Can check if QBittorrent is running and optionally stop/restart it
- **Dry Run Mode**: Test the tool without making any actual changes
- **Orphan Cleanup**: Optionally delete torrents that have no matching content files
- **Configurable Logging**: Multiple log levels (trace, debug, info, warning, error)

## Requirements

- Python 3.6+
- Required packages:
  - `torrent-parser`
  - `psutil`

Install dependencies:
```bash
pip install -r requirements.txt
```
or 

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python qbt-move.py ...
```

## Configuration

Create a `config.ini` file with the following settings:

```ini
[settings]
# Path to QBittorrent's BT_Backup directory (contains .torrent and .fastresume files)
bt_backup_dir_path = /path/to/.local/share/qBittorrent/BT_Backup

# Comma-separated list of content directories to scan
content_dir_paths = /path/to/content/dir1, /path/to/content/dir2

# Backup settings
backup_bt_backup = true
backup_bt_backup_path = /path/to/backups

# QBittorrent process management
check_qbittorrent_running = true
qbittorrent_process_name = qbittorrent-nox
qbittorrent_stop_if_running = false
qbittorrent_restart_after = false
qbittorrent_stop_command = systemctl stop qbittorrent-nox
qbittorrent_start_command = systemctl start qbittorrent-nox
qbittorrent_wait_after_stop = 10
```

### Configuration Options

- **bt_backup_dir_path**: Directory where QBittorrent stores `.torrent` and `.fastresume` files
  - Linux: `~/.local/share/qBittorrent/BT_Backup`
  - Windows: `%APPDATA%\qBittorrent\BT_Backup`

- **content_dir_paths**: Directories containing your actual torrent content files (comma-separated)

- **backup_bt_backup**: Whether to create a backup before making changes (recommended: `true`)

- **backup_bt_backup_path**: Where to store backups

- **check_qbittorrent_running**: Check if QBittorrent is running before proceeding

- **qbittorrent_process_name**: Process name to check (e.g., `qbittorrent-nox`, `qbittorrent`)

- **qbittorrent_stop_if_running**: Automatically stop QBittorrent if running

- **qbittorrent_restart_after**: Restart QBittorrent after updating files

- **qbittorrent_stop_command**: Command to stop QBittorrent

- **qbittorrent_start_command**: Command to start QBittorrent

- **qbittorrent_wait_after_stop**: Seconds to wait after stopping QBittorrent

## Usage

### Basic Usage

```bash
python qbt-move.py
```

### Command Line Arguments

```bash
python qbt-move.py [OPTIONS]
```

**Options:**

- `--config PATH`: Path to configuration file (default: `config.ini`)
- `--log-level LEVEL`: Logging level - trace, debug, info, warning, error (default: `info`)
- `--dry-run`: Perform a dry run without making changes
- `--delete-orphans`: Delete torrents that have no matching content files

### Examples

**Dry run that does not alter files**
```bash
python qbt-move.py --dry-run
```

**Delete orphaned torrents:**
```bash
python qbt-move.py --delete-orphans
```

**Use custom config file:**
```bash
python qbt-move.py --config /path/to/custom-config.ini
```

## How It Works

1. **Load Configuration**: Reads settings from `config.ini`

2. **Process Management**: Checks if QBittorrent is running and stops it if configured

3. **Backup**: Creates a timestamped backup of the BT_Backup directory (if enabled)

4. **Scan Content**: Walks through all content directories and catalogs files with their sizes

5. **Match Torrents**: For each torrent with a fast resume file:
   - Extracts the list of files from the `.torrent` file
   - Searches content directories for matching files (by path suffix and size)
   - Finds the common base path where all torrent files exist
   - Handles both single-file and multi-file torrents
   - Handles files in subdirectories of content folders

6. **Update Paths**: Updates the save paths in `.fastresume` files:
   - `qBt-savePath`: Save path for manual torrents
   - `qBt-downloadPath`: Download path for incomplete files
   - `save_path`: libtorrent save path

7. **Cleanup**: Optionally deletes orphaned torrent files (if `--delete-orphans` is used)

8. **Restart**: Restarts QBittorrent if configured

## File Matching Logic

The tool uses this matching logic to handle various scenarios:

- **Size Matching**: Files must match exactly by size
- **Path Matching**: Uses suffix matching to handle subdirectories
- **Multi-file Torrents**: All files in a torrent must be found together
- **Base Path Detection**: Finds the shallowest common directory containing all files
- **Subdirectory Support**: Handles content files in subdirectories of the configured content paths

### Example Scenarios

**Single-file torrent in subdirectory:**
```
Content Dir: /mnt/data/movies
Actual file: /mnt/data/movies/Action/movie.mkv
Torrent expects: movie.mkv
Result: save_path set to /mnt/data/movies/Action
```

**Multi-file torrent:**
```
Content Dir: /mnt/data/movies
Actual files: /mnt/data/movies/MovieName/movie.mkv
              /mnt/data/movies/MovieName/subs.srt
Torrent expects: MovieName/movie.mkv
                 MovieName/subs.srt
Result: save_path set to /mnt/data/movies
```

## Safety Features

- **Dry Run Mode**: Test without making changes
- **Automatic Backup**: Creates backups before modifications
- **Path Validation**: Only updates if all torrent files are found
- **Size Verification**: Matches files by size to prevent errors
- **Process Detection**: Prevents running while QBittorrent is active (optional)

## Logging Levels

- **trace**: Very verbose, shows all file comparisons
- **debug**: Detailed information about operations
- **info**: General information about matches and updates
- **warning**: Warnings about unmatched torrents
- **error**: Errors during processing

## Troubleshooting

**Torrent not matched:**
- Check file sizes match exactly
- Verify file paths with `--log-level trace`
- Ensure content directory paths are correct
- Check for permission issues

**QBittorrent not detecting changes:**
- Ensure QBittorrent was stopped before running the tool
- Check that backup was created successfully
- Verify fast resume files were actually modified

**Permission errors:**
- Ensure you have read/write access to BT_Backup directory
- Ensure you have read access to content directories

## License

see LICENSE

## Warning

Always backup your QBittorrent configuration before using this tool! While the tool includes backup functionality, it's recommended to create manual backups as well.


This readme was create by a Claude agent because I am lazy.