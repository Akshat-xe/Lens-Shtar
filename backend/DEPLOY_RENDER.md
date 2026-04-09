# Deploy Lens Shtar Backend to Render

## Quick Start (5 Minutes)

### 1. Push to GitHub
```bash
git add .
git commit -m "Backend ready for Render deployment"
git push origin main
```

### 2. Create Render Web Service
1. Go to [render.com](https://render.com)
2. Click "New +" -> "Web Service"
3. Connect your GitHub repository
4. Select the `backend` folder as root directory
5. Choose "Python" runtime
6. Use these settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python start.py`
   - **Health Check Path**: `/api/health`

### 3. Set Environment Variables in Render
Copy these exact values to your Render dashboard:

```
SUPABASE_URL=https://tgmvethwaquialwxenld.supabase.co
SUPABASE_ANON_KEY=sb_publishable_QVxcf5DEQufi3bdpxlNtYg_aT9kI4o3
SUPABASE_JWT_SECRET=your-jwt-secret-from-supabase
SUPABASE_JWT_AUDIENCE=authenticated
CORS_ORIGINS=https://lens-flow.shtar.space,http://localhost:5173,http://127.0.0.1:5173
SESSION_INACTIVITY_SECONDS=2700
VIDEO_PLACEHOLDER_ENABLED=true
MAX_UPLOAD_MB=50
GEMINI_MODEL=gemini-2.0-flash
GEMINI_TIMEOUT_SECONDS=120
GEMINI_AI_SUMMARY_ENABLED=true
```

### 4. Deploy
Click "Create Web Service" - Render will automatically deploy.

### 5. Get Your Backend URL
After deployment, Render will give you a URL like:
`https://lens-shtar-api.onrender.com`

### 6. Update Frontend
In your frontend `app.js`, update the API base:
```javascript
const API_BASE = "https://lens-shtar-api.onrender.com";
```

## Required Environment Variables

| Variable | Required? | Description |
|----------|-----------|-------------|
| `SUPABASE_URL` | YES | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | YES | Your Supabase anonymous key |
| `SUPABASE_JWT_SECRET` | YES | Your Supabase JWT secret |
| `SUPABASE_JWT_AUDIENCE` | YES | Usually "authenticated" |
| `CORS_ORIGINS` | YES | Comma-separated frontend URLs |
| `SESSION_INACTIVITY_SECONDS` | NO | Session timeout (default: 2700) |
| `VIDEO_PLACEHOLDER_ENABLED` | NO | Enable video placeholder (default: true) |
| `MAX_UPLOAD_MB` | NO | Max file size (default: 50) |
| `GEMINI_MODEL` | NO | AI model (default: gemini-2.0-flash) |
| `GEMINI_TIMEOUT_SECONDS` | NO | AI timeout (default: 120) |
| `GEMINI_AI_SUMMARY_ENABLED` | NO | Enable AI summaries (default: true) |

## Supabase Configuration

### Get JWT Secret
1. Go to your Supabase project
2. Settings -> API
3. Copy the "JWT Secret" value

### Set Auth Redirect URL
1. Supabase -> Authentication -> URL Configuration
2. Add: `https://lens-flow.shtar.space/auth/callback`

## Endpoints

All endpoints are production-ready:

- `GET /api/health` - Health check
- `POST /api/settings/set-api-key` - Save Gemini API key
- `GET /api/settings/status` - Get API key status
- `POST /api/settings/clear-api-key` - Clear API key
- `POST /api/upload` - Upload and analyze file
- `GET /api/dashboard/{file_id}` - Get dashboard data

## Testing Your Deployment

### 1. Health Check
```bash
curl https://your-backend-url.onrender.com/api/health
```
Should return: `{"status": "ok"}`

### 2. Test Full Flow
1. Open your frontend
2. Sign in with Google
3. Add Gemini API key in settings
4. Upload a PDF/CSV file
5. Check dashboard shows real data

## Troubleshooting

### "Failed to fetch" Errors
- Check CORS origins include your frontend URL
- Verify environment variables are set correctly
- Check Render logs for errors

### Upload Fails
- Verify file size is under 50MB
- Check Gemini API key is valid
- Check Render logs for processing errors

### Auth Issues
- Verify Supabase JWT secret is correct
- Check Supabase project URL and anon key
- Ensure frontend uses correct Supabase config

## Production Checklist

- [ ] Backend deployed to Render
- [ ] All environment variables set
- [ ] Health check endpoint working
- [ ] CORS configured for production domain
- [ ] Supabase JWT secret configured
- [ ] Frontend API base URL updated
- [ ] Full user flow tested end-to-end
- [ ] Error handling verified
- [ ] File upload tested successfully

## Security Notes

- Never commit real secrets to git
- Use environment variables for all sensitive data
- API keys are stored in session only (never in database)
- JWT verification protects all endpoints
- CORS restricts access to approved origins

## Support

If you encounter issues:
1. Check Render logs
2. Verify environment variables
3. Test health endpoint
4. Check CORS configuration
5. Verify Supabase settings
