# NeoTrade Session Starter Instructions

**Give these instructions to Claude Code at the start of each session to ensure consistent documentation practices.**

---

## 🚀 Quick Session Starter

**Copy and paste this to Claude Code at session start:**

```
I'm working on the NeoTrade2 project. Please follow these guidelines for ALL documentation work:

📚 DOCUMENTATION GUIDELINES:

1. SEMANTIC ORGANIZATION - Always organize docs by meaning, not convenience:
   - System level → TECHNICAL_DOCS/system/
   - Component level → TECHNICAL_DOCS/components/[area]/
   - Specific level → TECHNICAL_DOCS/components/[area]/specific/
   - Reference level → TECHNICAL_DOCS/reference/

2. NO DUPLICATES - Before creating new docs:
   - Search TECHNICAL_DOCS/ for existing content first
   - Link to existing docs rather than copying
   - Update existing docs in place rather than creating new ones

3. MAINTAIN STRUCTURE - Follow these principles:
   - Keep root TECHNICAL_DOCS/ clean (no accidental .md files)
   - Use semantic hierarchy (your coffee cup example!)
   - Update navigation when adding/modifying docs
   - Archive outdated content promptly

4. QUALITY STANDARDS - For every documentation change:
   - Follow naming conventions (XX_ for system/component)
   - Update "Last Updated" dates
   - Check for broken internal links
   - Write for the right audience level

📖 KEY DOCUMENTATION TO USE:
- TECHNICAL_DOCS/00_START_HERE.md - Main entry point
- TECHNICAL_DOCS/QUICK_REFERENCE.md - Fast lookup guide
- TECHNICAL_DOCS/DOCUMENTATION_MAINTENANCE_GUIDE.md - Full guidelines

🏗️ PROJECT STRUCTURE:
- Main: /Users/mac/NeoTrade2/
- Research: /Users/mac/NeoTrade2/research/
- Prediction: /Users/mac/NeoTrade2/STOCKPREDICTION/
- Docs: /Users/mac/NeoTrade2/TECHNICAL_DOCS/

Please follow these guidelines for ANY documentation work - reading, creating, or updating project docs.
```

---

## 📋 Alternative Quick Starters

### For Documentation-Focused Sessions:
```
Working on NeoTrade2 documentation. Please:
1. Read TECHNICAL_DOCS/DOCUMENTATION_MAINTENANCE_GUIDE.md first
2. Follow semantic organization principles (system/component/specific/reference)
3. Use QUICK_REFERENCE.md for common tasks
4. Maintain clean structure in TECHNICAL_DOCS/
```

### For Development Sessions with Documentation:
```
Working on NeoTrade2 development. For any documentation changes:
- Follow semantic organization (check TECHNICAL_DOCS/ structure first)
- No root-level .md files in TECHNICAL_DOCS/
- Update existing docs rather than creating duplicates
- Use QUICK_REFERENCE.md for placement decisions
```

### For Quick Reference:
```
NeoTrade2 project - follow TECHNICAL_DOCS guidelines for documentation.
Key principle: Organize by semantic meaning (system/component/specific/reference).
Maintain clean structure, no duplicates, update navigation.
```

---

## 🎯 What This Achieves

**Consistent Behavior Across Sessions**:
- ✅ Same semantic organization principles every time
- ✅ No accidental duplication or root-level file bloat
- ✅ Proper navigation updates for all changes
- ✅ Quality standards applied consistently

**Prevents Common Issues**:
- ✅ Files ending up in wrong locations
- ✅ Duplicate documentation being created
- ✅ Broken navigation links
- ✅ Mixed semantic levels (general + specific together)
- ✅ Outdated content accumulating

---

## 📝 When to Use Different Instructions

**Use these specific starters for different scenarios:**

### Bug Fix Session:
```
NeoTrade2 bug fix. For any documentation updates, follow TECHNICAL_DOCS semantic organization.
Update reference/operations_guide.md if new troubleshooting, otherwise update relevant component docs.
```

### Feature Development Session:
```
NeoTrade2 feature development. Document new features following TECHNICAL_DOCS structure:
- System features → system/
- Component features → components/[area]/
- Specific implementations → components/[area]/specific/
Update relevant overview docs and 00_START_HERE.md.
```

### Research/Analysis Session:
```
NeoTrade2 research work. For documentation:
- Research plans → system/ (if project-level) or research/ project docs
- Analysis results → Archive to TECHNICAL_DOCS/ARCHIVE/[quarter]/
- Temporary working docs → research/temporary/ (not TECHNICAL_DOCS/)
```

---

## 🔍 Verification Checklist

**After giving Claude Code the session starter, verify it understood:**

**Claude Code should acknowledge:**
- [ ] Semantic organization principles (4-level hierarchy)
- [ ] No duplication rule (search first, link second)
- [ ] Clean structure requirement (no root-level files)
- [ ] Navigation update responsibility
- [ ] Quality standards (naming, dates, links)
- [ ] Key documentation files to reference

**If Claude Code seems confused:**
- Point to TECHNICAL_DOCS/QUICK_REFERENCE.md
- Reference the coffee cup example (specific vs. general)
- Emphasize: "Organize by meaning, not convenience"

---

## 💡 Pro Tips

**Make it a habit**: Always start sessions with the documentation guidelines
**Be specific**: Different sessions need different emphasis (docs vs. development)
**Check early**: Verify Claude Code is following guidelines early in session
**Provide feedback**: If Claude Code violates guidelines, correct immediately
**Update guidelines**: If you find better approaches, update SESSION_STARTER.md

---

## 📞 Quick Reference Card

**Session Starter (Full Version)**:
```
NeoTrade2 project - follow TECHNICAL_DOCS guidelines:
- Semantic organization (system/component/specific/reference)
- No duplicates (search first, link second)  
- Clean structure (no root-level files)
- Update navigation, follow quality standards
Key docs: 00_START_HERE.md, QUICK_REFERENCE.md, DOCUMENTATION_MAINTENANCE_GUIDE.md
```

**Session Starter (Short Version)**:
```
NeoTrade2 docs - follow TECHNICAL_DOCS semantic organization.
No duplicates, clean structure, update navigation.
Key: organize by meaning (system/component/specific/reference).
```

---

**Created**: 2026-04-16  
**Purpose**: Ensure consistent documentation practices across all Claude Code sessions  
**Usage**: Copy appropriate starter to Claude Code at beginning of each session
