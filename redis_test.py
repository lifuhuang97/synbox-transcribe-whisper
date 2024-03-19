import redis

# Connect to Redis through the SSH tunnel
ssh_tunnel = redis.Redis(host='localhost', port=6379)

# Perform operations on the Redis server
value = ssh_tunnel.get('key').decode('utf-8')  # Decode the byte string to a regular string
print(value)

# Close the connection (not necessary as redis-py manages connection pooling)
# ssh_tunnel.close()