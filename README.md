<<<<<<< HEAD
# ReconTool — Payment Reconciliation Dashboard

A web app that takes a **Forward & Return Payment Reconciliation** CSV/Excel report
and generates an interactive dashboard showing payment journeys, disputed/overdue
alerts, and channel-wise breakdowns.

---

## Deploy to Render (free, no card needed)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

1. Fork this repo on GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Render auto-detects `render.yaml` — just click **Deploy**
5. Your app will be live at `https://recon-tool.onrender.com`

---

## Run locally

```bash
git clone https://github.com/YOUR_USERNAME/recon-tool.git
cd recon-tool

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

python -m pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000**

---

## How to use

1. Open the app → click **Choose File** or drag & drop your reconciliation CSV/Excel
2. Click **Analyse Report**
3. Use the **Channel** dropdown to filter by Amazon, Myntra, Flipkart, etc.

---

## Business logic

| Rule | Detail |
|---|---|
| Forward journey | `Return Type = NONE` |
| Return journey | `Return Type = CIR` or `RTO` |
| % denominator | AWAITING + DISPUTED + OVERDUE + RECONCILED + RECONCILED_BY_DELTA |
| Overpaid (Forward) | Expected − Actual > 0 |
| Underpaid (Forward) | Expected − Actual < 0 |
| Overpaid (Return) | Vice versa |
| Actionable flag | Disputed > 25% OR Overdue > 25% |

---

## Project structure

```
recon-tool/
├── app.py                   ← Flask routes (in-memory, no disk writes)
├── requirements.txt         ← flask, pandas, openpyxl, gunicorn
├── render.yaml              ← Render.com deploy config
│
├── ingestion/
│   └── loader.py            ← reads CSV/Excel bytes, validates, cleans
│
├── modules/
│   └── engine.py            ← all business logic & computation
│
├── templates/
│   ├── index.html           ← upload landing page
│   └── dashboard.html       ← results dashboard
│
└── static/
    ├── css/
    │   ├── upload.css
    │   └── dashboard.css
    └── js/
        └── upload.js        ← drag-drop, file preview
```
=======
# recon-tool
>>>>>>> 2a800265e75e7d282c2b70e937b0ec8cb2c92b35
