document.addEventListener('DOMContentLoaded', function() {
    const apiKeysTableBody = document.querySelector('#apiKeysTable tbody');
    const showAddApiKeyFormBtn = document.getElementById('showAddApiKeyFormBtn');
    const addEditApiKeyFormContainer = document.getElementById('addEditApiKeyFormContainer');
    const apiKeyForm = document.getElementById('apiKeyForm');
    const cancelApiKeyFormBtn = document.getElementById('cancelApiKeyFormBtn');
    const formTitle = document.getElementById('formTitle');
    let currentEditApiId = null;

    // Function to fetch and display API keys
    async function fetchApiKeys() {
        try {
            const response = await fetch('/apis/');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const apiKeys = await response.json();
            
            apiKeysTableBody.innerHTML = ''; // Clear existing rows
            apiKeys.forEach(apiKey => {
                const row = apiKeysTableBody.insertRow();
                const keyDisplay = apiKey.api_key.substring(0, 4) + '...' + apiKey.api_key.substring(apiKey.api_key.length - 4);
                row.innerHTML = `
                    <td>${apiKey.alias}</td>
                    <td>${keyDisplay}</td>
                    <td>${apiKey.mode}</td>
                    <td style="color: ${apiKey.connection_status === 'connected' ? 'green' : 'red'};">${apiKey.connection_status}</td>
                    <td>
                        <button class="editBtn" data-id="${apiKey.id}">Edit</button>
                        <button class="deleteBtn" data-id="${apiKey.id}">Delete</button>
                    </td>
                `;
            });
            addEventListenersToButtons();
        } catch (error) {
            console.error('Error fetching API keys:', error);
            apiKeysTableBody.innerHTML = '<tr><td colspan="5">Error loading API keys.</td></tr>';
        }
    }

    // Show/Hide Add/Edit Form
    showAddApiKeyFormBtn.addEventListener('click', () => {
        formTitle.textContent = 'Add API Key';
        apiKeyForm.reset();
        currentEditApiId = null;
        document.getElementById('secret_key').required = true; // Secret key required for new
        document.getElementById('secret_key').placeholder = ""; // Clear placeholder for add
        addEditApiKeyFormContainer.style.display = 'block';
    });

    cancelApiKeyFormBtn.addEventListener('click', () => {
        addEditApiKeyFormContainer.style.display = 'none';
        apiKeyForm.reset();
    });

    // Handle Form Submission (Add/Edit)
    apiKeyForm.addEventListener('submit', async function(event) {
        event.preventDefault();
        const formData = new FormData(apiKeyForm);
        const data = Object.fromEntries(formData.entries());

        // Pydantic models expect specific types, ensure mode is correct if needed
        // For now, string values from form are okay for FastAPI to coerce.

        let url = '/apis/';
        let method = 'POST';

        if (currentEditApiId) {
            url = `/apis/${currentEditApiId}`;
            method = 'PUT';
            // For PUT, if secret_key is not provided, don't send it
            // The backend model ApiKeyUpdate has optional fields.
            // If secret_key field is empty and it's an edit, remove it from data
            if (!data.secret_key) {
                delete data.secret_key;
            }
        } else {
            // Ensure secret key is provided for new API keys
            if (!data.secret_key) {
                alert('Secret Key is required for new API Key.');
                return;
            }
        }
        
        delete data.apiId; // remove the hidden input if it was captured

        try {
            const response = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(`HTTP error! status: ${response.status}, message: ${errorData.detail || 'Unknown error'}`);
            }
            
            await response.json(); // Or process response data
            fetchApiKeys(); // Refresh table
            addEditApiKeyFormContainer.style.display = 'none';
            apiKeyForm.reset();
        } catch (error) {
            console.error('Error saving API key:', error);
            alert(`Error saving API key: ${error.message}`);
        }
    });

    // Add event listeners to Edit and Delete buttons (call after table is populated)
    function addEventListenersToButtons() {
        document.querySelectorAll('.editBtn').forEach(button => {
            button.addEventListener('click', async function() {
                currentEditApiId = this.dataset.id;
                formTitle.textContent = 'Edit API Key';
                try {
                    const response = await fetch(`/apis/${currentEditApiId}`);
                    if (!response.ok) throw new Error('Failed to fetch API key details');
                    const apiKey = await response.json();
                    
                    document.getElementById('apiId').value = apiKey.id;
                    document.getElementById('alias').value = apiKey.alias;
                    document.getElementById('api_key').value = apiKey.api_key;
                    // Secret key is not sent back by GET /apis/{id} for security,
                    // so it should be optional on edit or re-entered.
                    // For edit, make secret_key not required, or prompt user.
                    document.getElementById('secret_key').value = ''; // Clear it
                    document.getElementById('secret_key').placeholder = "Enter new secret to change";
                    document.getElementById('secret_key').required = false; 
                    document.getElementById('mode').value = apiKey.mode;
                    addEditApiKeyFormContainer.style.display = 'block';
                } catch (error) {
                    console.error('Error preparing edit form:', error);
                    alert('Error loading API key for editing.');
                }
            });
        });

        document.querySelectorAll('.deleteBtn').forEach(button => {
            button.addEventListener('click', async function() {
                const apiId = this.dataset.id;
                if (confirm('Are you sure you want to delete this API key?')) {
                    try {
                        const response = await fetch(`/apis/${apiId}`, { method: 'DELETE' });
                        if (!response.ok) { // Check for non-204 responses as well for errors
                            let errorDetail = "Failed to delete API key";
                            try {
                                const errorData = await response.json();
                                errorDetail = errorData.detail || errorDetail;
                            } catch (e) { /* ignore if no json body */ }
                            throw new Error(errorDetail);
                        }
                        fetchApiKeys(); // Refresh table
                    } catch (error) {
                        console.error('Error deleting API key:', error);
                        alert(`Error deleting API key: ${error.message}`);
                    }
                }
            });
        });
    }

    // Initial fetch of API keys
    fetchApiKeys();
});
