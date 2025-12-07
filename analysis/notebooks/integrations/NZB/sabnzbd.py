import requests
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv
import time

class SABnzbdClient:
    def __init__(self):
        load_dotenv()
        self.host = os.getenv('SABNZBD_HOST', 'http://localhost:8080').rstrip('/')
        self.api_key = os.getenv('SABNZBD_API_KEY')
        if not self.api_key:
            raise ValueError("SABNZBD_API_KEY not found in environment variables")

    def add_nzb_url(self, nzb_url: str, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Add an NZB to SABnzbd queue via URL
        
        Args:
            nzb_url: The URL of the NZB file
            name: Optional name for the download
            
        Returns:
            dict: Response containing status and nzo_id if successful
                 Example: {'status': True, 'nzo_id': 'SABnzbd_nzo_xxx'}
                 or {'status': False, 'error': 'error message'} on failure
        """
        params = {
            'apikey': self.api_key,
            'mode': 'addurl',
            'name': nzb_url,
            'output': 'json'
        }
        if name:
            params['nzbname'] = name

        try:
            response = requests.get(f"{self.host}/api", params=params)
            response.raise_for_status()
            
            # SABnzbd might return empty response for success
            if not response.text:
                return {'status': True, 'error': 'No nzo_id returned'}
                
            try:
                result = response.json()
                # SABnzbd returns different response formats
                if isinstance(result, dict):
                    if 'nzo_ids' in result:
                        return {
                            'status': True,
                            'nzo_id': result['nzo_ids'][0]
                        }
                    elif 'error' in result:
                        return {
                            'status': False,
                            'error': result['error']
                        }
                return {'status': True, 'error': 'No nzo_id in response'}
            except ValueError:
                # If response isn't JSON but request succeeded
                return {
                    'status': True,
                    'error': 'Invalid JSON response'
                }
                
        except Exception as e:
            print(f"Error adding NZB to SABnzbd: {e}")
            print(f"Response content: {response.text if 'response' in locals() else 'No response'}")
            return {
                'status': False,
                'error': str(e)
            }

    def get_queue_details(self, nzo_id: str) -> Dict[str, Any]:
        """
        Get details about a specific item in the queue
        
        Args:
            nzo_id: The SABnzbd NZO ID
            
        Returns:
            dict: Queue item details including status and path information
        """
        params = {
            'apikey': self.api_key,
            'mode': 'queue',
            'output': 'json',
            'nzo_ids': [nzo_id]
        }

        try:
            response = requests.get(f"{self.host}/api", params=params)
            response.raise_for_status()
            data = response.json()
            
            # Find the specific queue item
            if 'queue' in data and 'slots' in data['queue']:
                for item in data['queue']['slots']:
                    if item['nzo_id'] == nzo_id:
                        return item
            return {}
        except Exception as e:
            print(f"Error getting queue details: {e}")
            return {}

    def get_history_details(self, nzo_id: str) -> Dict[str, Any]:
        """
        Get details about a completed download from history
        
        Args:
            nzo_id: The SABnzbd NZO ID
            
        Returns:
            dict: History item details including final path
        """
        params = {
            'apikey': self.api_key,
            'mode': 'history',
            'output': 'json',
            'nzo_ids': [nzo_id]
        }

        try:
            response = requests.get(f"{self.host}/api", params=params)
            response.raise_for_status()
            data = response.json()
            
            # Find the specific history item
            if 'history' in data and 'slots' in data['history']:
                for item in data['history']['slots']:
                    if item['nzo_id'] == nzo_id:
                        return item
            return {}
        except Exception as e:
            print(f"Error getting history details: {e}")
            return {}

    def wait_for_completion(self, nzo_id: str, timeout: int = 3600, check_interval: int = 10) -> Dict[str, Any]:
        """
        Wait for a download to complete and return its final details
        
        Args:
            nzo_id: The SABnzbd NZO ID
            timeout: Maximum time to wait in seconds (default 1 hour)
            check_interval: Time between checks in seconds (default 10 seconds)
            
        Returns:
            dict: Download details including status and path information
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check queue first
            queue_item = self.get_queue_details(nzo_id)
            if queue_item:
                if queue_item.get('status', '').lower() == 'failed':
                    return {'status': 'failed', 'error': queue_item.get('error', 'Unknown error')}
                # Still in queue, wait and check again
                time.sleep(check_interval)
                continue
                
            # Not in queue, check history
            history_item = self.get_history_details(nzo_id)
            if history_item:
                status = history_item.get('status', '').lower()
                if status == 'completed':
                    return {
                        'status': 'completed',
                        'path': history_item.get('storage', ''),
                        'filename': history_item.get('filename', ''),
                        'download_time': history_item.get('download_time', 0),
                        'size': history_item.get('size', ''),
                        'category': history_item.get('category', '')
                    }
                elif status == 'failed':
                    return {'status': 'failed', 'error': history_item.get('fail_message', 'Unknown error')}
                    
            # Not found in either queue or history
            time.sleep(check_interval)
            
        return {'status': 'timeout', 'error': f'Download did not complete within {timeout} seconds'} 