import secrets
import string

def generate_sk_token(length=128):
    """
    Generate a token starting with 'sk-' and total length of specified characters
    """
    # Token starts with 'sk-'
    prefix = "sk-"
    
    # Calculate remaining length needed
    remaining_length = length - len(prefix)
    
    # Generate random characters (letters and digits)
    characters = string.ascii_letters + string.digits
    random_part = ''.join(secrets.choice(characters) for _ in range(remaining_length))
    
    # Combine prefix and random part
    token = prefix + random_part
    
    return token

if __name__ == "__main__":
    token = generate_sk_token()
    print(f"Generated token: {token}")
    print(f"Token length: {len(token)}")
    
    # Verify the token starts with 'sk-'
    if token.startswith("sk-"):
        print("✓ Token starts with 'sk-'")
    else:
        print("✗ Token does not start with 'sk-'")
    
    # Verify the length
    if len(token) == 128:
        print("✓ Token length is 128 characters")
    else:
        print(f"✗ Token length is {len(token)}, expected 128")