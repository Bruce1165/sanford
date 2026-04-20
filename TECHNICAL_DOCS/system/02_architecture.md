# NeoTrade2 System Architecture

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   User Browser                          │
│                    (HTTPS)                           │
│                       ↓                              │
│              ┌─────────────────┐                   │
│              │   Cpolar       │                   │
│              │   Tunnel        │                   │
│              └────────┬────────┘                   │
│                       ↓ HTTP                     │
│              ┌─────────────────┐                   │
│              │  Flask (8765)   │                   │
│              │  Dashboard       │                   │
│              └────────┬────────┘                   │
│         ┌────────────┼────────────┐                │
│         ↓            ↓            ↓                │
│    ┌────────┐  ┌────────┐ ┌────────┐          │
│    │ Frontend│  │  API   │ │ Screeners│          │
│    │ (React) │  │ (REST) │ │ (Python) │          │
│    └────────┘  └────────┘ └────────┘          │
│                                            ↓         │
│                                    ┌────────────────┐     │
│                                    │ SQLite DBs    │     │
│                                    │ stock_data.db  │     │
│                                    │ dashboard.db   │     │
│                                    └────────────────┘     │
└─────────────────────────────────────────────────────────┘
```

## 🧩 Component Architecture

### Core Components

**1. Flask Dashboard (`components/web_and_api/`)**
- **File**: `backend/app.py`
- **Port**: 8765 (HTTP Basic Auth protected)
- **Responsibilities**:
  - REST API endpoints
  - Static file serving (React frontend)
  - Authentication & authorization
  - Screener orchestration
- **Detailed Architecture**: [flask_architecture.md](components/web_and_api/flask_architecture.md)

**2. Frontend (`frontend/`)**
- **Framework**: React + TypeScript
- **Build**: Vite production build in `dist/`
- **Key Pages**: Monitor, Screener Management, Configuration
- **Styling**: Ant Design components

**3. Screener System (`components/screeners/`)**
- **Base Class**: `screeners/base_screener.py`
- **Active Screeners**: 11 technical analysis modules
- **Management**: JSON configuration system in `config/screeners/`
- **Documentation**: [screener overview](components/screeners/overview.md)

**4. Data Pipeline (`components/data_pipeline/`)**
- **Primary Source**: Baostock API
- **Database**: SQLite (`data/stock_data.db`, `data/dashboard.db`)
- **Automation**: Daily download scripts, cron jobs
- **Documentation**: [data pipeline overview](components/data_pipeline/overview.md)

**5. Monitoring System (`components/monitoring/`)**
- **Health Checks**: Screener status, data quality
- **Alerting**: Daily QA reports
- **Logging**: Structured logs in `logs/`
- **Documentation**: [monitoring setup](components/monitoring/setup.md)

## 📊 Data Flow

### Ingestion Pipeline
```
Baostock API → fetcher_baostock.py → Daily Prices → SQLite
                                            ↓
                                    Stock Basic Info
```

### Screening Pipeline
```
SQLite Data → Screener Modules → Pattern Detection → Results (Excel)
                                            ↓
                                    Dashboard Display
```

### User Interaction Pipeline
```
User Browser → Cpolar Tunnel → Flask Dashboard → API → Screener Execution
                                    ↓
                            Results Display
```

## 🔐 Security & Authentication

**Authentication Layer**:
- **Method**: HTTP Basic Auth
- **Implementation**: Flask `before_request` middleware
- **Password**: `DASHBOARD_PASSWORD` environment variable
- **Current Password**: `NeoTrade123`
- **Configuration**: [system configuration](system/04_configuration.md)

**Access Control**:
- **External Access**: Cpolar HTTPS tunnel
- **Internal Access**: localhost:8765
- **Password Protection**: All requests except `/api/health`

## 🌐 Network Architecture

### External Access
```
Internet → https://neotrade.vip.cpolar.cn/ → Cpolar Tunnel → localhost:8765
```

### Service Management
- **Flask Service**: macOS LaunchAgent (`com.neotrade2.flask`)
- **Cpolar Service**: macOS LaunchAgent (`com.neotrade.cpolar`)
- **Auto-restart**: KeepAlive enabled for crash recovery
- **Documentation**: [service management](components/web_and_api/services.md)

## 🗄️ Database Architecture

### stock_data.db (Main Data)
- **Tables**: `stocks`, `daily_prices`
- **Records**: ~1.4M rows (4,663 stocks × ~300 days)
- **Size**: ~326MB
- **Purpose**: Historical and daily price data

### dashboard.db (Application Data)
- **Tables**: `screeners`, `screener_runs`, `screener_results`, etc.
- **Purpose**: Dashboard state, screener configurations, user preferences
- **Integration**: Links to stock_data.db via stock codes

## 🔄 System Integration Points

### Screener Integration
```
Dashboard → screeners.py (discovery) → Individual Screener → Results → Dashboard
```

### Data Integration
```
Baostock → fetcher_baostock.py → SQLite → All Components
```

### Monitoring Integration
```
Cron Jobs → QA Scripts → Health Checks → Dashboard Alerts → Logs
```

## 📈 Scalability Considerations

### Current Capacity
- **Stocks**: 4,663 A-shares (filtered)
- **Data Range**: 6 months historical data
- **Concurrent Screeners**: 11 (sequential execution)
- **Dashboard Users**: Single user (personal use)

### Bottlenecks
1. **Sequential Screener Execution**: Could parallelize
2. **SQLite Performance**: Consider PostgreSQL for production scale
3. **Data Freshness**: T+1 dependency on Baostock updates

## 🚀 Deployment Architecture

### Development Environment
- **Local Development**: `npm run dev` (Vite dev server on :5173)
- **Backend Testing**: Direct Python execution
- **Database**: Local SQLite files

### Production Environment
- **Frontend**: Built static files (`frontend/dist/`)
- **Backend**: Flask production server on :8765
- **Tunnel**: Cpolar for external HTTPS access
- **Automation**: macOS LaunchAgents for auto-start

---

**Last Updated**: 2026-04-16  
**Version**: 2.0 (Semantic Reorganization)
