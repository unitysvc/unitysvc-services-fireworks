# Environment variables used for this test:
# API_KEY=fw_3Zi68xUugi1ZrFnAn31LW4BY
# API_ENDPOINT=https://api.fireworks.ai/inference/v1
#
# To reproduce this test, export these variables:
# export API_KEY='fw_3Zi68xUugi1ZrFnAn31LW4BY'
# export API_ENDPOINT='https://api.fireworks.ai/inference/v1'
#

import openai
import json
import os

# Initialize client
client = openai.OpenAI(
    base_url=os.environ.get("API_ENDPOINT"),
    api_key=os.environ.get("API_KEY")
)

# Example function
def echo_message(message):
    return f"Echo: {message}"

# Send chat completion request with function calling
response = client.chat.completions.create(
    model= "accounts/fireworks/models/gpt-oss-120b",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Repeat: Hello world"}
    ],
    functions=[
        {
            "name": "echo_message",
            "description": "Echoes back the given message",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message to echo"
                    }
                },
                "required": ["message"]
            }
        }
    ],
    function_call="auto"
)

# Extract the function call (if any)
message = response.choices[0].message

if hasattr(message, "function_call") and message.function_call:
    function_name = message.function_call.name
    function_args = json.loads(message.function_call.arguments)

    if function_name == "echo_message":
        result = echo_message(function_args["message"])
        print(result)
else:
    # If no function call, print normal response
    print(message.content)