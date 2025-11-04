# Environment variables used for this test:
# API_KEY=fw_3Zi68xUugi1ZrFnAn31LW4BY
# API_ENDPOINT=https://api.fireworks.ai/inference/v1
#
# To reproduce this test, export these variables:
# export API_KEY='fw_3Zi68xUugi1ZrFnAn31LW4BY'
# export API_ENDPOINT='https://api.fireworks.ai/inference/v1'
#

from openai import OpenAI
import os

# Use environment variables or fallback
#os.environ.get("API_ENDPOINT") or 
#os.environ.get("API_KEY")


import requests


base_url = os.environ.get("API_ENDPOINT")
api_key = os.environ.get("API_KEY")

url = base_url + "/workflows/" + accounts/fireworks/models/flux-1-dev-fp8 + "/text_to_image"
headers = {
    "Content-Type": "application/json",
    "Accept": "image/jpeg",
    "Authorization": "Bearer api_key",
}
data = {
    "prompt": "A beautiful sunset over the ocean"
}

response = requests.post(url, headers=headers, json=data)

if response.status_code == 200:
    with open("a.jpg", "wb") as f:
        f.write(response.content)
    print("Image saved as a.jpg")
else:
    print("Error:", response.status_code, response.text)
