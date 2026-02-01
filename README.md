# LT Project

This project automates video watching using Selenium. It connects to a Chrome browser instance with remote debugging enabled to interact with video players.

## Prerequisites

- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Google Chrome browser

## Installation

1. Clone or download the project.
2. Install dependencies using uv:

   ```bash
   uv sync
   ```

## Running the Project

1. Start Chrome with remote debugging enabled:

   ### For macOS:
   ```bash
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome_dev_test"
   ```

   ### For Windows:
   ```powershell
   & "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\selenium\ChromeProfile"
   ```

   Note: Adjust the paths if Chrome is installed in a different location.

2. Run the main script:

   ```bash
   uv run main.py
   ```

## Configuration

The script uses the following default configurations (defined in `main.py`):
- Debug Port: `127.0.0.1:9222`
- Wait Timeout: 30 seconds
- Play Buffer: 2.5 seconds

Modify these values in `main.py` if needed.

## Usage

Open the page where the course is in the Chrome instance you started. It should look similar to this screenshot:

![Course Page Screenshot](image.png)

The script will automatically detect and handle video playback.