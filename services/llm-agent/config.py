import os

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://gateway:8003")
MODEL_BASE_URL = os.environ.get("MODEL_BASE_URL", "https://api.groq.com/openai/v1")
MODEL = os.environ.get("MODEL", "qwen/qwen3.6-27b")
LLM_API_KEY = os.environ.get("LLM_API_KEY")
