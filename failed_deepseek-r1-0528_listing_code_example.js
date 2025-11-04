# Environment variables used for this test:
# API_KEY=fw_3Zi68xUugi1ZrFnAn31LW4BY
# API_ENDPOINT=https://api.fireworks.ai/inference/v1
#
# To reproduce this test, export these variables:
# export API_KEY='fw_3Zi68xUugi1ZrFnAn31LW4BY'
# export API_ENDPOINT='https://api.fireworks.ai/inference/v1'
#

import OpenAI from "openai";

const openai = new OpenAI({
  baseURL: process.env.API_ENDPOINT,
  apiKey: process.env.API_KEY,
});

async function main() {
  const completion = await openai.chat.completions.create({
    model: "accounts/fireworks/deployedModels/deepseek-r1-0528-oxf9jwo4",
    messages: [
      { role: "system", content: "You are a helpful assistant." },
      { role: "user", content: "Say this is a test" }
    ],
  });

  console.log(completion.choices[0].message.content);
}

main();