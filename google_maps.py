import os
from typing import Any, Dict, List, Optional
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("google-maps")

# Get API key from environment
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
if not GOOGLE_MAPS_API_KEY:
    raise ValueError("GOOGLE_MAPS_API_KEY environment variable is required")

# Base URL for Google Maps APIs
GOOGLE_MAPS_BASE_URL = "https://maps.googleapis.com/maps/api"

async def make_google_request(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any] | None:
    """Make a request to Google Maps API with proper error handling."""
    params["key"] = GOOGLE_MAPS_API_KEY
    
    url = f"{GOOGLE_MAPS_BASE_URL}/{endpoint}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "OK":
                print(f"Google Maps API error: {data.get('error_message', data.get('status'))}")
                return None
                
            return data
        except Exception as e:
            print(f"Request failed: {e}")
            return None

@mcp.tool()
async def geocode_address(address: str) -> str:
    """Convert an address into geographic coordinates.
    
    Args:
        address: The address to geocode (e.g., "1600 Amphitheatre Parkway, Mountain View, CA")
    """
    params = {"address": address}
    data = await make_google_request("geocode/json", params)
    
    if not data or not data.get("results"):
        return "Unable to geocode the provided address."
    
    result = data["results"][0]
    location = result["geometry"]["location"]
    
    return f"""
Address: {result['formatted_address']}
Coordinates: {location['lat']}, {location['lng']}
Place ID: {result['place_id']}
"""

@mcp.tool()
async def reverse_geocode(latitude: float, longitude: float) -> str:
    """Convert coordinates into an address.
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
    """
    params = {"latlng": f"{latitude},{longitude}"}
    data = await make_google_request("geocode/json", params)
    
    if not data or not data.get("results"):
        return "Unable to reverse geocode the provided coordinates."
    
    result = data["results"][0]
    
    return f"""
Formatted Address: {result['formatted_address']}
Place ID: {result['place_id']}
Coordinates: {latitude}, {longitude}
"""

@mcp.tool()
async def search_places(
    query: str, 
    location: Optional[str] = None, 
    radius: Optional[int] = None
) -> str:
    """Search for places using Google Places API.
    
    Args:
        query: Search query (e.g., "pizza restaurants", "gas stations")
        location: Optional center point as "lat,lng" (e.g., "37.7749,-122.4194")
        radius: Optional search radius in meters (max 50000)
    """
    params = {"query": query}
    
    if location:
        params["location"] = location
    if radius:
        params["radius"] = str(radius)
    
    data = await make_google_request("place/textsearch/json", params)
    
    if not data or not data.get("results"):
        return "No places found for the search query."
    
    places = []
    for place in data["results"][:5]:  # Limit to 5 results
        place_info = f"""
Name: {place['name']}
Address: {place.get('formatted_address', 'Address not available')}
Rating: {place.get('rating', 'No rating')} stars
Types: {', '.join(place.get('types', []))}
Place ID: {place['place_id']}
"""
        places.append(place_info)
    
    return "\n---\n".join(places)

@mcp.tool()
async def get_place_details(place_id: str) -> str:
    """Get detailed information about a specific place.
    
    Args:
        place_id: The Google Places ID for the location
    """
    params = {
        "place_id": place_id,
        "fields": "name,formatted_address,formatted_phone_number,website,rating,reviews,opening_hours,geometry"
    }
    
    data = await make_google_request("place/details/json", params)
    
    if not data or not data.get("result"):
        return "Unable to fetch place details."
    
    place = data["result"]
    
    details = f"""
Name: {place.get('name', 'Unknown')}
Address: {place.get('formatted_address', 'Address not available')}
Phone: {place.get('formatted_phone_number', 'Phone not available')}
Website: {place.get('website', 'Website not available')}
Rating: {place.get('rating', 'No rating')} stars
"""
    
    # Add opening hours if available
    if place.get('opening_hours'):
        hours = place['opening_hours']
        if hours.get('weekday_text'):
            details += f"\nOpening Hours:\n" + "\n".join(hours['weekday_text'])
        details += f"\nCurrently Open: {'Yes' if hours.get('open_now') else 'No'}"
    
    # Add recent reviews if available
    if place.get('reviews'):
        details += f"\n\nRecent Reviews:"
        for review in place['reviews'][:3]:  # Show 3 most recent reviews
            details += f"""
- {review['author_name']} ({review['rating']} stars): {review['text'][:200]}...
"""
    
    return details

@mcp.tool()
async def get_directions(
    origin: str, 
    destination: str, 
    mode: str = "driving"
) -> str:
    """Get directions between two locations.
    
    Args:
        origin: Starting location (address or coordinates)
        destination: Ending location (address or coordinates)
        mode: Travel mode - "driving", "walking", "bicycling", or "transit"
    """
    if mode not in ["driving", "walking", "bicycling", "transit"]:
        return "Invalid travel mode. Use: driving, walking, bicycling, or transit"
    
    params = {
        "origin": origin,
        "destination": destination,
        "mode": mode
    }
    
    data = await make_google_request("directions/json", params)
    
    if not data or not data.get("routes"):
        return "Unable to find directions for the specified route."
    
    route = data["routes"][0]
    leg = route["legs"][0]
    
    directions = f"""
Route Summary: {route.get('summary', 'Direct route')}
Distance: {leg['distance']['text']}
Duration: {leg['duration']['text']}
Travel Mode: {mode.title()}

Turn-by-Turn Directions:
"""
    
    for i, step in enumerate(leg["steps"][:10], 1):  # Limit to 10 steps
        # Remove HTML tags from instructions
        instructions = step["html_instructions"].replace("<b>", "").replace("</b>", "").replace("<div>", " ").replace("</div>", "")
        directions += f"{i}. {instructions} ({step['distance']['text']}, {step['duration']['text']})\n"
    
    return directions

@mcp.tool()
async def calculate_distance_matrix(
    origins: List[str], 
    destinations: List[str], 
    mode: str = "driving"
) -> str:
    """Calculate travel distances and times between multiple origins and destinations.
    
    Args:
        origins: List of origin locations
        destinations: List of destination locations  
        mode: Travel mode - "driving", "walking", "bicycling", or "transit"
    """
    if mode not in ["driving", "walking", "bicycling", "transit"]:
        return "Invalid travel mode. Use: driving, walking, bicycling, or transit"
    
    params = {
        "origins": "|".join(origins),
        "destinations": "|".join(destinations),
        "mode": mode
    }
    
    data = await make_google_request("distancematrix/json", params)
    
    if not data or not data.get("rows"):
        return "Unable to calculate distance matrix."
    
    results = f"Distance Matrix ({mode.title()} mode):\n\n"
    
    for i, origin in enumerate(data["origin_addresses"]):
        results += f"From: {origin}\n"
        
        for j, destination in enumerate(data["destination_addresses"]):
            element = data["rows"][i]["elements"][j]
            
            if element["status"] == "OK":
                results += f"  To {destination}: {element['distance']['text']} ({element['duration']['text']})\n"
            else:
                results += f"  To {destination}: Route not available\n"
        
        results += "\n"
    
    return results

@mcp.tool()
async def get_elevation(locations: List[Dict[str, float]]) -> str:
    """Get elevation data for specific coordinates.
    
    Args:
        locations: List of coordinate dictionaries with 'lat' and 'lng' keys
                  Example: [{"lat": 37.7749, "lng": -122.4194}]
    """
    # Convert locations to string format
    location_strings = [f"{loc['lat']},{loc['lng']}" for loc in locations]
    
    params = {"locations": "|".join(location_strings)}
    
    data = await make_google_request("elevation/json", params)
    
    if not data or not data.get("results"):
        return "Unable to fetch elevation data."
    
    results = "Elevation Data:\n\n"
    
    for i, result in enumerate(data["results"]):
        location = result["location"]
        results += f"Location {i+1}: {location['lat']}, {location['lng']}\n"
        results += f"Elevation: {result['elevation']:.2f} meters ({result['elevation'] * 3.28084:.2f} feet)\n"
        results += f"Resolution: {result['resolution']:.2f} meters\n\n"
    
    return results

if __name__ == "__main__":
    mcp.run(transport="stdio")
