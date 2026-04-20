# Coffee Cup Wizard - Dashboard Integration Plan

**Date**: 2026-04-10
**Version**: 1.0
**Type**: Minimal Integration (Option A)

---

## 📋 Overview

Integrate Coffee Cup Wizard prediction model into existing NeoTrade2 Dashboard as a separate research tool.

### Integration Points

1. **Backend API Endpoint**
   - Path: `/api/wizard/analyze` or `/api/wizard/run`
   - Method: POST
   - Body: JSON with optional `date` parameter
   - Returns: Wizard prediction results

2. **Frontend Access**
   - Add "Coffee Cup Wizard" menu item in Dashboard
   - Leads to wizard page (new or existing)
   - Simple table view of predictions
   - Export to Excel button
   - Stock details button (single stock deep dive)

3. **Data Flow**
   ```
   Dashboard → API → Wizard → Database → JSON Response → Dashboard → Display
   ```

4. **File Output Location**
   - Wizard results: `data/wizard_outputs/YYYY-MM-DD.json`
   - Format: Same as existing screeners (`data/screeners/{screener_name}/{date}.xlsx`)

---

## 🎨 Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                    NeoTrade2 Dashboard (Existing)              │
│ ┌──────────────┐ Wizard API (New)                         │
│  │ ┌──────────────┴                                │
│  │ │ ┌────────────┘                                │
│  │ │ ┌────────────┴─┐                │
│ │ │ │ ┌────────────┴                                │
│  │ │ ┌─────────────┐                │
│                 ↑                                    │
│                 │ Flask App                          │
│            ┌──────┴─────────┐                │
│ │                 │     API Routes                       │
│ │                 │      ┌───────┴               │
│ │                 │   Wizard (New)                     │
│ │                 │                     ↓           │
│ │                 │      ↓               │
│ │                 │           ↓               │
│ │                 │           ↓               │
│ │                 │           ↓               │
│ │                 │    Wizard Config                   │
│ │                 │    - params.json              │
│ │                 │           ↓               │
│ │                 │           ↓               │
│ │                 │           ↓               │
│ │                 │    SQLite Database              │
│ │                 │           ↓           │
│ │                 │           ↓               │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Implementation Tasks

### Task 1: Backend API Endpoint

**File**: `backend/app.py`

**Changes required**:
```python
# Add wizard API endpoint
@app.route('/api/wizard/run', methods=['POST'])
@auth_required
def wizard_run_api():
    """Run Coffee Cup Wizard and return results"""
    from backend.wizard.coffee_cup_wizard import CoffeeCupWizard
    
    request_data = request.json.get_json(force=True)
    analysis_date = request_data.get('date')
    
    wizard = CoffeeCupWizard()
    
    # Run wizard
    predictions = wizard.batch_analyze(
        codes=wizard._get_all_stock_codes(),
        end_date=analysis_date
        limit=100
    )
    
    # Filter by threshold
    top_predictions = [p for p in predictions if p.adjusted_probability >= 50]
    
    # Save to database
    # save_wizard_run_result() function should handle this
    
    return jsonify({
        'success': True,
        'predictions': top_predictions,
        '✓ count': len(top_predictions),
        'timestamp': datetime.now().isoformat()
    })
```

---

### Task 2: Dashboard Frontend

**File**: `frontend/src/pages/CoffeeCupWizard.tsx` (NEW)

**Components**:
- Prediction table with sort/filter
- Stock detail modal (charts, deep analysis)
- Export to Excel button
- Config preview (show factor weights)

**Data Display**:
```typescript
// Prediction columns
const PREDICTED_STOCKS = 'predicted_stocks';  // Matches your wizard output structure

// Chart visualization
const CHART_COMPONENT = 'ChartComponent'; // Reuse or create
const DETAIL_MODAL = 'DetailModal';  // Stock deep dive

// Data flow
const fetchPredictions = async () => {
  const response = await axios.post('/api/wizard/run', {
    date: getCurrentDate(),
  });
  const data = response.data.predictions;
  setPredictions(data.predictions);
};

// Export to Excel
const exportToExcel = async () => {
  await axios.post('/api/wizard/export', {
    predictions: selectedRows,
    format: 'excel',
  });
};
```

---

### Task 3: Database Integration

**File**: `backend/models.py` (EXTENSION)

**Add table**:
```python
# Wizard run results table
CREATE TABLE IF NOT EXISTS wizard_run_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    num_stocks_analyzed INTEGER NOT NULL,
    num_stocks_predicted INTEGER NOT NULL,
    prediction_threshold REAL NOT NULL DEFAULT 0.50,
    config_json TEXT,  -- Complete wizard config snapshot
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    UNIQUE(run_date, prediction_threshold);
);

-- Index
CREATE INDEX IF NOT EXISTS idx_wizard_run_results_date (run_date);
CREATE INDEX IF NOT EXISTS idx_wizard_run_results_threshold (prediction_threshold);
```

**Add methods**:
```python
def save_wizard_run_result(config, predictions):
    """Save wizard run result to database"""
    pass
```

---

## 🔧 API Specification

### POST `/api/wizard/run`

**Request Body**:
```json
{
  "date": "YYYY-MM-DD"  // Optional: default today
  "limit": 50 // Number of top predictions to return
}
```

**Response**:
```json
{
  "success": true,
  "predictions": [
    {
      "code": "600XXX",
      "name": "股票名称",
      "probability": 78.5,  // 0-50 = 100% for Cup Edge detected + 50% base
      "stage": "edge_ready_high_volume", // Example stages
      "target_days": 10,
      "factors": {
        "cup_edge": {
          "detected": true,
          "quality": 0.72
        },
        "sentiment": {
          "score": 72,
          "level": "high"
        },
        "capital": {
          "structure": "retail_heavy"
        },
        "limit_up_proximity": {
          "level": "medium",
          "days": 5 // 7天前涨停
        }
      }
    }
  ],
  "count": 42,
  "timestamp": "2026-04-10T12:34:56"
}
```
```

---

## 📝 Frontend Pages

### Page Structure
```
frontend/src/
├── pages/
│   ├── CoffeeCupWizard.tsx       # Main wizard page
├── components/
│       └── PredictionTable.tsx
│       └── StockDetailModal.tsx
│       └── ExportButton.tsx
└── ConfigPreviewModal.tsx
```

---

## 🔄 Data Flow

```
User clicks "Coffee Cup Wizard" → Frontend page loads
→ User selects "Analyze All Stocks" button
→ Frontend calls POST /api/wizard/run with date=today
→ Wizard analyzes 4,663 stocks (takes 1-2 mins)
→ API returns top 100 predictions (≥50% prob)
→ Frontend displays table with sorted predictions
→ User can filter/sort by probability, stage, sentiment, etc.
→ User clicks stock → StockDetailModal shows charts, component breakdown, factor values
→ User can export to Excel → Downloads `data/wizard_outputs/YYYY-MM-DD.xlsx`
```

---

## 🎯 Success Criteria

- [ ] Wizard analyzes all 4,663 stocks in <2 minutes
- [ ] Top 100 predictions displayed correctly
- [ ] Stock detail modal shows charts and deep analysis
- [ ] Excel export generates proper file in existing format
- [ ] No impact to existing screeners or dashboard stability
- [ ] Wizard can be called repeatedly without caching issues
- [ ] Predictions stored separately from screeners (no conflict)
- [ ] Config versioning tracked in JSON

---

## ⚠️ Risk Mitigation

- [ ] Wizard runs in subprocess (isolated from Flask)
- [ ] Database writes via Flask API (not direct SQLite access)
- [ ] No heavy computation that crashes Flask
- [ ] Predictions stored separately from screeners (no conflict)
- [ ] Config versioning tracked in JSON

---

## 📅 Files to Create

1. `backend/app.py` - Add wizard API endpoint (~30 lines)
2. `frontend/src/pages/CoffeeCupWizard.tsx` - New wizard page (~200 lines)
3. `frontend/src/components/` - Reusable chart/detail components (~150 lines)

**Estimated Effort**: 4-6 hours
**Estimated Time to Test**: 1 hour
**Total**: 5-7 hours

---

## 🚀 Next Steps After This

1. **Create this plan** → Write plan files
2. **Get your approval** → Review plan together
3. **Implement backend API** → Add `/api/wizard/run` endpoint
4. **Implement frontend page** → Create wizard UI components
5. **Test integration** → End-to-end test
6. **Verify predictions** → Test on real data, validate factors
7. **Document** → Update CLAUDE.md with wizard usage
8. **Deploy** → Push to production when ready

---

**Ready to write implementation plan?** Yes/No/Need more info/Refine approach?

Please provide:
- Should I add the Flask API endpoint to this plan?
- Should I include the frontend page in this plan?
- What's your preference for chart library?
- Any specific requirements for stock detail view?
- Should export support multiple formats (Excel, CSV)?
