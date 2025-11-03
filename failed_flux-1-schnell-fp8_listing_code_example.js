# Environment variables used for this test:
# API_KEY=fw_3Zi68xUugi1ZrFnAn31LW4BY
# API_ENDPOINT=https://api.fireworks.ai/inference/v1
#
# To reproduce this test, export these variables:
# export API_KEY='fw_3Zi68xUugi1ZrFnAn31LW4BY'
# export API_ENDPOINT='https://api.fireworks.ai/inference/v1'
#

const API_KEY = process.env.API_KEY;
const ENDPOINT = process.env.API_ENDPOINT;

async function main() {
  const response = await fetch(`${ENDPOINT}/chat/completions`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "accounts/fireworks/models/flux-1-schnell-fp8",
      messages: [
        { role: "system", content: "You are a helpful assistant." },
        { role: "user", content: "Say this is a test" },
      ],
    }),
  });

  const data = await response.json();
  console.log(data.choices[0].message.content);
}

main();