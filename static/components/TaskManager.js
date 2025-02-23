class TaskManager extends HTMLElement {
    constructor() {
        super();
        this.tasks = new Map();
        this.attachShadow({ mode: 'open' });
        this.render();
    }

    connectedCallback() {
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Listen for file upload events
        document.addEventListener('filesUploaded', (event) => {
            const { taskId } = event.detail;
            this.addTask(taskId);
        });
    }

    addTask(taskId) {
        this.tasks.set(taskId, {
            status: 'pending',
            progress: 0,
            results: null,
            error: null
        });
        this.startPolling(taskId);
        this.render();
    }

    async startPolling(taskId) {
        const pollStatus = async () => {
            try {
                const response = await fetch(`/api/tasks/${taskId}/status`);
                if (!response.ok) {
                    throw new Error('Failed to fetch task status');
                }
                
                const status = await response.json();
                const task = this.tasks.get(taskId);
                
                if (task) {
                    task.status = status.status;
                    task.progress = Math.round(
                        (status.processed_files / status.total_files) * 100
                    );
                    task.error = status.error_message;
                    
                    if (['completed', 'failed'].includes(status.status)) {
                        await this.fetchResults(taskId);
                        clearInterval(task.interval);
                    }
                    
                    this.render();
                }
            } catch (error) {
                console.error('Error polling task status:', error);
                const task = this.tasks.get(taskId);
                if (task) {
                    task.error = error.message;
                    this.render();
                }
            }
        };

        // Poll every 2 seconds
        const task = this.tasks.get(taskId);
        task.interval = setInterval(pollStatus, 2000);
        pollStatus(); // Initial poll
    }

    async fetchResults(taskId) {
        try {
            const response = await fetch(`/api/tasks/${taskId}/results`);
            if (!response.ok) {
                throw new Error('Failed to fetch results');
            }
            
            const data = await response.json();
            const task = this.tasks.get(taskId);
            if (task) {
                task.results = data.results;
                this.render();
            }
        } catch (error) {
            console.error('Error fetching results:', error);
            const task = this.tasks.get(taskId);
            if (task) {
                task.error = error.message;
                this.render();
            }
        }
    }

    formatJson(data) {
        try {
            return JSON.stringify(data, null, 2)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
        } catch (error) {
            return 'Error formatting data';
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
                .task {
                    border: 1px solid #ddd;
                    margin: 10px 0;
                    padding: 15px;
                    border-radius: 4px;
                    background-color: white;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                }
                .task-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 10px;
                }
                .progress-bar {
                    height: 20px;
                    background-color: #f0f0f0;
                    border-radius: 10px;
                    overflow: hidden;
                    margin: 10px 0;
                }
                .progress-fill {
                    height: 100%;
                    background-color: #4CAF50;
                    transition: width 0.3s ease;
                }
                .status {
                    display: inline-block;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: bold;
                    text-transform: uppercase;
                }
                .status.pending { 
                    background-color: #ffd700;
                    color: #856404;
                }
                .status.processing { 
                    background-color: #87ceeb;
                    color: #004085;
                }
                .status.completed { 
                    background-color: #90ee90;
                    color: #155724;
                }
                .status.failed { 
                    background-color: #ffcccb;
                    color: #721c24;
                }
                .results {
                    margin-top: 10px;
                }
                .file-result {
                    margin: 5px 0;
                    padding: 10px;
                    background-color: #f9f9f9;
                    border-radius: 4px;
                    border: 1px solid #eee;
                }
                .file-result-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 10px;
                }
                .error {
                    color: #dc3545;
                    font-size: 12px;
                    margin-top: 5px;
                    padding: 8px;
                    background-color: #fff3f3;
                    border-radius: 4px;
                }
                pre {
                    background-color: #f8f9fa;
                    padding: 10px;
                    border-radius: 4px;
                    overflow-x: auto;
                    font-size: 12px;
                    margin: 5px 0;
                }
                .task-id {
                    font-family: monospace;
                    font-size: 12px;
                    color: #666;
                }
                h2, h3, h4 {
                    color: #333;
                    margin: 0;
                }
            </style>
        `;

        const tasks = Array.from(this.tasks.entries()).map(([taskId, task]) => `
            <div class="task">
                <div class="task-header">
                    <h3>Task: <span class="task-id">${taskId}</span></h3>
                    <span class="status ${task.status}">${task.status}</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${task.progress}%"></div>
                </div>
                ${task.error ? `<div class="error">${task.error}</div>` : ''}
                ${task.results ? `
                    <div class="results">
                        <h4>Results:</h4>
                        ${task.results.map(result => `
                            <div class="file-result">
                                <div class="file-result-header">
                                    <strong>${result.filename}</strong>
                                    <span class="status ${result.status}">${result.status}</span>
                                </div>
                                ${result.error_message ? 
                                    `<div class="error">${result.error_message}</div>` : 
                                    `<pre>${this.formatJson(result.extracted_data)}</pre>`
                                }
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
            </div>
        `).join('');

        this.shadowRoot.innerHTML = `
            ${style}
            <div class="task-manager">
                <h2>Extraction Tasks</h2>
                ${tasks || '<p>No active tasks</p>'}
            </div>
        `;
    }
}

customElements.define('task-manager', TaskManager); 