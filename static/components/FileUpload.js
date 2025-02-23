class FileUpload extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });
        this.render();
    }

    connectedCallback() {
        this.setupEventListeners();
    }

    setupEventListeners() {
        const dropZone = this.shadowRoot.querySelector('.drop-zone');
        const fileInput = this.shadowRoot.querySelector('input[type="file"]');
        const uploadButton = this.shadowRoot.querySelector('.upload-button');

        // Make the drop zone clickable
        dropZone.addEventListener('click', () => {
            fileInput.click();
        });

        // Drag and drop events
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('dragover');
        });

        dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('dragover');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('dragover');
            const files = e.dataTransfer.files;
            this.handleFiles(files);
        });

        // File input change
        fileInput.addEventListener('change', (e) => {
            this.handleFiles(e.target.files);
        });

        // Upload button click
        uploadButton.addEventListener('click', () => {
            const files = this.shadowRoot.querySelector('input[type="file"]').files;
            if (files.length > 0) {
                this.uploadFiles(files);
            }
        });
    }

    handleFiles(files) {
        const fileList = this.shadowRoot.querySelector('.file-list');
        fileList.innerHTML = '';

        Array.from(files).forEach(file => {
            if (!file.name.toLowerCase().endsWith('.pdf')) {
                alert('Only PDF files are allowed');
                return;
            }
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';
            fileItem.innerHTML = `
                <span class="file-name">${file.name}</span>
                <span class="file-size">${this.formatFileSize(file.size)}</span>
            `;
            fileList.appendChild(fileItem);
        });

        const hasValidFiles = fileList.children.length > 0;
        this.shadowRoot.querySelector('.upload-button').style.display = hasValidFiles ? 'block' : 'none';
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    async uploadFiles(files) {
        const formData = new FormData();
        Array.from(files).forEach(file => {
            formData.append('files', file);
        });

        try {
            const response = await fetch('/api/extract/batch', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Upload failed');
            }

            const data = await response.json();
            
            // Dispatch event for task manager
            const event = new CustomEvent('filesUploaded', {
                detail: { taskId: data.task_id },
                bubbles: true,
                composed: true
            });
            this.dispatchEvent(event);

            // Reset the form
            this.shadowRoot.querySelector('input[type="file"]').value = '';
            this.shadowRoot.querySelector('.file-list').innerHTML = '';
            this.shadowRoot.querySelector('.upload-button').style.display = 'none';

        } catch (error) {
            console.error('Error uploading files:', error);
            alert('Failed to upload files. Please try again.');
        }
    }

    render() {
        const style = `
            <style>
                :host {
                    display: block;
                    margin: 20px;
                    font-family: Arial, sans-serif;
                }
                .drop-zone {
                    border: 2px dashed #ccc;
                    border-radius: 4px;
                    padding: 20px;
                    text-align: center;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    background-color: #fafafa;
                }
                .drop-zone:hover {
                    border-color: #4CAF50;
                    background-color: #f0f0f0;
                }
                .drop-zone.dragover {
                    border-color: #4CAF50;
                    background-color: rgba(76, 175, 80, 0.1);
                }
                .file-input {
                    display: none;
                }
                .upload-button {
                    display: none;
                    margin-top: 10px;
                    padding: 10px 20px;
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    transition: background-color 0.3s ease;
                    font-size: 14px;
                    font-weight: bold;
                }
                .upload-button:hover {
                    background-color: #45a049;
                }
                .file-list {
                    margin-top: 10px;
                }
                .file-item {
                    display: flex;
                    justify-content: space-between;
                    padding: 8px;
                    background-color: #f9f9f9;
                    border-radius: 4px;
                    margin: 5px 0;
                    border: 1px solid #eee;
                }
                .file-name {
                    flex-grow: 1;
                    margin-right: 10px;
                    font-size: 14px;
                }
                .file-size {
                    color: #666;
                    font-size: 12px;
                }
            </style>
        `;

        this.shadowRoot.innerHTML = `
            ${style}
            <div class="file-upload">
                <div class="drop-zone">
                    <p>Drag and drop PDF files here or click to select files</p>
                    <input type="file" class="file-input" multiple accept=".pdf">
                </div>
                <div class="file-list"></div>
                <button class="upload-button">Upload Files</button>
            </div>
        `;
    }
}

customElements.define('file-upload', FileUpload); 