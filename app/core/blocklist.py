import redis
from app.core.configs import settings

# Setup our redis connection for storing the blocklisted tokens. Container was set with
# volume so data won't be lost after restart

jwt_redis_blocklist = redis.StrictRedis(
    host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0, decode_responses=True
)
