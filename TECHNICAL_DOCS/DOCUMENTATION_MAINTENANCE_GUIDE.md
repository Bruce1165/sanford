# Documentation Maintenance Guide
**Purpose**: Keep NeoTrade documentation clean, semantically organized, and maintainable  
**Created**: 2026-04-16  
**Status**: Active Guidelines

---

## 🎯 Core Principles

### 1. Semantic-First Organization
**Always organize by subject meaning, not convenience**:
- System-level docs → `system/`
- Component docs → `components/[component_name]/`
- Specific implementations → `components/[component]/specific/`
- Reference material → `reference/`

### 2. Single Source of Truth
**One document per subject, avoid duplication**:
- If information exists elsewhere, link to it instead of copying
- Update existing docs rather than creating new ones
- Archive outdated versions, don't keep duplicates

### 3. Audience-Appropriate Content
**Write for the right level**:
- **System docs**: Architects, leads, new team members
- **Component docs**: Developers, system operators  
- **Specific docs**: Feature developers, maintainers
- **Reference docs**: All users (quick lookup)

---

## 📝 Documentation Creation Guidelines

### When Creating New Documentation

**Step 1: Determine Semantic Level**
```
Is this about:
❓ System architecture/deployment? → system/
❓ Major functional area? → components/[area]/
❓ Specific implementation? → components/[area]/specific/
❓ Quick reference/troubleshooting? → reference/
```

**Step 2: Check for Existing Content**
```bash
# Search for related documentation before creating new
grep -r "keyword" TECHNICAL_DOCS/
```

**Step 3: Follow Naming Conventions**
```
System Level:     XX_topic.md              (01_architecture.md)
Component Level:  XX_topic.md              (screeners_overview.md)  
Specific Level:   topic.md                 (coffee_cup.md)
Reference Level:   topic.md                 (operations_guide.md)
```

**Step 4: Update Navigation**
- Add to relevant parent document
- Update `00_START_HERE.md` if system/component level
- Update component `overview.md` if specific level
- Update cross-references in related docs

### Documentation Templates

**System Level Template**:
```markdown
# [Topic Name]

**Purpose**: [What this covers]
**Audience**: [Who should read this]
**Last Updated**: YYYY-MM-DD

## Overview
[Brief description of system aspect]

## Architecture
[System design details]

## Configuration
[Setup and configuration]

## Related Documentation
- [Link to related docs]
```

**Component Level Template**:
```markdown
# [Component Name]

**Purpose**: [Component function]
**Audience**: [Component developers/operators]
**Last Updated**: YYYY-MM-DD

## Overview
[Component description and purpose]

## Architecture
[Component design and integration]

## Configuration
[Component-specific setup]

## Operations
[How to use/maintain component]

## Related Documentation
- [Link to system docs]
- [Link to specific implementations]
```

**Specific Level Template**:
```markdown
# [Specific Implementation Name]

**Purpose**: [Implementation details]
**Audience**: [Feature developers/maintainers]
**Last Updated**: YYYY-MM-DD

## Implementation Details
[Technical specifics]

## Parameters/Configuration
[All parameters and their values]

## Usage Examples
[How to use this specific implementation]

## Related Documentation
- [Link to component overview]
- [Link to other specific implementations]
```

---

## 🔄 Documentation Update Workflow

### When Updating Existing Documentation

**Step 1: Locate Correct File**
```
Use semantic hierarchy to find the right file:
system/           → system/01_project_overview.md
components/        → components/[area]/[file].md
components/specific/ → components/[area]/specific/[file].md
reference/         → reference/[file].md
```

**Step 2: Update Last Modified Date**
```markdown
**Last Updated**: 2026-04-16 (today's date)
```

**Step 3: Update Cross-References**
- Check if other docs link to this one
- Update those links if file moved or renamed
- Add new links if content expanded

**Step 4: Review for Duplicates**
- Search for similar content that might now be redundant
- Consolidate or remove duplicates
- Update navigation to point to correct location

### Update Frequency Guidelines

| Document Type | Update Frequency | Trigger Events |
|---------------|------------------|-----------------|
| System Overview | Quarterly | Major architectural changes |
| Architecture | As needed | System design changes |
| Deployment | As needed | Deployment process changes |
| Component Overview | Monthly | Component functionality changes |
| API Reference | Per release | API changes |
| Specific Implementation | As needed | Feature changes |
| Operations Guide | Monthly | New issues/solutions |

---

## 🧹 Regular Maintenance Tasks

### Weekly (Quick Check)
- [ ] Review new documentation created this week
- [ ] Verify files are in correct semantic locations
- [ ] Check for duplicate content
- [ ] Update navigation if new docs added

### Monthly (Light Cleanup)
- [ ] Review ARCHIVE/ for files older than 90 days
- [ ] Check for broken internal links
- [ ] Update "Last Updated" dates on frequently used docs
- [ ] Archive outdated planning/analysis documents

### Quarterly (Deep Review)
- [ ] Complete documentation audit
- [ ] Identify subjects needing reorganization
- [ ] Archive historical content by quarter
- [ ] Review and update semantic hierarchy
- [ ] Update cross-project integration

### Annual (Major Reorganization)
- [ ] Comprehensive documentation review
- [ ] Evaluate semantic hierarchy effectiveness
- [ ] Restructure if needed (like today's reorganization)
- [ ] Archive old content (1+ years)
- [ ] Update documentation philosophy and guidelines

---

## 🚫 Prevention Guidelines

### What NOT to Do

**❌ Don't Create Root-Level Files**
- Avoid: `new_feature_doc.md` in `TECHNICAL_DOCS/`
- Do: Place in appropriate semantic directory

**❌ Don't Duplicate Content**
- Avoid: Copying same info to multiple files
- Do: Link to existing content, update in place

**❌ Don't Mix Semantic Levels**
- Avoid: General and specific content in same file
- Do: Separate by semantic level (your coffee cup example!)

**❌ Don't Ignore Navigation**
- Avoid: Creating docs without updating entry points
- Do: Always update relevant overview/navigation files

**❌ Don't Leave Orphans**
- Avoid: Moving files without updating references
- Do: Update all links and cross-references

**❌ Don't Skip Archiving**
- Avoid: Keeping outdated docs in active directories
- Do: Move to ARCHIVE/[quarter]/ promptly

---

## ✅ Quality Checklist

### Before Committing New Documentation

- [ ] **Semantic Level**: File is in correct directory for its subject level
- [ ] **No Duplicates**: Checked for existing similar content
- [ ] **Navigation Updated**: Added to relevant parent/overview documents
- [ ] **Cross-References**: Links to related documentation
- [ ] **Audience Clear**: Content is appropriate for intended readers
- [ ] **Date Updated**: "Last Updated" reflects current date
- [ ] **Name Consistent**: Follows naming convention for semantic level

### Before Completing Documentation Updates

- [ ] **Accuracy**: Content is technically correct
- [ ] **Completeness**: All relevant aspects covered
- [ ] **Clarity**: Writing is clear and understandable
- [ ] **Links Working**: All internal links resolve correctly
- [ ] **No Dead Content**: Removed or archived outdated sections

---

## 🛠️ Automation Opportunities

### Pre-Commit Hooks (Future Consideration)

```bash
# Documentation quality checks before committing
# 1. Check file location matches semantic level
# 2. Check for duplicate file names
# 3. Verify internal links work
# 4. Check naming conventions
```

### Documentation Review Scripts

```bash
# Weekly automated checks
# 1. Find docs in wrong locations
# 2. Identify duplicate content
# 3. Check for broken links
# 4. Report issues for review
```

### Navigation Updater

```bash
# Auto-update navigation when new docs added
# 1. Scan for new documentation files
# 2. Update relevant overview/entry files
# 3. Verify semantic hierarchy maintained
```

---

## 📊 Documentation Metrics to Track

### Quality Metrics
- **Duplicate Content**: Count of redundant information
- **Broken Links**: Number of invalid internal references
- **Outdated Content**: Files with "Last Updated" > 6 months old
- **Orphan Files**: Documents not linked from navigation

### Usage Metrics  
- **Most Accessed**: Frequently viewed documentation
- **Least Accessed**: Rarely used documentation (candidates for archival)
- **Search Terms**: What users are looking for (gaps to fill)

### Maintenance Metrics
- **Files Created**: New documentation per week/month
- **Files Updated**: Modifications per week/month
- **Files Archived**: Content moved to archive per quarter
- **Review Completion**: % of scheduled reviews completed

---

## 🎓 Training & Onboarding

### For New Team Members
1. **Review this guide**: Understand semantic hierarchy principles
2. **Study structure**: Learn documentation organization
3. **Practice**: Create first few documents with supervision
4. **Feedback**: Get review on documentation placement and quality

### For Existing Team Members
1. **Refresher**: Review this guide quarterly
2. **Updates**: Communicate any guideline changes
3. **Best Practices**: Share examples of good documentation
4. **Continuous Improvement**: Suggest improvements to maintenance process

---

## 🚨 Red Flags to Watch

### Warning Signs Documentation Needs Attention

- **Root directory bloat**: Many files accumulating in `TECHNICAL_DOCS/`
- **Duplicate filenames**: Multiple versions of similar content
- **Broken navigation**: Links in `00_START_HERE.md` don't work
- **Mixed semantic levels**: General and specific content confused
- **Stale dates**: Many "Last Updated" > 6 months old
- **Archive overflow**: ARCHIVE/ growing without organization

### Immediate Actions When Red Flags Appear

1. **Stop**: Pause new documentation creation
2. **Assess**: Review what's causing the issue
3. **Plan**: Determine reorganization approach
4. **Execute**: Apply fixes (like today's semantic reorganization)
5. **Document**: Record what went wrong and how to prevent

---

## 📞 Support & Escalation

### When Guidelines Are Unclear
- **Check examples**: Review existing well-organized docs
- **Ask for clarification**: Don't guess semantic level
- **Review this guide**: Refresh on maintenance principles

### When Structure Needs Changes
- **Propose changes**: Suggest hierarchy improvements
- **Get consensus**: Agree on structural modifications
- **Update this guide**: Keep maintenance guidelines current
- **Communicate changes**: Inform team of structural updates

---

## 🎯 Success Criteria

### Documentation Health Indicators

**Excellent Health**:
- ✅ 95%+ files in correct semantic locations
- ✅ < 5% duplicate content
- ✅ 100% working internal links
- ✅ All "Last Updated" < 3 months
- ✅ Clear navigation from entry points

**Good Health**:
- ✅ 80%+ files in correct semantic locations
- ✅ < 10% duplicate content
- ✅ 95%+ working internal links
- ✅ Most "Last Updated" < 6 months
- ✅ Good navigation from entry points

**Needs Attention**:
- ⚠️ < 80% files in correct semantic locations
- ⚠️ 10%+ duplicate content
- ⚠️ Broken internal links
- ⚠️ Many "Last Updated" > 6 months
- ⚠️ Poor navigation from entry points

---

## 📋 Quick Reference Card

### Before Creating Documentation
1. **What semantic level?** (system/component/specific/reference)
2. **Does this already exist?** (search first)
3. **Where should it go?** (follow hierarchy)
4. **What needs updating?** (navigation, cross-refs)

### Before Updating Documentation  
1. **Is this the right file?** (semantic location)
2. **What else references this?** (update links)
3. **Is this now duplicate?** (check for redundancy)
4. **Date updated?** (set current date)

### Weekly Maintenance
1. **New docs in right places?**
2. **Any duplicates created?**
3. **Navigation still accurate?**
4. **Archive outdated content?**

---

**Maintenance Guide Created**: 2026-04-16  
**Next Review**: 2026-07-16 (Quarterly)  
**Owner**: Documentation Team  
**Status**: Active - Follow these guidelines to maintain clean semantic organization
