"""
Kroger API Example Script

This script demonstrates how to:
1. Authenticate with the Kroger API using OAuth2
2. Search for store locations
3. Search for products and get pricing information
4. Save results to CSV

Setup:
1. Create a free account at https://developer.kroger.com/
2. Register an application to get your CLIENT_ID and CLIENT_SECRET
3. Set environment variables:
   - KROGER_CLIENT_ID
   - KROGER_CLIENT_SECRET

Documentation: https://developer.kroger.com/reference/
"""

import os
import base64
import json
from typing import Dict, List, Optional
import requests
import pandas as pd
from datetime import datetime


class KrogerAPI:
    """Simple wrapper for Kroger API"""
    
    BASE_URL = "https://api.kroger.com/v1"
    TOKEN_URL = "https://api.kroger.com/v1/connect/oauth2/token"
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expiry = None
    
    def _get_auth_header(self) -> str:
        """Generate the base64 encoded authorization header"""
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return encoded
    
    def authenticate(self, scope: str = "product.compact") -> Dict:
        """
        Get access token using client credentials flow
        
        Args:
            scope: API scope (product.compact for basic product info)
        
        Returns:
            Token information dictionary
        """
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {self._get_auth_header()}'
        }
        
        data = {
            'grant_type': 'client_credentials',
            'scope': scope
        }
        
        response = requests.post(self.TOKEN_URL, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        
        token_data = response.json()
        self.access_token = token_data['access_token']
        print(f"✓ Authenticated successfully. Token expires in {token_data['expires_in']} seconds")
        
        return token_data
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make an authenticated API request"""
        if not self.access_token:
            raise ValueError("Not authenticated. Call authenticate() first.")
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/json'
        }
        
        url = f"{self.BASE_URL}{endpoint}"
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        return response.json()
    
    def search_locations(self, zip_code: str, radius_miles: int = 10, 
                        limit: int = 5) -> List[Dict]:
        """
        Search for Kroger store locations
        
        Args:
            zip_code: ZIP code to search near
            radius_miles: Search radius in miles
            limit: Maximum number of results
        
        Returns:
            List of location dictionaries
        """
        params = {
            'filter.zipCode.near': zip_code,
            'filter.radiusInMiles': radius_miles,
            'filter.limit': limit
        }
        
        result = self._make_request('/locations', params)
        return result.get('data', [])
    
    def search_products(self, term: str, location_id: Optional[str] = None,
                       limit: int = 10) -> List[Dict]:
        """
        Search for products
        
        Args:
            term: Search term (e.g., "milk", "eggs")
            location_id: Optional location ID for local pricing/availability
            limit: Maximum number of results
        
        Returns:
            List of product dictionaries
        """
        params = {
            'filter.term': term,
            'filter.limit': limit
        }
        
        if location_id:
            params['filter.locationId'] = location_id
        
        result = self._make_request('/products', params)
        return result.get('data', [])
    
    def get_product(self, product_id: str, location_id: Optional[str] = None) -> Dict:
        """
        Get details for a specific product
        
        Args:
            product_id: Product ID
            location_id: Optional location ID for local pricing
        
        Returns:
            Product dictionary
        """
        params = {}
        if location_id:
            params['filter.locationId'] = location_id
        
        result = self._make_request(f'/products/{product_id}', params)
        return result.get('data', {})


def extract_product_info(product: Dict) -> Dict:
    """Extract relevant information from product data"""
    # Get price information
    items = product.get('items', [{}])
    price_info = items[0].get('price', {}) if items else {}
    
    return {
        'product_id': product.get('productId', ''),
        'upc': product.get('upc', ''),
        'brand': product.get('brand', ''),
        'description': product.get('description', ''),
        'categories': ', '.join(product.get('categories', [])),
        'regular_price': price_info.get('regular', 0),
        'promo_price': price_info.get('promo', 0),
        'size': items[0].get('size', '') if items else '',
        'image_url': (product.get('images', [{}])[0].get('sizes', [{}])[0].get('url', '') 
                     if product.get('images') else '')
    }


def main():
    # Load credentials from environment variables
    CLIENT_ID = os.getenv('KROGER_CLIENT_ID')
    CLIENT_SECRET = os.getenv('KROGER_CLIENT_SECRET')
    
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: Please set KROGER_CLIENT_ID and KROGER_CLIENT_SECRET environment variables")
        print("\nTo get credentials:")
        print("1. Create account at https://developer.kroger.com/")
        print("2. Register an application")
        print("3. Copy your Client ID and Client Secret")
        return
    
    # Initialize API client
    api = KrogerAPI(CLIENT_ID, CLIENT_SECRET)
    
    # Authenticate
    print("Authenticating with Kroger API...")
    api.authenticate()
    
    # Example 1: Search for nearby stores
    print("\n" + "="*60)
    print("SEARCHING FOR STORES")
    print("="*60)
    zip_code = "30301"  # Atlanta, GA
    locations = api.search_locations(zip_code, radius_miles=10, limit=3)
    
    print(f"\nFound {len(locations)} stores near {zip_code}:")
    for i, loc in enumerate(locations, 1):
        print(f"\n{i}. {loc.get('name', 'Unknown')}")
        print(f"   Location ID: {loc.get('locationId', '')}")
        address = loc.get('address', {})
        print(f"   Address: {address.get('addressLine1', '')}, {address.get('city', '')}")
        print(f"   Phone: {loc.get('phone', 'N/A')}")
    
    # Get location ID for product search
    location_id = locations[0].get('locationId') if locations else None
    
    # Example 2: Search for products
    print("\n" + "="*60)
    print("SEARCHING FOR PRODUCTS")
    print("="*60)
    
    search_terms = ["milk", "eggs", "bread"]
    all_products = []
    
    for term in search_terms:
        print(f"\nSearching for: {term}")
        products = api.search_products(term, location_id=location_id, limit=5)
        print(f"Found {len(products)} products")
        
        for product in products:
            info = extract_product_info(product)
            all_products.append(info)
            
            print(f"\n  • {info['description']}")
            print(f"    Brand: {info['brand']}")
            print(f"    Size: {info['size']}")
            print(f"    Regular Price: ${info['regular_price']:.2f}")
            if info['promo_price'] > 0:
                print(f"    Promo Price: ${info['promo_price']:.2f}")
    
    # Example 3: Save results to CSV
    if all_products:
        df = pd.DataFrame(all_products)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'kroger_products_{timestamp}.csv'
        df.to_csv(filename, index=False)
        print(f"\n{'='*60}")
        print(f"✓ Saved {len(all_products)} products to {filename}")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()