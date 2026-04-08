# Lens Shtar - Manual Testing Checklist

## Prerequisites
- Backend server running on `http://127.0.0.1:8000` (or configured API base)
- Frontend served from `http://localhost:3000` or production domain
- Supabase project configured with OAuth

## Authentication Flow Tests
- [ ] Sign in with Google from home page
- [ ] Verify account menu appears in navbar
- [ ] Click account menu - dropdown opens correctly
- [ ] Verify user name and email displayed
- [ ] Sign out from account menu
- [ ] Verify redirected to home page
- [ ] Sign in again - session restored

## Navigation Tests
- [ ] Home → Dashboard (authenticated user)
- [ ] Home → Dashboard (unauthenticated user) - should prompt sign in
- [ ] Dashboard → Settings
- [ ] Settings → Dashboard
- [ ] Dashboard → Upload (via button)
- [ ] Upload → Dashboard (after successful upload)
- [ ] All navigation works on mobile/tablet/desktop

## Settings Page Tests
- [ ] Settings page loads correctly when authenticated
- [ ] Account summary shows user info
- [ ] API key status displays correctly
- [ ] Save valid Gemini API key - success message
- [ ] Clear API key - success message
- [ ] Invalid API key - error message
- [ ] Backend unreachable - clear error message
- [ ] All buttons work on touch devices

## Upload Flow Tests
- [ ] Upload without auth - prompts sign in
- [ ] Upload without API key - redirects to settings with message
- [ ] File type validation (PDF, CSV, XLS, XLSX)
- [ ] File size validation (50MB limit)
- [ ] Successful upload shows progress states
- [ ] Success message shows transaction count
- [ ] Auto-redirect to dashboard after success
- [ ] Dashboard shows uploaded data
- [ ] Drag & drop functionality works
- [ ] Mobile file picker works

## Dashboard Tests
- [ ] Dashboard loads with real data after upload
- [ ] KPI cards show correct values
- [ ] Money leaks section populates
- [ ] Suggestions section populates
- [ ] Transactions list shows data
- [ ] Mobile sidebar toggle works
- [ ] Navigation links work correctly
- [ ] Settings button works from dashboard

## Error Handling Tests
- [ ] Network errors show clear messages
- [ ] CORS errors handled gracefully
- [ ] Invalid session redirects appropriately
- [ ] Backend offline shows helpful message
- [ ] File upload errors handled properly

## Responsive Design Tests
- [ ] Mobile (< 428px) - all actions accessible
- [ ] Tablet (428px - 834px) - layout adapts correctly
- [ ] Desktop (> 834px) - full experience
- [ ] Account dropdown works on all screen sizes
- [ ] Touch interactions work on mobile
- [ ] No horizontal scroll on any page

## Cross-browser Tests
- [ ] Chrome/Chromium - full functionality
- [ ] Firefox - full functionality
- [ ] Safari - full functionality
- [ ] Edge - full functionality

## Performance Tests
- [ ] Page load times under 3 seconds
- [ ] Upload progress updates smoothly
- [ ] No layout shifts during loading
- [ ] Smooth transitions between states
