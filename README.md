# UnitySVC Services - Fireworks

Service data repository for Fireworks digital services on the UnitySVC platform.

This repository hosts and manages Fireworks service offerings with **automated population** from the Fireworks API and automated validation/upload workflows.

**[Full Documentation](https://unitysvc-services.readthedocs.io)** | **[Getting Started Guide](https://unitysvc-services.readthedocs.io/en/latest/getting-started/)** | **[CLI Reference](https://unitysvc-services.readthedocs.io/en/latest/cli-reference/)**

## Key Feature: Automated Service Population

This repository uses `usvc data populate` to automatically fetch and update service data from the Fireworks API. A GitHub Actions workflow runs daily to:

1. Execute the populate script defined in `provider.toml`
2. Generate/update service offering and listing files
3. Create a pull request with any changes for review

This ensures the service catalog stays in sync with the Fireworks API without manual intervention.

## Quick Start

### Install unitysvc-services CLI

```bash
pip install unitysvc-services
```

See the [CLI Reference](https://unitysvc-services.readthedocs.io/en/latest/cli-reference/) for all available commands.

### Validate and Format Data

Before committing changes:

```bash
# Validate all files
usvc data validate

# Format files to match requirements
usvc data format
```

## Repository Structure

```
data/
└── fireworks/                       # Provider directory
    ├── provider.toml                # Provider metadata + populate config
    ├── scripts/
    │   └── update_services.py       # Populate script
    └── services/                    # Service definitions
        └── ${service_name}/
            ├── offering.json        # Service offering (technical specs)
            └── listing-*.json       # Service listing (user-facing info)
```

See [Data Structure Documentation](https://unitysvc-services.readthedocs.io/en/latest/data-structure/) for complete details.

## GitHub Actions Workflows

This repository includes automated workflows to streamline the development process:

### 1. Populate Services Workflow

**File**: `.github/workflows/populate-services.yml`
**Triggers**:

- Daily at 2 AM UTC (scheduled)
- Manual trigger via GitHub Actions UI

Automatically updates Fireworks service data by:

1. Running `usvc data populate` to execute the provider's update script
2. Formatting generated files
3. Creating a pull request with changes (if any)

**How It Works**:

The workflow uses the `services_populator` configuration in `provider.toml`:

```toml
# data/fireworks/provider.toml
[services_populator]
command = ['scripts/update_services.py', '--force']

[services_populator.envs]
FIREWORKS_API_KEY = 'your-api-key'
FIREWORKS_API_BASE_URL = "https://api.fireworks.ai/v1"
```

The `usvc data populate` command will:

- Find all providers with `services_populator` configured
- Execute the specified command (e.g., `scripts/update_services.py`)
- Pass environment variables from `services_populator.envs`
- Generate/update service files automatically

**Running Populate Locally**:

```bash
# Populate all providers
usvc data populate

# Populate specific provider
usvc data populate --provider fireworks

# Dry-run to preview what would be executed
usvc data populate --dry-run
```

See [Automated Workflow Documentation](https://unitysvc-services.readthedocs.io/en/latest/workflows/#automated-workflow) for details on writing populate scripts.

### 2. Validate Data Workflow

**File**: `.github/workflows/validate-data.yml`
**Triggers**: Every pull request and push to main

Automatically validates all data files to ensure:

- Schema compliance
- File references exist
- Directory name consistency
- Valid data structure

This prevents invalid data from being merged.

### 3. Format Check Workflow

**File**: `.github/workflows/format-check.yml`
**Triggers**: Every pull request and push to main

Checks that all JSON and TOML files are properly formatted:

- JSON files have 2-space indentation
- Keys are sorted alphabetically
- Files end with newlines
- No trailing whitespace

Run `usvc data format` locally to auto-fix formatting issues.

### 4. Upload Data Workflow

**File**: `.github/workflows/publish-data.yml`
**Triggers**: Push to main branch (after PR merge)

Automatically uploads data to the UnitySVC backend. Services are uploaded atomically (provider + offering + listing together).

**Setup Required**: Configure GitHub secrets (see below).

## GitHub Secrets Configuration

To enable automatic uploading when changes are merged to `main`, configure the following GitHub secrets:

### Step 1: Navigate to Repository Settings

1. Go to your repository on GitHub
2. Click **Settings** tab
3. In the left sidebar, click **Secrets and variables** -> **Actions**

### Step 2: Add Secrets

Click **New repository secret** and add the following:

#### `UNITYSVC_BASE_URL`

- **Description**: The UnitySVC backend API URL
- **Example values**:
  - Production: `https://api.unitysvc.com/v1`

#### `UNITYSVC_API_KEY`

- **Description**: API key for authenticating with the UnitySVC backend
- **How to obtain**:
  1. Log in to the UnitySVC platform (username should match the "seller" in service listings)
  2. Navigate to **Settings** -> **API Keys**
  3. Generate a new API key for your organization
  4. Copy the key (you won't be able to see it again)

### Step 3: Verify Configuration

After adding the secrets:

1. Make a change to a file in the `data/` directory
2. Create a pull request
3. Merge the pull request to `main`
4. Check the **Actions** tab to see the upload workflow run
5. Verify that data appears on your UnitySVC backend

## Development Workflow

### Common Commands

```bash
# Validate data locally
usvc data validate

# Format data files
usvc data format

# Populate services from provider API
usvc data populate

# List local data
usvc data list

# Upload manually (optional - usually done via CI/CD)
export UNITYSVC_BASE_URL="https://api.unitysvc.com/v1"
export UNITYSVC_API_KEY="your-api-key"
usvc services upload
```

### Service Lifecycle Management

After uploading, manage service status:

```bash
# List uploaded services
usvc services list

# Submit a draft service for review
usvc services submit <service-id>

# Deprecate an active service
usvc services deprecate <service-id>

# Withdraw a submitted service back to draft
usvc services withdraw <service-id>
```

For complete CLI documentation, see [CLI Reference](https://unitysvc-services.readthedocs.io/en/latest/cli-reference/).

### Pre-commit Hooks (Recommended)

Install pre-commit hooks to automatically validate and format files before each commit:

```bash
pip install pre-commit
pre-commit install
```

The hooks will automatically format JSON files and validate data on every commit.

## Contributing

1. Create a new branch for your changes
2. Make your changes to files in the `data/` directory
3. Run `usvc data validate` to check your changes
4. Run `usvc data format` to format files
5. Commit your changes (pre-commit hooks will run automatically)
6. Push your branch and create a pull request
7. Once approved and merged, data will be automatically uploaded

## Documentation

For detailed information:

- **[Getting Started](https://unitysvc-services.readthedocs.io/en/latest/getting-started/)** - Installation and first steps
- **[Data Structure](https://unitysvc-services.readthedocs.io/en/latest/data-structure/)** - File organization rules
- **[Workflows](https://unitysvc-services.readthedocs.io/en/latest/workflows/)** - Manual and automated patterns
- **[CLI Reference](https://unitysvc-services.readthedocs.io/en/latest/cli-reference/)** - All commands and options
- **[File Schemas](https://unitysvc-services.readthedocs.io/en/latest/file-schemas/)** - Schema specifications

## Support

For issues or questions:

- **UnitySVC Services SDK**: https://github.com/unitysvc/unitysvc-services
- **Documentation**: https://unitysvc-services.readthedocs.io
- **Issues**: Open an issue in this repository

## License

This repository is provided under the MIT License. Service data is subject to respective provider licensing terms.
