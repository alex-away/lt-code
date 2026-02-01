from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchFrameException, StaleElementReferenceException
import time

# --- CONFIGURATION ---
DEBUG_PORT = "127.0.0.1:9222"
WAIT_TIMEOUT = 30   # Max time to wait for video to load
PLAY_BUFFER = 5   # Seconds before the end to skip to
PLAYBACK_RATE = 2.0  # Video playback speed multiplier
CLICK_SLEEP = 0.5    # Sleep after clicking elements
LOAD_SLEEP = 4       # Sleep after clicking topic to load
SECTION_SLEEP = 2    # Sleep after expanding section
RETRY_SLEEP = 2      # Sleep before retrying section open
VERIFICATION_PASS = True  # Whether to run verification round
VERIFICATION_DELAY = 2    # Delay before starting verification
FINAL_ASSESSMENT_PATTERN = "Final Assessment"  # Pattern to skip sections

# --- CONNECT TO CHROME ---
chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", DEBUG_PORT)
driver = webdriver.Chrome(options=chrome_options)
print(f"Connected to Chrome session on {DEBUG_PORT}...")

def watch_video():
    """
    Robust video handler that handles Network Drops & Frame Errors gracefully.
    Returns True if successful, False if it failed.
    """
    print("    [Status] Looking for video player...")

    # Check for player container
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, "videoPlayer"))
        )
    except TimeoutException:
        print("    [Skip] No 'videoPlayer' found (Text/Quiz or Network Lag).")
        return False

    try:
        # Drill down into iframes
        outer_iframe = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "myPlayer"))
        )
        driver.switch_to.frame(outer_iframe)

        inner_iframe = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.ID, "content"))
        )
        driver.switch_to.frame(inner_iframe)

        # Find video tag
        video = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "video"))
        )
        print("    [Status] Video found. Checking state...")

        # Wait for metadata
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            lambda d: d.execute_script("return arguments[0].readyState >= 1;", video)
        )

        # Execute double jump
        print(f"    [Action] Executing Double Jump...")
        driver.execute_script(f"""
            var v = arguments[0];
            v.muted = true;
            v.playbackRate = {PLAYBACK_RATE};         
            v.currentTime = Math.max(0, v.duration - {PLAY_BUFFER}); 
            v.play();
        """, video)
        
        time.sleep(SECTION_SLEEP) 
        
        driver.execute_script(f"""
            var v = arguments[0];
            v.currentTime = Math.max(0, v.duration - 0.5);
            v.play();
        """, video)

        # Verify completion
        start_wait = time.time()
        while True:
            try:
                is_ended = driver.execute_script("""
                    var v = arguments[0];
                    return v.ended || (v.currentTime >= v.duration - 0.1);
                """, video)
                
                if is_ended:
                    print("    [Success] Video finished.")
                    break
            except:
                break

            if time.time() - start_wait > 15:
                print("    [Warning] Timeout. Forcing 'ended' event...")
                driver.execute_script("arguments[0].dispatchEvent(new Event('ended'));", video)
                break
                
            time.sleep(1)

        time.sleep(2) 
        return True

    except Exception as e:
        print(f"    [Error] Video error: {str(e)[:50]}")
        return False

    finally:
        try:
            driver.switch_to.default_content()
        except: pass

def run_course_loop(is_verification_round=False):
    """
    Main Logic wrapped in a function so we can run it twice (Main Pass + Verification Pass).
    Returns the number of videos attempted to watch.
    """
    pass_name = "VERIFICATION PASS" if is_verification_round else "MAIN PASS"
    print(f"\n========== STARTING {pass_name} ==========")

    video_count = 0  # Counter for videos attempted

    # Get Sections
    sections = driver.find_elements(By.CLASS_NAME, "tocSubTitle")
    print(f"Found {len(sections)} Course Sections.")

    for i in range(len(sections)):
        try:
            # Refresh reference
            sections = driver.find_elements(By.CLASS_NAME, "tocSubTitle")
            current_section = sections[i]
            section_title = current_section.text

            # --- SKIP FULL SECTION IF COMPLETE ---
            # If the header has a green tick, we don't need to open it.
            try:
                if len(current_section.find_elements(By.CLASS_NAME, "icon-Tick")) > 0:
                    # Only print this in the main pass to keep logs clean
                    if not is_verification_round:
                        print(f"--- Section {i+1}: Already Fully Complete. Skipping. ---")
                    continue
            except: pass

            # --- SKIP FINAL ASSESSMENT ---
            if FINAL_ASSESSMENT_PATTERN in section_title:
                print(f"--- Section {i+1}: Skipped (Final Assessment/Quiz) ---")
                continue

            # --- OPEN SECTION ---
            try:
                arrow = current_section.find_element(By.CSS_SELECTOR, ".icon-DownArrow")
                if "expand_more" in arrow.get_attribute("class"):
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", current_section)
                    current_section.click()
                    time.sleep(SECTION_SLEEP) 
            except: pass 

            # Find Topics
            xpath_topics = f"(//mat-card-subtitle)[{i+1}]/following-sibling::div//div[contains(@class, 'modTitle')]"
            topics = driver.find_elements(By.XPATH, xpath_topics)
            
            # --- RETRY LOGIC FOR 0 TOPICS ---
            if len(topics) == 0:
                print("  [Retry] Found 0 topics. Refreshing section...")
                time.sleep(RETRY_SLEEP)
                # Toggle Close then Open
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", sections[i])
                    sections[i].click() # Close
                    time.sleep(CLICK_SLEEP)
                    sections[i].click() # Open
                    time.sleep(LOAD_SLEEP)
                except: pass
                topics = driver.find_elements(By.XPATH, xpath_topics)

            print(f"\n--- Section {i+1}: Processing {len(topics)} Topics ---")
            
            for j in range(len(topics)):
                try:
                    # Refresh references inside loop
                    topics = driver.find_elements(By.XPATH, xpath_topics)
                    
                    # List index protection
                    if j >= len(topics):
                        print("    [Warn] Topic list shrank unexpectedly. Moving to next section.")
                        break
                    
                    current_topic = topics[j]
                    
                    # Check for Green Tick
                    try:
                        parent = current_topic.find_element(By.XPATH, "./..")
                        if len(parent.find_elements(By.CLASS_NAME, "icon-Tick")) > 0:
                            if not is_verification_round: # Reduce spam in verification round
                                print(f"  > Topic {j+1}: Already Completed.")
                            continue 
                    except: pass 

                    # Click Topic
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", current_topic)
                    time.sleep(CLICK_SLEEP)
                    current_topic.click()
                    
                    print(f"  > Topic {j+1}: Loading...")
                    time.sleep(LOAD_SLEEP) 

                    # Run Watcher
                    watch_video()
                    video_count += 1  # Increment counter
                    time.sleep(CLICK_SLEEP)

                except Exception as e:
                    print(f"  [Error Topic {j+1}]: {str(e)[:50]}... Continuing.")
                    try: driver.switch_to.default_content()
                    except: pass
                    continue

            # --- CLOSE SECTION ---
            try:
                sections = driver.find_elements(By.CLASS_NAME, "tocSubTitle")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", sections[i])
                sections[i].click()
                time.sleep(CLICK_SLEEP)
            except: pass

        except Exception as e:
            print(f"  [Section Error]: {e}")
            continue

    return video_count

# --- EXECUTION START ---
try:
    videos_watched = run_course_loop(is_verification_round=False)
    while videos_watched > 0:
        print("\n\n>>> RUN COMPLETE. STARTING NEXT VERIFICATION ROUND <<<")
        time.sleep(VERIFICATION_DELAY)
        videos_watched = run_course_loop(is_verification_round=True)

    print("\n--- ALL DONE ---")

    # Close the browser after completion
    driver.quit()

except KeyboardInterrupt:
    print("\n[Stopped] User stopped script.")
except Exception as e:
    print(f"\n[CRITICAL FAILURE] Script stopped: {e}")