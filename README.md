# NetBox Cloud to Catalyst Center Webhook Receiver

A Flask-based webhook receiver that synchronizes interface descriptions from NetBox Cloud to Cisco Catalyst Center. When an interface is updated in NetBox, this service automatically updates the corresponding interface in Catalyst Center.

## Overview

This application:
- Receives webhook notifications from NetBox Cloud when interfaces are updated
- Verifies webhook authenticity using HMAC-SHA512 signatures
- Extracts the Catalyst Center interface UUID and description from the webhook payload
- Authenticates with Catalyst Center and updates the interface description
- Runs in Docker with ngrok for public webhook exposure

## Prerequisites

- Docker and Docker Compose
- A NetBox Cloud instance with:
  - Custom field `catalyst_interface_uuid` on interface objects
  - Webhook configured to send interface update events
- Cisco Catalyst Center instance with API access
- ngrok account and authtoken (for receiving webhooks)

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/richbibby/nbx-cc-receiver.git
cd nbx-cc-receiver
```

### 2. Configure Environment Variables

Copy the example environment file and fill in your details:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```bash
# Catalyst Center connection
CC_HOST=https://your-catalyst-center-host
CC_USER=your-username
CC_PASS=your-password

# Webhook secret (must match NetBox Cloud webhook Secret)
NB_SECRET=your-webhook-secret

# TLS verification (set to false only if CC uses self-signed certs)
VERIFY_TLS=false

# Deployment mode for PUT operations (Deploy or Preview)
DEPLOYMENT_MODE=Deploy

# Interface API path selector
# - generic: Uses /interface/{id}
# - wireless: Uses /wirelessSettings/interfaces/{id}
INTERFACE_PATH=generic

# ngrok authentication token
NGROK_AUTHTOKEN=your-ngrok-authtoken-here
```

Get your ngrok authtoken from: https://dashboard.ngrok.com/get-started/your-authtoken

### 3. Configure ngrok (optional)

The `ngrok.yml` file is pre-configured and doesn't require changes. The authtoken is read from the `NGROK_AUTHTOKEN` environment variable in your `.env` file. If you need to customize ngrok settings, you can edit `ngrok.yml`

### 4. Start the Application

```bash
docker-compose up -d
```

Check the logs to get your ngrok public URL:

```bash
docker-compose logs ngrok
```

Look for a line like:
```
started tunnel  url=https://xxxx-xx-xx-xxx-xxx.ngrok-free.app
```

## NetBox Cloud Configuration

### 1. Create Custom Field

In NetBox Cloud, create a custom field for interfaces:
- **Name**: `catalyst_interface_uuid`
- **Type**: Text
- **Object Type**: dcim > interface
- **Description**: UUID of the corresponding Catalyst Center interface

### 2. Configure Webhook

Create a webhook in NetBox Cloud:
- **Name**: Catalyst Center Interface Sync
- **URL**: `https://your-ngrok-url.ngrok-free.app/netbox/interface-updated`
- **HTTP Method**: POST
- **HTTP Content Type**: application/json
- **Secret**: (same value as `NB_SECRET` in your `.env` file)
- **Events**:
  - dcim > interface > updated
- **Enabled**: ✓

### 3. Populate Interface Data

For each interface you want to sync:
1. Find the interface UUID in Catalyst Center
2. In NetBox, edit the interface and set the `catalyst_interface_uuid` custom field
3. Update the interface description in NetBox

## Usage

Once configured, the synchronization is automatic:

1. Update an interface description in NetBox Cloud
2. NetBox sends a webhook to your receiver
3. The receiver verifies the webhook signature
4. The receiver updates the corresponding interface in Catalyst Center

### API Endpoints

- `GET /` - Status message
- `GET /healthz` - Health check endpoint (returns "ok")
- `POST /netbox/interface-updated` - Webhook receiver endpoint

### Monitoring

View application logs:

```bash
docker-compose logs -f app
```

View ngrok logs:

```bash
docker-compose logs -f ngrok
```

## Configuration Options

### VERIFY_TLS

Set to `false` if your Catalyst Center uses self-signed certificates. For production environments, it's recommended to properly configure certificate trust instead.

### DEPLOYMENT_MODE

- `Deploy`: Immediately deploys the interface change
- `Preview`: Stages the change for review before deployment

### INTERFACE_PATH

- `generic`: Uses the standard interface API endpoint (`/interface/{id}`)
- `wireless`: Uses the wireless-specific endpoint (`/wirelessSettings/interfaces/{id}`)

## Troubleshooting

### Webhook not received

1. Check ngrok is running: `docker-compose ps`
2. Verify the ngrok URL is correct in NetBox webhook configuration
3. Check ngrok logs: `docker-compose logs ngrok`

### Signature verification fails

- Ensure `NB_SECRET` in `.env` matches the secret configured in NetBox webhook
- If testing without a secret, set `NB_SECRET=` (empty) in `.env`

### Catalyst Center authentication fails

- Verify `CC_HOST`, `CC_USER`, and `CC_PASS` are correct
- Check if the Catalyst Center user has API access permissions
- Review app logs: `docker-compose logs app`

### Interface not updating

- Ensure the `catalyst_interface_uuid` custom field is populated in NetBox
- Verify the UUID exists in Catalyst Center
- Check if `INTERFACE_PATH` is set correctly for your interface type
- Review app logs for Catalyst Center API responses

### Logs show "No-op: missing uuid/desc"

This means either:
- The interface doesn't have the `catalyst_interface_uuid` custom field set
- The webhook payload structure is unexpected

Check the logs for details about the payload structure received.

## Development

### Running without Docker

```bash
pip install flask requests
export $(cat .env | xargs)
python app.py
```

The app will run on `http://localhost:5100`

### Testing

You can test the webhook endpoint locally:

```bash
curl -X POST http://localhost:5100/netbox/interface-updated \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "description": "Test Interface Description",
      "custom_fields": {
        "catalyst_interface_uuid": "your-interface-uuid-here"
      }
    }
  }'
```

## License

This project is provided as-is for integration between NetBox Cloud and Cisco Catalyst Center.

## Support

For issues and questions, please open an issue on GitHub: https://github.com/richbibby/nbx-cc-receiver/issues
