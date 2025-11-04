# Environment variables used for this test:
# API_KEY=fw_3Zi68xUugi1ZrFnAn31LW4BY
# API_ENDPOINT=https://api.fireworks.ai/inference/v1
#
# To reproduce this test, export these variables:
# export API_KEY='fw_3Zi68xUugi1ZrFnAn31LW4BY'
# export API_ENDPOINT='https://api.fireworks.ai/inference/v1'
#

import fs from "fs";
import fetch from "node-fetch";

async function textToImage(prompt, modelName, outputFile = "a.jpg") {
  const baseUrl = process.env.API_ENDPOINT;
  const apiKey = process.env.API_KEY;

  const url = `${baseUrl}/workflows/${modelName}/text_to_image`;
  const headers = {
    "Content-Type": "application/json",
    "Accept": "image/jpeg",
    "Authorization": `Bearer ${apiKey}`,
  };
  const data = { prompt };

  const response = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(data),
  });

  if (response.ok) {
    const buffer = await response.arrayBuffer();
    fs.writeFileSync(outputFile, Buffer.from(buffer));
    console.log(`Image saved as ${outputFile}`);
  } else {
    const errorText = await response.text();
    console.error("Error:", response.status, errorText);
  }
}

// Example call:
// textToImage("A beautiful sunset over the ocean", "accounts/fireworks/models/flux-kontext-pro");