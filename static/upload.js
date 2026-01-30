/**
 * ACI Analysis Tool - Enhanced Upload with Progress Tracking
 */

// Global state
const uploadQueue = [];
let activeUploads = 0;
const MAX_CONCURRENT_UPLOADS = 2;
const RETRY_STATUS = 429;
const RETRY_FALLBACK_MS = 10000;
const RETRY_JITTER_MS = 2500;
const RETRY_MAX_ATTEMPTS = 6;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initializeUploadZone();
    setupEventListeners();
});

function initializeUploadZone() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    if (!dropZone || !fileInput) return;

    // Click handler
    dropZone.addEventListener('click', (e) => {
        if (e.target.tagName !== 'BUTTON') {
            fileInput.click();
        }
    });

    // File input change
    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });

    // Drag & Drop handlers
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('drag-over');
        handleFiles(e.dataTransfer.files);
    });
}

function setupEventListeners() {
    // Additional listeners can be added here
    const cmdbInput = document.getElementById('cmdb-input');
    if (cmdbInput) {
        cmdbInput.addEventListener('change', (e) => {
            handleFiles(e.target.files);
        });
    }
}

function handleFiles(files) {
    if (!files || files.length === 0) return;

    // Validate and add files to queue
    for (const file of files) {
        const validation = validateUploadFile(file);
        if (validation.valid) {
            addFileToQueue(file);
        } else {
            showError(`${file.name}: ${validation.error}`);
        }
    }

    // Show queue
    document.getElementById('file-queue').style.display = 'block';

    // Auto-start uploads
    startAllUploads();
}

function validateUploadFile(file) {
    const allowedExtensions = ['json', 'xml', 'csv', 'txt', 'cfg', 'conf'];
    const maxSize = 1024 * 1024 * 1024; // 1GB

    // Check extension
    const ext = file.name.split('.').pop().toLowerCase();
    if (!allowedExtensions.includes(ext)) {
        return {
            valid: false,
            error: `Unsupported file type. Allowed: ${allowedExtensions.join(', ')}`
        };
    }

    // Check size
    if (file.size > maxSize) {
        return {
            valid: false,
            error: `File too large. Maximum size is 1GB`
        };
    }

    // Check for duplicates in queue
    if (uploadQueue.find(item => item.file.name === file.name)) {
        return {
            valid: false,
            error: 'File already in upload queue'
        };
    }

    return { valid: true };
}

function addFileToQueue(file) {
    const fileId = `file-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    const fileItem = {
        id: fileId,
        file: file,
        status: 'queued',  // queued, uploading, complete, error
        progress: 0,
        uploadedBytes: 0,
        totalBytes: file.size,
        xhr: null,
        startTime: null,
        error: null,
        attempts: 0,
        nextRetryAt: null
    };

    uploadQueue.push(fileItem);
    renderFileItem(fileItem);
    updateOverallProgress();
}

function renderFileItem(fileItem) {
    const fileList = document.getElementById('file-list');

    const fileItemDiv = document.createElement('div');
    fileItemDiv.className = 'file-item';
    fileItemDiv.id = fileItem.id;

    fileItemDiv.innerHTML = `
        <div class="file-header">
            <div class="file-info">
                <div class="file-icon">${getFileIcon(fileItem.file.name)}</div>
                <div class="file-details">
                    <h4>${fileItem.file.name}</h4>
                    <span class="file-size">${formatBytes(fileItem.file.size)}</span>
                </div>
            </div>
            <div class="file-actions">
                <button class="btn btn-xs" onclick="pauseUpload('${fileItem.id}')" id="${fileItem.id}-pause" disabled>
                    ⏸️
                </button>
                <button class="btn btn-xs btn-danger" onclick="cancelUpload('${fileItem.id}')">
                    ✖️
                </button>
            </div>
        </div>
        <div class="file-progress">
            <div class="progress-bar-container">
                <div id="${fileItem.id}-progress-bar" class="progress-bar" style="width: 0%"></div>
            </div>
            <div class="progress-text">
                <span id="${fileItem.id}-status">Queued</span>
                <span id="${fileItem.id}-percent">0%</span>
            </div>
        </div>
    `;

    fileList.appendChild(fileItemDiv);
}

function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const icons = {
        'json': '📄',
        'xml': '📄',
        'csv': '📊',
        'txt': '📝',
        'cfg': '⚙️',
        'conf': '⚙️'
    };
    return icons[ext] || '📄';
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function startAllUploads() {
    document.getElementById('start-all-btn').disabled = true;
    document.getElementById('pause-all-btn').disabled = false;

    // Start uploads up to max concurrent
    for (const fileItem of uploadQueue) {
        if (fileItem.status === 'queued' && activeUploads < MAX_CONCURRENT_UPLOADS) {
            startUpload(fileItem);
        }
    }
}

function startUpload(fileItem) {
    if (fileItem.status !== 'queued') return;

    activeUploads++;
    fileItem.status = 'uploading';
    fileItem.startTime = Date.now();

    const formData = new FormData();
    formData.append('file', fileItem.file);
    const fabricInput = document.getElementById('fabric-name-input');
    if (fabricInput && fabricInput.value) {
        formData.append('fabric_name', fabricInput.value);
    }

    const xhr = new XMLHttpRequest();
    fileItem.xhr = xhr;
    xhr.timeout = 60 * 60 * 1000;

    // Progress handler
    xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
            fileItem.uploadedBytes = e.loaded;
            fileItem.progress = (e.loaded / e.total) * 100;
            updateFileProgress(fileItem);
            updateOverallProgress();
        }
    });

    // Complete handler
    xhr.addEventListener('load', () => {
        activeUploads--;

        let response = null;
        if (xhr.responseText) {
            try {
                response = JSON.parse(xhr.responseText);
            } catch (e) {
                response = null;
            }
        }

        if (xhr.status === 200 && response && response.success) {
            fileItem.status = 'complete';
            fileItem.progress = 100;
            updateFileProgress(fileItem);
            showSuccess(`${fileItem.file.name} uploaded successfully`);

            // Start next queued upload
            startNextUpload();
        } else if (xhr.status === RETRY_STATUS) {
            const retryAfter = parseInt(xhr.getResponseHeader('Retry-After') || '', 10);
            const delayMs = Number.isFinite(retryAfter)
                ? Math.max(1, retryAfter) * 1000
                : RETRY_FALLBACK_MS + Math.floor(Math.random() * RETRY_JITTER_MS);
            fileItem.attempts += 1;
            if (fileItem.attempts <= RETRY_MAX_ATTEMPTS) {
                fileItem.status = 'queued';
                fileItem.nextRetryAt = Date.now() + delayMs;
                fileItem.error = `Rate limited. Retrying in ${Math.round(delayMs / 1000)}s...`;
                updateFileProgress(fileItem);
                setTimeout(() => {
                    if (fileItem.status === 'queued') startUpload(fileItem);
                }, delayMs);
            } else {
                fileItem.status = 'error';
                fileItem.error = 'Rate limit exceeded too many times. Try again later.';
                updateFileProgress(fileItem);
                showError(`${fileItem.file.name}: ${fileItem.error}`);
            }
        } else {
            fileItem.status = 'error';
            if (response && response.error) {
                fileItem.error = response.error;
            } else if (xhr.status === 0) {
                fileItem.error = 'Upload failed (network error or CORS)';
            } else if (!response && xhr.responseText) {
                fileItem.error = `HTTP ${xhr.status}: ${xhr.statusText} (${xhr.responseText.slice(0, 200)})`;
            } else {
                fileItem.error = `HTTP ${xhr.status}: ${xhr.statusText}`;
            }
            updateFileProgress(fileItem);
            showError(`${fileItem.file.name}: ${fileItem.error}`);
        }

        updateOverallProgress();

        // Check if all done
        if (isQueueComplete()) {
            onAllUploadsComplete();
        }
    });

    xhr.addEventListener('error', () => {
        activeUploads--;
        fileItem.status = 'error';
        fileItem.error = 'Network error during upload';
        updateFileProgress(fileItem);
        showError(`${fileItem.file.name}: ${fileItem.error}`);
        updateOverallProgress();
        if (isQueueComplete()) {
            onAllUploadsComplete();
        }
    });

    xhr.addEventListener('timeout', () => {
        activeUploads--;
        fileItem.status = 'error';
        fileItem.error = 'Upload timed out';
        updateFileProgress(fileItem);
        showError(`${fileItem.file.name}: ${fileItem.error}`);
        updateOverallProgress();
        if (isQueueComplete()) {
            onAllUploadsComplete();
        }
    });

    // Abort handler
    xhr.addEventListener('abort', () => {
        activeUploads--;
        fileItem.status = 'cancelled';
        updateFileProgress(fileItem);
        updateOverallProgress();
    });

    // Send request
    xhr.open('POST', '/upload');
    xhr.send(formData);

    updateFileProgress(fileItem);
}

function startNextUpload() {
    for (const fileItem of uploadQueue) {
        if (fileItem.status === 'queued' && activeUploads < MAX_CONCURRENT_UPLOADS) {
            startUpload(fileItem);
            break;
        }
    }
}

function updateFileProgress(fileItem) {
    const progressBar = document.getElementById(`${fileItem.id}-progress-bar`);
    const statusSpan = document.getElementById(`${fileItem.id}-status`);
    const percentSpan = document.getElementById(`${fileItem.id}-percent`);
    const fileItemDiv = document.getElementById(fileItem.id);
    const pauseBtn = document.getElementById(`${fileItem.id}-pause`);

    if (!progressBar) return;

    progressBar.style.width = `${fileItem.progress}%`;
    percentSpan.textContent = `${Math.round(fileItem.progress)}%`;

    if (fileItem.status === 'queued') {
        statusSpan.textContent = 'Queued';
        fileItemDiv.className = 'file-item';
        pauseBtn.disabled = true;
    } else if (fileItem.status === 'uploading') {
        const speed = calculateSpeed(fileItem);
        const remaining = calculateRemainingTime(fileItem);
        statusSpan.textContent = `Uploading... ${speed} | ${remaining} remaining`;
        fileItemDiv.className = 'file-item uploading';
        progressBar.className = 'progress-bar';
        pauseBtn.disabled = false;
    } else if (fileItem.status === 'complete') {
        statusSpan.textContent = 'Complete';
        fileItemDiv.className = 'file-item complete';
        progressBar.className = 'progress-bar complete';
        pauseBtn.disabled = true;
    } else if (fileItem.status === 'error') {
        statusSpan.textContent = `Error: ${fileItem.error}`;
        fileItemDiv.className = 'file-item error';
        progressBar.className = 'progress-bar error';
        pauseBtn.disabled = true;
    }
}

function calculateSpeed(fileItem) {
    if (!fileItem.startTime || fileItem.uploadedBytes === 0) return '-- KB/s';

    const elapsed = (Date.now() - fileItem.startTime) / 1000; // seconds
    const speed = fileItem.uploadedBytes / elapsed; // bytes per second

    return formatBytes(speed) + '/s';
}

function calculateRemainingTime(fileItem) {
    if (!fileItem.startTime || fileItem.uploadedBytes === 0) return '--s';

    const elapsed = (Date.now() - fileItem.startTime) / 1000;
    const speed = fileItem.uploadedBytes / elapsed;
    const remaining = (fileItem.totalBytes - fileItem.uploadedBytes) / speed;

    if (remaining < 60) {
        return Math.round(remaining) + 's';
    } else if (remaining < 3600) {
        return Math.round(remaining / 60) + 'm';
    } else {
        return Math.round(remaining / 3600) + 'h';
    }
}

function updateOverallProgress() {
    const totalFiles = uploadQueue.length;
    const completeFiles = uploadQueue.filter(f => f.status === 'complete').length;
    const totalBytes = uploadQueue.reduce((sum, f) => sum + f.totalBytes, 0);
    const uploadedBytes = uploadQueue.reduce((sum, f) => sum + f.uploadedBytes, 0);
    const overallProgress = totalBytes > 0 ? (uploadedBytes / totalBytes) * 100 : 0;

    // Update if elements exist
    const overallStatus = document.getElementById('overall-status');
    const overallStats = document.getElementById('overall-stats');
    const overallProgressBar = document.getElementById('overall-progress-bar');
    const overallPercent = document.getElementById('overall-percent');

    if (overallStatus) {
        overallStatus.textContent = `${completeFiles} / ${totalFiles} files complete`;
    }
    if (overallStats) {
        overallStats.textContent = `${formatBytes(uploadedBytes)} / ${formatBytes(totalBytes)}`;
    }
    if (overallProgressBar) {
        overallProgressBar.style.width = `${overallProgress}%`;
    }
    if (overallPercent) {
        overallPercent.textContent = `${Math.round(overallProgress)}%`;
    }
}

function pauseUpload(fileId) {
    const fileItem = uploadQueue.find(f => f.id === fileId);
    if (fileItem && fileItem.xhr) {
        fileItem.xhr.abort();
        fileItem.status = 'paused';
        updateFileProgress(fileItem);
    }
}

function cancelUpload(fileId) {
    const fileItem = uploadQueue.find(f => f.id === fileId);
    if (fileItem) {
        if (fileItem.xhr) {
            fileItem.xhr.abort();
        }

        // Remove from queue
        const index = uploadQueue.indexOf(fileItem);
        if (index > -1) {
            uploadQueue.splice(index, 1);
        }

        // Remove from UI
        const fileItemDiv = document.getElementById(fileId);
        if (fileItemDiv) {
            fileItemDiv.remove();
        }

        updateOverallProgress();
    }
}

function pauseAllUploads() {
    for (const fileItem of uploadQueue) {
        if (fileItem.status === 'uploading') {
            pauseUpload(fileItem.id);
        }
    }
    document.getElementById('pause-all-btn').disabled = true;
    document.getElementById('start-all-btn').disabled = false;
}

function cancelAllUploads() {
    // Create copy to avoid mutation during iteration
    const queueCopy = [...uploadQueue];
    for (const fileItem of queueCopy) {
        cancelUpload(fileItem.id);
    }

    document.getElementById('file-queue').style.display = 'none';
}

function isQueueComplete() {
    return uploadQueue.every(f => f.status === 'complete' || f.status === 'error');
}

function onAllUploadsComplete() {
    const successCount = uploadQueue.filter(f => f.status === 'complete').length;
    const errorCount = uploadQueue.filter(f => f.status === 'error').length;

    showSuccess(`Upload complete! ${successCount} file(s) uploaded successfully`);

    if (errorCount > 0) {
        showError(`${errorCount} file(s) failed to upload`);
    }

    // Reload page after 2 seconds to show new datasets
    setTimeout(() => {
        location.reload();
    }, 2000);
}

function showSuccess(message) {
    // Simple alert for now - can be enhanced with toast notifications
    console.log('✓ Success:', message);
    // Could add a toast notification here
}

function showError(message) {
    // Simple alert for now - can be enhanced with toast notifications
    console.error('✗ Error:', message);
    alert(message);
}

// Dataset management functions
function viewDataset(filename) {
    // Implementation for viewing dataset details
    alert(`View dataset: ${filename}\n\nThis feature can be enhanced to show detailed object breakdown.`);
}

function deleteDataset(filename) {
    if (confirm(`Are you sure you want to delete "${filename}"?`)) {
        fetch(`/api/dataset/${filename}`, {
            method: 'DELETE'
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showSuccess(`Deleted ${filename}`);
                location.reload();
            } else {
                showError(data.error || 'Failed to delete dataset');
            }
        })
        .catch(err => {
            showError('Network error while deleting dataset');
        });
    }
}
