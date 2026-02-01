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
PLAY_BUFFER = 2.5   # Seconds before the end to skip to

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

    # 1. CHECK FOR PLAYER CONTAINER
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, "videoPlayer"))
        )
    except TimeoutException:
        print("    [Skip] No 'videoPlayer' found (Text/Quiz or Network Lag).")
        return False

    try:
        # 2. DRILL DOWN INTO IFRAMES
        outer_iframe = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "myPlayer"))
        )
        driver.switch_to.frame(outer_iframe)

        inner_iframe = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.ID, "content"))
        )
        driver.switch_to.frame(inner_iframe)

        # 3. FIND VIDEO TAG
        video = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "video"))
        )
        print("    [Status] Video found. Checking state...")

        # 4. WAIT FOR METADATA
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            lambda d: d.execute_script("return arguments[0].readyState >= 1;", video)
        )

        # 5. EXECUTE 'DOUBLE JUMP'
        print(f"    [Action] Executing Double Jump...")
        driver.execute_script("""
            var v = arguments[0];
            v.muted = true;
            v.playbackRate = 2.0;         
            v.currentTime = Math.max(0, v.duration - 5); 
            v.play();
        """, video)
        
        time.sleep(2) 
        
        driver.execute_script(f"""
            var v = arguments[0];
            v.currentTime = Math.max(0, v.duration - 0.5);
            v.play();
        """, video)

        # 6. VERIFY COMPLETION
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
    """
    pass_name = "VERIFICATION PASS" if is_verification_round else "MAIN PASS"
    print(f"\n========== STARTING {pass_name} ==========")

    # Get Sections
    sections = driver.find_elements(By.CLASS_NAME, "tocSubTitle")
    print(f"Found {len(sections)} Course Sections.")

    for i in range(len(sections)):
        try:
            # Refresh reference
            sections = driver.find_elements(By.CLASS_NAME, "tocSubTitle")
            current_section = sections[i]
            section_title = current_section.text

            # --- [NEW] SKIP FULL SECTION IF COMPLETE ---
            # If the header has a green tick, we don't need to open it.
            try:
                if len(current_section.find_elements(By.CLASS_NAME, "icon-Tick")) > 0:
                    # Only print this in the main pass to keep logs clean
                    if not is_verification_round:
                        print(f"--- Section {i+1}: Already Fully Complete. Skipping. ---")
                    continue
            except: pass

            # --- SKIP FINAL ASSESSMENT ---
            if "Final Assessment" in section_title:
                print(f"--- Section {i+1}: Skipped (Final Assessment/Quiz) ---")
                continue

            # --- OPEN SECTION ---
            try:
                arrow = current_section.find_element(By.CSS_SELECTOR, ".icon-DownArrow")
                if "expand_more" in arrow.get_attribute("class"):
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", current_section)
                    current_section.click()
                    time.sleep(2) 
            except: pass 

            # Find Topics
            xpath_topics = f"(//mat-card-subtitle)[{i+1}]/following-sibling::div//div[contains(@class, 'modTitle')]"
            topics = driver.find_elements(By.XPATH, xpath_topics)
            
            # --- RETRY LOGIC FOR 0 TOPICS ---
            if len(topics) == 0:
                print("  [Retry] Found 0 topics. Refreshing section...")
                time.sleep(2)
                # Toggle Close then Open
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", sections[i])
                    sections[i].click() # Close
                    time.sleep(1)
                    sections[i].click() # Open
                    time.sleep(3)
                except: pass
                topics = driver.find_elements(By.XPATH, xpath_topics)

            print(f"\n--- Section {i+1}: Processing {len(topics)} Topics ---")
            
            for j in range(len(topics)):
                try:
                    # Refresh references inside loop
                    topics = driver.find_elements(By.XPATH, xpath_topics)
                    
                    # [FIX] List Index Out Of Range Protection
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
                    time.sleep(0.5)
                    current_topic.click()
                    
                    print(f"  > Topic {j+1}: Loading...")
                    time.sleep(4) 

                    # Run Watcher
                    watch_video()
                    time.sleep(1)

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
                time.sleep(1)
            except: pass

        except Exception as e:
            print(f"  [Section Error]: {e}")
            continue

# --- EXECUTION START ---
try:
    # 1. Run the Main Pass
    run_course_loop(is_verification_round=False)

    # 2. Run the Final Verification Pass (Checks for missed videos)
    print("\n\n>>> INITIAL RUN COMPLETE. STARTING FINAL VERIFICATION ROUND <<<")
    time.sleep(2)
    run_course_loop(is_verification_round=True)

    print("\n--- ALL DONE ---")

except KeyboardInterrupt:
    print("\n[Stopped] User stopped script.")
except Exception as e:
    print(f"\n[CRITICAL FAILURE] Script stopped: {e}")