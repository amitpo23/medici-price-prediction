# Medici Hotels - GitHub Repository Documentation

> **OnlyNight-LTD**  
> 9 Repositories | 2 Active Projects  
> Last Updated: January 13, 2026

---

## 🏢 GitHub Organization Overview

| Property | Value |
|----------|-------|
| Organization | OnlyNight-LTD |
| URL | github.com/OnlyNight-LTD |
| Total Repositories | 9 |
| Visibility | All Private |

---

## 📁 All Repositories

| Repository | Language | Last Updated | Description |
|------------|----------|--------------|-------------|
| **medici-hotels** | C# | Oct 20, 2024 | Backend API (.NET Core) |
| **medici_web** | TypeScript | Oct 12, 2024 | Frontend (Angular) |
| only_night_server_v2_2 | Python | Aug 25, 2024 | Server v2.2 |
| only_night_server_v2 | Python | Jul 26, 2024 | Server v2 |
| only_night_server | Python | Apr 3, 2024 | Original server (backup) |
| server | Python | Apr 2, 2024 | Server |
| medici_hotels | — | Apr 2, 2024 | Old/Archive |

---

## 🔧 medici-hotels (Backend)

> Main Backend Repository - .NET Core API

| Property | Value |
|----------|-------|
| Repository | medici-hotels |
| Full URL | github.com/OnlyNight-LTD/medici-hotels |
| Visibility | Private |
| Language | C# (100%) |
| Default Branch | main |
| Total Branches | 11 |
| Last Contributor | RomanMyronchuk |
| Last Commit | 8ce32a2 - Add project files |

### Deployments

| Environment | Status | Last Deploy |
|-------------|--------|-------------|
| Production | ✅ Active | 11 months ago |
| Preview | ✅ Active | 9 months ago |

### Project Structure (17 Projects)

| Folder | Description | Node.js Equivalent |
|--------|-------------|-------------------|
| **ApiInstant** | Innstant API client library | ❌ Not implemented |
| **Backend** | Main ASP.NET Core Web API (Controllers) | ✅ `medici-backend-node/` |
| **EFModel** | Entity Framework models & database context | ✅ `config/database.js` |
| **Extensions** | Extension methods & utilities | — |
| **MediciAgent** | Agent service | ❌ Not implemented |
| **MediciAutoCancellation** | WebJob - Auto cancellation | ❌ Not implemented |
| **MediciBuyRooms** | WebJob - Automatic room purchasing | ❌ Not implemented |
| **MediciUpdatePrices** | WebJob - Price update service | ❌ Not implemented |
| **ModelsLibrary** | Shared models library | ✅ Angular models |
| **Notifications** | Email & SMS notification services | ❌ Not implemented |
| **ProcessRevisedFile** | File processing service | — |
| **SharedLibrary** | Shared utilities & helpers | — |
| **SlackLibrary** | Slack integration | ❌ Not implemented |
| **WebHotel** | Hotel service - Zenith integration | ❌ Not implemented |
| **WebHotelLib** | Hotel library | — |
| **WebHotelRevise** | Hotel revision service | — |
| **WebInnstant** | Innstant web service | ❌ Not implemented |

---

## 🎨 medici_web (Frontend)

> Main Frontend Repository - Angular Application

| Property | Value |
|----------|-------|
| Repository | medici_web |
| Full URL | github.com/OnlyNight-LTD/medici_web |
| Visibility | Private |
| Language | TypeScript |
| Framework | Angular 16 |
| Default Branch | master |
| Total Branches | 10+ |
| Last Contributor | Puz1ngg321 |
| Last Commit | e1a5841 - Fix cors header error on prod |

### Deployments

| Environment | Status | Last Deploy |
|-------------|--------|-------------|
| Production | ✅ Active | 2 months ago |
| Preview | ✅ Active | 10 months ago |
| + 24 more | Various | See GitHub |

**Total Deployments: 26**

### Vercel Integration

| Property | Value |
|----------|-------|
| Hosting | Vercel |
| Project Name | medici-web |
| Production Branch | develop-azure |
| Production URL | admin.medicihotels.com |
| Vercel URL | medici-web.vercel.app |
| Auto Deploy | ✅ Enabled |

---

## 🚀 Deployment Workflow

### Backend (medici-hotels)

**Current Status:** Manual deployment (no CI/CD configured in Azure)

**Deployment Method:**
1. Build locally in Visual Studio
2. Publish to Azure via Visual Studio or FTPS
3. WebJobs deployed separately

### Frontend (medici_web)

**Current Status:** ✅ Automatic deployment via Vercel

**Deployment Flow:**
1. Push to `develop-azure` branch
2. Vercel automatically builds and deploys
3. Preview deployments for other branches

---

## 📋 Quick Reference

### Clone Commands

```bash
# Clone Backend (Original .NET)
git clone https://github.com/OnlyNight-LTD/medici-hotels.git

# Clone Frontend
git clone https://github.com/OnlyNight-LTD/medici_web.git

# Clone This Replica (Node.js)
git clone https://github.com/amitpo23/medici_web03012026.git
```

### Key Branches

| Repository | Branch | Purpose |
|------------|--------|---------|
| medici-hotels | main | Production code |
| medici_web | master | Default branch |
| medici_web | develop-azure | Production deployment branch |
| **medici_web03012026** | **master** | **Node.js replica** |

### Contributors

| Username | Repository | Role |
|----------|------------|------|
| RomanMyronchuk | medici-hotels | Backend developer |
| Puz1ngg321 | medici_web | Frontend developer |
| rkuzmenko-softheme | medici_web | Deployment (Vercel) |
| amitpo23 | medici_web03012026 | Node.js replica |

### Live URLs

| Service | URL |
|---------|-----|
| Frontend (Production) | https://admin.medicihotels.com |
| Frontend (Vercel) | https://medici-web.vercel.app |
| Backend API (.NET) | https://medici-backend.azurewebsites.net |
| Backend (Vercel?) | https://medici-hotels.vercel.app |

---

## 🔄 Node.js Replica Status

### Implemented ✅

| .NET Project | Node.js Equivalent | Status |
|--------------|-------------------|--------|
| Backend (Controllers) | `routes/*.js` | ✅ Complete |
| EFModel | `config/database.js` | ✅ Complete |

### Not Yet Implemented ❌

| .NET Project | Description | Priority |
|--------------|-------------|----------|
| ApiInstant | Innstant API client | 🔴 High |
| WebHotel | Zenith integration | 🔴 High |
| SlackLibrary | Slack notifications | 🟡 Medium |
| Notifications | Email/SMS | 🟡 Medium |
| MediciBuyRooms | Auto room purchase | 🔴 High |
| MediciAutoCancellation | Auto cancellation | 🔴 High |
| MediciUpdatePrices | Price updates | 🟡 Medium |

---

*Generated: January 13, 2026*

