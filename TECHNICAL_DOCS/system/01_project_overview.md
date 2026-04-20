# NeoTrade Ecosystem Overview

## 🌟 Project Portfolio

The NeoTrade ecosystem consists of three main projects working together to provide comprehensive A-share stock analysis and prediction capabilities.

### Main Project: NeoTrade2
**Purpose**: A-share stock screening and technical analysis dashboard
**Key Features**:
- 11 technical analysis screeners (O'Neil patterns, limit-up patterns, etc.)
- Real-time Flask Dashboard with password protection
- Automated data pipeline from Baostock
- Comprehensive monitoring and alerting

**Target User**: Personal investors seeking technical analysis tools

**Technology Stack**: Flask (backend), React (frontend), SQLite (database)

---

### Research Project: Predictive Cup Analysis
**Purpose**: Research and development of predictive cup formation patterns
**Location**: `../research/predictive_cup/`

**Key Features**:
- Agent-based analysis system
- Predictive cup formation detection
- Advanced pattern recognition research
- Safety-constrained experimentation

**Technology Stack**: Python, Agent framework, Research utilities

**Documentation**: [predictive_cup/TECHNICAL_DOCS/](../../research/predictive_cup/TECHNICAL_DOCS/)

---

### Prediction Project: STOCKPREDICTION
**Purpose**: Machine learning-based stock prediction system
**Location**: `../STOCKPREDICTION/`

**Key Features**:
- ML models for stock price prediction
- Feature engineering pipeline
- Training and inference pipelines
- API for predictions

**Technology Stack**: Python, ML frameworks, Feature engineering

**Documentation**: [../STOCKPREDICTION/docs/](../../STOCKPREDICTION/docs/)

---

## 🔄 Integration Between Projects

### Data Flow
```
Baostock API → NeoTrade2 Data Pipeline → SQLite Database
                                            ↓
                              Dashboard Display
                              ↓
                    User Analysis & Research
                              ↓
                Research & Prediction Insights
```

### Shared Resources
- **Data**: NeoTrade2 maintains the master stock database
- **Documentation**: Unified technical documentation hub (this directory)
- **Monitoring**: Shared monitoring and alerting infrastructure

### Cross-Project Workflows
1. **Data Discovery**: Research projects use NeoTrade2 data for analysis
2. **Pattern Validation**: New patterns tested in Research → deployed to NeoTrade2
3. **Model Integration**: ML models from STOCKPREDICTION → integrated into NeoTrade2

---

## 🎯 Strategic Goals

### Short Term (Current)
- Stabilize NeoTrade2 core functionality
- Complete predictive cup research
- Integrate ML predictions into main system

### Medium Term  
- Enhance prediction accuracy
- Expand screener library
- Improve user experience

### Long Term
- Comprehensive AI-powered trading assistant
- Real-time market monitoring
- Advanced pattern recognition

---

## 📊 Project Metrics

| Project | Lines of Code | Documentation | Status | Priority |
|----------|----------------|----------------|----------|-----------|
| NeoTrade2 | ~15,000 | 21 docs | Production | High |
| Research | ~5,000 | 9 docs | Active | Medium |
| STOCKPREDICTION | ~8,000 | 13 docs | Development | Medium |

---

## 👥 Team & Roles

**Bruce**: Primary user and stakeholder
- Personal investor focused on A-share market
- Drives requirements based on trading experience
- Provides domain expertise in Chinese stock market

**AI Assistant**: Technical implementation
- Code development and maintenance
- Documentation and system design
- Technical problem-solving

---

## 📞 Contact & Support

**Technical Issues**: Check relevant component documentation
**Feature Requests**: Discuss with project lead
**System Status**: Dashboard monitoring and logs

---

**Last Updated**: 2026-04-16  
**Version**: 2.0 (Semantic Reorganization)
