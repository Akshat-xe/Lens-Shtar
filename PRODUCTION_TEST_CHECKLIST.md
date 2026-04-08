# Lens Shtar - Production Test Checklist

## Critical User Flow Test

### 1. Authentication Flow
- [ ] Open site → Click "Sign in with Google"
- [ ] Supabase OAuth completes → Redirect to dashboard
- [ ] Navbar updates → Shows account dropdown
- [ ] Account menu displays user info correctly
- [ ] Sign out works → Resets UI completely

### 2. Settings & API Key Management
- [ ] Navigate to settings from account menu
- [ ] Settings page loads with user info
- [ ] Enter valid Gemini API key → Save succeeds
- [ ] Status shows "Gemini key is active in current session"
- [ ] Clear API key → Status shows "No Gemini key configured"
- [ ] Error handling works for invalid keys
- [ ] Backend unreachable shows clear error message

### 3. Upload Flow
- [ ] Navigate to upload section
- [ ] File picker opens for PDF/CSV/XLSX
- [ ] File validation works (size, type)
- [ ] Upload without API key → Redirects to settings with message
- [ ] Upload without auth → Starts sign-in flow
- [ ] Valid upload → Shows progress states
- [ ] Success → Shows transaction count and leak count
- [ ] Auto-redirect to dashboard after 1 second

### 4. Dashboard Data Display
- [ ] Dashboard loads with real backend data
- [ ] KPI cards show actual numbers
- [ ] Money leaks list shows real data
- [ ] Suggestions show real AI insights
- [ ] Transactions list shows real data
- [ ] Charts are data-driven (no demo data)
- [ ] Empty states work when no data

### 5. Navigation Loop
- [ ] Home ↔ Dashboard works smoothly
- [ ] Dashboard ↔ Settings works smoothly
- [ ] Settings ↔ Account menu works
- [ ] Account menu ↔ Upload works
- [ ] No unexpected redirects to index.html
- [ ] All navigation uses relative paths

### 6. Mobile/Tablet Testing
- [ ] Account dropdown works on touch devices
- [ ] Upload flow works on mobile
- [ ] Settings page works on tablet
- [ ] Dashboard responsive on all screen sizes
- [ ] Touch targets are 44px minimum
- [ ] No horizontal scroll on mobile

### 7. Error Handling
- [ ] Backend offline shows clear message
- [ ] CORS errors handled gracefully
- [ ] Network timeouts show user feedback
- [ ] Invalid sessions redirect appropriately
- [ ] File upload errors are specific

### 8. Production Configuration
- [ ] Backend CORS includes production domain
- [ ] API base URL configurable
- [ ] Supabase URLs are correct
- [ ] Environment variables documented

## Backend Verification

### Required Endpoints
- [ ] POST /api/settings/set-api-key ✅
- [ ] GET /api/settings/status ✅
- [ ] POST /api/settings/clear-api-key ✅
- [ ] POST /api/upload ✅
- [ ] GET /api/dashboard/{file_id} ✅
- [ ] GET /api/health ✅

### Session Management
- [ ] API keys stored in session only (no localStorage)
- [ ] JWT validation works correctly
- [ ] Session expiration handled
- [ ] Cross-tab auth sync works

### File Processing
- [ ] PDF parsing with Gemini works
- [ ] CSV/XLSX parsing works
- [ ] File size limit enforced (50MB)
- [ ] File type validation works
- [ ] Error handling for malformed files

## Final Verification Steps

1. **Start Fresh**: Clear all localStorage/session
2. **Full Flow**: Complete steps 1-7 above
3. **Cross-browser**: Test in Chrome, Firefox, Safari
4. **Production URLs**: Test with production backend
5. **Stress Test**: Multiple rapid actions
6. **Error Scenarios**: Network failures, invalid data

## Success Criteria

✅ All 15 critical user flow steps work
✅ All 5 backend endpoints respond correctly
✅ All 3 device categories work properly
✅ All error scenarios handled gracefully
✅ Production configuration is correct
✅ No console errors in production
✅ Smooth transitions and premium feel maintained
