# File Storage Setup

This guide explains how to configure file storage for uploaded attachments in HyperAgent.

## Storage Backends

HyperAgent supports two file storage backends:

1. **Local Filesystem** (default for development)
2. **Cloudflare R2** (recommended for production)

## Quick Start (Development)

For local development, no additional configuration is needed! Files are stored in `./uploads` by default.

Just ensure your `api/.env` has:
```bash
STORAGE_BACKEND=local
```

That's it! You can now upload files and they'll be stored locally.

## Local Filesystem Storage

### Configuration

Add to `api/.env`:
```bash
STORAGE_BACKEND=local
LOCAL_STORAGE_PATH=./uploads  # Optional, defaults to ./uploads
```

### How it Works

- Files are stored in `{LOCAL_STORAGE_PATH}/{user_id}/{file_id}/{filename}`
- Example: `./uploads/a762ba19-1452-4097-be34-5317d8a21a16/123e4567-e89b-12d3-a456-426614174000/document.pdf`
- The `uploads/` directory is automatically created
- Files are automatically excluded from git (see `.gitignore`)

### Pros & Cons

**Pros:**
- ✅ Zero configuration needed
- ✅ No external dependencies
- ✅ Fast for development
- ✅ Free

**Cons:**
- ❌ Not suitable for production (no CDN, no scalability)
- ❌ Files are lost when server restarts (if using ephemeral storage)
- ❌ No built-in backup/redundancy

## Cloudflare R2 Storage (Production)

### What is R2?

Cloudflare R2 is S3-compatible object storage with:
- Zero egress fees
- Global CDN distribution
- 99.999999999% durability
- Affordable pricing ($0.015/GB/month)

### Setup Instructions

#### 1. Create R2 Bucket

1. Log in to [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Go to R2 → Create bucket
3. Name: `hyperagent` (or your preferred name)
4. Location: Auto (or choose specific region)
5. Click "Create bucket"

#### 2. Create API Token

1. In R2, go to "Manage R2 API Tokens"
2. Click "Create API token"
3. Permissions: "Object Read & Write"
4. Bucket: Select your `hyperagent` bucket
5. Click "Create API Token"
6. **Save the credentials** (shown only once):
   - Access Key ID
   - Secret Access Key
   - Endpoint URL (format: `https://[account-id].r2.cloudflarestorage.com`)

#### 3. Configure Environment

Add to `api/.env`:
```bash
STORAGE_BACKEND=r2
R2_ACCESS_KEY_ID=your_access_key_id_here
R2_SECRET_ACCESS_KEY=your_secret_access_key_here
R2_BUCKET_NAME=hyperagent
R2_ENDPOINT_URL=https://your-account-id.r2.cloudflarestorage.com
```

#### 4. Test the Configuration

Restart your API server and try uploading a file. Check the logs:
```
INFO     [app.services.file_storage] storage_backend backend='r2' bucket='hyperagent'
INFO     [app.services.file_storage] file_uploaded_r2 ...
```

### Pros & Cons

**Pros:**
- ✅ Production-ready
- ✅ Scalable (unlimited storage)
- ✅ Fast global delivery
- ✅ No egress fees
- ✅ Automatic backups

**Cons:**
- ❌ Requires Cloudflare account
- ❌ Costs money (but very cheap)
- ❌ Slightly more complex setup

## Troubleshooting

### Error: "Access Denied" when uploading to R2

**Cause:** Invalid credentials or insufficient permissions

**Solution:**
1. Verify `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY` are correct
2. Ensure API token has "Object Read & Write" permission
3. Check that the bucket name matches exactly
4. Verify endpoint URL is correct

### Error: "file_upload_failed_local"

**Cause:** Permission issues or disk full

**Solution:**
1. Check write permissions on `LOCAL_STORAGE_PATH`
2. Ensure sufficient disk space
3. Try using absolute path for `LOCAL_STORAGE_PATH`

### Files not appearing

**Check:**
1. Backend is correctly set: `echo $STORAGE_BACKEND` (should show "local" or "r2")
2. For local: Check `./uploads` directory exists and has files
3. For R2: Check Cloudflare dashboard → R2 → Your bucket → Objects
4. Check API logs for upload errors

### Cannot download files (local storage)

**Note:** Local storage returns paths like `/api/v1/files/download/{storage_key}`. You may need to implement a download endpoint for serving local files in production.

For development, files are in `./uploads/` and can be accessed directly.

## Migration Between Backends

### Local → R2

To migrate existing files from local to R2:

1. Upload local files to R2 manually:
   ```bash
   aws s3 sync ./uploads/ s3://hyperagent/ --endpoint-url https://your-account-id.r2.cloudflarestorage.com
   ```

2. Update database `storage_bucket` field from "local" to "hyperagent"

3. Switch backend: `STORAGE_BACKEND=r2`

### R2 → Local (Not Recommended)

For testing only:

1. Download R2 files:
   ```bash
   aws s3 sync s3://hyperagent/ ./uploads/ --endpoint-url https://your-account-id.r2.cloudflarestorage.com
   ```

2. Switch backend: `STORAGE_BACKEND=local`

## Best Practices

### Development
- Use `STORAGE_BACKEND=local` for faster iteration
- Don't commit uploaded files to git
- Periodically clean up `./uploads/` to save disk space

### Production
- Use `STORAGE_BACKEND=r2` for reliability
- Set up bucket lifecycle policies for automatic cleanup
- Enable bucket encryption
- Monitor storage usage in Cloudflare dashboard
- Set up alerts for quota limits

### Security
- Never commit R2 credentials to git
- Use environment variables for sensitive data
- Rotate R2 API tokens periodically
- Use restrictive IAM permissions (read/write only, no admin)

## Cost Estimation

### Local Storage
- **Cost:** $0 (uses server disk space)
- **Typical usage:** 1-10 GB

### Cloudflare R2
- **Storage:** $0.015/GB/month
- **Operations:** $4.50 per million writes, $0.36 per million reads
- **Egress:** $0 (free!)

**Example:** 100 GB storage + 1M operations/month = ~$6/month

## Support

For issues related to:
- **Local storage:** Check file permissions and disk space
- **R2 storage:** Contact Cloudflare support or check [R2 docs](https://developers.cloudflare.com/r2/)
- **HyperAgent integration:** Check application logs and this documentation
