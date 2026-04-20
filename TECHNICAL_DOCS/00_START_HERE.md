# NeoTrade Ecosystem Documentation

**⚠️ MANDATORY SESSION START VERIFICATION**

**Before proceeding with ANY work, Claude Code MUST complete session start verification:**

1. **[ ]** Complete `/TECHNICAL_DOCS/SESSION_START_VERIFICATION.md` checklist
2. **[ ]** Explicitly acknowledge understanding of all guidelines
3. **[ ]** Confirm current working directory and task scope
4. **[ ]** State commitment to follow all rules

**📋 Verification File**: `TECHNICAL_DOCS/SESSION_START_VERIFICATION.md`
- Location: `/Users/mac/NeoTrade2/TECHNICAL_DOCS/SESSION_START_VERIFICATION.md`
- Purpose: Ensure all guidelines are reviewed and acknowledged
- Required: MUST BE COMPLETED before any work begins

**✅ Session start verification is COMPLETE when:**
- All checklist items acknowledged with explicit confirmations
- Claude Code states understanding of each guideline set
- Working directory and task scope confirmed
- Explicit commitments made to follow all rules

---

## 🚀 Quick Start

**New to NeoTrade?** Start here:
1. **[system/01_project_overview.md](system/01_project_overview.md)** - Complete ecosystem overview
2. **[system/02_architecture.md](system/02_architecture.md)** - System architecture and design
3. **[system/03_deployment.md](system/03_deployment.md)** - How to deploy and run services

**Working with specific components?** Jump directly:
- **[components/screeners/](components/screeners/)** - Stock screening system
- **[components/data_pipeline/](components/data_pipeline/)** - Data management
- **[components/web_and_api/](components/web_and_api/)** - Flask Dashboard and API
- **[components/monitoring/](components/monitoring/)** - Monitoring and alerts
- **[components/ml_prediction/](components/ml_prediction/)** - ML prediction system

**Research and analysis?** 
- **[research/](../research/)** - Predictive cup analysis research
- **[../STOCKPREDICTION/](../STOCKPREDICTION/)** - ML stock prediction project

## 📚 Documentation Structure

### System Level (Architecture & Deployment)
- **[system/01_project_overview.md](system/01_project_overview.md)** - All projects overview
- **[system/02_architecture.md](system/02_architecture.md)** - System architecture
- **[system/03_deployment.md](system/03_deployment.md)** - Deployment guide
- **[system/04_configuration.md](system/04_configuration.md)** - Configuration management
- **[system/01_strategic_decisions.md](system/01_strategic_decisions.md)** - Strategic decisions log (development approach, architecture choices)

### Component Level (Major Functional Areas)
- **[components/screeners/overview.md](components/screeners/overview.md)** - Screener system overview
- **[components/screeners/configuration.md](components/screeners/configuration.md)** - Screener configuration
- **[components/screeners/management.md](components/screeners/management.md)** - Screener CRUD operations
- **[components/screeners/specific/](components/screeners/specific/)** - Individual screener details
- **[components/data_pipeline/overview.md](components/data_pipeline/overview.md)** - Data pipeline overview
- **[components/monitoring/setup.md](components/monitoring/setup.md)** - Monitoring setup
- **[components/web_and_api/flask_architecture.md](components/web_and_api/flask_architecture.md)** - Flask backend
- **[components/web_and_api/api_reference.md](components/web_and_api/api_reference.md)** - API documentation
- **[components/web_and_api/services.md](components/web_and_api/services.md)** - Service management

### Specific Level (Implementation Details)
- **[components/screeners/specific/coffee_cup.md](components/screeners/specific/coffee_cup.md)** - Coffee cup screener
- **[components/screeners/specific/o_neil_methods.md](components/screeners/specific/o_neil_methods.md)** - O'Neil methodology

### Reference Level (Quick Reference)
- **[reference/operations_guide.md](reference/operations_guide.md)** - Operations & troubleshooting
- **[reference/incident_history.md](reference/incident_history.md)** - Historical incidents
- **[reference/change_log.md](reference/change_log.md)** - System changes

## 🎯 Find by Topic

| Question | Documentation |
|----------|----------------|
| How do I start the system? | [system/03_deployment.md](system/03_deployment.md) |
| What's the system architecture? | [system/02_architecture.md](system/02_architecture.md) |
| How do screeners work? | [components/screeners/overview.md](components/screeners/overview.md) |
| How do I configure a screener? | [components/screeners/configuration.md](components/screeners/configuration.md) |
| Where's the API documentation? | [components/web_and_api/api_reference.md](components/web_and_api/api_reference.md) |
| How do I troubleshoot issues? | [reference/operations_guide.md](reference/operations_guide.md) |
| What are the specific screener parameters? | [components/screeners/specific/](components/screeners/specific/) |
| How do I use the Lao Ya Tou classifier? | [components/screeners/lao_ya_tou_db_classifier.md](components/screeners/lao_ya_tou_db_classifier.md) |

## 🗂️ Project Navigation

**Main Project (NeoTrade2)**
- Current location - you are here
- Core functionality: Stock screening, Dashboard, data management

**Research Project**
- Location: `../research/`
- Focus: Predictive cup formation analysis
- Documentation: [research/predictive_cup/TECHNICAL_DOCS/](../research/predictive_cup/TECHNICAL_DOCS/)

**Prediction Project** 
- Location: `../STOCKPREDICTION/`
- Focus: ML-based stock prediction
- Documentation: [../STOCKPREDICTION/docs/](../STOCKPREDICTION/docs/)

## 📝 Documentation Philosophy

This documentation is organized by **semantic levels**:
- **System Level** - Big picture, architecture, cross-project concerns
- **Component Level** - Major functional areas and their management
- **Specific Level** - Implementation details for individual features
- **Reference Level** - Quick reference, troubleshooting, historical info

This structure ensures you can navigate from broad concepts to specific implementation details logically.

## 🛠️ Documentation Maintenance

**Keeping documentation clean and organized**:

- **[Maintenance Guide](DOCUMENTATION_MAINTENANCE_GUIDE.md)** - Complete guidelines for maintaining semantic organization
- **[Quick Reference](QUICK_REFERENCE.md)** - Fast lookup for common documentation tasks
- **[Session Starter](SESSION_STARTER.md)** - Instructions for Claude Code to follow guidelines
- **[Reorganization Summary](REORGANIZATION_SUMMARY_20260416.md)** - Details of today's semantic reorganization

**Key Maintenance Principles**:
1. **Organize by semantic meaning** (not convenience)
2. **Single source of truth** (link, don't duplicate)
3. **Audience-appropriate content** (write for the right level)
4. **Regular cleanup** (archive outdated, remove duplicates)

**Quick Decision Tree**:
```
System/overview/architecture?     → system/
Major functional area?           → components/[area]/
Specific implementation?          → components/[area]/specific/
Quick reference/troubleshooting?  → reference/
```

---

**Last Updated**: 2026-04-17
**Version**: 2.1 (Added Lao Ya Tou Database Classifier)
