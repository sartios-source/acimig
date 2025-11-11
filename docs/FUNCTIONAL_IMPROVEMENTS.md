# ACI Analysis Tool - Functional Improvements Plan

## Executive Summary

Comprehensive functional improvements to enhance usability, performance, and user experience. Focus areas: file uploads, data validation, progress tracking, and workflow optimization.

---

## 1. Enhanced File Upload System

### Current State
- Max file size: 100MB
- Basic upload UI
- No progress tracking
- Sequential uploads
- No pre-validation
- No chunk upload support

### Proposed Improvements

#### 1.1 Large File Support (500MB+)
**Implementation:**
- Increase `MAX_CONTENT_LENGTH` to 1GB
- Add chunked upload support for files >100MB
- Stream processing for large files (don't load entire file in memory)
- Background processing with job queue

**Benefits:**
- Support enterprise-scale ACI exports
- Prevent timeout errors
- Reduce memory usage
- Better server stability

**Technical Approach:**
```python
# Chunked upload endpoint
@app.route('/upload/chunk', methods=['POST'])
def upload_chunk():
    chunk = request.files['chunk']
    chunk_number = int(request.form['chunkNumber'])
    total_chunks = int(request.form['totalChunks'])
    file_id = request.form['fileId']

    # Save chunk to temp location
    # When all chunks received, reassemble and process
```

#### 1.2 Multiple File Upload with Progress Tracking
**Implementation:**
- Drag-and-drop interface
- Multiple file selection
- Individual progress bars per file
- Overall progress indicator
- Parallel uploads (configurable max 3)
- Retry failed uploads

**UI Components:**
```
┌─────────────────────────────────────────────────────┐
│ 📤 Upload ACI Data Files                            │
├─────────────────────────────────────────────────────┤
│ Drag files here or click to browse                  │
│ [Browse Files]                                       │
├─────────────────────────────────────────────────────┤
│ aci_export.json          [████████░░] 80%  15s left │
│ cmdb_devices.csv         [██████████] 100% Complete │
│ legacy_config.txt        [██░░░░░░░░] 20%  45s left │
├─────────────────────────────────────────────────────┤
│ Overall: 3 files, 2.1 GB  [███████░░░] 67%          │
│ Cancel All | Pause | Resume                         │
└─────────────────────────────────────────────────────┘
```

#### 1.3 Pre-Upload Validation
**Implementation:**
- Client-side validation before upload
- File type checking
- Size validation
- Format detection (JSON/XML structure peek)
- Duplicate file detection

**Validation Checks:**
```javascript
// Before upload
- File extension matches allowed types
- File size within limits
- JSON/XML well-formed (first 1KB check)
- Not a duplicate of existing dataset
- Warn if file seems too small/large for type
```

---

## 2. Data Completeness Validation

### Current State
- Basic parsing validation
- No completeness checks
- No object count warnings
- No missing data alerts

### Proposed Improvements

#### 2.1 Required Object Detection
**Implementation:**
- Check for required ACI object types
- Warn if critical objects missing
- Suggest additional data to upload

**Validation Matrix:**
```
Required for Analysis:
✓ fvAEPg (EPGs)               - REQUIRED
✓ fabricNode (Leafs/Spines)   - REQUIRED
○ eqptFex (FEX)               - Optional for offboard mode
✓ fvRsPathAtt (Path bindings) - REQUIRED for mapping
○ fvBD (Bridge Domains)       - Optional but recommended
○ vzBrCP (Contracts)          - Optional but recommended
○ fvCtx (VRFs)                - Optional but recommended

Analysis Impact:
- Missing eqptFex: Cannot perform port utilization analysis
- Missing fvBD: Cannot perform BD-EPG mapping
- Missing vzBrCP: Cannot detect contract dependencies
```

#### 2.2 Data Quality Indicators
**Visual Dashboard:**
```
┌──────────────────────────────────────────┐
│ Data Completeness: 85%                   │
├──────────────────────────────────────────┤
│ ✓ EPGs:          981 objects             │
│ ✓ Leafs:         120 objects             │
│ ✓ FEX:           633 objects             │
│ ✓ Path Bindings: 2,841 objects           │
│ ⚠ Bridge Domains: 0 objects (missing)    │
│ ⚠ VRFs:          0 objects (missing)     │
│ ✓ Contracts:     22 objects              │
├──────────────────────────────────────────┤
│ Analysis Capabilities:                   │
│ ✓ Port Utilization                       │
│ ✓ Topology Mapping                       │
│ ✓ EPG Complexity                         │
│ ✗ BD-EPG Mapping (missing BDs)           │
│ ⚠ Contract Analysis (partial)            │
└──────────────────────────────────────────┘
```

#### 2.3 Smart Data Suggestions
**Implementation:**
- Analyze uploaded data
- Suggest what's missing
- Provide data collection commands

**Example Output:**
```
💡 Suggested Additional Data:

To enable full analysis capabilities, please upload:

1. Bridge Domains (fvBD)
   Command: moquery -c fvBD -o json > bridge_domains.json

2. VRFs (fvCtx)
   Command: moquery -c fvCtx -o json > vrfs.json

3. Subnets (fvSubnet)
   Command: moquery -c fvSubnet -o json > subnets.json
```

---

## 3. Progress Tracking & Status Updates

### Current State
- No upload progress
- No processing status
- Blocking operations
- Page reload after upload

### Proposed Improvements

#### 3.1 Real-time Progress Updates
**Implementation:**
- WebSocket or Server-Sent Events (SSE)
- Upload progress percentage
- Processing status updates
- Parse progress for large files

**Status Phases:**
```
1. Uploading:    [████████░░] 80% (1.2 GB / 1.5 GB)
2. Saving:       [██████████] 100%
3. Parsing:      [████░░░░░░] 40% (12,000 / 31,000 objects)
4. Validating:   [████████░░] 80%
5. Indexing:     [██████████] 100%
✓ Complete: 31,757 objects indexed in 45 seconds
```

#### 3.2 Background Processing
**Implementation:**
- Job queue (Redis + Celery or simple Python queue)
- Process large files asynchronously
- Status polling endpoint
- Notification when complete

**User Experience:**
```
User uploads large file →
  Returns immediately with job ID →
    Shows "Processing in background..." →
      Poll /api/jobs/<id>/status →
        Update UI with progress →
          Notify when complete
```

#### 3.3 Processing Time Estimates
**Implementation:**
- Track historical processing times
- Estimate time based on file size
- Update estimate as processing progresses

---

## 4. Upload UI/UX Enhancements

### Proposed Improvements

#### 4.1 Drag & Drop Interface
**Features:**
- Visual drop zone
- Hover state animation
- Multiple file drop
- File type icons
- Thumbnail previews for CSV

#### 4.2 Upload Queue Management
**Features:**
- Pause/Resume individual uploads
- Cancel uploads
- Reorder queue
- Priority setting
- Auto-retry failed uploads

#### 4.3 Upload History & Management
**Features:**
- View recent uploads
- Re-upload previous files
- Delete old datasets
- Export dataset list
- Dataset versioning

---

## 5. Workflow Improvements

### 5.1 Guided Upload Wizard
**Implementation:**
- Step-by-step upload process
- Explain what each file type does
- Suggest upload order
- Validate at each step

**Wizard Steps:**
```
Step 1: Select Mode
  ○ Offboard (FEX decommission)
  ○ Onboard (New deployment)
  ○ EVPN Migration

Step 2: Upload ACI Data
  Required:
  - ACI fabric export (JSON/XML)

  Recommended:
  - CMDB data (CSV)
  - Legacy configs (TXT)

  [Upload Files...]

Step 3: Validate Data
  ✓ 981 EPGs detected
  ✓ 120 Leafs detected
  ⚠ No CMDB data (optional)

  [Continue] [Add More Files]

Step 4: Configure Analysis
  - Select tenants to analyze
  - Set migration timeline
  - Configure VLAN ranges

  [Start Analysis]
```

### 5.2 Batch Upload Templates
**Implementation:**
- Pre-configured upload templates
- Common data collection scenarios
- Command generators

**Templates:**
```
Enterprise Full Export:
  ☐ All EPGs (fvAEPg)
  ☐ All Tenants (fvTenant)
  ☐ Fabric Nodes (fabricNode)
  ☐ FEX Devices (eqptFex)
  ☐ Path Attachments (fvRsPathAtt)
  ☐ Bridge Domains (fvBD)
  ☐ Contracts (vzBrCP)

  [Generate Collection Script]

Output: collect_aci_data.sh with all moquery commands
```

### 5.3 Auto-Detection of Upload Type
**Implementation:**
- Analyze file content
- Auto-categorize as ACI/CMDB/Legacy
- Suggest format corrections

---

## 6. Error Handling & Recovery

### 6.1 Graceful Error Handling
**Features:**
- Detailed error messages
- Suggested fixes
- Partial upload recovery
- Rollback capability

**Example:**
```
❌ Upload Failed: aci_export.json

Error: Invalid JSON at line 15,234
  "attributes": {
    "dn": "uni/tn-Production/ap-WebApp/epg-Frontend"
    "name": "Frontend"  <-- Missing comma
  }

💡 Suggested Fix:
  1. Open file in text editor
  2. Navigate to line 15,234
  3. Add comma after "Frontend"

[Download Error Report] [Retry Upload] [Skip File]
```

### 6.2 Upload Resume
**Implementation:**
- Save upload state
- Resume from last chunk
- Handle network interruptions

---

## 7. Performance Optimizations

### 7.1 Streaming Parser
**Implementation:**
- Stream large JSON/XML files
- Don't load entire file in memory
- Process incrementally

**Benefits:**
- Support 1GB+ files
- Constant memory usage
- Faster processing start

### 7.2 Parallel Processing
**Implementation:**
- Process multiple files concurrently
- Parse while uploading next file
- Multi-threaded validation

### 7.3 Caching
**Implementation:**
- Cache parsed objects
- Index file checksums
- Skip re-parsing unchanged files

---

## 8. Data Export & Portability

### 8.1 Export Functionality
**Features:**
- Export fabric data as JSON
- Export analysis results
- Export visualizations
- Backup entire fabric

### 8.2 Import/Export Fabrics
**Features:**
- Export fabric with all datasets
- Import fabric bundle (zip)
- Share fabric configurations

---

## Priority Implementation Roadmap

### Phase 1: Critical (Immediate)
1. ✅ Large file support (500MB+)
2. ✅ Progress bars for uploads
3. ✅ Multiple file upload
4. ✅ Data completeness validation

### Phase 2: High Priority (Next Sprint)
5. Drag & drop interface
6. Chunked upload for >100MB files
7. Background processing
8. Upload queue management

### Phase 3: Medium Priority
9. Guided upload wizard
10. Smart data suggestions
11. Upload history
12. Auto-retry

### Phase 4: Enhancement
13. Batch templates
14. Streaming parser
15. Export functionality
16. WebSocket progress updates

---

## Technical Implementation Notes

### File Size Configuration
```python
# config.py
MAX_CONTENT_LENGTH = 1024 * 1024 * 1024  # 1GB
CHUNK_SIZE = 5 * 1024 * 1024  # 5MB chunks
MAX_PARALLEL_UPLOADS = 3
UPLOAD_TIMEOUT = 3600  # 1 hour for large files
```

### Progress Tracking Backend
```python
# upload_progress.py
class UploadManager:
    def __init__(self):
        self.jobs = {}

    def create_job(self, job_id, total_size):
        self.jobs[job_id] = {
            'status': 'uploading',
            'progress': 0,
            'total_size': total_size,
            'uploaded_size': 0,
            'start_time': time.time()
        }

    def update_progress(self, job_id, uploaded_size):
        job = self.jobs[job_id]
        job['uploaded_size'] = uploaded_size
        job['progress'] = (uploaded_size / job['total_size']) * 100

    def get_status(self, job_id):
        return self.jobs.get(job_id)
```

### Client-side Progress
```javascript
// upload.js
function uploadWithProgress(file) {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append('file', file);

    xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
            const percentComplete = (e.loaded / e.total) * 100;
            updateProgressBar(file.name, percentComplete);
        }
    });

    xhr.addEventListener('load', () => {
        if (xhr.status === 200) {
            const response = JSON.parse(xhr.responseText);
            showSuccess(response);
        }
    });

    xhr.open('POST', '/upload');
    xhr.send(formData);
}
```

---

## Success Metrics

### User Experience Metrics
- Upload time for 500MB file: < 2 minutes
- Time to first progress update: < 1 second
- Failed upload rate: < 1%
- User satisfaction: > 90%

### Performance Metrics
- Memory usage during 1GB upload: < 200MB
- Concurrent uploads supported: 3+
- Parse time for 50K objects: < 30 seconds
- UI responsiveness during upload: 60 FPS

---

## Conclusion

These functional improvements will significantly enhance the user experience, especially for enterprise-scale deployments. Priority focus on large file support, progress tracking, and data validation will provide immediate value while setting foundation for future enhancements.

**Next Steps:**
1. Implement Phase 1 critical improvements
2. User testing with large datasets
3. Gather feedback
4. Iterate on Phase 2 features

