# Nexus Manager

## 📝 Overview

Nexus Manager is a cross-platform tool for managing Nexus Repository and IQ Server, providing both a web interface, REST API, and CLI. It is distributed as a standalone executable for Windows, macOS, and Linux—no Python installation required.

---

## 📦 Using the Release Executable

### 1. Download & Extract

- Download the appropriate archive for your platform from the release page.
- Extract the archive. You will get a folder containing:
  - The executable (`nexus-manager` or `nexus-manager.exe`)
  - `config/` (configuration files)
  - `templates/` (web UI templates)
  - `pyproject.toml`
  - `README.md`

### 2. Configure Environment

- Copy `config/.env.example` to `config/.env` and fill in your server details and secrets.

### 3. Run the Application

- **Web UI:**
  - On Linux/macOS: `./nexus-manager`
  - On Windows: `nexus-manager.exe`
  - Access at `http://localhost:5000`
- **REST API:**
  - Same startup as Web UI, API endpoints available at `http://localhost:5000/api/`

---

## 🔌 REST API

### Base URL

```
http://localhost:5000/api
```

### Authentication

The REST API uses the same configuration as the web interface. Ensure your `.env` file is properly configured with Nexus and IQ Server credentials.

### Endpoints

#### 1. Health Check

```http
GET /api/health
```

**Response:**

```json
{
  "success": true,
  "status": "healthy",
  "version": "1.0.0"
}
```

#### 2. Get Configuration

```http
GET /api/config
```

**Response:**

```json
{
  "success": true,
  "data": {
    "organizations": [
      {
        "id": "org1",
        "name": "Organization 1",
        "chineseName": "組織一"
      }
    ],
    "package_managers": [
      "apt",
      "docker",
      "maven2",
      "npm",
      "nuget",
      "pypi",
      "yum"
    ],
    "shared_package_managers": ["npm", "maven2", "nuget", "yum", "raw"]
  }
}
```

#### 3. Create Repository

```http
POST /api/repository
Content-Type: application/json
```

**Request Body:**

```json
{
  "organization_id": "org1",
  "ldap_username": "john.doe",
  "package_manager": "npm",
  "shared": false,
  "app_id": "my-app"
}
```

**Request Fields:**

- `organization_id` (string, required): Organization ID for IQ Server role assignment
- `ldap_username` (string, required): LDAP username for repository access
- `package_manager` (string, required): Package manager type (npm, maven2, etc.)
- `shared` (boolean, optional): Whether to use shared repository (default: false)
- `app_id` (string, required if shared=false): Application ID for repository naming

**Response:**

```json
{
  "success": true,
  "data": {
    "action": "create",
    "repository_name": "npm-release-my-app",
    "ldap_username": "john.doe",
    "organization_id": "org1",
    "package_manager": "npm",
    "shared": false,
    "app_id": "my-app"
  },
  "message": "Successfully created repository and privileges."
}
```

#### 4. Delete Repository

```http
DELETE /api/repository
Content-Type: application/json
```

**Request Body:** Same as Create Repository

**Response:**

```json
{
  "success": true,
  "data": {
    "action": "delete",
    "repository_name": "npm-release-my-app",
    "ldap_username": "john.doe",
    "organization_id": "org1",
    "package_manager": "npm",
    "shared": false,
    "app_id": "my-app"
  },
  "message": "Successfully deleted repository and privileges."
}
```

#### 5. API Documentation

```http
GET /api/docs
```

Returns the complete API documentation in JSON format.

### Error Responses

All endpoints return consistent error responses:

```json
{
  "success": false,
  "error": "Error description"
}
```

Common HTTP status codes:

- `400`: Bad Request (missing required fields, invalid data)
- `500`: Internal Server Error (configuration issues, API failures)

### Example Usage

#### Using curl:

**Create a shared repository:**

```bash
curl -X POST http://localhost:5000/api/repository \
  -H "Content-Type: application/json" \
  -d '{
    "organization_id": "org1",
    "ldap_username": "john.doe",
    "package_manager": "npm",
    "shared": true
  }'
```

**Create an app-specific repository:**

```bash
curl -X POST http://localhost:5000/api/repository \
  -H "Content-Type: application/json" \
  -d '{
    "organization_id": "org1",
    "ldap_username": "john.doe",
    "package_manager": "maven2",
    "shared": false,
    "app_id": "my-java-app"
  }'
```

**Delete a repository:**

```bash
curl -X DELETE http://localhost:5000/api/repository \
  -H "Content-Type: application/json" \
  -d '{
    "organization_id": "org1",
    "ldap_username": "john.doe",
    "package_manager": "npm",
    "shared": false,
    "app_id": "my-app"
  }'
```

#### Using Python requests:

```python
import requests

# Configuration
api_base = "http://localhost:5000/api"

# Create repository
response = requests.post(f"{api_base}/repository", json={
    "organization_id": "org1",
    "ldap_username": "john.doe",
    "package_manager": "npm",
    "shared": False,
    "app_id": "my-app"
})

if response.status_code == 200:
    result = response.json()
    print(f"Success: {result['message']}")
else:
    error = response.json()
    print(f"Error: {error['error']}")
```

---

## 🎨 Customization

### Configuration

- All configuration is in the `config/` directory.
- Edit `config/.env` for environment variables (see `.env.example` for options).
- Edit `config/organisations.json` and `config/package_manager_config.json` for organization and package manager settings.

### Web Templates

- The web UI uses Jinja2 templates in the `templates/` directory.
- Customize `index.html` and `result.html` as needed.

---

## 🛠️ Codebase Maintenance

### Structure

- `nexus_manager.py`: Main entry point.
- `nexus_manager/`: Core logic and utilities.
  - `core.py`: Main business logic.
  - `utils.py`: Helper functions.
  - `error_handler.py`: Error handling.
- `config/`: Configuration files.
- `templates/`: Web UI templates.

### Adding Features

- Add new logic in `nexus_manager/` as needed.
- Register new CLI commands or web routes in `nexus_manager.py` or `core.py`.
- Update templates for UI changes.

### Dependency Management

- Dependencies are managed with [uv](https://github.com/astral-sh/uv) and listed in `pyproject.toml`.
- To add a dependency:
  1. Install [uv](https://github.com/astral-sh/uv) locally.
  2. Run `uv pip install <package>`.
  3. Update `pyproject.toml` and commit changes.

### Building the Executable

- Builds are automated via GitHub Actions.
- To build locally:
  1. Install [uv](https://github.com/astral-sh/uv) and [pyinstaller](https://pyinstaller.org/).
  2. Run the build command as in `.github/workflows/build-release.yml`.

---

## 💬 Support

- For issues, open a GitHub issue in this repository.
- For configuration help, see comments in `config/.env.example`.

---

## 📄 License

See `LICENSE` file (if present) for license information.
