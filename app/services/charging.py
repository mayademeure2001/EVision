import requests
import logging

logger = logging.getLogger(__name__)

class ChargingService:
    def __init__(self, api_key=None, base_url=None):
        self.api_key = api_key or '78796da0-ae35-4cfc-8c3e-550d70f0e7e5'
        self.base_url = base_url or 'https://api.openchargemap.io/v3'

    def find_stations_along_route(self, start_coords, end_coords, radius_km=5):
        """
        Find charging stations along a route within a specified radius
        start_coords and end_coords are tuples of (lat, lng)
        """
        try:
            # Get stations near the route
            params = {
                'key': self.api_key,
                'output': 'json',
                'maxresults': 10,
                'compact': True,
                'verbose': False,
                'latitude': start_coords[0],
                'longitude': start_coords[1],
                'distance': radius_km,
                'distanceunit': 'km'
            }

            response = requests.get(f"{self.base_url}/poi", params=params)
            response.raise_for_status()
            
            stations = response.json()
            
            # Process and format station data
            formatted_stations = []
            for station in stations:
                formatted_stations.append({
                    'id': station.get('ID'),
                    'name': station.get('AddressInfo', {}).get('Title'),
                    'latitude': station.get('AddressInfo', {}).get('Latitude'),
                    'longitude': station.get('AddressInfo', {}).get('Longitude'),
                    'address': station.get('AddressInfo', {}).get('AddressLine1'),
                    'distance_km': station.get('AddressInfo', {}).get('Distance'),
                    'connections': [
                        {
                            'type': conn.get('ConnectionType', {}).get('Title'),
                            'power_kw': conn.get('PowerKW'),
                            'status': conn.get('StatusType', {}).get('Title')
                        }
                        for conn in station.get('Connections', [])
                    ]
                })

            return formatted_stations

        except Exception as e:
            logger.error(f"Error finding charging stations: {str(e)}")
            return [] 