#!/usr/bin/env python3
"""
pull_services.py - Extract model data from Fireworks.ai API and pricing pages

This script:
1. Retrieves all models from Fireworks.ai API (or processes specific models if --models is used)
2. Extracts pricing information from web pages using BeautifulSoup
3. Gets detailed model information from API endpoints
4. Writes organized data to service.toml files
5. Creates summary and flags deprecated directories

Usage:
  python pull_services.py [output_dir]                    # Process all models
  python pull_services.py --models model1 model2         # Process specific models
  python pull_services.py custom_dir --models model1     # Custom output directory + specific models
"""

import os
import sys
import json
import requests
import time
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse
import re
from datetime import datetime

from bs4 import BeautifulSoup


class FireworksModelExtractor:
    def __init__(self, api_key: str, api_base_url: str, model_base_url: str):
        self.api_key = api_key
        self.api_base_url = api_base_url
        # e.g. https://fireworks.ai/models/fireworks/qwen2p5-32b
        self.model_base_url = model_base_url
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            }
        )
        self.extracted_data = {}
        self.summary = {
            "total_models": 0,
            "successful_extractions": 0,
            "failed_extractions": 0,
            "skipped_models": 0,
            "pricing_found": 0,
            "deprecated_models": [],
            "extraction_date": datetime.now().isoformat(),
            "force_mode": False,
            "processing_limit": None,
        }

    def get_all_models(self) -> List[Dict]:
        """Retrieve all models from Fireworks.ai API with pagination support"""
        print("🔍 Fetching all models from Fireworks.ai API...")

        url = f"{self.api_base_url}/accounts/fireworks/models"
        all_models = []
        page_token = None
        page_count = 0
        max_pages = 100  # Safety limit to prevent infinite loops

        try:
            while page_count < max_pages:
                page_count += 1
                params = {"pageSize": 200}

                # Add page token for subsequent requests
                if page_token:
                    params["pageToken"] = page_token
                    print(
                        f"📄 Fetching page {page_count} with token: {page_token[:20]}..."
                    )
                else:
                    print(f"📄 Fetching page {page_count}...")

                response = self.session.get(url, params=params)
                response.raise_for_status()

                data = response.json()
                page_models = data.get("models", [])

                # Safety check: if we get no models on a page, break
                if not page_models:
                    print(
                        f"⚠️  No models found on page {page_count}, stopping pagination."
                    )
                    break

                all_models.extend(page_models)
                print(f"   Found {len(page_models)} models on page {page_count}")

                # Check for next page token
                next_page_token = data.get("nextPageToken")
                if not next_page_token:
                    print(f"✅ Pagination complete. No more pages.")
                    break

                page_token = next_page_token

            if page_count >= max_pages:
                print(
                    f"⚠️  Reached maximum page limit ({max_pages}), stopping pagination."
                )

            self.summary["total_models"] = len(all_models)
            print(f"✅ Found {len(all_models)} models total across {page_count} pages")

            # Sort models by name for easier debugging
            all_models.sort(key=lambda x: x["name"])
            # with open("models.json", "w") as models:
            #     json.dump(all_models, models)
            return all_models

        except requests.RequestException as e:
            print(f"❌ Error fetching models: {e}")
            return []

    def extract_pricing_from_page(self, model_name: str) -> Optional[Dict]:
        """Extract pricing information from model's details page using BeautifulSoup"""
        # Remove accounts/fireworks/ prefix if present and convert to URL-friendly format
        clean_model_name = model_name.split("/")[-1]

        model_slug = clean_model_name.replace("/", "-").replace(":", "-").lower()
        pricing_url = f"{self.model_base_url}/{model_slug}"

        print(f"  📄 Fetching pricing from: {pricing_url}")
        response = self.session.get(pricing_url, timeout=10)

        if response.status_code == 404:
            raise requests.RequestException(
                f"  ⚠️  Pricing page not found for {model_name}"
            )

        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        pricing_info = {}

        # Look for the specific HTML structure:
        # <h3 class="text-md text-black">Pricing Per 1M Tokens</h3>
        # <p class="ml-auto text-right font-medium text-display-xs sm:text-display-sm lg:text-display-md">$0.2</p>
        # OR
        # <h3 class="text-md text-black">Pricing Per Image</h3>
        # <p class="ml-auto text-right font-medium text-display-xs sm:text-display-sm lg:text-display-md">$0.04</p>

        # Find h3 elements containing pricing patterns
        pricing_patterns = [
            r"Pricing Per 1M Tokens Input/Output",
            r"Pricing Per 1M Tokens",
            r"Pricing Per Image",
            r"Pricing Per Step",
        ]

        pricing_headers = []
        for pattern in pricing_patterns:
            headers = soup.find_all("h3", string=re.compile(pattern, re.IGNORECASE))
            pricing_headers.extend(headers)

        for header in pricing_headers:
            pricing_info["unit"] = header.get_text().strip()
            # print(f"  🔍 Found pricing unit: {pricing_info['unit']}")

            # Look for the next p element that contains a price (starts with $)
            next_element = header.find_next_sibling()

            # Search through next siblings to find the price
            while next_element:
                if next_element.name == "p":
                    price_text = next_element.get_text().strip()
                    # Check if this p element contains a price (starts with $ and contains numbers)
                    if price_text.startswith("$") and re.search(r"\d", price_text):
                        pricing_info["price"] = price_text
                        # print(f"  💰 Found price: {pricing_info['price']}")
                        break
                next_element = next_element.find_next_sibling()

            # If we found both unit and price, we're done
            if "unit" in pricing_info and "price" in pricing_info:
                break

        # Fallback: if the specific structure wasn't found, look for pricing patterns in general text
        if not pricing_info:
            text_content = soup.get_text()
            fallback_patterns = [
                "Pricing Per 1M Tokens Input/Output",
                "Pricing Per 1M Tokens",
                "Pricing Per Image",
                "Pricing Per Step",
            ]

            # Search for pricing patterns in text
            for pattern in fallback_patterns:
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                if matches:
                    pricing_info["unit"] = pattern
                    pricing_info["price"] = matches
                    pricing_info["reference"] = pricing_url
                    print(f"  🔍 Found pricing pattern in text: {matches}")
                    break

        if pricing_info:
            self.summary["pricing_found"] += 1
            print(f"  ✅ Extracted pricing data: {pricing_info}")
            return pricing_info
        else:
            print(f"  ⚠️  No pricing data found")
            return None

    def get_model_details(self, model_name: str) -> Optional[Dict]:
        """Get detailed model information from API endpoint"""
        # Try different API endpoints for model details
        endpoint = (
            f"{self.api_base_url}/accounts/fireworks/models/{model_name.split('/')[-1]}"
        )

        try:
            response = self.session.get(endpoint, timeout=10)

            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ Retrieved API details")
                return data
            elif response.status_code == 404:
                print(
                    f"  ⚠️ Failed to retrieve model details from API endpoint: {endpoint}"
                )
                return None
            else:
                response.raise_for_status()

        except requests.RequestException:
            return None

        print(f"  ⚠️  No API details available")
        return None

    def parse_pricing_string(
        self, price_string: str, pricing_unit: str
    ) -> Dict[str, Any]:
        """Parse pricing string and return structured pricing data"""
        pricing_data = {}

        if pricing_unit == "Pricing Per 1M Tokens Input/Output":
            # Handle format like "$0.07 / $0.3" or "$0.55 / $2.19"
            if " / " in price_string:
                input_price, output_price = price_string.split(" / ")
                # Remove $ and convert to float
                pricing_data["price_input"] = float(
                    input_price.strip().replace("$", "")
                )
                pricing_data["price_output"] = float(
                    output_price.strip().replace("$", "")
                )
            else:
                # Single price, treat as both input and output
                price = float(price_string.strip().replace("$", ""))
                pricing_data["price_input"] = price
                pricing_data["price_output"] = price
        else:
            # Single price for other pricing models
            pricing_data["price"] = float(price_string.strip().replace("$", ""))

        return pricing_data

    def create_pricing_info_structure(self, pricing_data: Dict) -> Dict[str, Any]:
        """Create pricing info structure based on pricing data"""
        if not pricing_data:
            return {}

        # Parse the price string into structured data
        parsed_pricing = self.parse_pricing_string(
            pricing_data["price"], pricing_data["unit"]
        )

        match pricing_data["unit"]:
            case "Pricing Per 1M Tokens Input/Output":
                return {
                    "description": pricing_data["unit"],
                    "currency": "USD",
                    "price_data": {
                        "input": parsed_pricing["price_input"],
                        "output": parsed_pricing["price_output"],
                    },
                    "unit": "one_million_tokens",
                    "reference": pricing_data.get("reference", None),
                }
            case "Pricing Per 1M Tokens":
                return {
                    "description": pricing_data["unit"],
                    "currency": "USD",
                    "price_data": {"price": parsed_pricing["price"]},
                    "unit": "one_million_tokens",
                    "reference": pricing_data.get("reference", None),
                }
            case "Pricing Per Image":
                return {
                    "description": pricing_data["unit"],
                    "currency": "USD",
                    "price_data": {"price": parsed_pricing["price"]},
                    "unit": "image",
                    "reference": pricing_data.get("reference", None),
                }
            case "Pricing Per Step":
                return {
                    "description": pricing_data["unit"],
                    "currency": "USD",
                    "price_data": {"price": parsed_pricing["price"]},
                    "unit": "step",
                    "reference": pricing_data.get("reference", None),
                }
            case _:
                raise RuntimeError(f"Unknown pricing unit {pricing_data['unit']}")

    def determine_service_type(
        self, model_name: str, pricing_data: Optional[Dict] = None
    ) -> str:
        """Determine service type based on model name and pricing unit"""
        model_lower = model_name.lower()

        # First, check pricing unit which is often a reliable indicator
        if pricing_data and "unit" in pricing_data:
            pricing_unit = pricing_data["unit"]
            if "image" in pricing_unit.lower():
                return "image_generation"
            elif "step" in pricing_unit.lower():
                return "image_generation"  # Step-based pricing is typically for image generation
            elif "token" in pricing_unit.lower():
                # Could be LLM, vision language model, or embedding model
                if any(keyword in model_lower for keyword in ["embedding", "embed"]):
                    return "embedding"
                elif any(
                    keyword in model_lower
                    for keyword in ["vision", "llava", "minicpm", "gpt-4-vision"]
                ):
                    return "vision_language_model"
                else:
                    return "llm"

        # Fallback to model name analysis
        # Embedding models
        if any(keyword in model_lower for keyword in ["embedding", "embed"]):
            return "embedding"

        # Image generation models
        if any(
            keyword in model_lower
            for keyword in [
                "flux",
                "dalle",
                "midjourney",
                "stable-diffusion",
                "controlnet",
            ]
        ):
            return "image_generation"

        # Vision language models
        if any(
            keyword in model_lower
            for keyword in ["vision", "llava", "minicpm", "gpt-4-vision"]
        ):
            return "vision_language_model"

        # Audio models
        if any(
            keyword in model_lower
            for keyword in ["whisper", "audio", "speech", "transcri"]
        ):
            return "prerecorded_transcription"  # Most common audio use case

        # Default to LLM for text models
        return "llm"

    def _extract_model_size(self, model_name: str) -> Optional[str]:
        """Extract model size from name (e.g., 7b, 13b, 70b)"""
        import re

        size_pattern = r"(\d+\.?\d*[bmk])"
        match = re.search(size_pattern, model_name.lower())
        return match.group(1) if match else None

    def create_service_data_structure(
        self,
        model_name: str,
        model_data: Dict,
        pricing_data: Optional[Dict],
        api_key: str,
    ) -> Dict:
        """Create a structured service configuration for the model"""

        # Determine the service type based on model name and pricing data
        service_type = self.determine_service_type(model_name, pricing_data)

        #  {
        #    "baseModelDetails":{
        #       "checkpointFormat":"NATIVE",
        #       "defaultPrecision":"FP16",
        #       "modelType":"",
        #       "moe":false,
        #       "parameterCount":"6000000000",
        #       "supportsFireattention":true,
        #       "supportsMtp":false,
        #       "tunable":false,
        #       "worldSize":1
        #    },
        #    "calibrated":false,
        #    "cluster":"",
        #    "contextLength":4096,
        #    "conversationConfig":{
        #       "style":"",
        #       "system":"",
        #       "template":""
        #    },
        #    "createTime":"2023-11-21T01:40:13.573799Z",
        #    "defaultDraftModel":"",
        #    "defaultDraftTokenCount":0,
        #    "defaultSamplingParams":{
        #       "temperature":1,
        #       "top_k":50,
        #       "top_p":1
        #    },
        #    "deployedModelRefs":[

        #    ],
        #    "deprecationDate":"None",
        #    "description":"The Yi series models are the next generation of open-source large language models trained from scratch by 01.AI. Targeted as a bilingual language model and trained on 3T multilingual corpus, the Yi series models become one of the strongest LLM worldwide, showing promise in language understanding, commonsense reasoning, reading comprehension, and more.",
        #    "displayName":"Yi 6B",
        #    "fineTuningJob":"",
        #    "githubUrl":"https://github.com/01-ai/Yi",
        #    "huggingFaceUrl":"https://huggingface.co/01-ai/Yi-6B",
        #    "importedFrom":"",
        #    "kind":"HF_BASE_MODEL",
        #    "name":"accounts/fireworks/models/yi-6b",
        #    "peftDetails":{
        #       "baseModel":"",
        #       "baseModelType":"",
        #       "mergeAddonModelName":"",
        #       "r":0,
        #       "targetModules":[

        #       ]
        #    },
        #    "public":true,
        #    "rlTunable":false,
        #    "state":"READY",
        #    "status":{
        #       "code":"OK",
        #       "message":""
        #    },
        #    "supportedPrecisions":[
        #       "FP16"
        #    ],
        #    "supportedPrecisionsWithCalibration":[

        #    ],
        #    "supportsImageInput":false,
        #    "supportsLora":true,
        #    "supportsTools":false,
        #    "teftDetails":"None",
        #    "trainingContextLength":0,
        #    "tunable":false,
        #    "updateTime":"2025-07-03T06:49:11.639169Z",
        #    "useHfApplyChatTemplate":false
        # }
        now = datetime.utcnow()
        timestamp = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        handled_model_fields = [
            "createTime",
            "description",
            "displayName",
            "name",
            "public",
            "state",
            "updateTime",
        ]
        header_fields = ["baseModelDetails"]
        base_mode_details_fields = [
            "checkpointFormat",
            "defaultPrecision",
            "modelType",
            "moe",
            "parameterCount",
            "supportsFireattention",
            "supportsMtp",
            "tunable",
            "worldSize",
        ]
        top_level_model_fields = [
            "calibrated",
            "cluster",
            "contextLength",
            "conversationConfig",  # dict
            "defaultDraftModel",
            "defaultDraftTokenCount",
            "defaultSamplingParams",  # dictionary
            "deployedModelRefs",  # list
            "deprecationDate",
            "fineTuningJob",
            "githubUrl",
            "huggingFaceUrl",
            "importedFrom",
            "kind",
            "peftDetails",  # a dictionary
            "rlTunable",
            "status",
            "supportedPrecisions",  # list
            "supportedPrecisionsWithCalibration",  # list
            "supportsImageInput",
            "supportsLora",
            "supportsTools",
            "teftDetails",
            "trainingContextLength",
            "tunable",
            "useHfApplyChatTemplate",
        ]
        service_config = {
            "schema": "service_v1",
            "time_created": model_data.get("createTime", timestamp),
            "name": model_name.split("/")[-1],
            # type of service to group services
            "service_type": service_type,
            # common display name for the service, allowing across provider linking
            "display_name": model_data.get("displayName", model_name.split("/")[-1]),
            "version": "",
            "description": model_data.get("description", ""),
            "upstream_status": model_data.get("state").lower(),
            "details": {},
            "upstream_access_interface": {},
            "upstream_price": {},
        }
        # top level details
        for field in top_level_model_fields:
            if field in model_data:
                service_config["details"][field] = model_data[field]

        for field in model_data.keys():
            if (
                field
                not in top_level_model_fields + handled_model_fields + header_fields
            ):
                print(f" {field} for model {model_name} is not processed.")

        # baseModelDetails
        if "baseModelDetails" in model_data:
            for field in base_mode_details_fields:
                if field in model_data["baseModelDetails"]:
                    service_config["details"][field] = model_data["baseModelDetails"][
                        field
                    ]
            for field in model_data["baseModelDetails"].keys():
                if field not in base_mode_details_fields:
                    print(f" {field} for model {model_name} is not processed.")

        # Add pricing information if available
        if pricing_data is not None:
            service_config["upstream_price"] = self.create_pricing_info_structure(
                pricing_data
            )
        elif service_config["upstream_status"] == "ready":
            # if no pricing information, the service cannot be ready
            service_config["upstream_status"] == "uploading"

        service_config["upstream_access_interface"] = {
            "name": "Fireworks API",
            "api_key": api_key,
            "api_endpoint": "https://api.fireworks.ai/inference/v1",
            "access_method": "http",
            "rate_limits": [
                {
                    "description": "Requests per minute",
                    "limit": 60,
                    "unit": "requests",
                    "window": "minute",
                },
                {
                    "description": "Input tokens per minute",
                    "limit": 60000,
                    "unit": "input_tokens",
                    "window": "minute",
                },
                {
                    "description": "Output tokens per minute",
                    "limit": 6000,
                    "unit": "output_tokens",
                    "window": "minute",
                },
            ],
        }
        return service_config

    def create_operation_data_structure(
        self,
        pricing_data: Optional[Dict],
        upstream_ready: bool,
    ) -> Dict:
        """Create a structured operation configuration for the model"""

        now = datetime.utcnow()
        timestamp = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        operation_config = {
            "schema": "listing_v1",
            "seller_name": "svcreseller",
            "time_created": timestamp,
            "listing_status": "upstream_ready" if upstream_ready else "unknown",
            # type of service to group services
            "user_access_interfaces": [],
            # common display name for the service, allowing across provider linking
            "user_price": {},
        }

        # Add pricing information if available
        if pricing_data is not None:
            pricing_info = self.create_pricing_info_structure(pricing_data)
            # For operations, we set user_price instead of upstream_price for the first case
            operation_config["user_price"] = pricing_info

        operation_config["user_access_interfaces"] = [
            {
                "name": "Provider API",
                "api_endpoint": "${GATEWAY_BASE_URL}/p/fireworks.ai",
                "access_method": "http",
                "documents": [
                    {
                        "title": "Python code example",
                        "description": "Example code to use the model",
                        "mime_type": "python",
                        "category": "code_examples",
                        "file_path": "../../docs/code_example.py",
                        "is_active": True,
                        "is_public": True,
                    },
                    {
                        "title": "Python function calling code example",
                        "description": "Example code to use the model",
                        "mime_type": "python",
                        "category": "code_examples",
                        "file_path": "../../docs/code_example_1.py",
                        "is_active": True,
                        "is_public": True,
                    },
                    {
                        "title": "JavaScript code example",
                        "description": "Example code to use the model",
                        "mime_type": "javascript",
                        "category": "code_examples",
                        "file_path": "../../docs/code_example.js",
                        "is_active": True,
                        "is_public": True,
                    },
                    {
                        "title": "cURL code example",
                        "description": "Example code to use the model",
                        "mime_type": "bash",
                        "category": "code_examples",
                        "file_path": "../../docs/code_example.sh",
                        "is_active": True,
                        "is_public": True,
                    },
                    {
                        "title": "How to use this model",
                        "description": "",
                        "mime_type": "markdown",
                        "category": "getting_started",
                        "file_path": "../../docs/description.md",
                        "is_active": True,
                        "is_public": True,
                    },
                ],
            }
        ]
        return operation_config

    def write_service_files(self, service_data, output_dir):
        """Write service.json file"""
        base_path = Path(output_dir)
        base_path.mkdir(parents=True, exist_ok=True)
        output_file = base_path / "service.json"

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(
                    service_data, f, sort_keys=True, indent=2, separators=(",", ": ")
                )
                f.write("\n")

            print(f"  ✅ Written: {output_file}")

        except Exception as e:
            print(f"  ❌ Error writing {output_file}: {e}")

    def write_operation_files(self, operation_data, output_dir):
        """Write listing-svcreseller.json file"""
        base_path = Path(output_dir)
        base_path.mkdir(parents=True, exist_ok=True)

        # Create shared examples directory
        shared_path = base_path / ".." / ".." / "docs"
        shared_path.mkdir(parents=True, exist_ok=True)

        output_file = base_path / "listing-svcreseller.json"

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(
                    operation_data, f, sort_keys=True, indent=2, separators=(",", ": ")
                )
                f.write("\n")

            print(f"  ✅ Written: {output_file}")

        except Exception as e:
            print(f"  ❌ Error writing {output_file}: {e}")

    def write_summary(self):
        """Write extraction summary"""
        try:
            print(f"   Total models: {self.summary['total_models']}")
            print(
                f"   Successful extractions: {self.summary['successful_extractions']}"
            )
            print(f"   Skipped models: {self.summary['skipped_models']}")
            print(f"   With pricing data: {self.summary['pricing_found']}")
            print(f"   Deprecated models: {len(self.summary['deprecated_models'])}")
            if self.summary["force_mode"]:
                print(f"   Force mode: Enabled")
            if self.summary["processing_limit"]:
                print(f"   Processing limit: {self.summary['processing_limit']}")

        except Exception as e:
            print(f"❌ Error writing summary: {e}")

    def mark_deprecated_services(
        self, output_dir: str, active_models: List[str], dry_run: bool = False
    ):
        """Mark services as deprecated if they no longer exist in active_models"""
        print("🔍 Checking for deprecated services...")

        base_path = Path(output_dir)
        if not base_path.exists():
            print(f"  ⚠️  Output directory {output_dir} does not exist")
            return

        # Convert active models to directory names for efficient lookup
        active_service_dirs = {
            model_name.split("/")[-1].replace(":", "_") for model_name in active_models
        }

        print(f"  Found {len(active_service_dirs)} active models")

        # Process all directories
        deprecated_count = 0
        for item in base_path.iterdir():
            if not item.is_dir():
                continue

            service_dir = item.name

            # Check if this service directory is still active
            if service_dir in active_service_dirs:
                continue  # Skip active services

            # This service is deprecated, process all JSON files in the directory
            deprecated_count += 1
            print(f"  🗑️  Processing deprecated service: {service_dir}")

            for json_file in item.glob("*.json"):
                try:
                    # Read and check schema
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    schema = data.get("schema")
                    updated = False

                    if schema == "service_v1":
                        # Update upstream_status to deprecated
                        current_status = data.get("upstream_status", "unknown")
                        if current_status != "deprecated":
                            data["upstream_status"] = "deprecated"
                            updated = True
                            status_msg = f"service upstream_status to deprecated"
                        else:
                            print(
                                f"    ⏭️  {json_file.name} service already marked as deprecated"
                            )

                    elif schema == "listing_v1":
                        # Update listing_status to upstream_deprecated
                        current_op_status = data.get("listing_status", "unknown")
                        if current_op_status != "upstream_deprecated":
                            data["listing_status"] = "upstream_deprecated"
                            updated = True
                            status_msg = (
                                f"operation operation_status to upstream_deprecated"
                            )
                        else:
                            print(
                                f"    ⏭️  {json_file.name} operation already marked as upstream_deprecated"
                            )
                    elif schema == "listing_v1":
                        # Update listing_status to upstream_deprecated
                        current_listing_status = data.get("listing_status", "unknown")
                        if current_listing_status != "upstream_deprecated":
                            data["listing_status"] = "upstream_deprecated"
                            updated = True
                            status_msg = (
                                f"listing listing_status to upstream_deprecated"
                            )
                        else:
                            print(
                                f"    ⏭️  {json_file.name} listing already marked as upstream_deprecated"
                            )

                    # Write updated file if changes were made
                    if updated:
                        if dry_run:
                            print(
                                f"    📝 [DRY-RUN] Would update {json_file.name} {status_msg}"
                            )
                        else:
                            with open(json_file, "w", encoding="utf-8") as f:
                                json.dump(
                                    data,
                                    f,
                                    sort_keys=True,
                                    indent=2,
                                    separators=(",", ": "),
                                )
                                f.write("\n")
                            print(f"    ✅ Updated {json_file.name} {status_msg}")

                except Exception as e:
                    print(f"    ❌ Error updating {json_file}: {e}")

        if deprecated_count == 0:
            print("  ✅ No deprecated services found")
        else:
            print(f"  🗑️  Processed {deprecated_count} deprecated services")

    def process_all_models(
        self,
        output_dir: str = "fireworks_services",
        specific_models: Optional[List[str]] = None,
        force: bool = False,
        limit: Optional[int] = None,
        dry_run: bool = False,
    ):
        """Main processing function"""
        print("🚀 Starting Fireworks.ai model extraction...\n")

        # Set force mode and limit in summary
        self.summary["force_mode"] = force
        self.summary["processing_limit"] = limit
        if dry_run:
            print(
                "🔍 Dry-run mode enabled - will show what would be done without writing files"
            )
        if force:
            print("💪 Force mode enabled - will overwrite all existing data files (service.json and listing-svcreseller.json)")

        if limit:
            print(f"🔢 Processing limit set to {limit} models")

        if specific_models:
            print(f"🎯 Processing specific models: {', '.join(specific_models)}")
            # Create mock model objects for specific models
            models = [{"name": model_name} for model_name in specific_models]
            self.summary["total_models"] = len(models)
        else:
            # Get all models
            models = self.get_all_models()
            if not models:
                print("❌ No models retrieved. Exiting.")
                return

            # Check for deprecated services when processing all models with force and no limit
            if force and limit is None:
                active_model_names = [
                    model.get("name", "") for model in models if model.get("name")
                ]
                self.mark_deprecated_services(output_dir, active_model_names, dry_run)

        # Process each model
        skipped_count = 0
        processed_count = 0
        for i, model_data in enumerate(models, start=1):
            model_name = model_data.get("name", "")
            if not model_name:
                continue

            print(f"\n[{i}/{len(models)}] Processing: {model_name}")

            # Check if we've reached the processing limit (not counting skipped models)
            if limit and processed_count >= limit:
                print(f"🔢 Reached processing limit of {limit} models, stopping...")
                break

            # Create expected directory path for this model
            base_path = Path(output_dir)
            dir_name = model_name.split("/")[-1].replace(":", "_")
            data_dir = base_path / dir_name
            data_file = data_dir / "service.json"

            # Check if model directory already exists
            if not force and data_dir.exists() and data_file.exists():
                print(
                    f"  ⏭️  Skipping {model_name} - service file already exists (use --force to overwrite)"
                )
                skipped_count += 1
                self.summary["skipped_models"] += 1
                continue

            # Increment processed count when we actually process a model
            processed_count += 1

            try:
                # Get pricing data
                try:
                    pricing_data = self.extract_pricing_from_page(model_name)
                    time.sleep(0.5)  # Rate limiting
                except Exception as e:
                    print(f"  ❌ Error parsing pricing page: {e}")
                    continue

                if pricing_data is None:
                    print(f"  ⚠️  No pricing data available")

                # Get API details
                model_data |= self.get_model_details(model_name)
                time.sleep(0.5)  # Rate limiting

                # Create service configuration
                service_config = self.create_service_data_structure(
                    model_name,
                    model_data,
                    pricing_data,
                    api_key,
                )

                # Create service configuration
                operation_config = self.create_operation_data_structure(
                    pricing_data,
                    service_config["upstream_status"] == "ready",
                )

                print(f"  📝 Generated service data")
                self.extracted_data[model_name] = service_config
                self.summary["successful_extractions"] += 1

                # Write service file
                if dry_run:
                    print(f"  📝 [DRY-RUN] Would write service files to {data_dir}")
                else:
                    print(f"  📝 Writing service files to {data_dir}...")
                    self.write_service_files(service_config, data_dir)

                # Write listing file
                listing_file = data_dir / "listing-svcreseller.json"
                if listing_file.exists() and not force:
                    print(
                        "  ⏭️  Skipping existing listing-svcreseller.json (use --force to overwrite)"
                    )
                    print(
                        "      💡 Manual customizations can be preserved in listing-svcreseller.override.json"
                    )
                else:
                    if dry_run:
                        action = "overwrite" if listing_file.exists() else "write"
                        print(f"  📝 [DRY-RUN] Would {action} listing files to {data_dir}")
                    else:
                        action = "Overwriting" if listing_file.exists() else "Writing"
                        print(f"  📝 {action} listing files to {data_dir}...")
                        self.write_operation_files(operation_config, data_dir)

                print(f"  ✅ Successfully processed {model_name}")

            except Exception as e:
                print(f"  ❌ Error processing {model_name}: {e}")
                self.summary["failed_extractions"] += 1

        # Write summary
        self.write_summary()

        print(f"\n🎉 Extraction complete! Check {output_dir}/ for results.")
        if skipped_count > 0:
            print(
                f"   ⏭️  Skipped {skipped_count} existing models (use --force to overwrite)"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract model data from Fireworks.ai API and pricing pages"
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default="services",
        help="Output directory for service files (default: fireworks_services)",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        help="Specific model names to process (e.g., --models accounts/fireworks/llama-v3p1-8b-instruct)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite all existing data files (service.json and listing-svcreseller.json). Without this flag, existing files will be skipped. Manual customizations can be preserved in .override.json files.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of models to process. Skipped models (when directories already exist) are not counted towards this limit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually writing files.",
    )

    args = parser.parse_args()

    # Get API key from command line argument or environment variable
    api_key = os.environ.get("FIREWORKS_API_KEY")
    api_base_url = os.environ.get("FIREWORKS_API_BASE_URL")
    model_base_url = os.environ.get("FIREWORKS_MODEL_BASE_URL")

    if not api_key:
        print(
            "❌ Error: No API key provided. Use --api-key or set FIREWORKS_API_KEY environment variable."
        )
        sys.exit(1)

    # Initialize extractor
    extractor = FireworksModelExtractor(api_key, api_base_url, model_base_url)

    # Process models (all or specific ones)
    extractor.process_all_models(
        args.output_dir,
        specific_models=args.models,
        force=args.force,
        limit=args.limit,
        dry_run=args.dry_run,
    )
