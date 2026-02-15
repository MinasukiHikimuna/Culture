import json
import time
from typing import Any, Optional

import requests
import websocket


def inject_data_to_window(
    ws, data: dict[str, Any], namespace: str = "stashData"
) -> bool:
    """
    Injects data into the window global object using Chrome DevTools Protocol.

    Args:
        ws: WebSocket connection to the tab
        data: Dictionary of data to inject
        namespace: Name of the global variable to create (default: "stashData")

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # First enable the Runtime domain
        ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))

        # Wait for the Runtime.enable response, ignoring console messages
        max_attempts = 10
        for attempt in range(max_attempts):
            response = ws.recv()
            result = json.loads(response)

            # Skip console messages and other events
            if "method" in result and result["method"] == "Runtime.consoleAPICalled":
                continue
            elif "id" in result and result["id"] == 1:
                break
        else:
            print("Failed to enable Runtime domain")
            return False

        # Create JavaScript to inject the data
        js_code = f"window.{namespace} = {json.dumps(data)};"

        # Execute the JavaScript
        ws.send(
            json.dumps(
                {
                    "id": 2,
                    "method": "Runtime.evaluate",
                    "params": {"expression": js_code, "returnByValue": True},
                }
            )
        )

        # Wait for the Runtime.evaluate response, ignoring console messages
        for attempt in range(max_attempts):
            response = ws.recv()
            result = json.loads(response)

            # Skip console messages and other events
            if "method" in result and result["method"] == "Runtime.consoleAPICalled":
                continue
            elif "id" in result and result["id"] == 2:
                break
        else:
            print("Failed to get Runtime.evaluate response")
            return False

        # Check if there was an error
        if "error" in result:
            print(f"Error injecting data: {result['error']}")
            return False

        # Check if the evaluation was successful
        if "result" in result and "exceptionDetails" not in result["result"]:
            print(f"Successfully injected data into window.{namespace}")
            return True
        else:
            print(f"Failed to inject data: {result}")
            return False

    except Exception as e:
        print(f"Exception while injecting data: {e!s}")
        return False


def open_or_update_tabs_with_data(
    urls: list[str], data: dict[str, Any] | None = None, namespace: str = "stashData"
) -> dict[str, bool]:
    """
    Opens or updates multiple tabs for the given URLs and optionally injects data into window global object.

    Args:
        urls: List of URLs to open
        data: Optional dictionary of data to inject into window global object
        namespace: Name of the global variable to create (default: "stashData")

    Returns:
        Dictionary mapping URLs to success status.
    """
    results = {}
    try:
        # Get list of pages/tabs from Chrome once
        response = requests.get("http://localhost:9222/json")
        print(f"Got response from Chrome: {response.status_code}")
        pages = json.loads(response.text)
        print(f"Found {len(pages)} existing pages")

        # Get browser websocket connection once
        browser_ws_url = pages[0]["webSocketDebuggerUrl"]
        browser_ws = websocket.create_connection(
            browser_ws_url, header=["Origin: http://localhost:9222"]
        )

        # Process each URL
        for url in urls:
            try:
                # Check if URL is already open in a tab
                matching_page = next(
                    (page for page in pages if url in page.get("url", "")), None
                )

                tab_ws = None
                if matching_page:
                    print(f"Found matching tab for {url}, bringing to front")
                    # Activate existing tab
                    tab_ws = websocket.create_connection(
                        matching_page["webSocketDebuggerUrl"],
                        header=["Origin: http://localhost:9222"],
                    )
                    tab_ws.send(json.dumps({"id": 1, "method": "Page.bringToFront"}))
                    tab_ws.recv()  # Wait for response

                else:
                    print(f"Creating new tab for {url}")
                    # Create new tab
                    browser_ws.send(
                        json.dumps(
                            {
                                "id": 1,
                                "method": "Target.createTarget",
                                "params": {"url": url},
                            }
                        )
                    )
                    create_response = browser_ws.recv()
                    create_result = json.loads(create_response)

                    if (
                        "result" in create_result
                        and "targetId" in create_result["result"]
                    ):
                        # Get the new tab's websocket URL
                        time.sleep(0.5)  # Give the tab time to load
                        updated_pages = json.loads(
                            requests.get("http://localhost:9222/json").text
                        )
                        new_tab = next(
                            (
                                page
                                for page in updated_pages
                                if page.get("id") == create_result["result"]["targetId"]
                            ),
                            None,
                        )

                        if new_tab:
                            tab_ws = websocket.create_connection(
                                new_tab["webSocketDebuggerUrl"],
                                header=["Origin: http://localhost:9222"],
                            )

                # Inject data if provided and we have a tab connection
                inject_success = True  # Default to True if no data to inject
                if data and tab_ws:
                    print(f"Injecting data into tab for {url}")
                    # Wait a bit for the page to load
                    time.sleep(1)
                    inject_success = inject_data_to_window(tab_ws, data, namespace)
                    if inject_success:
                        print(f"Data injection successful for {url}")
                    else:
                        print(f"Data injection failed for {url}")

                if tab_ws:
                    tab_ws.close()

                results[url] = inject_success

            except Exception as e:
                print(f"Error processing {url}: {e!s}")
                results[url] = False

        browser_ws.close()
        return results

    except Exception as e:
        print(f"Fatal error occurred: {e!s}")
        # Mark all remaining URLs as failed
        for url in urls:
            if url not in results:
                results[url] = False
        return results


def open_or_update_tabs(urls: list[str]) -> dict[str, bool]:
    """
    Opens or updates multiple tabs for the given URLs.
    Returns a dictionary mapping URLs to success status.
    """
    return open_or_update_tabs_with_data(urls, data=None)
