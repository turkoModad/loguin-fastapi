import os
new_secret_key = os.urandom(32).hex()
print(new_secret_key)