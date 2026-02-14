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
CLICK_SLEEP = 0.5    # Sleep after clicking elements
LOAD_SLEEP = 4       # Sleep after clicking topic to load
SECTION_SLEEP = 2    # Sleep after expanding section
RETRY_SLEEP = 2      # Sleep before retrying section open
VERIFICATION_PASS = True  # Whether to run verification round
VERIFICATION_DELAY = 2    # Delay before starting verification
FINAL_ASSESSMENT_PATTERN = "Final Assessment"  # Pattern to skip sections
MAX_SECTION_RETRIES = 3   # Max times to retry a section if the green tick doesn't appear

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

        # SPOOF: Trick the page into thinking it's always visible in this frame
        driver.execute_script("""
            Object.defineProperty(document, 'hidden', {get: function() {return false;}});
            Object.defineProperty(document, 'visibilityState', {get: function() {return 'visible';}});
            document.dispatchEvent(new Event('visibilitychange'));
        """)

        # Force video to wake up (crucial for background tabs)
        driver.execute_script("arguments[0].play().catch(() => {});", video)

        # Smart Wait for Metadata with Diagnostics
        max_retries = 10 # FAST TIMEOUT: 10 seconds. If it doesn't load by then, force complete.
        ready = False
        
        for i in range(max_retries):
            # Check for specific video errors first
            error_code = driver.execute_script("return arguments[0].error ? arguments[0].error.code : null;", video)
            if error_code:
                # Silently catch error and just let the force-finish logic handle it below
                pass 

            state = driver.execute_script(
                "return {ready: arguments[0].readyState, network: arguments[0].networkState, src: arguments[0].currentSrc};", 
                video
            )
            
            if state['ready'] >= 1:
                ready = True
                break
            
            # RECOVERY: Try to remove the time fragment from the src if it exists
            if i % 3 == 0 and i > 0:
                curr_src = str(state['src'])
                if "#t=" in curr_src:
                   clean_src = curr_src.split("#")[0]
                   driver.execute_script("arguments[0].src = arguments[1]; arguments[0].load(); arguments[0].play().catch(() => {});", video, clean_src)
                else:
                    driver.execute_script("arguments[0].play().catch(() => {});", video)
            
            time.sleep(1)

        # Force completion (works even if video didn't load properly)
        if not ready:
            # Mock the duration if it's missing to prevent event errors
            driver.execute_script("""
                if (isNaN(arguments[0].duration)) {
                    Object.defineProperty(arguments[0], 'duration', {get: function(){return 100;}});
                }
            """, video)

        # Force 'ended' event immediately
        driver.execute_script("arguments[0].dispatchEvent(new Event('ended'));", video)
        print("    [Success] Video finished.")

        time.sleep(2) 
        return True

    except Exception as e:
        error_msg = str(e).split('\n')[0] if str(e) else "No message"
        print(f"    [Error] Video failed ({type(e).__name__}): {error_msg}")
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
        section_attempt = 0
        # Retry loop for the current section (allows refresh + re-check)
        while section_attempt < MAX_SECTION_RETRIES:
            # Refresh reference (important after a refresh)
            sections = driver.find_elements(By.CLASS_NAME, "tocSubTitle")
            # If the sections list changed and i is out of range, break out
            if i >= len(sections):
                print(f"--- Section {i+1}: No longer present after refresh. Skipping. ---")
                break

            current_section = sections[i]
            section_title = current_section.text

            # --- SKIP FULL SECTION IF COMPLETE ---
            try:
                if len(current_section.find_elements(By.CLASS_NAME, "icon-Tick")) > 0:
                    if not is_verification_round:
                        print(f"--- Section {i+1}: Already Fully Complete. Skipping. ---")
                    break  # move to next section
            except:
                pass

            # --- SKIP FINAL ASSESSMENT ---
            if FINAL_ASSESSMENT_PATTERN in section_title:
                print(f"--- Section {i+1}: Skipped (Final Assessment/Quiz) ---")
                break

            # --- CLOSE OTHER SECTIONS ---
            # To prevent scrolling issues and keep focus, close all other open sections
            try:
                for k in range(len(sections)):
                    if k == i: continue # Don't close the current one we are about to process
                    
                    other_section = sections[k]
                    try:
                        other_arrow = other_section.find_element(By.CSS_SELECTOR, ".icon-DownArrow")
                        is_other_closed = "expand_more" in other_arrow.get_attribute("class")
                        
                        if not is_other_closed:
                            # It is open -> Click to close
                            # print(f"    [Cleanup] Closing expanded Section {k+1}...")
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", other_section)
                            other_section.click()
                            time.sleep(0.5)
                    except: pass
                
                # Refresh reference to current section after potential DOM updates
                sections = driver.find_elements(By.CLASS_NAME, "tocSubTitle")
                current_section = sections[i]

            except Exception as e:
                # print(f"    [Warn] Cleanup error: {e}")
                pass

            # --- OPEN (OR REFRESH) SECTION ---
            try:
                arrow = current_section.find_element(By.CSS_SELECTOR, ".icon-DownArrow")
                is_closed = "expand_more" in arrow.get_attribute("class")

                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", current_section)
                
                if is_closed:
                    # It is closed -> Open it
                    current_section.click()
                else:
                    # It is already open -> Close it and Re-open to refresh the list
                    current_section.click()
                    time.sleep(CLICK_SLEEP)
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
                if i < len(sections):
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", sections[i])
                    sections[i].click()
                    time.sleep(CLICK_SLEEP)
            except: pass

            # --- POST-CHECK: Verify Section Tick ---
            try:
                sections = driver.find_elements(By.CLASS_NAME, "tocSubTitle")
                if i < len(sections) and len(sections[i].find_elements(By.CLASS_NAME, "icon-Tick")) > 0:
                    # Success for this section
                    break
                else:
                    print("  [Warn] Section tick missing. Reloading page and retrying videos...")
                    driver.refresh()
                    time.sleep(5)
                    section_attempt += 1
                    continue
            except Exception as e:
                print(f"  [Section Error]: {e}")
                section_attempt += 1
                continue

        # End retry loop for this section

    return video_count

# --- EXECUTION START ---
try:
    run_course_loop(is_verification_round=False)

    # Always run at least one Verification Round
    print("\n\n>>> MAIN PASS COMPLETE. STARTING FIRST VERIFICATION ROUND <<<")
    time.sleep(VERIFICATION_DELAY)
    videos_watched = run_course_loop(is_verification_round=True)

    while videos_watched > 0:
        print("\n\n>>> PREVIOUS ROUND INCOMPLETE. STARTING ANOTHER VERIFICATION ROUND <<<")
        time.sleep(VERIFICATION_DELAY)
        videos_watched = run_course_loop(is_verification_round=True)

    print("\n--- ALL DONE ---")

    # Close the browser after completion
    driver.quit()

except KeyboardInterrupt:
    print("\n[Stopped] User stopped script.")
except Exception as e:
    print(f"\n[CRITICAL FAILURE] Script stopped: {e}")