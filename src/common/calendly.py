import requests
from typing import Any
import os

# Nach folgender Implementierung: https://github.com/universal-mcp/calendly


headers = {
    "Authorization": f"Bearer {os.getenv('CALENDLY_API_KEY')}",
    "Content-Type": "application/json",
}

def get_current_user() -> dict[str, Any]:
        """
        Retrieves information about the current user using the API.

        Returns:
            dict[str, Any]: OK

        Tags:
            users, me, important
        """
        url = f"https://api.calendly.com/users/me"
        
        #query_params = {}
        response = requests.get(url, headers = headers)
        response.raise_for_status()
        return response.json()
    
def get_event_type(uuid) -> dict[str, Any]:
        """
        Retrieves the details of a specific event type identified by its UUID using the path "/event_types/{uuid}" and the GET method.

        Args:
            uuid (string): uuid

        Returns:
            dict[str, Any]: OK

        Tags:
            event_types, {uuid}1
        """
        if uuid is None:
            raise ValueError("Missing required parameter 'uuid'")
        
        url = f"https://api.calendly.com/event_types?user={uuid}"
     
        #query_params = {}
        response = requests.get(url, headers = headers)
        response.raise_for_status()
        return response.json()
    
def list_event_type_available_times(event_type=None, start_time=None, end_time=None) -> dict[str, Any]:
        """
        Retrieves a list of available times for a specified event type within a given date range, using the event type, start time, and end time as query parameters.

        Args:
            event_type (string): (Required) The uri associated with the event type Example: '<uri>'.
            start_time (string): (Required) Start time of the requested availability range. Example: '<string>'.
            end_time (string): (Required) End time of the requested availability range. Example: '<string>'.

        Returns:
            dict[str, Any]: OK

        Tags:
            event_type_available_times
        """
        url = f"https://api.calendly.com/event_type_available_times"
        query_params = {k: v for k, v in [('event_type', event_type), ('start_time', start_time), ('end_time', end_time)] if v is not None}
        response = requests.get(url, params=query_params, headers = headers)
        response.raise_for_status()
        return response.json()
    

    
    