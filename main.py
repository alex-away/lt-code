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
    Returns True if successful, False if it failed (so we can move on).
    """
    print("    [Status] Looking for video player...")

    # 1. CHECK FOR PLAYER CONTAINER (With Retry)
    try:
        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CLASS_NAME, "videoPlayer"))
        )
    except TimeoutException:
        print("    [Skip] No 'videoPlayer' found (Text/Quiz or Network Lag).")
        return False

    try:
        # 2. DRILL DOWN INTO IFRAMES (With Safety Checks)
        
        # --- Frame 1: Outer Player ---
        outer_iframe = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "myPlayer"))
        )
        driver.switch_to.frame(outer_iframe)

        # --- Frame 2: Inner Content (The one that often fails on slow net) ---
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
        # If internet is dead, this will timeout naturally
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            lambda d: d.execute_script("return arguments[0].readyState >= 1;", video)
        )

        # 5. EXECUTE 'DOUBLE JUMP' STRATEGY
        print(f"    [Action] Executing Double Jump...")
        
        # Jump 1: Wake up
        driver.execute_script("""
            var v = arguments[0];
            v.muted = true;
            v.playbackRate = 2.0;         
            v.currentTime = Math.max(0, v.duration - 5); 
            v.play();
        """, video)
        
        time.sleep(2) # Give it a moment to buffer
        
        # Jump 2: Finish Line
        driver.execute_script(f"""
            var v = arguments[0];
            v.currentTime = Math.max(0, v.duration - 0.5);
            v.play();
        """, video)

        # 6. VERIFY COMPLETION (With Forced Exit)
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
                # If script fails (e.g. video player crashed), break loop
                break

            # Timeout after 15s to prevent infinite hanging
            if time.time() - start_wait > 15:
                print("    [Warning] Timeout. Forcing 'ended' event...")
                driver.execute_script("arguments[0].dispatchEvent(new Event('ended'));", video)
                break
                
            time.sleep(1)

        time.sleep(2) # Sync pause
        return True

    except (TimeoutException, NoSuchFrameException):
        print("    [Error] Video load timed out or frame lost (Network issue).")
        return False
    except Exception as e:
        print(f"    [Error] Unexpected video error: {e}")
        return False

    finally:
        # 7. ALWAYS EXIT FRAMES (Critical for next loop)
        try:
            driver.switch_to.default_content()
        except:
            pass # If browser closed, this might fail, which is fine

# --- MAIN AUTOMATION LOOP ---
try:
    # Get Sections
    sections = driver.find_elements(By.CLASS_NAME, "tocSubTitle")
    print(f"Found {len(sections)} Course Sections.")

    for i in range(len(sections)):
        # Refresh reference
        sections = driver.find_elements(By.CLASS_NAME, "tocSubTitle")
        
        # --- OPEN SECTION ---
        try:
            arrow = sections[i].find_element(By.CSS_SELECTOR, ".icon-DownArrow")
            if "expand_more" in arrow.get_attribute("class"):
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", sections[i])
                sections[i].click()
                time.sleep(2) 
        except: pass 

        # Find Topics
        xpath_topics = f"(//mat-card-subtitle)[{i+1}]/following-sibling::div//div[contains(@class, 'modTitle')]"
        topics = driver.find_elements(By.XPATH, xpath_topics)
        
        # --- RETRY LOGIC FOR 0 TOPICS ---
        if len(topics) == 0:
            print("  [Retry] Found 0 topics. Verifying section open...")
            time.sleep(3)
            try:
                # Force Open
                sections = driver.find_elements(By.CLASS_NAME, "tocSubTitle")
                arrow = sections[i].find_element(By.CSS_SELECTOR, ".icon-DownArrow")
                if "expand_more" in arrow.get_attribute("class"):
                    sections[i].click()
                    time.sleep(3)
            except: pass
            
            topics = driver.find_elements(By.XPATH, xpath_topics)
            print(f"  [Retry Result] Found {len(topics)} topics.")

        print(f"\n--- Section {i+1}: Found {len(topics)} Topics ---")
        
        for j in range(len(topics)):
            # !!! ERROR HANDLING WRAPPER FOR INDIVIDUAL TOPICS !!!
            try:
                # Refresh references inside loop (prevents Stale Element)
                topics = driver.find_elements(By.XPATH, xpath_topics)
                current_topic = topics[j]
                
                # Check for Green Tick
                try:
                    parent = current_topic.find_element(By.XPATH, "./..")
                    if len(parent.find_elements(By.CLASS_NAME, "icon-Tick")) > 0:
                        print(f"  > Topic {j+1}: Already Completed. Skipping.")
                        continue 
                except: pass 

                # Click Topic
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", current_topic)
                time.sleep(0.5)
                current_topic.click()
                
                print(f"  > Topic {j+1}: Loading...")
                time.sleep(4) # Wait for network load

                # Run Watcher
                success = watch_video()
                
                if not success:
                    print("    [Warn] Topic incomplete due to error. Moving to next.")

                time.sleep(1)

            except Exception as e:
                # If a specific topic crashes (StaleElement, Network), catch it here
                # So the loop continues to j+1
                print(f"  [Critical Error on Topic {j+1}]: {str(e)[:50]}... Moving on.")
                try:
                    driver.switch_to.default_content() # Ensure we are reset
                except: pass
                continue

        # --- CLOSE SECTION ---
        try:
            print(f"  [Action] Closing Section {i+1}...")
            sections = driver.find_elements(By.CLASS_NAME, "tocSubTitle")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", sections[i])
            sections[i].click()
            time.sleep(1)
        except Exception as e:
            print(f"  [Warning] Could not close section: {e}")

    print("\n--- COURSE COMPLETED ---")

except KeyboardInterrupt:
    print("\n[Stopped] User stopped script.")
except Exception as e:
    print(f"\n[CRITICAL FAILURE] Script stopped: {e}")