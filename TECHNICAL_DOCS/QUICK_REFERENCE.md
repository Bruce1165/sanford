# Documentation Quick Reference
**Print this for easy access during documentation work**

---

## 🎯 Where to Put New Documentation

```
❓ What are you writing about?

SYSTEM (architecture, deployment, overview)
    ↓ Put in: system/

COMPONENT (major functional area)
    ↓ Which component?
    - Screeners → components/screeners/
    - Web/API → components/web_and_api/
    - Data Pipeline → components/data_pipeline/
    - Monitoring → components/monitoring/
    - ML Prediction → components/ml_prediction/

SPECIFIC (individual implementation)
    ↓ Put in: components/[area]/specific/

REFERENCE (troubleshooting, quick lookup)
    ↓ Put in: reference/
```

---

## 📝 Naming Conventions

```
System Level:     XX_topic_name.md
Component Level:  XX_topic_name.md  
Specific Level:   topic_name.md
Reference Level:   topic_name.md
```

**Examples**:
- ✅ `01_project_overview.md` (System)
- ✅ `configuration.md` (Component)  
- ✅ `coffee_cup.md` (Specific)
- ✅ `operations_guide.md` (Reference)

---

## ✅ Before Creating Documentation

**Check these 4 things:**

1. **[ ] Semantic Level Correct?**
   - System → system/
   - Component → components/[area]/
   - Specific → components/[area]/specific/
   - Reference → reference/

2. **[ ] Already Exists?**
   ```bash
   grep -r "keyword" TECHNICAL_DOCS/
   ```

3. **[ ] Naming Convention?**
   - Follow XX_ format for system/component
   - Use descriptive names for specific/reference

4. **[ ] Navigation Updated?**
   - Add to parent overview if component/specific
   - Update 00_START_HERE.md if system/component

---

## 🔧 Common Documentation Tasks

### Adding a New Screener
```
1. Create: components/screeners/specific/[screener_name].md
2. Update: components/screeners/overview.md (add link)
3. Update: 00_START_HERE.md (if major screener)
4. Check: No duplicate screener docs exist
```

### Updating System Configuration
```
1. Edit: system/04_configuration.md
2. Update: "Last Updated" date
3. Check: components still reference correctly
4. Test: Verify changes work as documented
```

### Documenting a Bug Fix
```
1. Check: reference/operations_guide.md for existing solutions
2. Add: If new issue, add to operations guide
3. Update: "Last Updated" date
4. Link: From relevant component docs if needed
```

### Adding API Endpoint
```
1. Update: components/web_and_api/api_reference.md
2. Document: Method, parameters, responses, examples
3. Update: "Last Updated" date
4. Test: Verify API works as documented
```

---

## 🚨 Red Flags - Stop & Check

**⚠️ WARNING: Documentation Getting Disorganized**

**Look out for these signs:**
- Many .md files in `TECHNICAL_DOCS/` root
- Multiple versions of similar documentation
- Mixed general/specific content in same file
- Broken links in navigation documents
- "Last Updated" dates > 6 months old

**🛑 IMMEDIATE ACTIONS:**
1. Stop creating new documentation
2. Review semantic organization
3. Apply fixes (follow maintenance guide)
4. Archive outdated content
5. Update navigation

---

## 📅 Maintenance Schedule

### Weekly (5 minutes)
- [ ] Check new docs are in right locations
- [ ] Remove any accidental root-level files
- [ ] Update navigation if needed

### Monthly (15 minutes)  
- [ ] Archive outdated planning docs
- [ ] Check for broken internal links
- [ ] Update "Last Updated" on active docs

### Quarterly (1 hour)
- [ ] Complete documentation audit
- [ ] Archive historical content by quarter
- [ ] Review semantic hierarchy
- [ ] Update maintenance guide if needed

---

## 🎯 Golden Rules

1. **📍 ORGANIZE BY MEANING**: Not by convenience
   - Your coffee cup example: specific vs. general screeners!

2. **🔗 ONE SOURCE OF TRUTH**: Link, don't duplicate
   - If info exists, reference it, don't copy

3. **🎯 AUDIENCE FIRST**: Write for the right level
   - System → Architects/leads
   - Component → Developers/operators
   - Specific → Feature developers
   - Reference → Everyone

4. **🔄 KEEP IT CURRENT**: Update "Last Updated" dates
   - Archive outdated content promptly
   - Maintain navigation accuracy

5. **🧹 CLEAN AS YOU GO**: Don't let clutter accumulate
   - Remove duplicates immediately
   - Archive outdated content regularly
   - Maintain semantic hierarchy

---

## 📞 Need Help?

**Documentation Issues**: Check [DOCUMENTATION_MAINTENANCE_GUIDE.md](DOCUMENTATION_MAINTENANCE_GUIDE.md)

**Quick Questions**: 
- Where does this go? → Use semantic decision tree above
- Is this duplicate? → Search TECHNICAL_DOCS/ first
- How do I update? → Follow update workflow in maintenance guide

---

**Keep this handy!** Print or bookmark for quick reference during documentation work.

**Created**: 2026-04-16  
**Purpose**: Maintain clean semantic organization going forward
