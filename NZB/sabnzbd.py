import requests
from typing import Optional
import os
from dotenv import load_dotenv

class SABnzbdClient:
    def __init__(self):
        load_dotenv()
        self.host = os.getenv('SABNZBD_HOST', 'http://localhost:8080').rstrip('/')
        self.api_key = os.getenv('SABNZBD_API_KEY')
        if not self.api_key:
            raise ValueError("SABNZBD_API_KEY not found in environment variables")

    def add_nzb_url(self, nzb_url: str, name: Optional[str] = None) -> bool:
        """
        Add an NZB to SABnzbd queue via URL
        
        Args:
            nzb_url: The URL of the NZB file
            name: Optional name for the download
            
        Returns:
            bool: True if successful, False otherwise
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
                return True
                
            try:
                result = response.json()
                # SABnzbd returns different response formats
                if isinstance(result, dict):
                    return result.get('status', False) or 'error' not in result
                return True
            except ValueError:
                # If response isn't JSON but request succeeded, assume success
                return response.status_code == 200
                
        except Exception as e:
            print(f"Error adding NZB to SABnzbd: {e}")
            print(f"Response content: {response.text if 'response' in locals() else 'No response'}")
            return False 