import os

# Gunicorn configuration for production
bind = f"0.0.0.0:{os.getenv('PORT', 5423)}"
workers = 2
timeout = 120  # 2 minutes timeout for image generation
keepalive = 5
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
preload_app = True
