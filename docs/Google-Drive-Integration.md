# Google Drive Integration Setup

This document explains how to configure Google Drive integration for file attachments in HyperAgent.

## Overview

HyperAgent supports multiple attachment sources:
- **Local files** - Upload files directly from your device
- **Google Drive** - Import files from your Google Drive
- **OneDrive** (Coming soon)
- **Dropbox** (Coming soon)

## Prerequisites

1. A Google Cloud Project
2. OAuth 2.0 credentials configured
3. Google Drive API enabled
4. Google Picker API enabled

## Setup Instructions

### 1. Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your project ID

### 2. Enable Required APIs

Enable the following APIs in your project:

1. **Google Drive API**
   - Go to APIs & Services → Library
   - Search for "Google Drive API"
   - Click "Enable"

2. **Google Picker API**
   - Search for "Google Picker API"
   - Click "Enable"

### 3. Configure OAuth Consent Screen

1. Go to APIs & Services → OAuth consent screen
2. Choose "External" user type (or "Internal" if using Google Workspace)
3. Fill in the application information:
   - App name: `HyperAgent`
   - User support email: Your email
   - Developer contact email: Your email
4. Add scopes:
   - `https://www.googleapis.com/auth/drive.readonly`
5. Add test users (for development)
6. Save and continue

### 4. Create OAuth 2.0 Credentials

1. Go to APIs & Services → Credentials
2. Click "Create Credentials" → "OAuth client ID"
3. Application type: "Web application"
4. Name: `HyperAgent Web Client`
5. Authorized JavaScript origins:
   - `http://localhost:3000` (development)
   - `https://yourdomain.com` (production)
6. Authorized redirect URIs:
   - `http://localhost:3000/api/auth/callback/google` (development)
   - `https://yourdomain.com/api/auth/callback/google` (production)
7. Click "Create"
8. **Save your Client ID and Client Secret**

### 5. Create API Key

1. Go to APIs & Services → Credentials
2. Click "Create Credentials" → "API key"
3. (Optional) Restrict the key:
   - Application restrictions: HTTP referrers
   - API restrictions: Google Drive API, Google Picker API
4. **Save your API Key**

### 6. Configure Environment Variables

Add the following to your `.env.local` file:

```bash
# Google OAuth (already configured for NextAuth)
GOOGLE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret_here

# Google Drive API (new)
NEXT_PUBLIC_GOOGLE_API_KEY=your_api_key_here
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
```

**Important Notes:**
- The `NEXT_PUBLIC_` prefix makes these variables available in the browser
- Use the same `GOOGLE_CLIENT_ID` for both NextAuth and the Picker
- The API key is safe to expose in the browser (when properly restricted)

### 7. Security Best Practices

1. **Restrict API Key:**
   - Limit to specific HTTP referrers (your domain)
   - Limit to specific APIs (Drive, Picker)

2. **OAuth Scopes:**
   - Use minimal scopes (`drive.readonly` for read-only access)
   - Request additional scopes only when needed

3. **Production Setup:**
   - Use environment-specific credentials
   - Enable Google's advanced protection
   - Monitor API usage in Google Cloud Console

## Usage

Once configured, users can:

1. Click the plus (+) icon in the chat input
2. Select "Google Drive" from the menu
3. Authorize the application (first time only)
4. Browse and select files from their Drive
5. Files are downloaded and attached to the message

## Current Limitations

- Maximum file size: 25MB (configurable)
- Supported file types: Documents, images, spreadsheets, code files
- Files are downloaded to the server before processing
- No streaming for large files (yet)

## Troubleshooting

### "Google Drive integration not configured"
- Check that `NEXT_PUBLIC_GOOGLE_API_KEY` and `NEXT_PUBLIC_GOOGLE_CLIENT_ID` are set
- Restart the development server after adding environment variables

### "Failed to initialize Google API"
- Verify API key is valid and not restricted too tightly
- Check browser console for detailed error messages
- Ensure Google Drive API and Picker API are enabled

### OAuth errors
- Verify redirect URIs match exactly (including http/https)
- Check that OAuth consent screen is published (or user is added as test user)
- Clear browser cache and cookies

### Permission denied
- User must grant `drive.readonly` permission
- Check OAuth consent screen configuration
- Verify user has access to the files they're trying to select

## Development vs Production

### Development
```bash
NEXT_PUBLIC_GOOGLE_API_KEY=dev_api_key
NEXT_PUBLIC_GOOGLE_CLIENT_ID=dev_client_id.apps.googleusercontent.com
```

### Production
```bash
NEXT_PUBLIC_GOOGLE_API_KEY=prod_api_key
NEXT_PUBLIC_GOOGLE_CLIENT_ID=prod_client_id.apps.googleusercontent.com
```

Use separate Google Cloud projects for development and production.

## Future Enhancements

- [ ] Direct streaming from Google Drive (no download)
- [ ] Folder selection support
- [ ] Shared drive support
- [ ] Real-time file updates
- [ ] Google Docs/Sheets export formats
- [ ] Caching frequently accessed files

## References

- [Google Picker API Documentation](https://developers.google.com/drive/picker)
- [Google Drive API Documentation](https://developers.google.com/drive/api)
- [OAuth 2.0 for Web Apps](https://developers.google.com/identity/protocols/oauth2/web-server)
