# Testing Guide - Perple_X Workbench v1.1

**Purpose**: Manual testing checklist for v1.1 GUI enhancements  
**Tester**: Emma Vellard  
**Date**: 2024-07-01

---

## Pre-Testing Setup

### 1. Install Dependencies
```bash
cd /Users/evellard/Documents/Code/perplex-workbench
pip install -e .
```

**Expected**: No errors, pandas/openpyxl/plotly installed

### 2. Verify Installation
```bash
python -c "import pandas, openpyxl, plotly; print('✅ Dependencies OK')"
python -c "from perplex_workbench.gui.database_selector import show_database_selector; print('✅ Imports OK')"
```

**Expected**: Both print success messages

### 3. Launch GUI
```bash
perplex-gui
```

**Expected**: Browser opens to http://localhost:8501

---

## Feature Testing Checklist

### ✅ Feature 1: Database Selector

**Location**: Step 1 → Configuration section (right column)

- [ ] See "Thermodynamic Database" dropdown with stx21/hp633
- [ ] Default shows "stx21"
- [ ] Expand database details (shows modeled oxides)
- [ ] Click "Switch to hp633" button
- [ ] Success message appears
- [ ] All oxide labels update (check Composition Builder)
- [ ] Config persists (refresh page, still hp633)
- [ ] Switch back to stx21 works

**Pass/Fail**: ________  
**Notes**: _________________________________

---

### ✅ Feature 2: Enhanced Validation

**Location**: Composition Builder (when editing invalid composition)

- [ ] Go to Composition Builder mode
- [ ] Edit a composition with total < 95 wt%
- [ ] See ❌ error with specific suggestion (e.g., "Add X wt% to...")
- [ ] Fix composition to ~100 wt%
- [ ] See ✅ validation passed
- [ ] Try with hp633 database + TiO2 > 0.1
- [ ] See ⚠️ warning about database compatibility

**Pass/Fail**: ________  
**Notes**: _________________________________

---

### ✅ Feature 3: CSV/Excel Import/Export

**Location**: Composition Builder → "Import/Export Compositions" expander

#### Test Import
```bash
# Create test file:
cat > /tmp/test_comp.csv << 'EOF'
oxide,wt_percent
SiO2,45.0
MgO,35.0
Al2O3,4.0
FeO,8.0
CaO,3.5
Na2O,0.3
TiO2,0.2
K2O,0.0
P2O5,0.0
EOF
```

- [ ] Expand "Import/Export Compositions"
- [ ] Click "Upload CSV or Excel file"
- [ ] Upload `/tmp/test_comp.csv`
- [ ] See ✅ "Composition imported successfully"
- [ ] See table with oxide values
- [ ] Enter project name "test_import"
- [ ] Click "Save imported composition to config"
- [ ] See success message
- [ ] Verify "test_import" appears in saved models

#### Test Export
- [ ] Select existing model from dropdown
- [ ] Choose "CSV" format
- [ ] Click "Download CSV"
- [ ] File downloads successfully
- [ ] Open downloaded file - contains oxide values
- [ ] Repeat with "Excel" format
- [ ] Excel file downloads and opens correctly

**Pass/Fail**: ________  
**Notes**: _________________________________

---

### ✅ Feature 4: Batch Processing

**Location**: Sidebar → "Batch Processing" workspace mode

- [ ] Click "Batch Processing" in sidebar
- [ ] See batch processing interface
- [ ] Select base composition (e.g., moon_far_highlands)
- [ ] Choose oxide to vary: "FeO"
- [ ] Set min=6.0, max=10.0, step=1.0
- [ ] See "Number of models: 5"
- [ ] Expand "Preview generated models"
- [ ] See 5 models with FeO varying
- [ ] Click "Add batch to config"
- [ ] See ✅ success message
- [ ] Models appear in saved models list

**Optional** (if Perple_X installed):
- [ ] Click "Run all batch models"
- [ ] Pipeline executes
- [ ] See "Batch Results" matrix
- [ ] Validation status shows for each model

**Pass/Fail**: ________  
**Notes**: _________________________________

---

### ✅ Feature 5: Model Comparison

**Location**: Sidebar → "Compare Models" workspace mode

**Prerequisites**: Need at least 2 models in config

- [ ] Click "Compare Models" in sidebar
- [ ] See comparison interface
- [ ] Select 2 models from dropdown
- [ ] See 3 tabs: Composition, Properties, Validation

#### Tab 1: Composition
- [ ] See bar chart comparing oxide values
- [ ] For 2 models: see "Oxide Differences" table
- [ ] Differences shown in wt% and relative %

#### Tab 2: Properties
- [ ] If models have been run: see 4 property plots
- [ ] Density, Vp, Vs, Bulk Modulus vs Pressure
- [ ] Lines overlay correctly
- [ ] If no output: see info message

#### Tab 3: Validation
- [ ] See validation status table
- [ ] Check marks for existing files
- [ ] Status emoji (✅/❌/⏳)
- [ ] Summary metrics at bottom

**Pass/Fail**: ________  
**Notes**: _________________________________

---

### ✅ Feature 6: Phase Diagrams

**Location**: Step 5 → "Phase Diagram" tab

**Prerequisites**: Need a model that has been run through pipeline

- [ ] Run a model through pipeline (or use existing output)
- [ ] Go to Step 5: Validate / Export
- [ ] Click "Phase Diagram" tab
- [ ] See P-T coverage plot
- [ ] Toggle "Show density contours" checkbox
- [ ] Density colors appear on plot
- [ ] Hover over points shows T, P, ρ values
- [ ] See summary metrics (T range, P range, grid points)
- [ ] Info note explains this shows coverage, not full phase boundaries

**Pass/Fail**: ________  
**Notes**: _________________________________

---

### ✅ Feature 7: Auto-Save

**Location**: Sidebar → "Auto-save" section

- [ ] See "Auto-save" section in sidebar
- [ ] Toggle "Enable auto-save" checkbox ON
- [ ] Go to Composition Builder
- [ ] Start editing a composition
- [ ] Refresh the page (or close and reopen browser tab)
- [ ] See "🔄 Found unsaved work" banner
- [ ] Click "Recover" button
- [ ] Draft is restored
- [ ] Edit again and click "Dismiss" instead
- [ ] Banner disappears
- [ ] Toggle auto-save OFF
- [ ] Click "Clear all drafts" works

**Pass/Fail**: ________  
**Notes**: _________________________________

---

### ✅ Feature 8: UI Improvements

**Location**: Throughout app

- [ ] Sidebar shows 4 workspace modes (not just 2)
- [ ] All 4 modes clickable and switch correctly:
  - Run Pipeline
  - Build Composition
  - Batch Processing
  - Compare Models
- [ ] Step 5 has 3 tabs (not single page):
  - Validation & Output
  - Phase Diagram
  - Export
- [ ] Auto-save controls visible in sidebar
- [ ] Navigation feels smooth

**Pass/Fail**: ________  
**Notes**: _________________________________

---

## Integration Testing

### Workflow 1: Import → Edit → Run → Compare
- [ ] Import CSV composition
- [ ] Edit metadata in Composition Builder
- [ ] Run through pipeline (if Perple_X available)
- [ ] Compare with another model
- [ ] Export results

**Pass/Fail**: ________  
**Time taken**: ________ minutes

### Workflow 2: Batch → Run → Analyze
- [ ] Create batch sweep (5 models)
- [ ] Run batch through pipeline
- [ ] View results matrix
- [ ] Compare 2 models from batch
- [ ] View phase diagram for one

**Pass/Fail**: ________  
**Time taken**: ________ minutes

### Workflow 3: Database Switch Test
- [ ] Start with stx21
- [ ] Create composition with TiO2 = 0
- [ ] Switch to hp633
- [ ] Edit composition with TiO2 = 2.0 wt%
- [ ] Verify oxide labels updated
- [ ] Run pipeline
- [ ] Verify hp633 output includes TiO2

**Pass/Fail**: ________  
**Time taken**: ________ minutes

---

## Backward Compatibility

### Test v1.0 Config
- [ ] Use existing v1.0 config file
- [ ] Launch v1.1 GUI
- [ ] All models load correctly
- [ ] Old features still work (Run Pipeline, etc.)
- [ ] No errors or warnings

**Pass/Fail**: ________

---

## Performance Testing

### Large Dataset Test
- [ ] Create batch with 20 models
- [ ] Load comparison with 4 models
- [ ] Check GUI responsiveness
- [ ] Plotly renders in < 5 seconds
- [ ] No browser lag

**Pass/Fail**: ________  
**Performance notes**: _________________________________

---

## Edge Cases

### Invalid Inputs
- [ ] Upload invalid CSV (wrong format) → See error message
- [ ] Try to create batch with min > max → Error caught
- [ ] Compare 0 models → Info message shown
- [ ] View phase diagram with no output → Warning shown

**Pass/Fail**: ________  
**Notes**: _________________________________

---

## Final Checks

- [ ] No Python errors in terminal
- [ ] No browser console errors (F12 → Console)
- [ ] All buttons are clickable
- [ ] All text is readable
- [ ] No visual glitches
- [ ] Help text makes sense

**Pass/Fail**: ________

---

## Summary

**Total Features Tested**: 8  
**Features Passing**: ____  
**Features Failing**: ____  
**Critical Issues Found**: ____  
**Minor Issues Found**: ____  

**Overall Assessment**: __________________ (Ready/Needs fixes/Blocked)

**Next Steps**:
- [ ] Fix critical issues (if any)
- [ ] Update README.md with v1.1 features
- [ ] Create GitHub release
- [ ] Push to main branch

---

## Bug Report Template

If issues found, use this format:

```
**Bug**: [Brief description]
**Feature**: [Which feature - e.g., Database Selector]
**Steps to Reproduce**:
1. 
2. 
3. 

**Expected**: [What should happen]
**Actual**: [What actually happened]
**Error Messages**: [Copy any errors]
**Severity**: Critical / Major / Minor
**Screenshots**: [If applicable]
```

---

**Testing completed by**: ________________  
**Date**: ________________  
**Time spent**: ________ hours
