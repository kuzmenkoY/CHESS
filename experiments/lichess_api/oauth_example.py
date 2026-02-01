"""
Lichess OAuth 2.0 PKCE Flow Example

This demonstrates how to implement OAuth 2.0 with PKCE for user authorization.
This is a simplified example - in production, use proper OAuth libraries.
"""

import requests
import secrets
import base64
import hashlib
import urllib.parse
from urllib.parse import urlencode, parse_qs, urlparse

# OAuth Configuration
LICHESS_BASE = "https://lichess.org"
AUTHORIZE_URL = f"{LICHESS_BASE}/oauth"
TOKEN_URL = f"{LICHESS_BASE}/api/token"

# Your application's client ID (can be any unique string, no registration needed)
CLIENT_ID = "your-unique-client-id"

# Redirect URI (must match what you use in authorization request)
REDIRECT_URI = "http://localhost:8080/callback"

def generate_pkce_pair():
    """Generate PKCE code verifier and challenge."""
    # Generate code verifier (random string)
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    
    # Generate code challenge (SHA256 hash of verifier)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    
    return code_verifier, code_challenge

def get_authorization_url():
    """Generate authorization URL for user to visit."""
    code_verifier, code_challenge = generate_pkce_pair()
    
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "scope": "read:email"  # Requested scopes
    }
    
    auth_url = f"{AUTHORIZE_URL}?{urlencode(params)}"
    
    print("="*80)
    print("STEP 1: Authorization URL")
    print("="*80)
    print(f"\nSend user to this URL:")
    print(auth_url)
    print(f"\nCode Verifier (save this!): {code_verifier}")
    print("\nAfter user authorizes, they'll be redirected to:")
    print(f"{REDIRECT_URI}?code=<authorization_code>")
    
    return auth_url, code_verifier

def exchange_code_for_token(authorization_code, code_verifier):
    """Exchange authorization code for access token."""
    print("\n" + "="*80)
    print("STEP 2: Exchange Code for Token")
    print("="*80)
    
    data = {
        "grant_type": "authorization_code",
        "code": authorization_code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "code_verifier": code_verifier
    }
    
    try:
        response = requests.post(TOKEN_URL, data=data, timeout=10)
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get('access_token')
            
            print("\n✓ Successfully obtained access token!")
            print(f"\nAccess Token: {access_token[:20]}...")
            print(f"Token Type: {token_data.get('token_type', 'Bearer')}")
            print(f"Expires In: {token_data.get('expires_in', 'N/A')} seconds")
            
            return access_token
        else:
            print(f"\n✗ Error: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return None

def get_user_account(access_token):
    """Get authenticated user's account info."""
    print("\n" + "="*80)
    print("STEP 3: Use Access Token")
    print("="*80)
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "LichessAPI/1.0 (Python Script)"
    }
    
    try:
        response = requests.get(f"{LICHESS_BASE}/api/account", headers=headers, timeout=10)
        
        if response.status_code == 200:
            account = response.json()
            print("\n✓ Successfully retrieved account info!")
            print(f"\nUsername: {account.get('username')}")
            print(f"Email: {account.get('email', 'N/A')}")
            print(f"Title: {account.get('title', 'No title')}")
            return account
        else:
            print(f"\n✗ Error: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return None

def main():
    """Main OAuth flow demonstration."""
    print("="*80)
    print("LICHESS OAUTH 2.0 PKCE FLOW EXAMPLE")
    print("="*80)
    print("\nThis example demonstrates the OAuth 2.0 PKCE flow.")
    print("In a real application, this would be split across:")
    print("1. Backend: Generate auth URL, handle callback")
    print("2. Frontend: Redirect user, receive callback")
    print("3. Backend: Exchange code for token, store securely")
    print("\n" + "="*80)
    
    # Step 1: Generate authorization URL
    auth_url, code_verifier = get_authorization_url()
    
    print("\n" + "="*80)
    print("MANUAL STEPS REQUIRED:")
    print("="*80)
    print("\n1. Visit the authorization URL above")
    print("2. Log in with your Lichess account")
    print("3. Authorize the application")
    print("4. Copy the 'code' parameter from the redirect URL")
    print("5. Run this script again with the authorization code")
    print("\nExample redirect URL:")
    print(f"{REDIRECT_URI}?code=abc123xyz")
    
    # For demonstration, you would normally:
    # 1. Start a local server to receive the callback
    # 2. Extract the code from the callback URL
    # 3. Exchange it for a token
    
    print("\n" + "="*80)
    print("NOTE: This is a simplified example")
    print("="*80)
    print("\nFor production use:")
    print("- Use proper OAuth libraries (e.g., requests-oauthlib for Python)")
    print("- Implement proper error handling")
    print("- Store tokens securely")
    print("- Handle token refresh if needed")
    print("- Use HTTPS for redirect URIs")
    print("\nSee Lichess API docs for complete examples:")
    print("- Flask/Python example")
    print("- NodeJS Passport strategy")
    print("- Demo app: https://github.com/lichess-org/api-demo")

if __name__ == "__main__":
    main()




