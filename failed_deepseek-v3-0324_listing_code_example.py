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
base_url = os.environ.get("API_ENDPOINT")
api_key = os.environ.get("API_KEY")

client = OpenAI(api_key=api_key, base_url=base_url)

response = client.chat.completions.create(
    # model="accounts/fireworks/deployedModels/deepseek-r1-0528-oxf9jwo4",
    # model="accounts/fireworks/models/deepseek-v3-0324",
    # model= "accounts/fireworks/models/deepseek-v3p1",
    # model= "accounts/fireworks/models/deepseek-v3p1-terminus",
    model= " accounts/fireworks/models/deepseek-v3-0324 ",
    # model= "accounts/fireworks/models/flux-1-dev-fp8",
    # model= "accounts/fireworks/models/flux-1-schnell-fp8",
    # model= "accounts/fireworks/models/flux-kontext-max",
    # model= "accounts/fireworks/models/flux-kontext-pro",
    # model= "accounts/fireworks/models/glm-4p5",
    # model= "accounts/fireworks/models/glm-4p6",
    # model= "accounts/fireworks/models/gpt-oss-20b",
    # model= "accounts/fireworks/models/gpt-oss-120b",


    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say this is a test"}
    ]
)

print(response.choices[0].message.content)