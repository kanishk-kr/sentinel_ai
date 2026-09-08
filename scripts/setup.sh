#!/bin/bash
set -e

echo "SENTINEL — Setup Script"
echo "Creating missing secrets in secrets/..."

mkdir -p secrets

# Function to create a 16-character random secret if file doesn't exist
generate_secret() {
    local file=$1
    if [ ! -f "$file" ]; then
        openssl rand -base64 16 > "$file"
        echo "Created secret: $file"
    else
        echo "Secret already exists: $file"
    fi
}

# Generate required Postgres secrets
generate_secret "secrets/postgres_password.txt"
generate_secret "secrets/postgres_owner_password.txt"

# Generate other secrets if missing (they might be configured via env vars, but good to have defaults)
generate_secret "secrets/jwt_secret.txt"
generate_secret "secrets/service_token_secret.txt"

# Create .gitkeep
touch secrets/.gitkeep

echo "Setup complete. You can now run 'docker-compose up --build'."
