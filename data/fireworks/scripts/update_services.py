#!/usr/bin/env python3
"""
Simplified update_services.py using unitysvc_services data builders.

Usage: scripts/update_services.py [--force]

This script demonstrates how OfferingDataBuilder and ListingDataBuilder simplify:
- Data structure creation with fluent API
- Automatic timestamp management
- Smart write() that skips unchanged files
"""

import os
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from unitysvc_services import ListingDataBuilder, OfferingDataBuilder

# Output directory relative to script location
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR.parent / "services"


class FireworksModelExtractor:
    """Extract model data from Fireworks.ai API and create service files."""

    def __init__(self, api_key: str, api_base_url: str, model_base_url: str):
        self.api_key = api_key
        self.api_base_url = api_base_url
        self.model_base_url = model_base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization":
            f"Bearer {api_key}",
            "User-Agent":
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        })
        self.stats = {
            "total": 0,
            "processed": 0,
            "skipped": 0,
            "failed": 0,
            "pricing_found": 0
        }

    def get_all_models(self) -> list[dict]:
        """Retrieve all models from Fireworks.ai API with pagination."""
        print("Fetching all models from Fireworks.ai API...")
        url = f"{self.api_base_url}/accounts/fireworks/models"
        all_models = []
        page_token = None

        while True:
            params = {"pageSize": 200}
            if page_token:
                params["pageToken"] = page_token

            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            page_models = data.get("models", [])
            if not page_models:
                break

            all_models.extend(page_models)
            page_token = data.get("nextPageToken")
            if not page_token:
                break

        print(f"Found {len(all_models)} models")
        return sorted(all_models, key=lambda x: x["name"])

    def get_model_details(self, model_name: str) -> dict | None:
        """Get detailed model information from API."""
        endpoint = f"{self.api_base_url}/{model_name}"
        try:
            response = self.session.get(endpoint, timeout=10)
            if response.status_code == 200:
                return response.json()
        except requests.RequestException:
            pass
        return None

    def extract_pricing(self, model_name: str) -> dict | None:
        """Extract pricing from model's web page."""
        clean_name = model_name.split("/")[-1]
        model_slug = clean_name.replace("/", "-").replace(":", "-").lower()
        pricing_url = f"{self.model_base_url}/{model_slug}"

        try:
            response = self.session.get(pricing_url, timeout=10)
            if response.status_code == 404:
                return None
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")
            container = soup.find("h3",
                                  string=re.compile(r"Available Serverless",
                                                    re.IGNORECASE))

            if container:
                parent = container.find_parent("div")
                if parent:
                    parent = parent.find_parent("div")
                if parent:
                    text = parent.get_text()

                    # Try input/cached_input/output pricing (new format)
                    # e.g., "$0.90 / $0.45 / $0.90 Per 1M Tokens (input/cached input/output)"
                    match = re.search(
                        r"\$\s*(\d+\.?\d*)\s*/\s*\$\s*(\d+\.?\d*)\s*/\s*\$\s*(\d+\.?\d*)\s*Per\s*\d+[MKmk]?\s*Tokens",
                        text, re.IGNORECASE)
                    if match:
                        self.stats["pricing_found"] += 1
                        return {
                            "type": "one_million_tokens",
                            "input": match.group(1),
                            "cached_input": match.group(2),
                            "output": match.group(3),
                            "description": f"Pricing Per 1M Tokens (input/cached input/output): ${match.group(1)} / ${match.group(2)} / ${match.group(3)}",
                            "reference": pricing_url,
                        }

                    # Try input/output pricing (legacy format)
                    # e.g., "$0.90 / $0.45 Per 1M Tokens (input/output)"
                    match = re.search(
                        r"\$\s*(\d+\.?\d*)\s*/\s*\$\s*(\d+\.?\d*)\s*Per\s*\d+[MKmk]?\s*Tokens",
                        text, re.IGNORECASE)
                    if match:
                        self.stats["pricing_found"] += 1
                        return {
                            "type": "one_million_tokens",
                            "input": match.group(1),
                            "output": match.group(2),
                            "description": f"Pricing Per 1M Tokens (input/output): ${match.group(1)} / ${match.group(2)}",
                            "reference": pricing_url,
                        }

                    # Try unified token pricing
                    match = re.search(
                        r"\$\s*(\d+\.?\d*)\s*Per\s*\d+[MKmk]?\s*Tokens", text,
                        re.IGNORECASE)
                    if match:
                        self.stats["pricing_found"] += 1
                        return {
                            "type": "one_million_tokens",
                            "price": match.group(1),
                            "description": f"Pricing Per 1M Tokens: ${match.group(1)}",
                            "reference": pricing_url,
                        }

                    # Try image pricing
                    match = re.search(r"\$\s*(\d+\.?\d*)\s*Per\s*Image", text,
                                      re.IGNORECASE)
                    if match:
                        self.stats["pricing_found"] += 1
                        return {
                            "type": "image",
                            "price": match.group(1),
                            "description": f"Pricing Per Image: ${match.group(1)}",
                            "reference": pricing_url,
                        }

                    # Try step pricing
                    match = re.search(r"\$\s*(\d+\.?\d*)\s*Per\s*Step", text,
                                      re.IGNORECASE)
                    if match:
                        self.stats["pricing_found"] += 1
                        return {
                            "type": "step",
                            "price": match.group(1),
                            "description": f"Pricing Per Step: ${match.group(1)}",
                            "reference": pricing_url,
                        }

        except requests.RequestException:
            pass

        return None

    def determine_service_type(self, model_name: str,
                               pricing: dict | None) -> str:
        """Determine service type from model name and pricing."""
        model_lower = model_name.lower()

        if pricing and pricing.get("type") in ("image", "step"):
            return "image_generation"

        if any(kw in model_lower for kw in ["embedding", "embed"]):
            return "embedding"
        if any(kw in model_lower
               for kw in ["flux", "dalle", "stable-diffusion"]):
            return "image_generation"
        if any(kw in model_lower for kw in ["vision", "llava", "minicpm"]):
            return "vision_language_model"
        if any(kw in model_lower for kw in ["whisper", "audio", "speech"]):
            return "prerecorded_transcription"

        return "llm"

    def build_offering(self, model_name: str, model_data: dict,
                       pricing: dict | None) -> OfferingDataBuilder:
        """Build offering using OfferingDataBuilder - MUCH SIMPLER!"""
        service_name = model_name.split("/")[-1]
        service_type = self.determine_service_type(model_name, pricing)

        # Start building with fluent API
        builder = (OfferingDataBuilder(service_name).set_description(
            model_data.get("description",
                           "")).set_service_type(service_type).set_status(
                               model_data.get("state",
                                              "draft").lower()).add_detail(
                                                  "model_name", model_name))

        # Set display name if available
        if model_data.get("displayName"):
            builder.set_display_name(model_data["displayName"])

        # Add details from model data (all top-level fields except handled ones)
        top_level_detail_fields = [
            "calibrated",
            "cluster",
            "contextLength",
            "defaultDraftModel",
            "defaultDraftTokenCount",
            "defaultSamplingParams",
            "deprecationDate",
            "fineTuningJob",
            "githubUrl",
            "huggingFaceUrl",
            "importedFrom",
            "kind",
            "rlTunable",
            "snapshotType",
            "supportedPrecisions",
            "supportedPrecisionsWithCalibration",
            "supportsImageInput",
            "supportsLora",
            "supportsTools",
            "teftDetails",
            "trainingContextLength",
            "tunable",
            "useHfApplyChatTemplate",
        ]
        for field in top_level_detail_fields:
            if field in model_data:
                builder.add_detail(field, model_data[field])

        # Add base model details
        if "baseModelDetails" in model_data:
            base_model_fields = [
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
            for field in base_model_fields:
                if field in model_data["baseModelDetails"]:
                    builder.add_detail(field,
                                       model_data["baseModelDetails"][field])

        # Set payout pricing - default to 100% revenue share
        builder.set_payout_price({
            "type": "revenue_share",
            "percentage": "100.00",
            "description": "No platform commission",
        })

        # Add upstream interface
        builder.add_upstream_interface(
            "Fireworks API",
            base_url="https://api.fireworks.ai/inference/v1",
            rate_limits=[
                {
                    "description": "Requests per minute",
                    "limit": 60,
                    "unit": "requests",
                    "window": "minute"
                },
                {
                    "description": "Input tokens per minute",
                    "limit": 60000,
                    "unit": "input_tokens",
                    "window": "minute"
                },
                {
                    "description": "Output tokens per minute",
                    "limit": 6000,
                    "unit": "output_tokens",
                    "window": "minute"
                },
            ],
        )

        # Preserve original creation time if available
        if model_data.get("createTime"):
            builder.set_raw("time_created", model_data["createTime"])

        return builder

    def build_listing(self, model_name: str, pricing: dict | None,
                      is_ready: bool) -> ListingDataBuilder:
        """Build listing using ListingDataBuilder - MUCH SIMPLER!"""
        service_name = model_name.split("/")[-1]
        is_flux = "flux" in model_name.lower()

        builder = (
            ListingDataBuilder().set_display_name(service_name).set_status(
                "ready" if is_ready else "draft").add_user_interface(
                    "Provider API",
                    base_url="${GATEWAY_BASE_URL}/p/fireworks.ai"))

        # Set list pricing from extracted pricing (with description and reference)
        if pricing:
            description = pricing.get("description")
            reference = pricing.get("reference")

            if pricing.get("type") == "one_million_tokens":
                if "input" in pricing and "output" in pricing:
                    builder.set_token_pricing(
                        input_price=pricing["input"],
                        output_price=pricing["output"],
                        cached_input_price=pricing.get("cached_input"),
                        description=description,
                        reference=reference,
                    )
                elif "price" in pricing:
                    builder.set_token_pricing(
                        unified_price=pricing["price"],
                        description=description,
                        reference=reference,
                    )
            elif pricing.get("type") == "image":
                builder.set_image_pricing(
                    pricing["price"],
                    description=description,
                    reference=reference,
                )
            elif pricing.get("type") == "step":
                builder.set_list_price({
                    "type": "step",
                    "price": pricing["price"],
                    "description": description,
                    "reference": reference,
                })

        # Add code examples based on model type
        if is_flux:
            examples = [
                ("Python code example", "../../docs/code_example_flux.py.j2",
                 "python"),
                ("Python function calling code example",
                 "../../docs/code_example_flux_fc.py.j2", "python"),
                ("JavaScript code example",
                 "../../docs/code_example_flux.js.j2", "javascript"),
                ("cURL code example", "../../docs/code_example_flux.sh.j2",
                 "bash"),
            ]
        else:
            examples = [
                ("Python code example", "../../docs/code_example.py.j2",
                 "python"),
                ("Python function calling code example",
                 "../../docs/code_example_1.py.j2", "python"),
                ("JavaScript code example", "../../docs/code_example.js.j2",
                 "javascript"),
                ("cURL code example", "../../docs/code_example.sh.j2", "bash"),
            ]

        for title, path, mime_type in examples:
            builder.add_code_example(
                title,
                path,
                mime_type=mime_type,
                description="Example code to use the model")

        # Add connectivity test (not public)
        test_path = "../../docs/connectivity_flux.sh.j2" if is_flux else "../../docs/connectivity.sh.j2"
        builder.add_document(
            "connectivity test",
            file_path=test_path,
            category="connectivity_test",
            mime_type="bash",
            description="Connectivity test",
            is_public=False,
        )

        return builder

    def process_model(self, model_name: str, output_dir: Path,
                      force: bool) -> bool:
        """Process a single model and write files."""
        dir_name = model_name.split("/")[-1].replace(":", "_")
        data_dir = output_dir / dir_name

        # Get model details
        model_data = self.get_model_details(model_name) or {}
        if not model_data.get("deployedModelRefs"):
            print("  No serverless deployment")
            return False

        # Get pricing
        pricing = self.extract_pricing(model_name)
        if not pricing:
            print("  No pricing found")
            return False

        # Build offering and listing using the builders
        offering = self.build_offering(model_name, model_data, pricing)
        listing = self.build_listing(model_name, pricing,
                                     model_data.get("state") == "READY")

        # Write files - the builder handles:
        # - Creating directories
        # - Preserving time_created
        # - Skipping if only timestamps differ
        offering_written = offering.write(data_dir / "offering.json",
                                          force=force)
        listing_written = listing.write(data_dir / "listing.json", force=force)

        status = []
        if offering_written:
            status.append("offering")
        if listing_written:
            status.append("listing")

        if status:
            print(f"  Written: {', '.join(status)}")
        else:
            print("  Unchanged")

        return True

    def run(self, force: bool = False):
        """Main processing function."""
        print("Starting Fireworks.ai model extraction...\n")

        models = self.get_all_models()
        if not models:
            print("No models to process.")
            return

        self.stats["total"] = len(models)

        for i, model in enumerate(models, 1):
            model_name = model.get("name", "")
            if not model_name:
                continue

            print(f"\n[{i}/{len(models)}] {model_name}")

            # Check if already exists (unless force mode)
            dir_name = model_name.split("/")[-1].replace(":", "_")
            if not force and (OUTPUT_DIR / dir_name /
                              "offering.json").exists():
                print("  Skipped - exists (use --force)")
                self.stats["skipped"] += 1
                continue

            if self.process_model(model_name, OUTPUT_DIR, force):
                self.stats["processed"] += 1
            else:
                self.stats["failed"] += 1

            time.sleep(0.5)  # Rate limiting

        print(f"\nDone! Total: {self.stats['total']}, "
              f"Processed: {self.stats['processed']}, "
              f"Skipped: {self.stats['skipped']}, "
              f"Failed: {self.stats['failed']}")


def main():
    force = "--force" in sys.argv

    api_key = os.environ.get("FIREWORKS_API_KEY")
    api_base_url = os.environ.get("FIREWORKS_API_BASE_URL")
    model_base_url = os.environ.get("FIREWORKS_MODEL_BASE_URL")

    if not api_key:
        print("Error: FIREWORKS_API_KEY not set")
        sys.exit(1)

    extractor = FireworksModelExtractor(api_key, api_base_url, model_base_url)
    extractor.run(force=force)


if __name__ == "__main__":
    main()
