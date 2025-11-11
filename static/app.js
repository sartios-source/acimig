// ACI Analysis Tool - Client-Side Utilities with Modern Toast Notifications

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');

    // Icon mapping
    const icons = {
        success: `<svg class="h-5 w-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>`,
        error: `<svg class="h-5 w-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>`,
        warning: `<svg class="h-5 w-5 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
        </svg>`,
        info: `<svg class="h-5 w-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>`
    };

    // Color schemes
    const colorClasses = {
        success: 'bg-white border-l-4 border-green-500 shadow-lg',
        error: 'bg-white border-l-4 border-red-500 shadow-lg',
        warning: 'bg-white border-l-4 border-yellow-500 shadow-lg',
        info: 'bg-white border-l-4 border-blue-500 shadow-lg'
    };

    toast.className = `${colorClasses[type] || colorClasses.info} rounded-lg p-4 mb-4 flex items-start space-x-3 max-w-md transform transition-all duration-300 ease-out`;
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100px)';

    toast.innerHTML = `
        <div class="flex-shrink-0">
            ${icons[type] || icons.info}
        </div>
        <div class="flex-1 pt-0.5">
            <p class="text-sm font-medium text-gray-900">${message}</p>
        </div>
        <button onclick="this.parentElement.remove()" class="flex-shrink-0 ml-4 text-gray-400 hover:text-gray-600 transition-colors">
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
        </button>
    `;

    container.appendChild(toast);

    // Animate in
    setTimeout(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateX(0)';
    }, 10);

    // Auto remove after 5 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100px)';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

function validateFile(file, allowedExtensions) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (!allowedExtensions.includes(ext)) {
        showToast(`Invalid file type: .${ext}. Allowed: ${allowedExtensions.join(', ')}`, 'error');
        return false;
    }
    return true;
}
