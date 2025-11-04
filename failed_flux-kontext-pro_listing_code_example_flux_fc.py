# Environment variables used for this test:
# API_KEY=fw_3Zi68xUugi1ZrFnAn31LW4BY
# API_ENDPOINT=https://api.fireworks.ai/inference/v1
#
# To reproduce this test, export these variables:
# export API_KEY='fw_3Zi68xUugi1ZrFnAn31LW4BY'
# export API_ENDPOINT='https://api.fireworks.ai/inference/v1'
#

import os
import requests

base_url = os.environ.get("API_ENDPOINT")
api_key = os.environ.get("API_KEY")

url = base_url + "/workflows/" + "accounts/fireworks/models/flux-kontext-pro" + "/text_to_image"
headers = {
    "Content-Type": "application/json",
    "Accept": "image/jpeg",
    "Authorization": f"Bearer {api_key}",
}

response = requests.post(url, headers=headers, json=data)

if response.status_code == 200:
    with open(output_file, "wb") as f:
        f.write(response.content)
    print(f"Image saved as {output_file}")
else:
    print("Error:", response.status_code, response.text)