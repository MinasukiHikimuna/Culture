import json
import websocket
import requests

def open_or_update_tab(url):
    try:
        # Get list of pages/tabs from Chrome
        response = requests.get('http://localhost:9222/json')
        print(f"Got response from Chrome: {response.status_code}")
        pages = json.loads(response.text)
        print(f"Found {len(pages)} pages")
        
        # Check if URL is already open in a tab
        for page in pages:
            current_url = page.get('url', '')
            print(f"Checking page: {current_url}")
            if url in current_url:
                print(f"Found matching tab, bringing to front")
                # Activate this tab using CDP
                ws = websocket.create_connection(page['webSocketDebuggerUrl'])
                ws.send(json.dumps({
                    "id": 1,
                    "method": "Page.bringToFront"
                }))
                response = ws.recv()  # Wait for response
                print(f"CDP response: {response}")
                ws.close()
                return True
        
        print(f"No existing tab found, creating new one")
        # Create new tab using the Target.createTarget command
        browser_ws_url = pages[0]['webSocketDebuggerUrl']
        ws = websocket.create_connection(browser_ws_url, 
                                       header=["Origin: http://localhost:9222"])
        ws.send(json.dumps({
            "id": 1,
            "method": "Target.createTarget",
            "params": {
                "url": url
            }
        }))
        response = ws.recv()
        print(f"Create tab response: {response}")
        ws.close()
        return True

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return False
