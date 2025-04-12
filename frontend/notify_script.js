document.addEventListener('DOMContentLoaded', () => {
    // --- DOM References ---
    const productSelect = document.getElementById('product-select');
    const statusMessageDiv = document.getElementById('status-message');
    const createForm = document.getElementById('create-notification-form');
    const notifyQuantityInput = document.getElementById('notify-quantity');
    const enableNotificationCheckbox = document.getElementById('enable-notification');
    const addRuleBtn = document.getElementById('add-notification-rule-btn');
    const currentRulesTbody = document.getElementById('current-rules-tbody');
    const noNotificationsMessage = document.querySelector('.no-notifications-message');
    const confirmationModal = document.getElementById('confirmation-modal');
    const modalMessage = document.getElementById('modal-message');
    const modalConfirmBtn = document.getElementById('modal-confirm-btn');
    const modalCancelBtn = document.getElementById('modal-cancel-btn');
    // *** Reference for Stock Alert Popups ***
    const stockAlertContainer = document.getElementById('stock-alert-container'); // Make sure this ID exists in your HTML


    // --- Global State ---
    let inventoryItems = [];
    let confirmAction = null;

    // --- Utility Functions ---

    function showStatusMessage(message, type = 'info') {
        if (!statusMessageDiv) return;
        statusMessageDiv.textContent = message;
        statusMessageDiv.className = ''; // Clear previous classes
        if (type === 'success') statusMessageDiv.classList.add('status-success');
        else if (type === 'error') statusMessageDiv.classList.add('status-error');
        else if (type === 'loading') statusMessageDiv.classList.add('status-loading');
        else statusMessageDiv.classList.add('status-info');
        statusMessageDiv.style.display = 'block';

        if (type !== 'loading') {
            setTimeout(() => {
                if (statusMessageDiv.textContent === message) {
                    statusMessageDiv.style.display = 'none';
                }
            }, 5000);
        }
    }

    function showConfirmationModal(message = "Are you sure?", onConfirmCallback) {
        if (!confirmationModal) return;
        if (modalMessage) modalMessage.textContent = message;
        confirmAction = onConfirmCallback;
        confirmationModal.style.display = 'flex';
        setTimeout(() => confirmationModal.classList.add('show'), 10);
    }

    function hideConfirmationModal() {
        if (!confirmationModal) return;
        confirmationModal.classList.remove('show');
        setTimeout(() => {
            confirmationModal.style.display = 'none';
            confirmAction = null;
        }, 300); // Match CSS transition time
    }

    // --- Stock Alert Popup Function ---
    function showStockAlertPopup(productName) {
        // ** Crucial Check: Ensure container exists **
        if (!stockAlertContainer) {
            console.error("Stock alert container element (#stock-alert-container) not found in the DOM.");
            return;
        }
        if (!productName || typeof productName !== 'string' || productName.trim() === '') {
            console.warn("showStockAlertPopup called with invalid productName:", productName);
            return;
        }
        console.log(`Attempting to show alert popup for: ${productName}`); // Debug log

        const popup = document.createElement('div');
        popup.className = 'stock-alert-popup'; // Base class for styling

        // Icon
        const iconSpan = document.createElement('span');
        iconSpan.className = 'alert-icon';
        iconSpan.textContent = '⚠️';
        popup.appendChild(iconSpan);

        // Message
        const messageDiv = document.createElement('div');
        messageDiv.className = 'alert-message';
        messageDiv.innerHTML = `<strong>${productName}</strong> stock is low!`; // Use innerHTML for strong tag
        popup.appendChild(messageDiv);

        // Close Button
        const closeBtn = document.createElement('button');
        closeBtn.className = 'alert-close-btn';
        closeBtn.innerHTML = '×'; // Use HTML entity for '×'
        closeBtn.setAttribute('aria-label', 'Close alert'); // Accessibility
        closeBtn.onclick = () => {
            popup.classList.remove('show'); // Trigger fade-out animation
            // Remove from DOM after animation completes
            setTimeout(() => {
                 if (popup.parentNode) { // Check if it's still in the DOM
                      popup.remove();
                 }
            }, 450); // Match your fade-out transition duration + small buffer
        };
        popup.appendChild(closeBtn);

        // Add to container
        stockAlertContainer.appendChild(popup);
        console.log(`Popup for ${productName} appended to container.`); // Debug log

        // Trigger show animation (after ensuring it's in the DOM)
        // Use requestAnimationFrame for potentially smoother rendering start
        requestAnimationFrame(() => {
             setTimeout(() => { // Short delay can help ensure transition triggers
                  popup.classList.add('show');
                  console.log(`'show' class added to popup for ${productName}`); // Debug log
             }, 50);
        });


        // Auto-dismiss after a delay
        setTimeout(() => {
            // Check if the popup still exists and is shown before trying to close
            if (popup && popup.classList.contains('show') && popup.parentNode) {
                 console.log(`Auto-dismissing popup for ${productName}`); // Debug log
                 closeBtn.onclick(); // Trigger the close action
            }
        }, 7000); // 7 seconds
    }


    // --- Product & Rule Loading Functions ---

    async function loadProductsForDropdown() {
        console.log("Attempting to load products for dropdown...");
        showStatusMessage("Loading products...", "loading");
        try {
            const response = await fetch('/api/merchant/inventory');
            if (!response.ok) { /* ... error handling ... */ throw new Error(`HTTP error! status: ${response.status}`); }
            inventoryItems = await response.json();
            console.log("Received inventory items:", inventoryItems);
            productSelect.innerHTML = '<option value="" disabled selected>-- Select a Product --</option>';
            if (inventoryItems && inventoryItems.length > 0) {
                inventoryItems.sort((a, b) => (a.stock_name || '').localeCompare(b.stock_name || ''));
                inventoryItems.forEach(item => {
                    if (item.stock_name) {
                        const option = document.createElement('option');
                        option.value = item.stock_name;
                        option.textContent = (item.units && item.units.trim() !== '')
                            ? `${item.stock_name} (${item.units})`
                            : item.stock_name;
                        productSelect.appendChild(option);
                    }
                });
                if (statusMessageDiv && statusMessageDiv.classList.contains('status-loading')) {
                    statusMessageDiv.style.display = 'none';
                }
            } else {
                showStatusMessage("No products found.", "info");
            }
        } catch (error) {
            console.error("Error loading products:", error);
            showStatusMessage(`Error loading products: ${error.message}`, 'error');
        }
    }

    function addRuleToTable(rule) {
        if (!currentRulesTbody || !rule) return;
        const row = document.createElement('tr');
        const ruleId = rule.id || `temp-${Date.now()}`;
        row.setAttribute('data-rule-id', ruleId);

        const nameCell = document.createElement('td');
        nameCell.textContent = rule.productName;
        row.appendChild(nameCell);

        const thresholdCell = document.createElement('td');
        const thresholdInput = document.createElement('input');
        thresholdInput.type = 'number';
        thresholdInput.value = rule.threshold;
        thresholdInput.min = '0'; thresholdInput.step = '1';
        const unitsSpan = document.createElement('span');
        unitsSpan.className = 'units';
        unitsSpan.textContent = rule.units ? ` (${rule.units})` : ''; // Add space before units
        thresholdCell.appendChild(thresholdInput);
        thresholdCell.appendChild(unitsSpan);
        row.appendChild(thresholdCell);

        const statusCell = document.createElement('td');
        const toggleLabel = document.createElement('label');
        toggleLabel.className = 'toggle-switch';
        const toggleInput = document.createElement('input');
        toggleInput.type = 'checkbox';
        toggleInput.checked = rule.enabled;
        // TODO: Add 'change' listener to toggleInput for updating status
        const sliderSpan = document.createElement('span');
        sliderSpan.className = 'slider round';
        toggleLabel.appendChild(toggleInput);
        toggleLabel.appendChild(sliderSpan);
        statusCell.appendChild(toggleLabel);
        row.appendChild(statusCell);

        const actionsCell = document.createElement('td');
        const deleteButton = document.createElement('button');
        deleteButton.className = 'action-btn delete-btn';
        deleteButton.title = 'Delete Rule';
        deleteButton.innerHTML = '🗑️';
        deleteButton.addEventListener('click', () => handleDeleteRule(ruleId, row));
        actionsCell.appendChild(deleteButton);
        row.appendChild(actionsCell);

        currentRulesTbody.prepend(row); // Add new rules to the top
        if (noNotificationsMessage) noNotificationsMessage.style.display = 'none';
    }

    async function loadExistingRules() {
        console.log("Loading existing rules...");
        // showStatusMessage("Loading rules...", "loading"); // Optional
        try {
            const response = await fetch('/api/merchant/notifications');
            if (!response.ok) { /* ... error handling ... */ throw new Error(`HTTP error! status: ${response.status}`); }
            const rules = await response.json();
            console.log("Existing rules received:", rules);
            currentRulesTbody.innerHTML = ''; // Clear existing rows
            if (rules && rules.length > 0) {
                if (noNotificationsMessage) noNotificationsMessage.style.display = 'none';
                rules.forEach(rule => addRuleToTable(rule));
            } else {
                if (noNotificationsMessage) noNotificationsMessage.style.display = 'block';
            }
        } catch (error) {
            console.error("Error loading existing rules:", error);
            showStatusMessage(`Error loading rules: ${error.message}`, 'error');
        } finally {
             //if (statusMessageDiv && statusMessageDiv.classList.contains('status-loading')) {
             //    statusMessageDiv.style.display = 'none';
             //}
        }
    }


    // --- Event Handlers ---

    async function handleCreateRule(event) {
        event.preventDefault();
        // ... (validation logic as before - check product, threshold) ...
        const selectedProductName = productSelect.value;
        const thresholdValue = notifyQuantityInput.value.trim();
        const isEnabled = enableNotificationCheckbox.checked;
        // Basic Frontend Validation (keep your existing checks)
        if (!selectedProductName || thresholdValue === '' || isNaN(parseInt(thresholdValue)) || parseInt(thresholdValue) < 0) {
            showStatusMessage("Please select a product and enter a valid threshold.", 'error');
             // Add visual cues like red borders if needed
            return;
        }

        const selectedItem = inventoryItems.find(item => item.stock_name === selectedProductName);
        const units = selectedItem ? (selectedItem.units || '') : '';
        const ruleData = {
            productName: selectedProductName,
            threshold: parseInt(thresholdValue),
            enabled: isEnabled,
            units: units
        };

        console.log("Sending rule data:", ruleData);
        showStatusMessage("Adding rule...", "loading");
        addRuleBtn.disabled = true;

        try {
            const response = await fetch('/api/merchant/notifications', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(ruleData)
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || `Server error: ${response.status}`);

            console.log("Rule created successfully:", result);
            if (result.rule) {
                addRuleToTable(result.rule);
                showStatusMessage(result.message || "Rule added successfully!", "success");
                createForm.reset();
                // Reset validation styles if any
                productSelect.style.border = '';
                notifyQuantityInput.style.border = '';
            } else {
                 showStatusMessage("Rule added, but couldn't update table immediately.", "info");
                 createForm.reset();
            }
        } catch (error) {
            console.error("Error creating rule:", error);
            showStatusMessage(`Error adding rule: ${error.message}`, 'error');
        } finally {
            addRuleBtn.disabled = false;
            if (statusMessageDiv && statusMessageDiv.classList.contains('status-loading')) {
                 statusMessageDiv.style.display = 'none';
            }
        }
    }

    async function handleDeleteRule(ruleId, tableRow) {
        const productName = tableRow.cells[0].textContent; // Get product name for message
        showConfirmationModal(
            `Are you sure you want to delete the notification rule for "${productName}"?`,
            async () => { // onConfirm callback
                hideConfirmationModal();
                showStatusMessage(`Deleting rule for ${productName}...`, 'loading');
                tableRow.style.opacity = '0.5'; // Visual feedback
                const deleteButton = tableRow.querySelector('.delete-btn');
                if (deleteButton) deleteButton.disabled = true;

                try {
                    const response = await fetch(`/api/merchant/notifications/${ruleId}`, { method: 'DELETE' });
                    if (!response.ok) {
                         let errorMsg = `Failed to delete. Status: ${response.status}`;
                         try { const errData = await response.json(); errorMsg = errData.error || errorMsg; } catch (e) { /* ignore */ }
                         throw new Error(errorMsg);
                    }
                    // Success on backend
                    console.log(`Rule ${ruleId} (${productName}) deleted successfully.`);
                    showStatusMessage(`Rule for ${productName} deleted.`, 'success');
                    tableRow.remove(); // Remove row from table
                    // Check if table is now empty
                    if (currentRulesTbody && currentRulesTbody.rows.length === 0) {
                        if (noNotificationsMessage) noNotificationsMessage.style.display = 'block';
                    }
                } catch (error) {
                    console.error(`Error deleting rule ${ruleId}:`, error);
                    showStatusMessage(`Error deleting rule: ${error.message}`, 'error');
                    // Restore appearance on error
                    tableRow.style.opacity = '1';
                    if (deleteButton) deleteButton.disabled = false;
                } finally {
                    if (statusMessageDiv && statusMessageDiv.classList.contains('status-loading')) {
                        statusMessageDiv.style.display = 'none';
                    }
                }
            } // End onConfirm callback
        );
    }

    // --- *** MOCK STOCK UPDATE FUNCTION (Replace with your actual update logic) *** ---
    // This function simulates sending updates and receiving alerts.
    // You need to integrate the fetch call and alert processing
    // into YOUR actual function that saves stock changes.
    async function exampleSaveStockUpdates(updates) { // 'updates' = [{stock_name:.., new_stock:..}, ...]
        console.log("Simulating sending stock updates:", updates);
        // Example: Show loading state (use your actual status function)
        // showStatusMessage("Saving stock...", "loading");

        try {
            const response = await fetch('/api/merchant/stock_update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', },
                body: JSON.stringify({ updates: updates }) // Make sure body matches backend expectation
            });

            // Improved Response Handling: Check for non-JSON errors first
             if (!response.ok && response.status !== 207) { // 207 = Multi-Status (partial success)
                 let errorText = `HTTP error ${response.status}`;
                 try {
                     // Try to get error details from JSON body
                     const errData = await response.json();
                     errorText = errData.error || errData.message || errorText;
                 } catch (jsonError) {
                     // If response body is not JSON or empty
                     errorText = `${errorText}: ${response.statusText || 'Server error'}`;
                 }
                 throw new Error(errorText);
             }

             // If response is OK (200) or Multi-Status (207), parse JSON
             const result = await response.json();
             console.log("Stock Update Response Received (Full Object):", result);

             // --- *** PROCESS LOW STOCK ALERTS *** ---
             console.log("Checking for low_stock_alerts in response. Value:", result.low_stock_alerts);
             if (result.low_stock_alerts && Array.isArray(result.low_stock_alerts) && result.low_stock_alerts.length > 0) {
                 console.log("Processing low stock alerts array:", result.low_stock_alerts);
                 result.low_stock_alerts.forEach(productName => {
                     console.log(`--> Calling showStockAlertPopup for: ${productName}`);
                     showStockAlertPopup(productName); // <<< THIS IS THE CALL
                 });
             } else {
                 console.log("No low_stock_alerts array found or it's empty in the response.");
             }
             // --- ****************************** ---

            // Handle overall status messages from backend
            if (result.status === 'partial_success') {
                 console.warn("Partial success saving stock:", result.message, result.details || '');
                 // showStatusMessage(result.message || "Some updates failed.", "error"); // Or 'info'
            } else if (result.status === 'success') {
                 console.log("Stock saved successfully:", result.message);
                 // showStatusMessage(result.message || "Updates saved.", "success");
            } else if (response.ok) { // Handle 200 OK without specific status field
                 console.log("Stock update request successful.");
                 // showStatusMessage("Updates potentially saved.", "info");
            }

             // Refresh inventory table on the page if applicable
             // if (typeof fetchInventory === 'function') await fetchInventory();

        } catch (error) {
            console.error('Error saving stock updates or processing response:', error);
            // showStatusMessage(`Error saving changes: ${error.message}`, 'error');
        } finally {
            // Hide loading state, re-enable buttons etc.
            // if (statusMessageDiv && statusMessageDiv.classList.contains('status-loading')) {
            //     statusMessageDiv.style.display = 'none';
            // }
        }
    }

    // --- Initial Setup & Event Listeners ---

    // Load initial data
    loadProductsForDropdown();
    loadExistingRules();

    // Form submission listener
    if (createForm) {
        createForm.addEventListener('submit', handleCreateRule);
    } else {
        console.error("Create notification form (#create-notification-form) not found!");
    }

    // Modal button listeners
    if (modalConfirmBtn) {
        modalConfirmBtn.addEventListener('click', () => {
            if (typeof confirmAction === 'function') {
                confirmAction(); // Execute the stored action (e.g., delete)
            } else {
                console.warn("Modal confirm clicked, but no action stored.");
                hideConfirmationModal();
            }
        });
    }
    if (modalCancelBtn) {
        modalCancelBtn.addEventListener('click', hideConfirmationModal);
    }
    // Close modal on overlay click
    if (confirmationModal) {
        confirmationModal.addEventListener('click', (event) => {
            if (event.target === confirmationModal) { // Clicked on the semi-transparent background
                hideConfirmationModal();
            }
        });
    }
    
    // --- Example Usage (REMOVE THIS IN YOUR ACTUAL IMPLEMENTATION) ---
    // Simulate clicking a save button after changing stock for "Product A" and "Product B"
    // You would replace this with your actual event handler that gathers changes and calls the function
    /*
    const exampleSaveChangesButton = document.getElementById('your-save-button-id'); // Replace with your actual ID
    if (exampleSaveChangesButton) {
        exampleSaveChangesButton.addEventListener('click', () => {
             const exampleUpdates = [
                 { stock_name: "Product A", new_stock: 5 },
                 { stock_name: "Product B", new_stock: 15 }
             ];
             exampleSaveStockUpdates(exampleUpdates); // Call the function with the updates
        });
    }
    */

}); // End DOMContentLoaded