document.addEventListener('DOMContentLoaded', function() {
    const apiKeySelect = document.getElementById('api_id');
    const addStrategyForm = document.getElementById('addStrategyForm');
    const enableOrderTimeoutCheckbox = document.getElementById('enable_order_timeout');
    const orderTimeoutSecondsContainer = document.getElementById('orderTimeoutSecondsContainer');

    // Populate API Keys Dropdown
    async function populateApiKeys() {
        try {
            const response = await fetch('/apis/');
            if (!response.ok) throw new Error('Failed to fetch API keys');
            const apiKeys = await response.json();
            
            apiKeySelect.innerHTML = '<option value="">Select an API Key</option>'; // Clear loading/default
            let connectedKeysFound = false;
            apiKeys.forEach(apiKey => {
                if (apiKey.connection_status === 'connected') { // Only list connected APIs
                    const option = document.createElement('option');
                    option.value = apiKey.id;
                    option.textContent = `${apiKey.alias} (${apiKey.mode})`;
                    apiKeySelect.appendChild(option);
                    connectedKeysFound = true;
                }
            });
            if (!connectedKeysFound) { // Updated check
                 apiKeySelect.innerHTML = '<option value="">No connected API Keys found. Please add and check API connection.</option>';
            }
        } catch (error) {
            console.error('Error fetching API keys for dropdown:', error);
            apiKeySelect.innerHTML = '<option value="">Error loading API Keys</option>';
        }
    }

    // Conditional display for order timeout seconds
    enableOrderTimeoutCheckbox.addEventListener('change', function() {
        orderTimeoutSecondsContainer.style.display = this.checked ? 'block' : 'none';
    });

    // Handle Form Submission
    addStrategyForm.addEventListener('submit', async function(event) {
        event.preventDefault();
        const formData = new FormData(addStrategyForm);
        const data = {};
        formData.forEach((value, key) => {
            // Checkbox values are handled separately below to ensure correct boolean conversion
            if (key === 'cyclic_execution' || key === 'cover_orders_participate_in_profit_taking' || key === 'enable_order_timeout') {
                // Will be handled by direct .checked access
            } else if (key.includes('percentage') || key.includes('amount') || key.includes('multiplier') || key.includes('count') || key.includes('seconds')) {
                data[key] = parseFloat(value); // Convert numeric strings to numbers
            } 
            else {
                data[key] = value;
            }
        });
        
        // Ensure boolean for checkboxes
        data['cyclic_execution'] = document.getElementById('cyclic_execution').checked;
        data['cover_orders_participate_in_profit_taking'] = document.getElementById('cover_orders_participate_in_profit_taking').checked;
        data['enable_order_timeout'] = document.getElementById('enable_order_timeout').checked;

        if (!data['enable_order_timeout']) {
            delete data['order_timeout_seconds']; // Remove if not enabled
        } else {
            // Ensure it's parsed if it was included by forEach, or set it if it wasn't (e.g. if it was empty string)
             data['order_timeout_seconds'] = parseFloat(document.getElementById('order_timeout_seconds').value);
        }

        // Validate that api_id is selected
        if (!data['api_id']) {
            alert('Please select an API Key.');
            return;
        }

        try {
            const response = await fetch('/strategies/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                const errorData = await response.json();
                // FastAPI validation errors are often in errorData.detail which can be a list of objects
                let errorMessage = 'Unknown error';
                if (errorData.detail) {
                    if (typeof errorData.detail === 'string') {
                        errorMessage = errorData.detail;
                    } else if (Array.isArray(errorData.detail)) {
                        errorMessage = errorData.detail.map(err => `${err.loc ? err.loc.join('.')+': ' : ''}${err.msg}`).join('; ');
                    } else {
                        errorMessage = JSON.stringify(errorData.detail);
                    }
                }
                throw new Error(`HTTP error! status: ${response.status}, message: ${errorMessage}`);
            }
            
            alert('Strategy added successfully!');
            addStrategyForm.reset();
            // Reset checkbox dependent display
            orderTimeoutSecondsContainer.style.display = document.getElementById('enable_order_timeout').checked ? 'block' : 'none';
            populateApiKeys(); // Re-populate API keys in case some became non-connected or new ones added
            window.location.href = "/"; // Redirect to dashboard
        } catch (error) {
            console.error('Error adding strategy:', error);
            alert(`Error adding strategy: ${error.message}`);
        }
    });

    // Initial population
    populateApiKeys();
    // Initial state for timeout section
    orderTimeoutSecondsContainer.style.display = enableOrderTimeoutCheckbox.checked ? 'block' : 'none';
});
