import jwt
import sys

secret = "tyMDl1/B3DmfXZOtkBKgATre3OzKwE/PW3YPScs6Rsoh2AhbDQ4wmX6dPQ0745U5+CWDEM6Pt7hY1kO8umSO0g=="
payload = {"sub": "1234", "exp": 9999999999, "aud": "authenticated"}

print("== Testing STRING secret ==")
try:
    token1 = jwt.encode(payload, secret, algorithm="HS256")
    print("Encoded token using string secret:", token1)
    decoded1 = jwt.decode(token1, secret, algorithms=["HS256"], audience="authenticated")
    print("Decoded successfully!")
except Exception as e:
    print("Error:", e)

