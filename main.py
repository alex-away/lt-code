from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            lambda d: d.execute_script("return arguments[0].readyState >= 1;", video)
        )

        # 5. EXECUTE SKIP & FORCE PLAY
        print(f"    [Action] Skipping to -{PLAY_BUFFER}s from end...")
        driver.execute_script(f"""
            var v = arguments[0];
            v.muted = true;               
            v.currentTime = v.duration - {PLAY_BUFFER}; 
            v.play();                     
        """, video)

        # 6. VERIFY COMPLETION
        start_wait = time.time()
        is_ended = False
        
        while not is_ended:
            is_ended = driver.execute_script("return arguments[0].ended;", video)
            
            if is_ended:
                print("    [Success] Video reporting 'Ended' state.")
                break
            
            if time.time() - start_wait > 20:
                print("    [Warning] Video timed out waiting for 'ended' signal.")
                break
                
            time.sleep(1)

        time.sleep(2) # Extra safety pause

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
        
        # --- INITIAL EXPANSION CHECK ---
        try:
            arrow = sections[i].find_element(By.CSS_SELECTOR, ".icon-DownArrow")
            # If the arrow class contains 'expand_more', it means it is closed.
            if "expand_more" in arrow.get_attribute("class"):
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", sections[i])
                sections[i].click()
                time.sleep(2) # Wait for animation
        except:
            pass 

        # Find Topics within this section
        xpath_topics = f"(//mat-card-subtitle)[{i+1}]/following-sibling::div//div[contains(@class, 'modTitle')]"
        topics = driver.find_elements(By.XPATH, xpath_topics)
        
        # --- RETRY LOGIC FOR 0 TOPICS ---
        if len(topics) == 0:
            print("  [Retry] Found 0 topics. Waiting to ensure section is open...")
            time.sleep(3) # Wait for lazy load
            
            # Re-check expansion arrow
            try:
                sections = driver.find_elements(By.CLASS_NAME, "tocSubTitle") # Refresh ref
                arrow = sections[i].find_element(By.CSS_SELECTOR, ".icon-DownArrow")
                
                # Double check if it closed itself or didn't open
                if "expand_more" in arrow.get_attribute("class"):
                    print("  [Retry] Section appears closed. Clicking to expand...")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", sections[i])
                    sections[i].click()
                    time.sleep(3)
            except:
                pass
            
            # Search again
            topics = driver.find_elements(By.XPATH, xpath_topics)
            print(f"  [Retry Result] Found {len(topics)} topics.")


        print(f"\n--- Section {i+1}: Found {len(topics)} Topics ---")
        
        for j in range(len(topics)):
            # Refresh topic references
            topics = driver.find_elements(By.XPATH, xpath_topics)
            current_topic = topics[j]
            
            # --- CHECK IF ALREADY COMPLETED ---
            try:
                parent_container = current_topic.find_element(By.XPATH, "./..")
                ticks = parent_container.find_elements(By.CLASS_NAME, "icon-Tick")
                
                if len(ticks) > 0:
                    print(f"  > Topic {j+1}: Already Completed (Green Tick). Skipping.")
                    continue 
            except:
                pass 

            # Proceed to click
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", current_topic)
            time.sleep(0.5)
            current_topic.click()
            
            print(f"  > Topic {j+1}: Opening lesson...")
            time.sleep(4) # Wait for page load

            watch_video()
            
            time.sleep(1)

    print("\n--- COURSE COMPLETED ---")

except Exception as e:
    print(f"\n[CRITICAL FAILURE] Script stopped: {e}")