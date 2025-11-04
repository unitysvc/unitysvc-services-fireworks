import { createRequire } from "module";
const require = createRequire(import.meta.url);
const OpenAI = require("openai");

const openai = new OpenAI({
  baseURL: process.env.API_ENDPOINT,
  apiKey: process.env.API_KEY,
});

async function main() {
  try {
    const completion = await openai.chat.completions.create({
      model: "accounts/fireworks/deployedModels/deepseek-r1-0528-oxf9jwo4",
      messages: [
        { role: "system", content: "You are a helpful assistant." },
        { role: "user", content: "Say this is a test" }
      ],
    });

    console.log(completion.choices[0].message.content);
  } catch (err) {
    console.error("Error:", err);
  }
}

main();

