#!/usr/bin/env python3
"""
Nexus Repository Manager: Web Interface Only.

Usage:
  nexus-manager                   # Start web interface (default)
  nexus-manager --help            # Show help
"""

import sys
import os
import argparse
import webbrowser
import time
import threading
from flask import Flask, render_template, request, flash, redirect, url_for, session, jsonify
from dotenv import load_dotenv
from nexus_manager.core import Config, PrivilegeManager
from nexus_manager.utils import load_json_file, parse_bool, parse_csv

# Determine application path
if getattr(sys, "frozen", False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

# Load environment variables
env_path = os.path.join(application_path, "config", ".env")
load_dotenv(env_path)

app = Flask(__name__, template_folder=os.path.join(application_path, "templates"))
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default-secret-key-change-me")


def load_configuration_data():
    """Load organizations and package manager config."""
    shared_pm_env = os.getenv("SHARED_PACKAGE_MANAGERS", "npm,maven2,nuget,yum,raw")
    shared_package_managers = parse_csv(shared_pm_env)
    config_dir = os.path.join(application_path, "config")
    organizations = load_json_file(
        os.path.join(config_dir, "organisations.json"), default=[]
    )
    pm_config = load_json_file(
        os.path.join(config_dir, "package_manager_config.json"),
        default={"supported_formats": {}},
    )
    supported_formats = pm_config.get("supported_formats", {})
    package_managers = sorted(
        [
            pm
            for pm in supported_formats
            if supported_formats[pm].get("proxy_supported")
            and supported_formats[pm].get("default_url")
        ]
    )
    shared_package_managers = [
        pm
        for pm in shared_package_managers
        if pm in supported_formats and supported_formats[pm].get("proxy_supported")
    ]
    return organizations, package_managers, shared_package_managers


@app.route("/set_language/<lang>")
def set_language(lang):
    """Set UI language."""
    if lang not in ["en-us", "zh-tw"]:
        lang = "en-us"
    session["lang"] = lang
    return redirect(request.args.get("next") or url_for("index"))


def get_lang():
    return session.get("lang", "en-us")


@app.route("/")
def index():
    """Show main form."""
    current_values = {
        "organization_id": os.getenv("ORGANIZATION_ID", ""),
        "ldap_username": os.getenv("LDAP_USERNAME", ""),
        "app_id": os.getenv("APP_ID", ""),
        "shared": parse_bool(os.getenv("SHARED", "false")),
        "package_manager": os.getenv(
            "PACKAGE_MANAGER", os.getenv("DEFAULT_PACKAGE_MANAGER", "apt")
        ),
    }
    organizations, package_managers, shared_package_managers = load_configuration_data()
    return render_template(
        "index.html",
        values=current_values,
        package_managers=package_managers,
        shared_package_managers=shared_package_managers,
        organizations=organizations,
        lang=get_lang(),
    )


@app.route("/process", methods=["POST"])
def process_form():
    """Process form and run operation."""
    try:
        organization_id = request.form.get("organization_id", "").strip()
        ldap_username = request.form.get("ldap_username", "").strip()
        app_id = request.form.get("app_id", "").strip()
        shared = request.form.get("shared") == "on"
        package_manager = request.form.get(
            "package_manager", os.getenv("DEFAULT_PACKAGE_MANAGER", "apt")
        )
        action = request.form.get("action", "create")
        lang = get_lang()
        if not organization_id:
            flash(
                {"en-us": "Organization ID is required", "zh-tw": "組織 ID 為必填項目"}[
                    lang
                ],
                "error",
            )
            return redirect(url_for("index"))
        if not ldap_username:
            flash(
                {"en-us": "LDAP Username is required", "zh-tw": "LDAP 帳號為必填項目"}[
                    lang
                ],
                "error",
            )
            return redirect(url_for("index"))
        if not shared and not app_id:
            flash(
                {
                    "en-us": "APP ID is required when not using shared repository",
                    "zh-tw": "未勾選共用倉庫時，APP ID 為必填項目",
                }[lang],
                "error",
            )
            return redirect(url_for("index"))
        # Always use frontend input for these values
        os.environ.update(
            {
                "ORGANIZATION_ID": organization_id,
                "LDAP_USERNAME": ldap_username,
                "APP_ID": app_id if app_id else "shared",
                "SHARED": "true" if shared else "false",
                "PACKAGE_MANAGER": package_manager,
            }
        )
        # Load .env.example to get the list of all possible config keys
        config_dir = os.path.join(application_path, "config")
        env_example_path = os.path.join(config_dir, ".env.example")
        possible_keys = set()
        if os.path.exists(env_example_path):
            with open(env_example_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key = line.split("=", 1)[0].strip()
                        possible_keys.add(key)

        def get_env_value(key, fallback=None):
            # Priority: .env > fallback, but only for keys listed in .env.example
            if key in possible_keys:
                return os.environ.get(key) or fallback
            return fallback

        # Get extra roles from environment variable EXTRA_ROLE (comma-separated)
        extra_role_env = get_env_value("EXTRA_ROLE", "")
        extra_roles = parse_csv(extra_role_env)
        # Use get_env_value for all config values that exist in .env.example
        action = action  # from form
        nexus_url = get_env_value("NEXUS_URL", "")
        nexus_username = get_env_value("NEXUS_dba7d9ddcbd04fc787b2bc81ec519b3bUSERNAME", "")
        nexus_password = get_env_value("NEXUS_PASSWORD", "")
        iqserver_url = get_env_value("IQSERVER_URL", "")
        iqserver_username = get_env_value("IQSERVER_USERNAME", "")
        iqserver_password = get_env_value("IQSERVER_PASSWORD", "")
        # Generate names based on user input
        if shared:
            repository_name = f"{package_manager}-release-shared".lower()
        else:
            repository_name = f"{package_manager}-release-{app_id}".lower()
        privilege_name = repository_name
        role_name = ldap_username
        pm_config = load_json_file(
            os.path.join(config_dir, "package_manager_config.json"),
            default={"supported_formats": {}},
        )
        supported_formats = pm_config.get("supported_formats", {})
        default_url = supported_formats.get(package_manager, {}).get("default_url", "")
        config = Config(
            action=action,
            nexus_url=nexus_url,
            nexus_username=nexus_username,
            nexus_password=nexus_password,
            iqserver_url=iqserver_url,
            iqserver_username=iqserver_username,
            iqserver_password=iqserver_password,
            ldap_username=ldap_username,
            organization_id=organization_id,
            remote_url=default_url,
            extra_roles=extra_roles,
            repository_name=repository_name,
            privilege_name=privilege_name,
            role_name=role_name,
            package_manager=package_manager,
        )
        manager = PrivilegeManager(config)
        result = {
            "action": action,
            "repository_name": config.repository_name,
            "ldap_username": config.ldap_username,
            "success": True,
            "message": {
                "en-us": f"Successfully {action}d repository and privileges.",
                "zh-tw": f"{('建立' if action == 'create' else '刪除')}倉庫與權限成功。",
            }[lang],
        }
        try:
            manager.run()
        except Exception as e:
            result["success"] = False
            result["message"] = str(e)
        return render_template("result.html", result=result, lang=lang)
    except Exception as e:
        lang = get_lang()
        flash(
            {
                "en-us": f"❌ Configuration error: {str(e)}",
                "zh-tw": f"❌ 設定錯誤: {str(e)}",
            }[lang],
            "error",
        )
        return redirect(url_for("index"))


# REST API Endpoints
@app.route("/api/config", methods=["GET"])
def api_get_config():
    """Get available configurations (organizations, package managers)."""
    try:
        organizations, package_managers, shared_package_managers = load_configuration_data()
        return jsonify({
            "success": True,
            "data": {
                "organizations": organizations,
                "package_managers": package_managers,
                "shared_package_managers": shared_package_managers
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/repository", methods=["POST"])
def api_create_repository():
    """Create a repository via REST API."""
    return _api_repository_operation("create")


@app.route("/api/repository", methods=["DELETE"])
def api_delete_repository():
    """Delete a repository via REST API."""
    return _api_repository_operation("delete")


def _api_repository_operation(action):
    """Handle repository operations via REST API."""
    try:
        # Validate content type
        if not request.is_json:
            return jsonify({
                "success": False,
                "error": "Content-Type must be application/json"
            }), 400

        data = request.get_json()
        
        # Validate required fields
        required_fields = ["organization_id", "ldap_username", "package_manager"]
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return jsonify({
                "success": False,
                "error": f"Missing required fields: {', '.join(missing_fields)}"
            }), 400

        organization_id = data.get("organization_id", "").strip()
        ldap_username = data.get("ldap_username", "").strip()
        app_id = data.get("app_id", "").strip()
        shared = data.get("shared", False)
        package_manager = data.get("package_manager", "").strip()

        # Validate shared/app_id logic
        if not shared and not app_id:
            return jsonify({
                "success": False,
                "error": "app_id is required when shared is false"
            }), 400

        # Set environment variables for the operation
        os.environ.update({
            "ORGANIZATION_ID": organization_id,
            "LDAP_USERNAME": ldap_username,
            "APP_ID": app_id if app_id else "shared",
            "SHARED": "true" if shared else "false",
            "PACKAGE_MANAGER": package_manager,
        })

        # Load configuration
        config_dir = os.path.join(application_path, "config")
        env_example_path = os.path.join(config_dir, ".env.example")
        possible_keys = set()
        
        if os.path.exists(env_example_path):
            with open(env_example_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key = line.split("=", 1)[0].strip()
                        possible_keys.add(key)

        def get_env_value(key, fallback=None):
            if key in possible_keys:
                return os.environ.get(key) or fallback
            return fallback

        # Get extra roles
        extra_role_env = get_env_value("EXTRA_ROLE", "")
        extra_roles = parse_csv(extra_role_env)

        # Get system configuration
        nexus_url = get_env_value("NEXUS_URL", "")
        nexus_username = get_env_value("NEXUS_USERNAME", "")
        nexus_password = get_env_value("NEXUS_PASSWORD", "")
        iqserver_url = get_env_value("IQSERVER_URL", "")
        iqserver_username = get_env_value("IQSERVER_USERNAME", "")
        iqserver_password = get_env_value("IQSERVER_PASSWORD", "")

        # Validate system configuration
        required_system_vars = {
            "NEXUS_URL": nexus_url,
            "NEXUS_USERNAME": nexus_username,
            "NEXUS_PASSWORD": nexus_password,
            "IQSERVER_URL": iqserver_url,
            "IQSERVER_USERNAME": iqserver_username,
            "IQSERVER_PASSWORD": iqserver_password,
        }
        
        missing_system_vars = [k for k, v in required_system_vars.items() if not v]
        if missing_system_vars:
            return jsonify({
                "success": False,
                "error": f"Missing system configuration: {', '.join(missing_system_vars)}"
            }), 500

        # Generate names
        if shared:
            repository_name = f"{package_manager}-release-shared".lower()
        else:
            repository_name = f"{package_manager}-release-{app_id}".lower()

        privilege_name = repository_name
        role_name = ldap_username

        # Load package manager config
        pm_config = load_json_file(
            os.path.join(config_dir, "package_manager_config.json"),
            default={"supported_formats": {}}
        )
        supported_formats = pm_config.get("supported_formats", {})
        default_url = supported_formats.get(package_manager, {}).get("default_url", "")

        if not default_url:
            return jsonify({
                "success": False,
                "error": f"No default URL configured for package manager: {package_manager}"
            }), 400

        # Create config object
        config = Config(
            action=action,
            nexus_url=nexus_url,
            nexus_username=nexus_username,
            nexus_password=nexus_password,
            iqserver_url=iqserver_url,
            iqserver_username=iqserver_username,
            iqserver_password=iqserver_password,
            ldap_username=ldap_username,
            organization_id=organization_id,
            remote_url=default_url,
            extra_roles=extra_roles,
            repository_name=repository_name,
            privilege_name=privilege_name,
            role_name=role_name,
            package_manager=package_manager,
        )

        # Execute operation
        manager = PrivilegeManager(config)
        manager.run()

        return jsonify({
            "success": True,
            "data": {
                "action": action,
                "repository_name": config.repository_name,
                "ldap_username": config.ldap_username,
                "organization_id": config.organization_id,
                "package_manager": config.package_manager,
                "shared": shared,
                "app_id": app_id if not shared else None
            },
            "message": f"Successfully {action}d repository and privileges."
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/health", methods=["GET"])
def api_health():
    """Health check endpoint."""
    return jsonify({
        "success": True,
        "status": "healthy",
        "version": "1.0.0"
    })


@app.route("/api/docs", methods=["GET"])
def api_docs():
    """API documentation endpoint."""
    return jsonify({
        "name": "Nexus Repository Manager API",
        "version": "1.0.0",
        "endpoints": {
            "GET /api/health": {
                "description": "Health check endpoint",
                "response": {
                    "success": "boolean",
                    "status": "string",
                    "version": "string"
                }
            },
            "GET /api/config": {
                "description": "Get available configurations",
                "response": {
                    "success": "boolean",
                    "data": {
                        "organizations": "array",
                        "package_managers": "array",
                        "shared_package_managers": "array"
                    }
                }
            },
            "POST /api/repository": {
                "description": "Create a repository",
                "request_body": {
                    "organization_id": "string (required)",
                    "ldap_username": "string (required)",
                    "package_manager": "string (required)",
                    "shared": "boolean (optional, default: false)",
                    "app_id": "string (required if shared is false)"
                },
                "response": {
                    "success": "boolean",
                    "data": "object",
                    "message": "string"
                }
            },
            "DELETE /api/repository": {
                "description": "Delete a repository",
                "request_body": "Same as POST /api/repository",
                "response": {
                    "success": "boolean",
                    "data": "object",
                    "message": "string"
                }
            },
            "GET /api/docs": {
                "description": "API documentation",
                "response": "This documentation"
            }
        }
    })


def open_browser(host, port):
    """Open browser after server starts."""
    time.sleep(1.5)
    webbrowser.open(f"http://{host}:{port}")


def run_web_interface():
    """Start Flask web interface."""
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    auto_open = os.getenv("AUTO_OPEN_BROWSER", "true").lower() == "true"
    print("🚀 Starting Nexus Repository Manager Web Interface...")
    print(f"📍 Server: http://{host}:{port}")
    print(f"🔌 REST API: http://{host}:{port}/api/")
    print("💡 Press Ctrl+C to stop the server")
    if auto_open and host in ["127.0.0.1", "localhost", "0.0.0.0"]:
        browser_thread = threading.Thread(
            target=open_browser, args=("127.0.0.1" if host == "0.0.0.0" else host, port)
        )
        browser_thread.daemon = True
        browser_thread.start()
    try:
        app.run(debug=debug, host=host, port=port, use_reloader=False)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)


def main():
    """Main entry: always start web interface."""
    parser = argparse.ArgumentParser(
        description="Nexus Repository Manager - Web Interface Only",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  nexus-manager                    # Start web interface (default)

Environment Variables:
  PORT                 # Web server port (default: 5000)
  FLASK_HOST           # Web server host (default: 127.0.0.1)
  AUTO_OPEN_BROWSER    # Auto-open browser (default: true)
  FLASK_DEBUG          # Enable debug mode (default: false)

Configuration:
  Place your .env file in the config/ directory with your Nexus settings.
        """,
    )
    parser.add_argument(
        "--version", action="version", version="Nexus Repository Manager v1.0.0"
    )
    # Ignore all positional arguments, always start web interface
    run_web_interface()


if __name__ == "__main__":
    main()
