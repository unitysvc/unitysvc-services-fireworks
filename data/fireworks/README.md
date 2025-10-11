# Fireworks AI Services

This directory contains service offerings from Fireworks AI.

## Provider Information

- **Provider Name:** Fireworks AI
- **Website:** https://fireworks.ai/
- **Documentation:** https://docs.fireworks.ai/
- **Contact:** support@fireworks.ai

## Provider Contact Summary

- **Contact Person:** Dhruv Iyer
- **Email:** dhruv@fireworks.ai
- **Date:** Wednesday, July 9, 2025
- **Time:** 11:30 AM – 11:40 AM (America/Chicago)
- **Type:** Online meeting
- **Result:** Fireworks allows for the reselling of tokens

## Services

All Fireworks AI services are located in the `services/` subdirectory. Each service includes:

- `service.json` - Service offering with technical specifications
- `listing-svcreseller.json` - Service listing for the marketplace

## Updating Services

Services are automatically updated via the populate services workflow, which runs daily at 2 AM UTC. The workflow:

1. Executes the `populate_services.py` script
2. Fetches the latest service information from Fireworks AI API
3. Updates service and listing files
4. Creates a pull request with the changes

To manually update services:

```bash
unitysvc_services populate
```
