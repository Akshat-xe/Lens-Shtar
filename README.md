<!-- HEADER -->
<img src="https://capsule-render.vercel.app/api?type=waving&color=0:050505,30:0d0000,65:6b0000,100:900000&height=220&section=header&text=LENS%20SHTAR&fontSize=65&fontColor=e8e8e8&animation=twinkling&fontAlignY=42&desc=AI-Powered%20Personal%20Expense%20Analyzer%20%26%20Financial%20Privacy%20Engine&descSize=15&descAlignY=64&descColor=b08080" width="100%" />

<div align="center">

[![Live Product](https://img.shields.io/badge/LIVE_SITE-lens.shtar.space-850000?style=for-the-badge&logo=googlechrome&logoColor=e8e8e8&labelColor=0c0000)](https://lens.shtar.space)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI_Python-650000?style=for-the-badge&logo=fastapi&logoColor=e8e8e8&labelColor=0c0000)](https://fastapi.tiangolo.com/)
[![Privacy Standard](https://img.shields.io/badge/Privacy-100%25_Ephemeral-850000?style=for-the-badge&logo=shield&logoColor=e8e8e8&labelColor=0c0000)](#-privacy--data-security-architecture)

</div>

---

## ⚡ Overview

**Lens Shtar** is an intelligent, privacy-first personal financial analyzer designed to give you instant clarity on your spending. 

Simply upload your raw bank statement (PDF, XLSX, or CSV), and Lens Shtar automatically parses your transactions, categorizes your expenses (subscriptions, dining, utilities, transfers), surfaces hidden recurring leaks, and generates actionable, personalized savings insights — all in seconds.

> *"Understand where every rupee goes. Save smarter, effortless clarity."*

---

## 🚀 Key Features

- 📄 **Multi-Format Bank Statement Parsing**: Native extraction for bank statement PDFs, Excel sheets, and CSV exports across major Indian and international banks.
- 🏷️ **Smart Categorization Engine**: Automatically tags transactions into meaningful categories (Dining, Subscriptions, Shopping, Bills, Peer Transfers).
- 🚨 **Spending Leak & Subscription Audit**: Detects forgotten recurring subscriptions, hidden bank charges, and abnormal spending spikes.
- 💡 **Actionable Savings Recommendations**: Generates tailored monthly budget optimizations to help you save more money without compromising your lifestyle.
- 🔢 **Deterministic Math Engine**: Verifies all balances and mathematical totals before displaying insights — 100% accuracy, zero hallucinated math.

---

## 🛡️ Privacy & Data Security Architecture

We understand that financial statements contain sensitive personal information. Lens Shtar is engineered from the ground up around **Privacy-First Principles**:

> [!IMPORTANT]
> **Your financial privacy is non-negotiable.** Lens Shtar operates on zero-retention ephemeral pipelines.

### 🔒 Privacy Commitments:

1. **100% Ephemeral In-Memory Processing**: 
   Uploaded bank statements and parsed records are processed strictly in RAM during your session and are automatically purged. Files are **never stored permanently** on server disks or external databases.

2. **PII Masking & Automatic Sanitization**:
   Before any mathematical analysis occurs, sensitive Personally Identifiable Information (PII) — such as full bank account numbers, phone numbers, and physical addresses — are automatically masked and redacted.

3. **Zero Data Retention & Zero Selling**:
   We **do not sell, share, track, or commercialize** your financial data. No third-party tracking pixels or ad networks are attached to your upload stream.

4. **End-to-End Encrypted Transport**:
   All communication between your browser and the analysis engine is encrypted using industry-standard **TLS 1.3 / HTTPS** protocols.

---

## 🛠️ Built With

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)
![Google Gemini API](https://img.shields.io/badge/Google_Gemini_AI-8E75B2?style=for-the-badge&logo=google&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)

---

<div align="center">
  <i>Empowering individuals with mathematical truth, financial clarity, and absolute privacy.</i><br/>
  <b>Lens Shtar · Ever Shtar Product Suite</b>
</div>


## Environment Variables
- `NODE_ENV`: Runtime environment (`development` / `production`).


## Responsive Breakpoints
- Mobile (< 640px), Tablet (640px - 1024px), Desktop (> 1024px).


## Component Lifecycle
- Always unsubscribe from event listeners on component unmount.


/* Grid Breakpoint Specs */
@media (min-width: 1440px) { .container { max-width: 1320px; } }


/* Storage Namespaces */
const STORAGE_KEYS = { THEME: 'app_theme_pref', LANG: 'app_locale_pref' };


/* CORS Specs */
// Allowed origin headers configured per environment
