# LT Course Video Automation Script


This Python script automates the completion of online course videos using Selenium WebDriver. It connects to an existing Chrome browser instance with remote debugging enabled and intelligently navigates through course sections to watch videos, marking them as completed by skipping to near the end of each video.

## Table of Contents

- [What the Script Does](#what-the-script-does)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running the Script](#running-the-script)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Disclaimer and License](#disclaimer-and-license)

## What the Script Does

The script performs the following automated tasks:

1. **Connects to Chrome**: Attaches to a Chrome browser running on `127.0.0.1:9222` with remote debugging enabled.

2. **Course Navigation**:
   - Scans for course sections on the page.
   - Skips sections that are already fully completed (indicated by a green tick icon).
   - Skips "Final Assessment" sections to avoid quizzes.

3. **Video Processing**:
   - For each section, expands it and finds all video topics.
   - Checks if individual topics are already completed (green tick) and skips them.
   - Clicks on unwatched videos and handles playback.

4. **Smart Video Watching**:
   - Locates video elements within nested iframes.
   - Uses a "double jump" technique: jumps to 5 seconds before the end, then to 0.5 seconds before the end.
   - Sets playback rate to 2x speed and mutes the video for faster completion.
   - Verifies completion and handles timeouts or errors gracefully.

5. **Error Handling**:
   - Robust handling of network drops, frame loading issues, and stale elements.
   - Retries section expansion if topics don't load initially.
   - **Background Throttling Defense**: Actively detects stuck video downloads (caused by browser background throttling) and resets the connection. If a video refuses to load after 30 seconds, it forces a completion signal to keep the script moving.

6. **Two-Pass System**:
   - **Main Pass**: Processes all sections and videos.
   - **Verification Pass**: Runs again to catch any missed videos due to timing issues.

7. **Cleanup**: Automatically closes the Chrome browser after successful completion.

## Prerequisites

- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Google Chrome browser

## Installation

1. Clone or download the project.
2. Create a virtual environment using `uv`:

   ```bash
   uv venv
   ```

3. Activate the virtual environment (common paths):

   - Windows (PowerShell):

     ```powershell
     .venv\Scripts\Activate.ps1
     ```

   - Windows (Command Prompt):

     ```cmd
     .venv\Scripts\activate.bat
     ```

   - macOS / Linux (bash/zsh):

     ```bash
     source .venv/bin/activate
     ```

4. Install dependencies using `uv`:

   ```bash
   uv sync
   ```

## Running the Script

1. **Start Chrome with Remote Debugging**:

   ### For Windows:
   ```powershell
   & "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\selenium\ChromeProfile" --disable-background-timer-throttling --disable-backgrounding-occluded-windows --disable-renderer-backgrounding --disable-features=CalculateNativeWinOcclusion
   ```

   ### For macOS:
   ```bash
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome_dev_test" --disable-background-timer-throttling --disable-backgrounding-occluded-windows --disable-renderer-backgrounding --disable-features=CalculateNativeWinOcclusion
   ```

   Note: **These flags are crucial** to allow the script to run in the background without the browser throttling the video player. Adjust paths if Chrome is installed elsewhere. The `--user-data-dir` creates a separate profile to avoid interfering with your main browser.

2. **Navigate to the Course Page**:
   - In the opened Chrome window, go to your online course page.
   - Ensure you're logged in and on the course content page.
    ![LT Course Video Automation Script](image.png)

3. **Run the Script**:
   ```bash
   uv run main.py
   ```

The script will automatically detect the course structure and begin processing videos. It will print progress updates to the console.

## Configuration

Default settings in `main.py`:
- **Debug Port**: `127.0.0.1:9222` (Chrome connection)
- **Wait Timeout**: 30 seconds (max wait for video loading)
- **Play Buffer**: 5 seconds (seconds before video end to skip to for first jump)
- **Playback Rate**: 2.0 (video speed multiplier)
- **Click Sleep**: 0.5 seconds (delay after clicking elements)
- **Load Sleep**: 4 seconds (delay after clicking topic to load video)
- **Section Sleep**: 2 seconds (delay after expanding section)
- **Retry Sleep**: 2 seconds (delay before retrying section operations)
- **Verification Pass**: True (whether to run verification round)
- **Verification Delay**: 2 seconds (delay before starting verification)
- **Final Assessment Pattern**: "Final Assessment" (string pattern to skip sections)

Modify these in `main.py` if needed for different environments or behaviors.

## Troubleshooting

- **Video Stuck/Not Loading in Background**: Ensure you launched Chrome with the `--disable-background-timer-throttling` and `--disable-backgrounding-occluded-windows` flags. Modern browsers pause videos in background tabs to save battery.
- **Connection Issues**: Ensure Chrome is running with the correct port and user-data-dir.
- **Video Not Found**: The script skips non-video content (text, quizzes) automatically.
- **Stale Elements**: The script refreshes element references frequently to handle dynamic pages.
- **Network Errors**: Built-in retries and timeouts handle intermittent connectivity issues.

## Disclaimer and License

**Educational Experiment Only**: This script is provided solely for educational purposes as an experiment in automation scripting. It is not intended for production use or to bypass legitimate learning processes.

**Use at Your Own Risk**: By using this script, you acknowledge and accept that you do so entirely at your own risk. I am not responsible for any consequences, including but not limited to:
- Account suspensions or bans from course platforms
- Loss of access to educational materials
- Any other damages or losses incurred

**Honest Learning Encouraged**: This tool is designed to assist with repetitive tasks, but I strongly recommend watching videos honestly and engaging with course content properly for genuine learning. Automation should not replace active participation in education.

**No Warranty**: This software is provided "as is" without any warranties, express or implied. There is no guarantee of functionality, safety, or compliance with any platform's terms of service.

**License**: This project is released under the MIT License. See the [LICENSE](LICENSE) file for details.

**Final Note**: Respect platform terms of service and use this tool ethically. If you're caught automating course completion, it could result in serious consequences for your account or institution.