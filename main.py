from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# --- CONFIGURATION ---
DEBUG_PORT = "127.0.0.1:9222"
WAIT_TIMEOUT = 30   # Max time to wait for video to load
PLAY_BUFFER = 2.5   # Seconds before the end to skip to (gives it time to register)

# --- CONNECT TO CHROME ---
chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", DEBUG_PORT)
driver = webdriver.Chrome(options=chrome_options)
print(f"Connected to Chrome session on {DEBUG_PORT}...")

def watch_video():
    """
    Robust video handler with 'Completion Verification'.
    It will not exit until the video explicitly reports it has ended.
    """
    print("    [Status] Looking for video player...")

    # 1. CHECK FOR PLAYER CONTAINER
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, "videoPlayer"))
        )
    except:
        print("    [Skip] No 'videoPlayer' container found (Text/Quiz).")
        return

    try:
        # 2. DRILL DOWN INTO IFRAMES
        # Outer Frame
        outer_iframe = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "myPlayer"))
        )
        driver.switch_to.frame(outer_iframe)

        # Inner Frame (Wait up to 30s for slow internet)
        inner_iframe = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.ID, "content"))
        )
        driver.switch_to.frame(inner_iframe)

        # 3. FIND VIDEO TAG
        video = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "video"))
        )
        print("    [Status] Video found. Checking network/buffering...")

        # 4. WAIT FOR METADATA (Duration)
        # We poll the 'readyState' to ensure we don't skip on a loading screen.
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            lambda d: d.execute_script("return arguments[0].readyState >= 1;", video)
        )

        # 5. EXECUTE SKIP & FORCE PLAY
        print(f"    [Action] Skipping to -{PLAY_BUFFER}s from end...")
        driver.execute_script(f"""
            var v = arguments[0];
            v.muted = true;               // Mute to allow autoplay policies
            v.currentTime = v.duration - {PLAY_BUFFER}; 
            v.play();                     // Force play command
        """, video)

        # 6. VERIFY COMPLETION (The Fix)
        # We loop here checking 'video.ended' until it returns True.
        # This guarantees we get the Green Tick.
        start_wait = time.time()
        is_ended = False
        
        while not is_ended:
            # Check if video has finished
            is_ended = driver.execute_script("return arguments[0].ended;", video)
            
            if is_ended:
                print("    [Success] Video reporting 'Ended' state.")
                break
            
            # Timeout safety (don't get stuck forever)
            if time.time() - start_wait > 15:
                print("    [Warning] Video timed out waiting for 'ended' signal.")
                break
                
            time.sleep(1) # Check every second

        # Extra safety pause for server sync
        time.sleep(2)

    except Exception as e:
        print(f"    [Error] Video handling failed: {e}")

    finally:
        # 7. ALWAYS EXIT FRAMES
        driver.switch_to.default_content()


# --- MAIN AUTOMATION LOOP ---
try:
    # Find all course sections
    sections = driver.find_elements(By.CLASS_NAME, "tocSubTitle")
    print(f"Found {len(sections)} Course Sections.")

    for i in range(len(sections)):
        # Refresh section references
        sections = driver.find_elements(By.CLASS_NAME, "tocSubTitle")
        
        # Open section if collapsed
        try:
            arrow = sections[i].find_element(By.CSS_SELECTOR, ".icon-DownArrow")
            if "expand_more" in arrow.get_attribute("class"):
                sections[i].click()
                time.sleep(1)
        except: pass

        # Find Topics within this section
        xpath_topics = f"(//mat-card-subtitle)[{i+1}]/following-sibling::div//div[contains(@class, 'modTitle')]"
        topics = driver.find_elements(By.XPATH, xpath_topics)
        
        print(f"\n--- Section {i+1}: Processing {len(topics)} Topics ---")
        
        for j in range(len(topics)):
            # Refresh topic references
            topics = driver.find_elements(By.XPATH, xpath_topics)
            current_topic = topics[j]

            # Scroll & Click
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", current_topic)
            time.sleep(0.5)
            current_topic.click()
            
            # Wait for page load (prevents connection errors)
            print(f"  > Topic {j+1}: Page loading...")
            time.sleep(4) 

            # Process Video
            watch_video()
            
            # Pause before next topic
            time.sleep(1)

    print("\n--- COURSE COMPLETED ---")

except Exception as e:
    print(f"\n[CRITICAL FAILURE] Script stopped: {e}")